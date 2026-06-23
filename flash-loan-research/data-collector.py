#!/usr/bin/env python3
"""
Flash Loan Opportunity Data Collector
Monitors DeFi protocols for arbitrage opportunities
"""

import requests
import json
import time
import sqlite3
from datetime import datetime, timedelta
import logging
import math

class DeFiDataCollector:
    def __init__(self, config_path="research-config.json"):
        self.config = self.load_config(config_path)
        self.setup_database()
        self.setup_logging()
        
    def load_config(self, config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def setup_database(self):
        self.conn = sqlite3.connect('flash_loan_research.db')
        cursor = self.conn.cursor()
        
        # Create opportunities table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                opportunity_type TEXT,
                protocol TEXT,
            pair TEXT,
            profit_percentage REAL,
            estimated_profit_usd REAL,
            risk_score INTEGER,
            details TEXT,
            status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Create price_data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                protocol TEXT,
                pair TEXT,
                price REAL,
                volume_24h REAL,
                liquidity REAL
            )
        ''')
        
        self.conn.commit()
    
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('research.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def get_uniswap_prices(self):
        """Get Uniswap V3/V2 prices"""
        try:
            # Ethereum Mainnet Uniswap V3
            url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
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
                    reserve0
                    reserve1
                    price0
                    price1
                    volumeUSD
                    liquidityUSD
                    token0Price
                    token1Price
                }
            }
            """
            response = requests.post(url, json={"query": query})
            if response.status_code == 200:
                data = response.json()
                return data.get('data', {}).get('pairs', [])
        except Exception as e:
            self.logger.error(f"Error fetching Uniswap data: {e}")
        return []
    
    def get_aave_rates(self):
        """Get Aave lending rates"""
        try:
            url = "https://api.aave.com/v2"
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching Aave data: {e}")
        return {}
    
    def get_compound_rates(self):
        """Get Compound lending rates"""
        try:
            url = "https://api.compound.finance/api/v2/account"
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching Compound data: {e}")
        return {}
    
    def calculate_arbitrage_opportunities(self, prices):
        """Calculate arbitrage opportunities between DEXs"""
        opportunities = []
        
        # Simple arbitrage detection between different price sources
        for i, pair1 in enumerate(prices):
            for j, pair2 in enumerate(prices):
                if i >= j:
                    continue
                    
                # Calculate price difference
                price_diff = abs(pair1.get('price', 0) - pair2.get('price', 0))
                if price_diff > self.config['research']['thresholds']['dex_arbitrage']:
                    profit_percentage = price_diff / ((pair1.get('price', 0) + pair2.get('price', 0)) / 2)
                    
                    opportunity = {
                        'timestamp': datetime.now(),
                        'opportunity_type': 'dex_arbitrage',
                        'protocol': f"{pair1.get('token0', {}).get('symbol', 'UNKNOWN')}-{pair1.get('token1', {}).get('symbol', 'UNKNOWN')}",
                        'pair': f"{pair1.get('token0', {}).get('symbol', 'UNKNOWN')}/{pair1.get('token1', {}).get('symbol', 'UNKNOWN')}",
                        'profit_percentage': profit_percentage,
                        'estimated_profit_usd': profit_percentage * 10000, # Assuming $10k position
                        'risk_score': self.calculate_risk_score(pair1, pair2),
                        'details': {
                            'source1': pair1.get('protocol', 'unknown'),
                            'source2': pair2.get('protocol', 'unknown'),
                            'price1': pair1.get('price', 0),
                            'price2': pair2.get('price', 0),
                            'liquidity1': pair1.get('liquidityUSD', 0),
                            'liquidity2': pair2.get('liquidityUSD', 0)
                        }
                    }
                    opportunities.append(opportunity)
        
        return opportunities
    
    def calculate_risk_score(self, pair1, pair2):
        """Calculate risk score for opportunity (0-100, lower is better)"""
        liquidity_score = min(pair1.get('liquidityUSD', 0), pair2.get('liquidityUSD', 0))
        price_impact_score = abs(pair1.get('price', 0) - pair2.get('price', 0))
        
        # Lower liquidity and higher price impact = higher risk
        risk = min(100, int((price_impact_score * 1000) + (1000000 / max(liquidity_score, 1))))
        return max(0, min(100, risk))
    
    def store_opportunity(self, opportunity):
        """Store opportunity in database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO opportunities (
                timestamp, opportunity_type, protocol, pair, 
                profit_percentage, estimated_profit_usd, risk_score, details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            opportunity['timestamp'],
            opportunity['opportunity_type'],
            opportunity['protocol'],
            opportunity['pair'],
            opportunity['profit_percentage'],
            opportunity['estimated_profit_usd'],
            opportunity['risk_score'],
            json.dumps(opportunity['details'])
        ))
        self.conn.commit()
    
    def collect_data(self):
        """Main data collection method"""
        self.logger.info("Starting data collection...")
        
        # Collect DEX prices
        uniswap_data = self.get_uniswap_prices()
        
        # Process opportunities
        opportunities = self.calculate_arbitrage_opportunities(uniswap_data)
        
        # Store opportunities
        for opp in opportunities:
            self.store_opportunity(opp)
            self.logger.info(f"Found opportunity: {opp['pair']} - {opp['profit_percentage']*100:.2f}% profit")
        
        self.logger.info(f"Data collection complete. Found {len(opportunities)} opportunities.")

if __name__ == "__main__":
    collector = DeFiDataCollector()
    collector.collect_data()