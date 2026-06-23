#!/usr/bin/env python3
"""
Simple test script for Dynamic Gas Pricing and Network Monitoring systems
Tests the logic without requiring external dependencies
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockWeb3:
    """Mock Web3 class for testing"""
    def __init__(self):
        self.gas_price = int(20 * 1e9)  # 20 gwei default
    
    def is_connected(self):
        return True

class MockGasMetrics:
    """Mock gas metrics for testing"""
    def __init__(self):
        self.base_gas_price = int(20 * 1e9)  # 20 gwei
        self.priority_fee = int(6 * 1e9)    # 6 gwei
        self.max_fee = int(40 * 1e9)       # 40 gwei
        self.timestamp = datetime.now()
        self.confidence_score = 0.8

class MockNetworkConditions:
    """Mock network conditions for testing"""
    def __init__(self):
        self.mempool_size = 1500
        self.avg_block_time = 5.2
        self.gas_price_percentiles = {
            'p25': int(16 * 1e9),
            'p50': int(20 * 1e9),
            'p75': int(26 * 1e9),
            'p90': int(36 * 1e9),
            'p95': int(44 * 1e9),
            'p99': int(60 * 1e9)
        }
        self.pending_transactions = 1500
        self.network_load = 0.4
        self.timestamp = datetime.now()
        self.congestion_level = "medium"

class TestDynamicGasMonitor:
    """Test implementation of dynamic gas monitoring"""
    
    def __init__(self):
        self.w3 = MockWeb3()
        self.network = "arbitrum"
        self.gas_metrics_history = []
        self.network_conditions_history = []
        self.base_gas_multiplier = 1.3
        self.priority_gas_multiplier = 1.5
        self.congestion_thresholds = {
            'low': {'block_time': 3.0, 'mempool_size': 500},
            'medium': {'block_time': 8.0, 'mempool_size': 2000},
            'high': {'block_time': 15.0, 'mempool_size': 5000},
            'severe': {'block_time': 30.0, 'mempool_size': 10000}
        }
        
        logger.info(f"✅ Test Dynamic Gas Monitor initialized for {self.network}")
    
    def update_gas_metrics(self):
        """Update current gas price metrics"""
        try:
            # Get current base gas price
            base_gas = self.w3.gas_price
            
            # Calculate priority and max fees
            priority_fee = int(base_gas * 0.3)  # 30% of base
            max_fee = int(base_gas * 2.0)     # 2x base for EIP-1559
            
            metrics = MockGasMetrics()
            metrics.base_gas_price = base_gas
            metrics.priority_fee = priority_fee
            metrics.max_fee = max_fee
            metrics.timestamp = datetime.now()
            
            self.gas_metrics_history.append(metrics)
            
            # Keep only last 100 entries
            if len(self.gas_metrics_history) > 100:
                self.gas_metrics_history = self.gas_metrics_history[-100:]
                
        except Exception as e:
            logger.error(f"❌ Gas metrics update failed: {e}")
    
    def update_network_conditions(self):
        """Update network health conditions"""
        try:
            conditions = MockNetworkConditions()
            self.network_conditions_history.append(conditions)
            
            # Keep only last 50 entries
            if len(self.network_conditions_history) > 50:
                self.network_conditions_history = self.network_conditions_history[-50:]
                
        except Exception as e:
            logger.error(f"❌ Network conditions update failed: {e}")
    
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
    
    def get_optimal_gas_price(self, priority: str = "normal") -> Dict[str, int]:
        """Calculate optimal gas price based on network conditions"""
        if not self.gas_metrics_history or not self.network_conditions_history:
            # Fallback to basic calculation
            base_gas = self.w3.gas_price
            return {
                'base_gas_price': base_gas,
                'priority_fee': int(base_gas * 0.3),
                'max_fee': int(base_gas * 2.0)
            }
        
        current_metrics = self.gas_metrics_history[-1]
        current_conditions = self.network_conditions_history[-1]
        
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
        if not self.network_conditions_history:
            return True, "No network data available"
        
        conditions = self.network_conditions_history[-1]
        
        # Only send if network is not severely congested
        if conditions.congestion_level == 'severe':
            return False, "Network severely congested - wait"
        elif conditions.congestion_level == 'high':
            return True, "Network congested - use high priority"
        elif conditions.avg_block_time > 10:  # More than 10 seconds per block
            return True, "Slow blocks - use premium gas"
        else:
            return True, "Good conditions - normal priority"

class TestNetworkMonitor:
    """Test implementation of network monitoring"""
    
    def __init__(self):
        self.network = "arbitrum"
        self.health_metrics_history = []
        self.alerts = []
        self.alert_thresholds = {
            'block_time_high': 15.0,
            'block_time_low': 1.0,
            'mempool_high': 5000,
            'mempool_low': 100,
            'gas_spike': 2.0,
            'network_load_high': 0.8
        }
        
        logger.info(f"✅ Test Network Monitor initialized for {self.network}")
    
    def update_network_health(self):
        """Update network health metrics"""
        try:
            # Mock network health data
            health_metrics = {
                'network': self.network,
                'timestamp': datetime.now(),
                'avg_block_time': 5.2,
                'block_time_stddev': 1.1,
                'mempool_size': 1500,
                'pending_transactions': 1500,
                'gas_price_trend': {'current': int(20 * 1e9), 'trend_ratio': 1.0},
                'network_load': 0.4,
                'health_score': 75.0,
                'status': 'good'
            }
            
            self.health_metrics_history.append(health_metrics)
            
            # Keep only last 100 entries
            if len(self.health_metrics_history) > 100:
                self.health_metrics_history = self.health_metrics_history[-100:]
                
        except Exception as e:
            logger.error(f"❌ Network health update failed: {e}")
    
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
    
    def get_network_recommendations(self) -> List[str]:
        """Get network recommendations based on current conditions"""
        if not self.health_metrics_history:
            return ["No network data available"]
        
        current_metrics = self.health_metrics_history[-1]
        recommendations = []
        
        # Block time recommendations
        if current_metrics['avg_block_time'] > 15.0:
            recommendations.append("⚠️ Network severely congested - avoid sending transactions")
        elif current_metrics['avg_block_time'] > 8.0:
            recommendations.append("⚠️ Network congested - use high priority gas")
        elif current_metrics['avg_block_time'] > 5.0:
            recommendations.append("⚠️ Network moderately busy - use medium priority gas")
        
        # Mempool recommendations
        if current_metrics['mempool_size'] > 5000:
            recommendations.append("⚠️ Mempool very busy - wait for better conditions")
        elif current_metrics['mempool_size'] > 2000:
            recommendations.append("⚠️ Mempool busy - use higher gas prices")
        
        # Health score recommendations
        if current_metrics['health_score'] < 20:
            recommendations.append("🚨 Network conditions poor - avoid critical transactions")
        elif current_metrics['health_score'] < 40:
            recommendations.append("⚠️ Network conditions fair - use caution")
        
        return recommendations if recommendations else ["✅ Network conditions good - normal operations"]

def test_dynamic_gas_monitoring():
    """Test the dynamic gas monitoring system"""
    logger.info("🧪 Testing Dynamic Gas Monitoring System")
    
    try:
        # Initialize gas monitor
        gas_monitor = TestDynamicGasMonitor()
        
        # Test gas price calculation
        logger.info("🎯 Testing gas price calculations...")
        
        # Update metrics
        gas_monitor.update_gas_metrics()
        gas_monitor.update_network_conditions()
        
        # Test different priority levels
        priorities = ["normal", "medium", "high"]
        for priority in priorities:
            optimal_gas = gas_monitor.get_optimal_gas_price(priority)
            logger.info(f"📊 {priority.upper()} Priority Gas:")
            logger.info(f"   Base: {optimal_gas['base_gas_price']/1e9:.3f} gwei")
            logger.info(f"   Priority Fee: {optimal_gas['priority_fee']/1e9:.3f} gwei")
            logger.info(f"   Max Fee: {optimal_gas['max_fee']/1e9:.3f} gwei")
            logger.info(f"   Congestion: {optimal_gas['congestion_level']}")
            logger.info(f"   Confidence: {optimal_gas['confidence_score']:.2f}")
            logger.info("")
        
        # Test network suitability check
        should_send, reason = gas_monitor.should_send_transaction()
        logger.info(f"🚦 Network Suitability: {should_send} - {reason}")
        
        logger.info("✅ Dynamic Gas Monitoring test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Dynamic Gas Monitoring test failed: {e}")
        return False

def test_network_monitoring():
    """Test the network monitoring system"""
    logger.info("🧪 Testing Network Monitoring System")
    
    try:
        # Initialize network monitor
        network_monitor = TestNetworkMonitor()
        
        # Test network health metrics
        logger.info("🎯 Testing network health metrics...")
        
        # Update network conditions
        network_monitor.update_network_health()
        
        # Test scoring functions
        logger.info("🎯 Testing scoring functions...")
        
        block_time_scores = [1.0, 3.0, 6.0, 10.0, 18.0, 25.0]
        for block_time in block_time_scores:
            score = network_monitor.score_block_time(block_time)
            logger.info(f"   Block Time {block_time}s: {score:.1f}/100")
        
        mempool_sizes = [100, 800, 2000, 3500, 6000, 9000]
        for mempool_size in mempool_sizes:
            score = network_monitor.score_mempool_size(mempool_size)
            logger.info(f"   Mempool Size {mempool_size}: {score:.1f}/100")
        
        logger.info("")
        
        # Test network recommendations
        recommendations = network_monitor.get_network_recommendations()
        logger.info("🎯 Network Recommendations:")
        for rec in recommendations:
            logger.info(f"   {rec}")
        logger.info("")
        
        logger.info("✅ Network Monitoring test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Network Monitoring test failed: {e}")
        return False

def test_integration():
    """Test integration of both systems"""
    logger.info("🧪 Testing Integration of Dynamic Gas and Network Monitoring")
    
    try:
        # Initialize both monitors
        gas_monitor = TestDynamicGasMonitor()
        network_monitor = TestNetworkMonitor()
        
        # Update both systems
        gas_monitor.update_gas_metrics()
        gas_monitor.update_network_conditions()
        network_monitor.update_network_health()
        
        # Test network suitability
        should_send, reason = gas_monitor.should_send_transaction()
        logger.info(f"🚦 Network Suitability: {should_send} - {reason}")
        
        # Get optimal gas pricing
        optimal_gas = gas_monitor.get_optimal_gas_price("high")
        logger.info(f"🎯 Optimal Gas Pricing:")
        logger.info(f"   Base: {optimal_gas['base_gas_price']/1e9:.3f} gwei")
        logger.info(f"   Priority Fee: {optimal_gas['priority_fee']/1e9:.3f} gwei")
        logger.info(f"   Max Fee: {optimal_gas['max_fee']/1e9:.3f} gwei")
        
        # Test network recommendations
        recommendations = network_monitor.get_network_recommendations()
        logger.info("🎯 Network Recommendations:")
        for rec in recommendations:
            logger.info(f"   {rec}")
        
        # Calculate cost analysis
        gas_cost_usd = optimal_gas['base_gas_price'] / 1e18 * 21000  # Assume 21k gas
        profit_usd = 1000.0  # Mock profit
        profit_ratio = profit_usd / gas_cost_usd if gas_cost_usd > 0 else float('inf')
        
        logger.info(f"💰 Cost Analysis:")
        logger.info(f"   Gas Cost: ${gas_cost_usd:.2f}")
        logger.info(f"   Profit: ${profit_usd:.2f}")
        logger.info(f"   Profit Ratio: {profit_ratio:.1f}x")
        
        if profit_ratio < 2.0:
            logger.warning("⚠️ Gas cost is high relative to profit")
        else:
            logger.info("✅ Good profit ratio")
        
        logger.info("✅ Integration test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        return False

def main():
    """Main test function"""
    logger.info("🚀 Starting Dynamic Gas and Network Monitoring Tests")
    
    # Run tests
    tests = [
        ("Dynamic Gas Monitoring", test_dynamic_gas_monitoring),
        ("Network Monitoring", test_network_monitoring),
        ("Integration Test", test_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*60}")
        logger.info(f"Running {test_name}...")
        logger.info(f"{'='*60}")
        
        try:
            result = test_func()
            results.append((test_name, result))
            
            if result:
                logger.info(f"✅ {test_name} PASSED")
            else:
                logger.error(f"❌ {test_name} FAILED")
                
        except Exception as e:
            logger.error(f"❌ {test_name} ERROR: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed!")
    else:
        logger.error(f"⚠️ {total - passed} tests failed")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)