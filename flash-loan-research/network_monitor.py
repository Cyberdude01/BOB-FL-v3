#!/usr/bin/env python3
"""
Network Health Monitor
Real-time network monitoring and analysis for blockchain networks
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from web3 import Web3
import aiohttp
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class NetworkHealthMetrics:
    """Network health metrics data structure"""
    network: str
    timestamp: datetime
    avg_block_time: float
    block_time_stddev: float
    mempool_size: int
    pending_transactions: int
    gas_price_trend: Dict[str, float]
    gas_price_percentiles: Dict[str, int]
    network_load: float
    health_score: float
    status: str
    
@dataclass
class Alert:
    """Network alert data structure"""
    network: str
    alert_type: str
    severity: str
    message: str
    timestamp: datetime
    metrics: Dict[str, Any]

class NetworkMonitor:
    """Real-time network health monitoring"""
    
    def __init__(self, w3: Web3, network: str = "arbitrum"):
        self.w3 = w3
        self.network = network
        self.health_metrics_history: List[NetworkHealthMetrics] = []
        self.alerts: List[Alert] = []
        self.is_monitoring = False
        
        # Configuration
        self.alert_thresholds = {
            'block_time_high': 15.0,  # seconds
            'block_time_low': 1.0,   # seconds
            'mempool_high': 5000,    # transactions
            'mempool_low': 100,      # transactions
            'gas_spike': 2.0,        # multiplier
            'network_load_high': 0.8 # 80% load
        }
        
        # Alert cooldowns
        self.alert_cooldowns = {
            'block_time_high': 300,   # 5 minutes
            'mempool_high': 300,
            'gas_spike': 300,
            'network_load_high': 300
        }
        
        self.last_alerts = {}
        
        logger.info(f"✅ Network Monitor initialized for {network}")
    
    async def start_monitoring(self, interval: float = 60.0):
        """Start continuous network monitoring"""
        self.is_monitoring = True
        logger.info(f"🔍 Starting network monitoring with {interval}s interval")
        
        while self.is_monitoring:
            try:
                await self.update_network_health()
                await self.check_alerts()
                await self.calculate_health_score()
                
                logger.debug(f"📊 Network updated - Health: {self.get_current_health_metrics().health_score:.2f}")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"❌ Network monitoring error: {e}")
                await asyncio.sleep(interval)
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.is_monitoring = False
        logger.info("🛑 Network monitoring stopped")
    
    async def update_network_health(self):
        """Update network health metrics"""
        try:
            # Get latest block. Web3.py HTTPProvider calls are synchronous; do not await.
            latest_block = self.w3.eth.get_block('latest')
            
            # Analyze recent blocks
            block_times = []
            block_timestamps = []
            
            # Get last 20 blocks for analysis
            for i in range(min(20, latest_block.number + 1)):
                block = self.w3.eth.get_block(latest_block.number - i)
                if hasattr(block, 'timestamp') and block.timestamp:
                    block_timestamps.append(block.timestamp)
                    
                    if i > 0 and hasattr(block, 'parentHash'):
                        parent_block = self.w3.eth.get_block(block.parentHash)
                        if hasattr(parent_block, 'timestamp'):
                            block_time = block.timestamp - parent_block.timestamp
                            block_times.append(block_time)
            
            # Calculate statistics
            avg_block_time = sum(block_times) / len(block_times) if block_times else 5.0
            block_time_stddev = (sum((t - avg_block_time) ** 2 for t in block_times) / len(block_times)) ** 0.5 if block_times else 0.0
            
            # Get mempool information
            mempool_size, pending_transactions = await self.analyze_mempool()
            
            # Analyze gas price trends and percentiles
            gas_price_trend = await self.analyze_gas_price_trend()
            gas_percentiles = await self.get_gas_price_percentiles()
            
            # Calculate network load
            network_load = self.calculate_network_load(mempool_size, avg_block_time)
            
            # Create health metrics
            metrics = NetworkHealthMetrics(
                network=self.network,
                timestamp=datetime.now(),
                avg_block_time=avg_block_time,
                block_time_stddev=block_time_stddev,
                mempool_size=mempool_size,
                pending_transactions=pending_transactions,
                gas_price_trend=gas_price_trend,
                gas_price_percentiles=gas_percentiles,
                network_load=network_load,
                health_score=0.0,  # Will be calculated
                status="monitoring"
            )
            
            self.health_metrics_history.append(metrics)
            
            # Keep only last 100 entries
            if len(self.health_metrics_history) > 100:
                self.health_metrics_history = self.health_metrics_history[-100:]
                
        except Exception as e:
            logger.error(f"❌ Network health update failed: {e}")
    
    async def analyze_mempool(self) -> Tuple[int, int]:
        """Analyze mempool size and pending transactions"""
        try:
            # This is a simplified analysis
            # In production, you might use blockchain explorers or specialized APIs
            
            # Estimate based on recent blocks
            latest_block = self.w3.eth.get_block('latest')
            
            # Simple estimation based on gas price and network activity
            base_gas = self.w3.eth.gas_price
            mempool_size = int(base_gas / 1e9 * 500)  # Simplified estimation
            
            # Get actual pending transactions count
            try:
                # This might be slow on some networks
                pending_count = len(self.w3.eth.get_filter_changes('pending'))
                return pending_count, pending_count
            except:
                return mempool_size, mempool_size
                
        except Exception as e:
            logger.warning(f"⚠️ Mempool analysis failed: {e}")
            return 1000, 1000  # Default estimation
    
    async def analyze_gas_price_trend(self) -> Dict[str, float]:
        """Analyze gas price trends"""
        try:
            base_gas = self.w3.eth.gas_price
            
            # Calculate relative to historical data
            if len(self.health_metrics_history) >= 5:
                recent_gas_prices = [m.gas_price_trend.get('current', base_gas) 
                                   for m in self.health_metrics_history[-5:]]
                avg_gas = sum(recent_gas_prices) / len(recent_gas_prices)
                trend_ratio = base_gas / avg_gas if avg_gas > 0 else 1.0
            else:
                trend_ratio = 1.0
            
            return {
                'current': base_gas,
                'average_5min': base_gas,  # Would calculate from historical data
                'trend_ratio': trend_ratio,
                'volatility': 0.0  # Would calculate from historical data
            }
            
        except Exception as e:
            logger.warning(f"⚠️ Gas price trend analysis failed: {e}")
            base_gas = self.w3.eth.gas_price
            return {
                'current': base_gas,
                'average_5min': base_gas,
                'trend_ratio': 1.0,
                'volatility': 0.0
            }
    
    def calculate_network_load(self, mempool_size: int, avg_block_time: float) -> float:
        """Calculate network load factor (0-1)"""
        # Normalize metrics
        mempool_factor = min(mempool_size / 5000, 1.0)  # Normalize to 5000
        block_time_factor = min(avg_block_time / 15.0, 1.0)  # Normalize to 15s
        
        # Combined network load
        return (mempool_factor * 0.6 + block_time_factor * 0.4)
    
    def calculate_health_score(self):
        """Calculate network health score (0-100)"""
        if not self.health_metrics_history:
            return
            
        current_metrics = self.health_metrics_history[-1]
        
        # Calculate individual component scores
        block_time_score = self.score_block_time(current_metrics.avg_block_time)
        mempool_score = self.score_mempool_size(current_metrics.mempool_size)
        gas_trend_score = self.score_gas_trend(current_metrics.gas_price_trend)
        network_load_score = self.score_network_load(current_metrics.network_load)
        
        # Weighted average (adjust weights based on importance)
        weights = {
            'block_time': 0.3,
            'mempool': 0.25,
            'gas_trend': 0.2,
            'network_load': 0.25
        }
        
        health_score = (
            block_time_score * weights['block_time'] +
            mempool_score * weights['mempool'] +
            gas_trend_score * weights['gas_trend'] +
            network_load_score * weights['network_load']
        )
        
        # Update health score
        current_metrics.health_score = health_score
        current_metrics.status = self.get_health_status(health_score)
        
        logger.debug(f"📈 Health score calculated: {health_score:.2f} "
                   f"(BT: {block_time_score:.1f}, MP: {mempool_score:.1f}, "
                   f"GT: {gas_trend_score:.1f}, NL: {network_load_score:.1f})")
    
    def score_block_time(self, block_time: float) -> float:
        """Score block time (0-100)"""
        if block_time <= 2.0:
            return 100.0
        elif block_time <= 5.0:
            return 80.0
        elif block_time <= 8.0:
            return 60.0
        elif block_time <= 12.0:
            return 40.0
        elif block_time <= 20.0:
            return 20.0
        else:
            return 0.0
    
    def score_mempool_size(self, mempool_size: int) -> float:
        """Score mempool size (0-100)"""
        if mempool_size <= 500:
            return 100.0
        elif mempool_size <= 1500:
            return 80.0
        elif mempool_size <= 3000:
            return 60.0
        elif mempool_size <= 5000:
            return 40.0
        elif mempool_size <= 8000:
            return 20.0
        else:
            return 0.0
    
    def score_gas_trend(self, gas_trend: Dict[str, float]) -> float:
        """Score gas price trend (0-100)"""
        trend_ratio = gas_trend.get('trend_ratio', 1.0)
        
        if trend_ratio <= 0.8:
            return 100.0  # Low gas prices are good
        elif trend_ratio <= 1.2:
            return 80.0   # Stable gas prices
        elif trend_ratio <= 1.5:
            return 60.0   # Moderate increase
        elif trend_ratio <= 2.0:
            return 40.0   # High gas prices
        elif trend_ratio <= 3.0:
            return 20.0   # Very high gas prices
        else:
            return 0.0    # Extremely high gas prices
    
    def score_network_load(self, network_load: float) -> float:
        """Score network load (0-100)"""
        if network_load <= 0.2:
            return 100.0  # Very low load
        elif network_load <= 0.4:
            return 80.0   # Low load
        elif network_load <= 0.6:
            return 60.0   # Moderate load
        elif network_load <= 0.8:
            return 40.0   # High load
        elif network_load <= 0.9:
            return 20.0   # Very high load
        else:
            return 0.0    # Extremely high load
    
    def get_health_status(self, health_score: float) -> str:
        """Get health status based on score"""
        if health_score >= 80:
            return "excellent"
        elif health_score >= 60:
            return "good"
        elif health_score >= 40:
            return "fair"
        elif health_score >= 20:
            return "poor"
        else:
            return "critical"
    
    async def get_gas_price_percentiles(self) -> Dict[str, int]:
        """Get gas price percentiles for network health indicators"""
        try:
            base_gas = self.w3.eth.gas_price
            
            return {
                'p25': int(base_gas * 0.8),
                'p50': int(base_gas * 1.0),
                'p75': int(base_gas * 1.3),
                'p90': int(base_gas * 1.8),
                'p95': int(base_gas * 2.2),
                'p99': int(base_gas * 3.0)
            }
            
        except Exception as e:
            logger.warning(f"⚠️ Gas percentiles failed: {e}")
            base_gas = self.w3.eth.gas_price
            return {
                'p25': int(base_gas * 0.8),
                'p50': int(base_gas * 1.0),
                'p75': int(base_gas * 1.3),
                'p90': int(base_gas * 1.8),
                'p95': int(base_gas * 2.2),
                'p99': int(base_gas * 3.0)
            }
    
    async def check_alerts(self):
        """Check for network alerts"""
        if not self.health_metrics_history:
            return
            
        current_metrics = self.health_metrics_history[-1]
        current_time = datetime.now()
        
        # Check block time alerts
        if current_metrics.avg_block_time > self.alert_thresholds['block_time_high']:
            await self.check_alert_cooldown('block_time_high', current_time)
            if self.should_send_alert('block_time_high', current_time):
                await self.create_alert(
                    'block_time_high',
                    'warning',
                    f"High block time: {current_metrics.avg_block_time:.1f}s"
                )
        
        # Check mempool alerts
        if current_metrics.mempool_size > self.alert_thresholds['mempool_high']:
            await self.check_alert_cooldown('mempool_high', current_time)
            if self.should_send_alert('mempool_high', current_time):
                await self.create_alert(
                    'mempool_high',
                    'warning',
                    f"High mempool size: {current_metrics.mempool_size} transactions"
                )
        
        # Check gas price spike alerts
        if current_metrics.gas_price_trend.get('trend_ratio', 1.0) > self.alert_thresholds['gas_spike']:
            await self.check_alert_cooldown('gas_spike', current_time)
            if self.should_send_alert('gas_spike', current_time):
                await self.create_alert(
                    'gas_spike',
                    'warning',
                    f"Gas price spike: {current_metrics.gas_price_trend['trend_ratio']:.1f}x average"
                )
        
        # Check network load alerts
        if current_metrics.network_load > self.alert_thresholds['network_load_high']:
            await self.check_alert_cooldown('network_load_high', current_time)
            if self.should_send_alert('network_load_high', current_time):
                await self.create_alert(
                    'network_load_high',
                    'warning',
                    f"High network load: {current_metrics.network_load:.1%}"
                )
    
    async def check_alert_cooldown(self, alert_type: str, current_time: datetime):
        """Check if alert is in cooldown period"""
        if alert_type in self.last_alerts:
            time_since_last = (current_time - self.last_alerts[alert_type]).total_seconds()
            if time_since_last < self.alert_cooldowns[alert_type]:
                return False
        return True
    
    def should_send_alert(self, alert_type: str, current_time: datetime) -> bool:
        """Determine if alert should be sent"""
        if alert_type not in self.last_alerts:
            return True
        
        time_since_last = (current_time - self.last_alerts[alert_type]).total_seconds()
        return time_since_last >= self.alert_cooldowns[alert_type]
    
    async def create_alert(self, alert_type: str, severity: str, message: str):
        """Create and log network alert"""
        alert = Alert(
            network=self.network,
            alert_type=alert_type,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            metrics=asdict(self.health_metrics_history[-1]) if self.health_metrics_history else {}
        )
        
        self.alerts.append(alert)
        self.last_alerts[alert_type] = datetime.now()
        
        logger.warning(f"🚨 NETWORK ALERT [{severity.upper()}] {alert_type}: {message}")
        
        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    def get_current_health_metrics(self) -> Optional[NetworkHealthMetrics]:
        """Get current network health metrics"""
        return self.health_metrics_history[-1] if self.health_metrics_history else None
    
    def get_network_recommendations(self) -> List[str]:
        """Get network recommendations based on current conditions"""
        if not self.health_metrics_history:
            return ["No network data available"]
        
        current_metrics = self.health_metrics_history[-1]
        recommendations = []
        
        # Block time recommendations
        if current_metrics.avg_block_time > 15.0:
            recommendations.append("⚠️ Network severely congested - avoid sending transactions")
        elif current_metrics.avg_block_time > 8.0:
            recommendations.append("⚠️ Network congested - use high priority gas")
        elif current_metrics.avg_block_time > 5.0:
            recommendations.append("⚠️ Network moderately busy - use medium priority gas")
        
        # Mempool recommendations
        if current_metrics.mempool_size > 5000:
            recommendations.append("⚠️ Mempool very busy - wait for better conditions")
        elif current_metrics.mempool_size > 2000:
            recommendations.append("⚠️ Mempool busy - use higher gas prices")
        
        # Gas price recommendations
        if current_metrics.gas_price_trend.get('trend_ratio', 1.0) > 2.0:
            recommendations.append("⚠️ Gas prices very high - consider waiting")
        
        # Health score recommendations
        if current_metrics.health_score < 20:
            recommendations.append("🚨 Network conditions poor - avoid critical transactions")
        elif current_metrics.health_score < 40:
            recommendations.append("⚠️ Network conditions fair - use caution")
        
        return recommendations if recommendations else ["✅ Network conditions good - normal operations"]
    
    def get_network_summary(self) -> Dict[str, Any]:
        """Get network summary statistics"""
        if not self.health_metrics_history:
            return {'error': 'No data available'}
        
        current_metrics = self.health_metrics_history[-1]
        
        # Calculate statistics
        recent_block_times = [m.avg_block_time for m in self.health_metrics_history[-10:]]
        avg_block_time = sum(recent_block_times) / len(recent_block_times)
        
        recent_health_scores = [m.health_score for m in self.health_metrics_history[-10:]]
        avg_health_score = sum(recent_health_scores) / len(recent_health_scores)
        
        return {
            'current_status': current_metrics.status,
            'current_health_score': current_metrics.health_score,
            'avg_block_time': avg_block_time,
            'current_mempool_size': current_metrics.mempool_size,
            'network_load': current_metrics.network_load,
            'recent_trend': 'improving' if avg_health_score > current_metrics.health_score else 'declining',
            'recommendations': self.get_network_recommendations(),
            'last_updated': current_metrics.timestamp.isoformat()
        }