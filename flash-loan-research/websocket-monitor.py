#!/usr/bin/env python3
"""
WebSocket-based Real-time Monitoring System
Implements real-time alerts for flash loan opportunities
"""

import asyncio
import websockets
import json
import logging
import sqlite3
import time
from datetime import datetime
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RealTimeMonitor:
    def __init__(self):
        self.db_path = '/root/.openclaw/workspace/flash-loan-research/enhanced_flash_loan_research.db'
        self.setup_database()
        
        # WebSocket endpoints (corrected)
        self.websocket_endpoints = {
            'ethereum': 'wss://ws.coincap.io/prices?assets=ethereum',
            'binance': 'wss://stream.binance.com:9443/ws/ethusdt@ticker',
            'coinbase': 'wss://ws-feed.exchange.coinbase.com',
        }
        
        # Alert thresholds
        self.price_alert_threshold = 0.1  # 0.1% price change
        self.alert_cooldown = 60  # 60 seconds between alerts
        
        # Last alert times
        self.last_alerts = {}
        
    def setup_database(self):
        """Setup database for storing alerts"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS real_time_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    network TEXT,
                    asset TEXT,
                    price_change REAL,
                    alert_type TEXT,
                    message TEXT,
                    processed BOOLEAN DEFAULT FALSE
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database setup completed successfully")
            
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            raise
    
    async def connect_to_websocket(self, url, network):
        """Connect to WebSocket endpoint"""
        try:
            async with websockets.connect(url) as websocket:
                logger.info(f"Connected to {network} WebSocket")
                
                # Subscribe to price updates
                if network == 'ethereum':
                    await websocket.send(json.dumps({
                        "type": "subscribe",
                        "payload": "prices"
                    }))
                
                # Process messages
                async for message in websocket:
                    await self.process_message(json.loads(message), network)
                    
        except Exception as e:
            logger.error(f"WebSocket connection failed for {network}: {e}")
    
    async def process_message(self, message, network):
        """Process incoming WebSocket messages"""
        try:
            current_time = datetime.now()
            
            if network == 'ethereum':
                # Process CoinCap price updates
                if message.get('type') == 'price':
                    asset = message.get('asset')
                    price = float(message.get('price', 0))
                    
                    await self.check_price_alert(asset, price, network, current_time)
                    
            elif network == 'binance':
                # Process Binance ticker updates
                if message.get('stream') and 'ticker' in message.get('stream'):
                    data = message.get('data', {})
                    symbol = data.get('s')
                    price = float(data.get('c', 0))
                    
                    if symbol == 'ETHUSDT':
                        await self.check_price_alert('ETH', price, 'binance', current_time)
                        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    async def check_price_alert(self, asset, price, network, timestamp):
        """Check if price movement triggers an alert"""
        try:
            # Get previous price from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT price FROM price_history 
                WHERE asset = ? AND network = ? 
                ORDER BY timestamp DESC LIMIT 1
            ''', (asset, network))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                previous_price = float(result[0])
                price_change = ((price - previous_price) / previous_price) * 100
                
                # Check if alert threshold is met
                if abs(price_change) > self.price_alert_threshold:
                    alert_key = f"{asset}_{network}"
                    
                    # Check cooldown period
                    if (alert_key not in self.last_alerts or 
                        (timestamp - self.last_alerts[alert_key]).seconds > self.alert_cooldown):
                        
                        # Trigger alert
                        await self.trigger_alert(asset, price, price_change, network, timestamp)
                        self.last_alerts[alert_key] = timestamp
                        
                        # Log to database
                        conn = sqlite3.connect(self.db_path)
                        cursor = conn.cursor()
                        
                        cursor.execute('''
                            INSERT INTO real_time_alerts (timestamp, network, asset, price_change, alert_type, message)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (timestamp, network, asset, price_change, 'price_alert', 
                              f"Price alert: {asset} price changed by {price_change:.2f}%"))
                        
                        conn.commit()
                        conn.close()
            
            # Store current price
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO price_history (timestamp, network, asset, price)
                VALUES (?, ?, ?, ?)
            ''', (timestamp, network, asset, price))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error checking price alert: {e}")
    
    async def trigger_alert(self, asset, price, price_change, network, timestamp):
        """Trigger real-time alert"""
        alert_message = f"""
🚨 FLASH LOAN ALERT 🚨
Network: {network.upper()}
Asset: {asset}
Current Price: ${price:,.2f}
Price Change: {price_change:+.2f}%
Timestamp: {timestamp}
"""
        
        logger.info(alert_message)
        
        # TODO: Implement alert delivery (email, SMS, webhook)
        # For now, just log the alert
    
    async def start_monitoring(self):
        """Start real-time monitoring"""
        logger.info("Starting real-time WebSocket monitoring...")
        
        # Create tasks for each network
        tasks = []
        for network, url in self.websocket_endpoints.items():
            task = asyncio.create_task(self.connect_to_websocket(url, network))
            tasks.append(task)
        
        # Wait for all tasks
        await asyncio.gather(*tasks, return_exceptions=True)

def main():
    """Main function to start the monitor"""
    monitor = RealTimeMonitor()
    
    try:
        # Run the monitoring
        asyncio.run(monitor.start_monitoring())
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    except Exception as e:
        logger.error(f"Monitoring failed: {e}")

if __name__ == "__main__":
    main()