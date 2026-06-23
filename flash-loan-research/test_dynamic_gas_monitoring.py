#!/usr/bin/env python3
"""
Test script for Dynamic Gas Pricing and Network Monitoring systems
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from web3 import Web3
from dotenv import load_dotenv
import os

# Import our new modules
from gas_monitor import DynamicGasMonitor
from network_monitor import NetworkMonitor

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_dynamic_gas_monitoring():
    """Test the dynamic gas monitoring system"""
    logger.info("🧪 Testing Dynamic Gas Monitoring System")
    
    try:
        # Initialize Web3 connection
        w3 = Web3(Web3.HTTPProvider(os.getenv('ARBITRUM_RPC')))
        if not w3.is_connected():
            logger.error("❌ Failed to connect to Arbitrum network")
            return False
        
        logger.info(f"✅ Connected to Arbitrum network: {w3.is_connected()}")
        
        # Initialize gas monitor
        gas_monitor = DynamicGasMonitor(w3, "arbitrum")
        
        # Test gas price calculation
        logger.info("🎯 Testing gas price calculations...")
        
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
        
        # Test historical analysis
        trend_analysis = gas_monitor.get_historical_gas_trend(hours=1)
        logger.info(f"📈 Historical Trend Analysis:")
        logger.info(f"   {json.dumps(trend_analysis, indent=2)}")
        
        logger.info("✅ Dynamic Gas Monitoring test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Dynamic Gas Monitoring test failed: {e}")
        return False

async def test_network_monitoring():
    """Test the network monitoring system"""
    logger.info("🧪 Testing Network Monitoring System")
    
    try:
        # Initialize Web3 connection
        w3 = Web3(Web3.HTTPProvider(os.getenv('ARBITRUM_RPC')))
        if not w3.is_connected():
            logger.error("❌ Failed to connect to Arbitrum network")
            return False
        
        logger.info(f"✅ Connected to Arbitrum network: {w3.is_connected()}")
        
        # Initialize network monitor
        network_monitor = NetworkMonitor(w3, "arbitrum")
        
        # Test network health metrics
        logger.info("🎯 Testing network health metrics...")
        
        # Update network conditions
        await network_monitor.update_network_health()
        
        # Get current health metrics
        health_metrics = network_monitor.get_current_health_metrics()
        if health_metrics:
            logger.info(f"📊 Network Health Metrics:")
            logger.info(f"   Health Score: {health_metrics.health_score:.2f}")
            logger.info(f"   Status: {health_metrics.status}")
            logger.info(f"   Avg Block Time: {health_metrics.avg_block_time:.2f}s")
            logger.info(f"   Mempool Size: {health_metrics.mempool_size}")
            logger.info(f"   Network Load: {health_metrics.network_load:.2%}")
            logger.info("")
        
        # Test network recommendations
        recommendations = network_monitor.get_network_recommendations()
        logger.info("🎯 Network Recommendations:")
        for rec in recommendations:
            logger.info(f"   {rec}")
        logger.info("")
        
        # Test network summary
        summary = network_monitor.get_network_summary()
        logger.info("📈 Network Summary:")
        logger.info(f"   Status: {summary['current_status']}")
        logger.info(f"   Health Score: {summary['current_health_score']:.2f}")
        logger.info(f"   Trend: {summary['recent_trend']}")
        logger.info(f"   Last Updated: {summary['last_updated']}")
        logger.info("")
        
        logger.info("✅ Network Monitoring test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Network Monitoring test failed: {e}")
        return False

async def test_integration():
    """Test integration of both systems"""
    logger.info("🧪 Testing Integration of Dynamic Gas and Network Monitoring")
    
    try:
        # Initialize Web3 connection
        w3 = Web3(Web3.HTTPProvider(os.getenv('ARBITRUM_RPC')))
        if not w3.is_connected():
            logger.error("❌ Failed to connect to Arbitrum network")
            return False
        
        logger.info(f"✅ Connected to Arbitrum network: {w3.is_connected()}")
        
        # Initialize both monitors
        gas_monitor = DynamicGasMonitor(w3, "arbitrum")
        network_monitor = NetworkMonitor(w3, "arbitrum")
        
        # Simulate opportunity validation
        logger.info("🎯 Testing opportunity validation with integrated systems...")
        
        # Create mock opportunity
        class MockOpportunity:
            def __init__(self):
                self.estimated_profit_usd = 1000.0  # $1000 profit
                self.confidence_score = 0.85
                self.liquidity_usd = 100000.0  # $100K liquidity
        
        opportunity = MockOpportunity()
        
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
        
        # Calculate cost vs profit analysis
        gas_cost_usd = optimal_gas['base_gas_price'] / 1e18 * 21000  # Assume 21k gas
        profit_ratio = opportunity.estimated_profit_usd / gas_cost_usd if gas_cost_usd > 0 else float('inf')
        
        logger.info(f"💰 Cost Analysis:")
        logger.info(f"   Gas Cost: ${gas_cost_usd:.2f}")
        logger.info(f"   Profit: ${opportunity.estimated_profit_usd:.2f}")
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

async def main():
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
            result = await test_func()
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
    success = asyncio.run(main())
    exit(0 if success else 1)