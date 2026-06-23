#!/usr/bin/env python3
"""
Dynamic Gas Pricing Module
Real-time gas monitoring and optimization for flash loan execution
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
class GasMetrics:
    """Gas price metrics data structure"""
    base_gas_price: int
    priority_fee: int
    max_fee: int
    timestamp: datetime
    confidence_score: float = 0.0
    congestion_level: str = "normal"
    
@dataclass
class NetworkConditions:
    """Network health and congestion data"""
    mempool_size: int
    avg_block_time: float
    gas_price_percentiles: Dict[str, int]
    pending_transactions: int
    network_load: float
    timestamp: datetime
    congestion_level: str = "normal"

class DynamicGasMonitor:
    """Real-time gas monitoring and optimization"""
    
    def __init__(self, w3: Web3, network: str = "arbitrum"):
        self.w3 = w3
        self.network = network
        self.gas_metrics_history: List[GasMetrics] = []
        self.network_conditions_history: List[NetworkConditions] = []
        self.last_update: Optional[datetime] = None
        self.is_monitoring = False
        
        # Configuration
        self.base_gas_multiplier = 1.3  # 30% above base
        self.priority_gas_multiplier = 1.5  # 50% above base for high priority
        self.congestion_thresholds = {
            'low': {'block_time': 3.0, 'mempool_size': 500},
            'medium': {'block_time': 8.0, 'mempool_size': 2000},
            'high': {'block_time': 15.0, 'mempool_size': 5000},
            'severe': {'block_time': 30.0, 'mempool_size': 10000}
        }
        
        logger.info(f"✅ Dynamic Gas Monitor initialized for {network}")
    
    async def start_monitoring(self, interval: float = 30.0):
        """Start continuous gas monitoring"""
        self.is_monitoring = True
        logger.info(f"🔍 Starting gas monitoring with {interval}s interval")
        
        while self.is_monitoring:
            try:
                await self.update_gas_metrics()
                await self.update_network_conditions()
                await self.analyze_trends()
                
                logger.debug(f"📊 Gas updated - Base: {self.get_current_gas_metrics().base_gas_price/1e9:.3f} gwei")
                
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"❌ Gas monitoring error: {e}")
                await asyncio.sleep(interval)
    
    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.is_monitoring = False
        logger.info("🛑 Gas monitoring stopped")
    
    async def update_gas_metrics(self):
        """Update current gas price metrics"""
        try:
            # Get current base gas price
            base_gas = self.w3.eth.gas_price
            
            # Calculate priority and max fees
            priority_fee = int(base_gas * 0.3)  # 30% of base
            max_fee = int(base_gas * 2.0)     # 2x base for EIP-1559
            
            metrics = GasMetrics(
                base_gas_price=base_gas,
                priority_fee=priority_fee,
                max_fee=max_fee,
                timestamp=datetime.now(),
                confidence_score=0.8  # Default confidence
            )
            
            self.gas_metrics_history.append(metrics)
            
            # Keep only last 100 entries
            if len(self.gas_metrics_history) > 100:
                self.gas_metrics_history = self.gas_metrics_history[-100:]
                
            self.last_update = datetime.now()
            
        except Exception as e:
            logger.error(f"❌ Gas metrics update failed: {e}")
    
    async def update_network_conditions(self):
        """Update network health conditions"""
        try:
            # Get recent blocks for analysis. Web3.py HTTPProvider calls are synchronous;
            # do not await them or AttributeDict errors are raised.
            latest_block = self.w3.eth.get_block('latest')
            
            # Calculate average block time from last 10 blocks
            block_times = []
            for i in range(1, min(11, latest_block.number + 1)):
                block = self.w3.eth.get_block(latest_block.number - i)
                if hasattr(block, 'timestamp') and hasattr(block, 'parentHash') and block.parentHash:
                    parent_block = self.w3.eth.get_block(block.parentHash)
                    if hasattr(parent_block, 'timestamp'):
                        block_time = block.timestamp - parent_block.timestamp
                        block_times.append(block_time)
            
            avg_block_time = sum(block_times) / len(block_times) if block_times else 5.0
            
            # Estimate mempool size (simplified)
            mempool_size = await self.estimate_mempool_size()
            
            # Get gas price percentiles
            gas_percentiles = await self.get_gas_price_percentiles()
            
            conditions = NetworkConditions(
                mempool_size=mempool_size,
                avg_block_time=avg_block_time,
                gas_price_percentiles=gas_percentiles,
                pending_transactions=mempool_size,
                network_load=self.calculate_network_load(mempool_size, avg_block_time),
                timestamp=datetime.now(),
                congestion_level=self.determine_congestion_level(avg_block_time, mempool_size)
            )
            
            self.network_conditions_history.append(conditions)
            
            # Keep only last 50 entries
            if len(self.network_conditions_history) > 50:
                self.network_conditions_history = self.network_conditions_history[-50:]
                
        except Exception as e:
            logger.error(f"❌ Network conditions update failed: {e}")
    
    async def estimate_mempool_size(self) -> int:
        """Estimate current mempool size"""
        try:
            # This is a simplified estimation
            # In production, you might use blockchain explorers or specialized APIs
            base_gas = self.w3.eth.gas_price
            return int(base_gas / 1e9 * 1000)  # Simplified estimation
            
        except Exception as e:
            logger.warning(f"⚠️ Mempool estimation failed: {e}")
            return 1000  # Default estimation
    
    async def get_gas_price_percentiles(self) -> Dict[str, int]:
        """Get gas price percentiles"""
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
    
    def calculate_network_load(self, mempool_size: int, avg_block_time: float) -> float:
        """Calculate network load factor (0-1)"""
        # Normalize metrics
        mempool_factor = min(mempool_size / 5000, 1.0)  # Normalize to 5000
        block_time_factor = min(avg_block_time / 15.0, 1.0)  # Normalize to 15s
        
        # Combined network load
        return (mempool_factor * 0.6 + block_time_factor * 0.4)
    
    def determine_congestion_level(self, avg_block_time: float, mempool_size: int) -> str:
        """Determine network congestion level"""
        thresholds = self.congestion_thresholds
        
        if avg_block_time > thresholds['severe']['block_time'] or mempool_size > thresholds['severe']['mempool_size']:
            return 'severe'
        elif avg_block_time > thresholds['high']['block_time'] or mempool_size > thresholds['high']['mempool_size']:
            return 'high'
        elif avg_block_time > thresholds['medium']['block_time'] or mempool_size > thresholds['medium']['mempool_size']:
            return 'medium'
        elif avg_block_time > thresholds['low']['block_time'] or mempool_size > thresholds['low']['mempool_size']:
            return 'low'
        else:
            return 'normal'
    
    async def analyze_trends(self):
        """Analyze gas price trends"""
        if len(self.gas_metrics_history) < 5:
            return
            
        # Calculate gas price trend
        recent_prices = [m.base_gas_price for m in self.gas_metrics_history[-5:]]
        avg_price = sum(recent_prices) / len(recent_prices)
        current_price = recent_prices[-1]
        
        # Update confidence based on trend stability
        price_variance = sum((p - avg_price) ** 2 for p in recent_prices) / len(recent_prices)
        price_stability = 1.0 / (1.0 + price_variance / 1e18)  # Normalize variance
        
        # Update confidence scores
        for metric in self.gas_metrics_history[-3:]:
            metric.confidence_score = price_stability
    
    def get_current_gas_metrics(self) -> Optional[GasMetrics]:
        """Get current gas metrics"""
        return self.gas_metrics_history[-1] if self.gas_metrics_history else None
    
    def get_current_network_conditions(self) -> Optional[NetworkConditions]:
        """Get current network conditions"""
        return self.network_conditions_history[-1] if self.network_conditions_history else None
    
    def get_optimal_gas_price(self, priority: str = "normal") -> Dict[str, int]:
        """Calculate optimal gas price based on network conditions"""
        if not self.gas_metrics_history or not self.network_conditions_history:
            # Fallback to basic calculation
            base_gas = self.w3.eth.gas_price
            return {
                'base_gas_price': base_gas,
                'priority_fee': int(base_gas * 0.3),
                'max_fee': int(base_gas * 2.0)
            }
        
        current_metrics = self.get_current_gas_metrics()
        current_conditions = self.get_current_network_conditions()
        
        if not current_metrics or not current_conditions:
            base_gas = self.w3.eth.gas_price
            return {
                'base_gas_price': base_gas,
                'priority_fee': int(base_gas * 0.3),
                'max_fee': int(base_gas * 2.0)
            }
        
        base_gas = current_metrics.base_gas_price
        
        # Calculate multiplier based on network conditions
        congestion_multiplier = self.get_congestion_multiplier(current_conditions.congestion_level)
        
        # Adjust for priority level
        if priority == "high":
            priority_multiplier = 1.5
        elif priority == "medium":
            priority_multiplier = 1.3
        else:
            priority_multiplier = 1.1
        
        # Calculate final gas prices
        final_multiplier = congestion_multiplier * priority_multiplier
        
        optimal_gas = {
            'base_gas_price': int(base_gas * final_multiplier),
            'priority_fee': int(base_gas * 0.3 * final_multiplier),
            'max_fee': int(base_gas * 2.0 * final_multiplier),
            'congestion_level': current_conditions.congestion_level,
            'network_load': current_conditions.network_load,
            'confidence_score': current_metrics.confidence_score
        }
        
        logger.info(f"🎯 Optimal gas calculated - Priority: {priority}, Multiplier: {final_multiplier:.2f}, "
                   f"Base: {optimal_gas['base_gas_price']/1e9:.3f} gwei")
        
        return optimal_gas
    
    def get_congestion_multiplier(self, congestion_level: str) -> float:
        """Get gas price multiplier based on congestion level"""
        multipliers = {
            'normal': 1.0,
            'low': 1.1,
            'medium': 1.3,
            'high': 1.6,
            'severe': 2.0
        }
        return multipliers.get(congestion_level, 1.0)
    
    def should_send_transaction(self) -> Tuple[bool, str]:
        """Determine if current network conditions are suitable for transactions"""
        conditions = self.get_current_network_conditions()
        
        if not conditions:
            return True, "No network data available"
        
        # Only send if network is not severely congested
        if conditions.congestion_level == 'severe':
            return False, "Network severely congested - wait"
        elif conditions.congestion_level == 'high':
            return True, "Network congested - use high priority"
        elif conditions.avg_block_time > 10:  # More than 10 seconds per block
            return True, "Slow blocks - use premium gas"
        else:
            return True, "Good conditions - normal priority"
    
    def get_historical_gas_trend(self, hours: int = 1) -> Dict[str, Any]:
        """Get gas price trends over specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_metrics = [m for m in self.gas_metrics_history if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return {'error': 'No data available'}
        
        prices = [m.base_gas_price for m in recent_metrics]
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        
        return {
            'average_gas_price': avg_price,
            'min_gas_price': min_price,
            'max_gas_price': max_price,
            'price_volatility': (max_price - min_price) / avg_price if avg_price > 0 else 0,
            'data_points': len(recent_metrics),
            'time_range_hours': hours
        }