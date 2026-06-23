#!/usr/bin/env python3
"""
Enhanced Flash Loan Monitoring System
Expands to all available networks using Infura endpoints, The Graph subgraphs, and Dune Analytics
for comprehensive flashloan opportunity detection across multiple blockchain networks.
"""

import requests
import json
import time
import sqlite3
import asyncio
import aiohttp
from datetime import datetime, timedelta
import logging
import math
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from web3 import Web3
import hashlib
import hmac
import base64
import schedule
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import ccxt
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class NetworkConfig:
    name: str
    chain_id: int
    infura_endpoint: str
    the_graph_endpoint: str
    explorer: str
    currency: str
    block_time: float
    gas_currency: str

@dataclass
class FlashLoanOpportunity:
    id: str
    timestamp: datetime
    network: str
    protocol: str
    opportunity_type: str
    token_pair: str
    profit_percentage: float
    estimated_profit_usd: float
    gas_cost_usd: float
    liquidity_usd: float
    risk_score: int
    confidence_score: float
    details: Dict[str, Any]
    status: str = "pending"

class EnhancedFlashLoanMonitor:
    def __init__(self, config_path: str = "enhanced-config/"):
        self.config_path = config_path
        self.setup_logging()
        self.load_configurations()
        self.setup_database()
        self.setup_api_clients()
        self.opportunities = []
        self.is_running = False
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('enhanced-monitoring.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def load_configurations(self):
        """Load network and protocol configurations"""
        try:
            with open(f"{self.config_path}networks.json", 'r') as f:
                self.networks = json.load(f)
            
            with open(f"{self.config_path}flashloan-protocols.json", 'r') as f:
                self.protocols = json.load(f)
            
            with open("api-keys-config.json", 'r') as f:
                self.api_keys = json.load(f)
            
            self.logger.info("Configurations loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading configurations: {e}")
            raise
    
    def setup_database(self):
        """Setup enhanced database structure"""
        self.conn = sqlite3.connect('enhanced_flash_loan_research.db')
        cursor = self.conn.cursor()
        
        # Create opportunities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                timestamp DATETIME,
                network TEXT,
                protocol TEXT,
                opportunity_type TEXT,
                token_pair TEXT,
                profit_percentage REAL,
                estimated_profit_usd REAL,
                gas_cost_usd REAL,
                liquidity_usd REAL,
                risk_score INTEGER,
                confidence_score REAL,
                details TEXT,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create price_data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                network TEXT,
                protocol TEXT,
                token_pair TEXT,
                price REAL,
                volume_24h REAL,
                liquidity REAL,
                price_impact REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create gas_prices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gas_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                network TEXT,
                gas_price REAL,
                gas_price_usd REAL,
                block_number INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create dune_analytics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dune_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                query_id INTEGER,
                query_name TEXT,
                result TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
        self.logger.info("Database setup completed")
    
    def setup_api_clients(self):
        """Setup API clients for Infura, The Graph, and Dune Analytics"""
        self.web3_clients = {}
        
        # Setup Web3 clients for each network
        for network_name, network_config in self.networks["supported_networks"].items():
            try:
                web3 = Web3(Web3.HTTPProvider(network_config["infura_endpoint"]))
                if web3.is_connected():
                    self.web3_clients[network_name] = web3
                    self.logger.info(f"Connected to {network_name} via Infura")
                else:
                    self.logger.warning(f"Failed to connect to {network_name}")
            except Exception as e:
                self.logger.error(f"Error connecting to {network_name}: {e}")
        
        # Setup session for async requests
        self.session = aiohttp.ClientSession()
        
        # Setup Dune Analytics client
        self.dune_api_key = self.api_keys["dune"]["api_key"]
        self.dune_base_url = "https://api.dune.com/api/v1"
        
        # Setup The Graph client
        self.graph_jwt_token = self.api_keys["the_graph"]["jwt_token"]
    
    async def get_the_graph_data(self, subgraph_url: str, query: str) -> Optional[Dict]:
        """Fetch data from The Graph subgraph"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.graph_jwt_token}"
        }
        
        try:
            async with self.session.post(
                subgraph_url,
                json={"query": query},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if "data" in data:
                        return data["data"]
                    else:
                        self.logger.error(f"The Graph error: {data.get('errors', 'Unknown error')}")
                        return None
                else:
                    self.logger.error(f"The Graph request failed: {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching The Graph data: {e}")
            return None
    
    async def get_dune_analytics_data(self, query_id: int) -> Optional[Dict]:
        """Fetch data from Dune Analytics"""
        headers = {
            "Content-Type": "application/json",
            "X-Dune-API-Key": self.dune_api_key
        }
        
        try:
            async with self.session.get(
                f"{self.dune_base_url}/query/{query_id}/results",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    self.logger.error(f"Dune Analytics request failed: {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"Error fetching Dune Analytics data: {e}")
            return None
    
    async def get_gas_prices(self, network: str) -> Tuple[float, float]:
        """Get current gas prices for a network"""
        try:
            if network in self.web3_clients:
                web3 = self.web3_clients[network]
                gas_price = web3.eth.gas_price
                
                # Convert to USD (simplified - would need actual price feed)
                if network == "ethereum":
                    eth_price = await self.get_token_price("ethereum", "WETH", "USDC")
                    gas_price_usd = (gas_price / 1e18) * eth_price
                elif network == "polygon":
                    matic_price = await self.get_token_price("polygon", "WMATIC", "USDC")
                    gas_price_usd = (gas_price / 1e18) * matic_price
                else:
                    gas_price_usd = gas_price / 1e18  # Basic conversion
                
                return gas_price, gas_price_usd
            
            return 0, 0
        except Exception as e:
            self.logger.error(f"Error getting gas prices for {network}: {e}")
            return 0, 0
    
    async def get_token_price(self, network: str, base_token: str, quote_token: str) -> float:
        """Get token price from DEX or price feed"""
        try:
            # Try to get price from Uniswap V3 subgraph
            if network in ["ethereum", "polygon", "arbitrum", "base", "avalanche", "bsc", "optimism", "fantom"]:
                subgraph_urls = {
                    "ethereum": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3",
                    "polygon": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-polygon",
                    "arbitrum": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-arbitrum",
                    "base": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-base",
                    "avalanche": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-avalanche",
                    "bsc": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-bsc",
                    "optimism": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-optimism",
                    "fantom": "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-fantom"
                }
                
                if network in subgraph_urls:
                    query = f"""
                    {{
                        pairs(where: {{token0: "{base_token}", token1: "{quote_token}"}}) {{
                            token0 {{
                                symbol
                                id
                            }}
                            token1 {{
                                symbol
                                id
                            }}
                            price0
                            price1
                            reserve0
                            reserve1
                            volumeUSD
                            liquidityUSD
                        }}
                    }}
                    """
                    
                    data = await self.get_the_graph_data(subgraph_urls[network], query)
                    if data and "pairs" in data and len(data["pairs"]) > 0:
                        pair = data["pairs"][0]
                        return float(pair["price0"]) if pair["token0"]["symbol"] == base_token else float(pair["price1"])
            
            # Fallback to CCXT for price data
            try:
                exchange = ccxt.binance()
                if base_token == "WETH" and quote_token == "USDC":
                    symbol = "ETH/USDT"
                elif base_token == "WMATIC" and quote_token == "USDC":
                    symbol = "MATIC/USDT"
                else:
                    symbol = f"{base_token}/{quote_token}"
                
                ticker = exchange.fetch_ticker(symbol)
                return ticker["last"]
            except:
                return 1.0  # Fallback price
            
        except Exception as e:
            self.logger.error(f"Error getting token price for {base_token}/{quote_token} on {network}: {e}")
            return 1.0
    
    async def detect_flash_loan_opportunities(self) -> List[FlashLoanOpportunity]:
        """Detect flash loan opportunities across all networks and protocols"""
        opportunities = []
        
        # Get current gas prices for all networks
        gas_prices = {}
        for network_name in self.web3_clients.keys():
            gas_price, gas_price_usd = await self.get_gas_prices(network_name)
            gas_prices[network_name] = {"gas_price": gas_price, "gas_price_usd": gas_price_usd}
        
        # Monitor each protocol on each supported network
        for protocol_name, protocol_config in self.protocols["flash_loan_providers"].items():
            for network_name in protocol_config["supported_chains"]:
                if network_name in self.web3_clients:
                    try:
                        network_opportunities = await self.monitor_protocol(
                            protocol_name, protocol_config, network_name, gas_prices[network_name]
                        )
                        opportunities.extend(network_opportunities)
                    except Exception as e:
                        self.logger.error(f"Error monitoring {protocol_name} on {network_name}: {e}")
        
        # Monitor DEX arbitrage opportunities
        dex_opportunities = await self.monitor_dex_arbitrage()
        opportunities.extend(dex_opportunities)
        
        # Monitor cross-chain opportunities
        cross_chain_opportunities = await self.monitor_cross_chain_opportunities()
        opportunities.extend(cross_chain_opportunities)
        
        return opportunities
    
    async def monitor_protocol(self, protocol_name: str, protocol_config: Dict, 
                             network_name: str, gas_price_data: Dict) -> List[FlashLoanOpportunity]:
        """Monitor a specific protocol on a specific network"""
        opportunities = []
        
        try:
            # Get subgraph URL for this protocol on this network
            subgraph_url = protocol_config["subgraph_urls"].get(network_name)
            if not subgraph_url:
                return opportunities
            
            # Query for flash loan pools
            query = f"""
            {{
                pools(where: {{totalLiquidity_gt: 100000}}) {{
                    id
                    name
                    symbol
                    totalLiquidity
                    totalBorrows
                    variableBorrowRate
                    stableBorrowRate
                    reserveFactor
                    snapshot {{
                        totalLiquidity
                        totalBorrows
                        variableBorrowRate
                        stableBorrowRate
                    }}
                }}
            }}
            """
            
            data = await self.get_the_graph_data(subgraph_url, query)
            if not data or "pools" not in data:
                return opportunities
            
            # Analyze each pool for opportunities
            for pool in data["pools"]:
                opportunity = await self.analyze_flash_loan_pool(
                    protocol_name, protocol_config, network_name, 
                    pool, gas_price_data
                )
                if opportunity:
                    opportunities.append(opportunity)
        
        except Exception as e:
            self.logger.error(f"Error monitoring {protocol_name} on {network_name}: {e}")
        
        return opportunities
    
    async def analyze_flash_loan_pool(self, protocol_name: str, protocol_config: Dict,
                                    network_name: str, pool: Dict, gas_price_data: Dict) -> Optional[FlashLoanOpportunity]:
        """Analyze a specific flash loan pool for opportunities"""
        try:
            # Calculate opportunity metrics
            liquidity_usd = float(pool["totalLiquidity"])
            borrow_rate = float(pool["variableBorrowRate"])
            
            # Skip if liquidity is too low
            if liquidity_usd < 50000:
                return None
            
            # Calculate potential profit from arbitrage
            # This is a simplified calculation - in reality, you'd need more complex analysis
            estimated_profit = liquidity_usd * 0.001  # 0.1% profit estimate
            
            # Calculate gas costs
            gas_cost_usd = gas_price_data["gas_price_usd"] * 50000  # Estimate gas for complex transaction
            
            # Calculate net profit
            net_profit_usd = estimated_profit - gas_cost_usd
            
            # Apply thresholds
            if net_profit_usd < 100:  # Minimum $100 profit
                return None
            
            # Generate opportunity ID
            opportunity_id = hashlib.sha256(
                f"{protocol_name}_{network_name}_{pool['id']}_{datetime.now().isoformat()}".encode()
            ).hexdigest()[:16]
            
            # Create opportunity
            opportunity = FlashLoanOpportunity(
                id=opportunity_id,
                timestamp=datetime.now(),
                network=network_name,
                protocol=protocol_name,
                opportunity_type="flash_loan_arbitrage",
                token_pair=f"{pool['symbol']}/USDC",
                profit_percentage=(net_profit_usd / liquidity_usd) * 100,
                estimated_profit_usd=net_profit_usd,
                gas_cost_usd=gas_cost_usd,
                liquidity_usd=liquidity_usd,
                risk_score=self.calculate_risk_score(protocol_name, network_name, liquidity_usd),
                confidence_score=self.calculate_confidence_score(protocol_name, network_name, liquidity_usd),
                details={
                    "pool_id": pool["id"],
                    "pool_name": pool["name"],
                    "total_liquidity": liquidity_usd,
                    "borrow_rate": borrow_rate,
                    "protocol_config": protocol_config
                }
            )
            
            return opportunity
        
        except Exception as e:
            self.logger.error(f"Error analyzing flash loan pool: {e}")
            return None
    
    async def monitor_dex_arbitrage(self) -> List[FlashLoanOpportunity]:
        """Monitor DEX arbitrage opportunities"""
        opportunities = []
        
        try:
            # Get price data from multiple DEXes
            networks = ["ethereum", "polygon", "arbitrum", "base"]
            
            for network in networks:
                if network in self.web3_clients:
                    # Get Uniswap prices
                    uniswap_prices = await self.get_dex_prices(network, "uniswap")
                    # Get SushiSwap prices
                    sushiswap_prices = await self.get_dex_prices(network, "sushiswap")
                    
                    # Compare prices for arbitrage opportunities
                    if uniswap_prices and sushiswap_prices:
                        arbitrage_opps = await self.find_price_arbitrage(
                            network, uniswap_prices, sushiswap_prices
                        )
                        opportunities.extend(arbitrage_opps)
        
        except Exception as e:
            self.logger.error(f"Error monitoring DEX arbitrage: {e}")
        
        return opportunities
    
    async def get_dex_prices(self, network: str, dex: str) -> Dict[str, float]:
        """Get prices from a specific DEX"""
        try:
            if dex == "uniswap":
                subgraph_url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
            elif dex == "sushiswap":
                subgraph_url = "https://api.thegraph.com/subgraphs/name/sushiswap/exchange"
            else:
                return {}
            
            query = """
            {
                pairs(where: {reserveUSD_gt: 100000}) {
                    token0 {
                        symbol
                        id
                    }
                    token1 {
                        symbol
                        id
                    }
                    price0
                    price1
                    reserve0
                    reserve1
                    volumeUSD
                    liquidityUSD
                }
            }
            """
            
            data = await self.get_the_graph_data(subgraph_url, query)
            if data and "pairs" in data:
                prices = {}
                for pair in data["pairs"]:
                    token0 = pair["token0"]["symbol"]
                    token1 = pair["token1"]["symbol"]
                    prices[f"{token0}/{token1}"] = float(pair["price0"])
                    prices[f"{token1}/{token0}"] = float(pair["price1"])
                return prices
            
            return {}
        
        except Exception as e:
            self.logger.error(f"Error getting {dex} prices for {network}: {e}")
            return {}
    
    async def find_price_arbitrage(self, network: str, prices1: Dict, prices2: Dict) -> List[FlashLoanOpportunity]:
        """Find price arbitrage opportunities between two DEXes"""
        opportunities = []
        
        try:
            # Compare prices for common trading pairs
            for pair in prices1:
                if pair in prices2:
                    price1 = prices1[pair]
                    price2 = prices2[pair]
                    
                    # Calculate price difference
                    price_diff = abs(price1 - price2)
                    price_diff_percentage = (price_diff / max(price1, price2)) * 100
                    
                    # Check if arbitrage opportunity exists
                    if price_diff_percentage > 0.1:  # 0.1% minimum difference
                        # Estimate profit (simplified)
                        estimated_profit = 1000000 * price_diff_percentage / 100  # $1M position size
                        
                        # Calculate gas costs
                        gas_price, gas_price_usd = await self.get_gas_prices(network)
                        gas_cost_usd = gas_price_usd * 50000  # Estimate gas cost
                        
                        # Calculate net profit
                        net_profit_usd = estimated_profit - gas_cost_usd
                        
                        if net_profit_usd > 100:  # Minimum $100 profit
                            opportunity_id = hashlib.sha256(
                                f"arbitrage_{network}_{pair}_{datetime.now().isoformat()}".encode()
                            ).hexdigest()[:16]
                            
                            opportunity = FlashLoanOpportunity(
                                id=opportunity_id,
                                timestamp=datetime.now(),
                                network=network,
                                protocol="dex_arbitrage",
                                opportunity_type="price_arbitrage",
                                token_pair=pair,
                                profit_percentage=price_diff_percentage,
                                estimated_profit_usd=net_profit_usd,
                                gas_cost_usd=gas_cost_usd,
                                liquidity_usd=1000000,
                                risk_score=3,  # Medium risk
                                confidence_score=min(price_diff_percentage / 1.0, 1.0),  # Cap at 100%
                                details={
                                    "dex1_price": price1,
                                    "dex2_price": price2,
                                    "price_difference": price_diff,
                                    "position_size_usd": 1000000
                                }
                            )
                            
                            opportunities.append(opportunity)
        
        except Exception as e:
            self.logger.error(f"Error finding price arbitrage: {e}")
        
        return opportunities
    
    async def monitor_cross_chain_opportunities(self) -> List[FlashLoanOpportunity]:
        """Monitor cross-chain arbitrage opportunities"""
        opportunities = []
        
        try:
            # Get bridge fees and transfer times
            bridge_data = await self.get_bridge_data()
            
            # Monitor price differences across chains
            cross_chain_prices = await self.get_cross_chain_prices()
            
            # Find arbitrage opportunities
            for token, prices in cross_chain_prices.items():
                if len(prices) >= 2:
                    # Find highest and lowest prices
                    sorted_prices = sorted(prices.items(), key=lambda x: x[1])
                    lowest_network = sorted_prices[0]
                    highest_network = sorted_prices[-1]
                    
                    price_diff = highest_network[1] - lowest_network[1]
                    price_diff_percentage = (price_diff / lowest_network[1]) * 100
                    
                    # Check if opportunity exists
                    if price_diff_percentage > 0.1:  # 0.1% minimum difference (increased sensitivity)
                        # Get bridge fees
                        bridge_fee = bridge_data.get(lowest_network[0], {}).get(highest_network[0], {}).get("fee", 0)
                        
                        # Calculate profit
                        position_size = 100000  # $100K position
                        estimated_profit = position_size * price_diff_percentage / 100
                        net_profit_usd = estimated_profit - bridge_fee
                        
                        if net_profit_usd > 200:  # Minimum $200 profit after fees
                            opportunity_id = hashlib.sha256(
                                f"cross_chain_{token}_{lowest_network[0]}_{highest_network[0]}_{datetime.now().isoformat()}".encode()
                            ).hexdigest()[:16]
                            
                            opportunity = FlashLoanOpportunity(
                                id=opportunity_id,
                                timestamp=datetime.now(),
                                network=f"{lowest_network[0]}->{highest_network[0]}",
                                protocol="cross_chain_arbitrage",
                                opportunity_type="bridge_arbitrage",
                                token_pair=f"{token}/{token}",
                                profit_percentage=price_diff_percentage,
                                estimated_profit_usd=net_profit_usd,
                                gas_cost_usd=bridge_fee,
                                liquidity_usd=position_size,
                                risk_score=4,  # Higher risk due to bridge delays
                                confidence_score=min(price_diff_percentage / 2.0, 1.0),
                                details={
                                    "source_network": lowest_network[0],
                                    "target_network": highest_network[0],
                                    "source_price": lowest_network[1],
                                    "target_price": highest_network[1],
                                    "bridge_fee": bridge_fee,
                                    "position_size_usd": position_size
                                }
                            )
                            
                            opportunities.append(opportunity)
        
        except Exception as e:
            self.logger.error(f"Error monitoring cross-chain opportunities: {e}")
        
        return opportunities
    
    async def get_bridge_data(self) -> Dict:
        """Get bridge fee and transfer time data"""
        bridge_data = {}
        
        try:
            # This would typically query bridge APIs or use subgraphs
            # For now, return sample data
            bridge_data = {
                "ethereum": {
                    "polygon": {"fee": 5, "time": 5},
                    "arbitrum": {"fee": 2, "time": 2},
                    "avalanche": {"fee": 10, "time": 15}
                },
                "polygon": {
                    "ethereum": {"fee": 5, "time": 5},
                    "arbitrum": {"fee": 8, "time": 10}
                }
            }
        
        except Exception as e:
            self.logger.error(f"Error getting bridge data: {e}")
        
        return bridge_data
    
    async def get_cross_chain_prices(self) -> Dict:
        """Get token prices across different chains"""
        cross_chain_prices = {}
        
        try:
            # Monitor major tokens across chains
            tokens = ["USDC", "WETH", "WBTC"]
            
            for token in tokens:
                token_prices = {}
                
                # Get prices from different networks
                for network in ["ethereum", "polygon", "arbitrum", "avalanche"]:
                    if network in self.web3_clients:
                        price = await self.get_token_price(network, token, "USDC")
                        token_prices[network] = price
                
                cross_chain_prices[token] = token_prices
        
        except Exception as e:
            self.logger.error(f"Error getting cross-chain prices: {e}")
        
        return cross_chain_prices
    
    def calculate_risk_score(self, protocol: str, network: str, liquidity_usd: float) -> int:
        """Calculate risk score for an opportunity"""
        risk_score = 1
        
        # Protocol risk
        if protocol == "aave":
            risk_score += 1
        elif protocol == "dydx":
            risk_score += 2
        elif protocol == "maker":
            risk_score += 1
        
        # Network risk
        if network == "ethereum":
            risk_score += 1
        elif network == "polygon":
            risk_score += 0
        elif network == "bsc":
            risk_score += 2
        
        # Liquidity risk
        if liquidity_usd < 100000:
            risk_score += 2
        elif liquidity_usd < 500000:
            risk_score += 1
        
        return min(risk_score, 5)  # Cap at 5
    
    def calculate_confidence_score(self, protocol: str, network: str, liquidity_usd: float) -> float:
        """Calculate confidence score for an opportunity"""
        confidence = 0.5
        
        # Protocol confidence
        if protocol == "aave":
            confidence += 0.2
        elif protocol == "dydx":
            confidence += 0.1
        
        # Network confidence
        if network in ["ethereum", "polygon", "arbitrum"]:
            confidence += 0.1
        
        # Liquidity confidence
        if liquidity_usd > 1000000:
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    async def save_opportunity(self, opportunity: FlashLoanOpportunity):
        """Save opportunity to database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO opportunities 
                (id, timestamp, network, protocol, opportunity_type, token_pair, 
                 profit_percentage, estimated_profit_usd, gas_cost_usd, liquidity_usd, 
                 risk_score, confidence_score, details, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                opportunity.id,
                opportunity.timestamp,
                opportunity.network,
                opportunity.protocol,
                opportunity.opportunity_type,
                opportunity.token_pair,
                opportunity.profit_percentage,
                opportunity.estimated_profit_usd,
                opportunity.gas_cost_usd,
                opportunity.liquidity_usd,
                opportunity.risk_score,
                opportunity.confidence_score,
                json.dumps(opportunity.details),
                opportunity.status
            ))
            self.conn.commit()
            
            self.logger.info(f"Saved opportunity: {opportunity.id} - {opportunity.estimated_profit_usd:.2f} USD")
        
        except Exception as e:
            self.logger.error(f"Error saving opportunity: {e}")
    
    async def run_monitoring_cycle(self):
        """Run a single monitoring cycle"""
        try:
            self.logger.info("Starting monitoring cycle...")
            
            # Detect opportunities
            opportunities = await self.detect_flash_loan_opportunities()
            
            # Save opportunities
            for opportunity in opportunities:
                await self.save_opportunity(opportunity)
            
            self.logger.info(f"Monitoring cycle completed. Found {len(opportunities)} opportunities.")
            
            # Generate summary report
            await self.generate_summary_report(opportunities)
            
        except Exception as e:
            self.logger.error(f"Error in monitoring cycle: {e}")
    
    async def generate_summary_report(self, opportunities: List[FlashLoanOpportunity]):
        """Generate summary report of detected opportunities"""
        try:
            if not opportunities:
                return
            
            # Group opportunities by network
            by_network = {}
            for opp in opportunities:
                if opp.network not in by_network:
                    by_network[opp.network] = []
                by_network[opp.network].append(opp)
            
            # Generate report
            report = {
                "timestamp": datetime.now().isoformat(),
                "total_opportunities": len(opportunities),
                "total_estimated_profit": sum(opp.estimated_profit_usd for opp in opportunities),
                "opportunities_by_network": {},
                "top_opportunities": sorted(
                    [{"id": opp.id, "profit": opp.estimated_profit_usd, "network": opp.network} 
                     for opp in opportunities], 
                    key=lambda x: x["profit"], 
                    reverse=True
                )[:10]
            }
            
            # Add network breakdown
            for network, net_opps in by_network.items():
                report["opportunities_by_network"][network] = {
                    "count": len(net_opps),
                    "total_profit": sum(opp.estimated_profit_usd for opp in net_opps),
                    "average_profit": sum(opp.estimated_profit_usd for opp in net_opps) / len(net_opps) if net_opps else 0
                }
            
            # Save report
            with open(f"data/reports/summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 'w') as f:
                json.dump(report, f, indent=2)
            
            self.logger.info(f"Generated summary report with {len(opportunities)} opportunities")
            
        except Exception as e:
            self.logger.error(f"Error generating summary report: {e}")
    
    async def run_continuous_monitoring(self, interval_minutes: int = 30):
        """Run continuous monitoring at specified intervals"""
        self.is_running = True
        self.logger.info(f"Starting continuous monitoring with {interval_minutes}-minute intervals")
        
        while self.is_running:
            try:
                await self.run_monitoring_cycle()
                await asyncio.sleep(interval_minutes * 60)
            except KeyboardInterrupt:
                self.logger.info("Stopping continuous monitoring...")
                self.is_running = False
                break
            except Exception as e:
                self.logger.error(f"Error in continuous monitoring: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def close(self):
        """Close monitoring system"""
        self.is_running = False
        if self.session:
            await self.session.close()
        if self.conn:
            self.conn.close()
        self.logger.info("Monitoring system closed")

# Main execution
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Flash Loan Monitoring System")
    parser.add_argument("--config", default="enhanced-config/", help="Configuration path")
    parser.add_argument("--single-run", action="store_true", help="Run single monitoring cycle")
    parser.add_argument("--continuous", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--interval", type=int, default=30, help="Monitoring interval in minutes")
    
    args = parser.parse_args()
    
    async def main():
        monitor = EnhancedFlashLoanMonitor(args.config)
        
        try:
            if args.single_run:
                await monitor.run_monitoring_cycle()
            elif args.continuous:
                await monitor.run_continuous_monitoring(args.interval)
            else:
                print("Use --single-run or --continuous option")
        finally:
            await monitor.close()
    
    # Run the main function
    asyncio.run(main())