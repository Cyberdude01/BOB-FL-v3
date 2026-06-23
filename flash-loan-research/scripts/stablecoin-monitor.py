#!/usr/bin/env python3
"""
Stablecoin Pool Monitoring Script
Dedicated stablecoin opportunity detection for flash loan arbitrage
"""

import os
import json
import requests
import sqlite3
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv
import asyncio
import aiohttp

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class StablecoinPair:
    name: str
    token_a: str
    token_b: str
    pool_address: str
    dex_protocol: str
    network: str
    decimals_a: int
    decimals_b: int

class StablecoinMonitor:
    def __init__(self):
        self.db_path = '/root/.openclaw/workspace/flash-loan-research/enhanced_flash_loan_research.db'
        self.setup_database()
        
        # Define major stablecoin pairs to monitor
        self.stablecoin_pairs = [
            StablecoinPair("USDC-USDT", "USDC", "USDT", "0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8", "uniswap_v3", "ethereum", 6, 6),
            StablecoinPair("USDC-DAI", "USDC", "DAI", "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640", "uniswap_v3", "ethereum", 6, 18),
            StablecoinPair("USDT-DAI", "USDT", "DAI", "0xa478c2975ab1ea89e8196811f51a7b7ade33eb11", "uniswap_v3", "ethereum", 6, 18),
            StablecoinPair("FRAX-USDC", "FRAX", "USDC", "0x4e7c6b5f5a0d7e3a7b8c9d0e1f2a3b4c5d6e7f8a9", "uniswap_v3", "ethereum", 18, 6),
            StablecoinPair("FEI-USDC", "FEI", "USDC", "0x3f5b893f6e9c2d1e4a5b6c7d8e9f0a1b2c3d4e5f", "uniswap_v3", "ethereum", 18, 6),
        ]
        
        # DEX endpoints for different networks
        self.dex_endpoints = {
            'uniswap_v3': {
                'ethereum': 'https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3',
                'polygon': 'https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-polygon',
                'arbitrum': 'https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3-arbitrum'
            }
        }
        
        # Profit thresholds for stablecoins (lower than regular pairs)
        self.profit_thresholds = {
            'same_denomination': 0.02,  # 0.02% for same denomination stablecoins
            'cross_denomination': 0.05,  # 0.05% for cross-denomination
            'bridge_arbitrage': 0.1     # 0.1% for bridge arbitrage
        }
        
        self.session = None
    
    def setup_database(self):
        """Setup database for stablecoin monitoring"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create stablecoin opportunities table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stablecoin_opportunities (
                    id TEXT PRIMARY KEY,
                    timestamp DATETIME,
                    network TEXT,
                    pair_name TEXT,
                    opportunity_type TEXT,
                    profit_percentage REAL,
                    estimated_profit_usd REAL,
                    pool_address TEXT,
                    dex_protocol TEXT,
                    token_a TEXT,
                    token_b TEXT,
                    liquidity_usd REAL,
                    gas_cost_usd REAL,
                    confidence_score REAL,
                    status TEXT,
                    details_json TEXT
                )
            ''')
            
            # Create stablecoin_prices table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stablecoin_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    network TEXT,
                    pair_name TEXT,
                    token_a TEXT,
                    token_b TEXT,
                    price_a REAL,
                    price_b REAL,
                    spread_percentage REAL,
                    pool_address TEXT,
                    source TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database setup completed successfully")
            
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            raise
    
    async def get_pool_data(self, network: str, pool_address: str, protocol: str):
        """Get pool data from DEX subgraph"""
        if network not in self.dex_endpoints[protocol]:
            logger.warning(f"Network {network} not supported for protocol {protocol}")
            return None
        
        endpoint = self.dex_endpoints[protocol][network]
        query = f"""
        {{
            pool(id: "{pool_address}") {{
                token0 {{
                    symbol
                    id
                    decimals
                }}
                token1 {{
                    symbol
                    id
                    decimals
                }}
                sqrtPrice
                liquidity
                feeTier
                volumeUSD
                token0Price
                token1Price
                twap {{
                    period
                    price0
                    price1
                }}
            }}
        }}
        """
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(endpoint, json={'query': query}) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('data', {}).get('pool')
                    else:
                        logger.error(f"Failed to get pool data: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error fetching pool data: {e}")
            return None
    
    def calculate_price_impact(self, liquidity: float, amount: float) -> float:
        """Calculate price impact for large trades"""
        if liquidity == 0:
            return 0
        
        # Simplified price impact calculation
        # Price impact ≈ (amount / (2 * liquidity)) * 100
        price_impact = (amount / (2 * liquidity)) * 100
        return min(price_impact, 5.0)  # Cap at 5%
    
    def detect_stablecoin_opportunities(self, pool_data: Dict, pair: StablecoinPair) -> List[Dict]:
        """Detect arbitrage opportunities in stablecoin pools"""
        opportunities = []
        
        if not pool_data:
            return opportunities
        
        # Extract pool information
        token0 = pool_data.get('token0', {})
        token1 = pool_data.get('token1', {})
        
        if not token0 or not token1:
            return opportunities
        
        # Calculate current prices
        price0 = float(pool_data.get('token0Price', 1.0))
        price1 = float(pool_data.get('token1Price', 1.0))
        
        # Calculate spreads
        if price0 > 0 and price1 > 0:
            spread_01 = abs(price0 - price1) / min(price0, price1) * 100
            spread_10 = abs(price1 - price0) / min(price1, price0) * 100
            
            liquidity_usd = float(pool_data.get('volumeUSD', 0))
            
            # Check if spread exceeds threshold
            if spread_01 > self.profit_thresholds['same_denomination']:
                opportunity = {
                    'id': f"{pair.network}_{pair.name}_{int(time.time())}",
                    'network': pair.network,
                    'pair_name': pair.name,
                    'opportunity_type': 'same_denomination_arbitrage',
                    'profit_percentage': spread_01,
                    'estimated_profit_usd': liquidity_usd * spread_01 / 100,
                    'pool_address': pair.pool_address,
                    'dex_protocol': pair.dex_protocol,
                    'token_a': token0.get('symbol', 'UNKNOWN'),
                    'token_b': token1.get('symbol', 'UNKNOWN'),
                    'liquidity_usd': liquidity_usd,
                    'gas_cost_usd': 5.0,  # Estimated gas cost
                    'confidence_score': min(spread_01 / self.profit_thresholds['same_denomination'], 1.0),
                    'status': 'detected',
                    'details_json': json.dumps({
                        'price0': price0,
                        'price1': price1,
                        'liquidity': pool_data.get('liquidity', 0),
                        'fee_tier': pool_data.get('feeTier', 0),
                        'timestamp': datetime.now().isoformat()
                    })
                }
                opportunities.append(opportunity)
            
            # Check for larger cross-denomination opportunities
            if spread_01 > self.profit_thresholds['cross_denomination']:
                opportunity = {
                    'id': f"{pair.network}_{pair.name}_cross_{int(time.time())}",
                    'network': pair.network,
                    'pair_name': pair.name,
                    'opportunity_type': 'cross_denomination_arbitrage',
                    'profit_percentage': spread_01,
                    'estimated_profit_usd': liquidity_usd * spread_01 / 100,
                    'pool_address': pair.pool_address,
                    'dex_protocol': pair.dex_protocol,
                    'token_a': token0.get('symbol', 'UNKNOWN'),
                    'token_b': token1.get('symbol', 'UNKNOWN'),
                    'liquidity_usd': liquidity_usd,
                    'gas_cost_usd': 5.0,
                    'confidence_score': min(spread_01 / self.profit_thresholds['cross_denomination'], 1.0),
                    'status': 'detected',
                    'details_json': json.dumps({
                        'price0': price0,
                        'price1': price1,
                        'liquidity': pool_data.get('liquidity', 0),
                        'fee_tier': pool_data.get('feeTier', 0),
                        'timestamp': datetime.now().isoformat()
                    })
                }
                opportunities.append(opportunity)
        
        return opportunities
    
    async def monitor_all_pairs(self):
        """Monitor all stablecoin pairs for opportunities"""
        logger.info("Starting stablecoin monitoring...")
        
        for pair in self.stablecoin_pairs:
            logger.info(f"Monitoring {pair.name} on {pair.network}")
            
            try:
                # Get pool data
                pool_data = await self.get_pool_data(pair.network, pair.pool_address, pair.dex_protocol)
                
                if pool_data:
                    # Detect opportunities
                    opportunities = self.detect_stablecoin_opportunities(pool_data, pair)
                    
                    if opportunities:
                        logger.info(f"Found {len(opportunities)} opportunities for {pair.name}")
                        for opp in opportunities:
                            self.save_opportunity(opp)
                    else:
                        logger.info(f"No opportunities found for {pair.name}")
                else:
                    logger.warning(f"Failed to get pool data for {pair.name}")
                
                # Small delay between requests
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error monitoring {pair.name}: {e}")
                continue
    
    def save_opportunity(self, opportunity: Dict):
        """Save opportunity to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO stablecoin_opportunities 
                (id, timestamp, network, pair_name, opportunity_type, profit_percentage, 
                 estimated_profit_usd, pool_address, dex_protocol, token_a, token_b, 
                 liquidity_usd, gas_cost_usd, confidence_score, status, details_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                opportunity['id'],
                datetime.now(),
                opportunity['network'],
                opportunity['pair_name'],
                opportunity['opportunity_type'],
                opportunity['profit_percentage'],
                opportunity['estimated_profit_usd'],
                opportunity['pool_address'],
                opportunity['dex_protocol'],
                opportunity['token_a'],
                opportunity['token_b'],
                opportunity['liquidity_usd'],
                opportunity['gas_cost_usd'],
                opportunity['confidence_score'],
                opportunity['status'],
                opportunity['details_json']
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving opportunity: {e}")
    
    def save_price_data(self, network: str, pair_name: str, token_a: str, token_b: str, 
                       price_a: float, price_b: float, spread: float, pool_address: str):
        """Save price data to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO stablecoin_prices 
                (timestamp, network, pair_name, token_a, token_b, price_a, price_b, 
                 spread_percentage, pool_address, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(),
                network,
                pair_name,
                token_a,
                token_b,
                price_a,
                price_b,
                spread,
                pool_address,
                'monitor'
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving price data: {e}")
    
    async def run_monitoring(self, duration_minutes: int = 60):
        """Run continuous monitoring"""
        logger.info(f"Starting stablecoin monitoring for {duration_minutes} minutes")
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        while datetime.now() < end_time:
            try:
                await self.monitor_all_pairs()
                
                # Wait before next cycle
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(10)
        
        logger.info("Stablecoin monitoring completed")
    
    def get_recent_opportunities(self, hours: int = 24) -> List[Dict]:
        """Get recent stablecoin opportunities"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            since_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute('''
                SELECT * FROM stablecoin_opportunities 
                WHERE timestamp > ? 
                ORDER BY timestamp DESC 
                LIMIT 50
            ''', (since_time,))
            
            columns = [desc[0] for desc in cursor.description]
            opportunities = []
            
            for row in cursor.fetchall():
                opportunity = dict(zip(columns, row))
                opportunities.append(opportunity)
            
            conn.close()
            return opportunities
            
        except Exception as e:
            logger.error(f"Error getting recent opportunities: {e}")
            return []

if __name__ == "__main__":
    monitor = StablecoinMonitor()
    
    # Run monitoring for 1 hour
    asyncio.run(monitor.run_monitoring(60))