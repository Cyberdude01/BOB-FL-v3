#!/usr/bin/env python3
"""
Monitor Services Diagnostic Test
Check if monitor services are working and identify issues
"""

import asyncio
import sys
import os
from datetime import datetime
from web3 import Web3

# Add current directory to path
sys.path.append('.')

from gas_monitor import DynamicGasMonitor, GasMetrics
from network_monitor import NetworkMonitor, NetworkHealthMetrics

async def test_gas_monitor():
    """Test gas monitor functionality"""
    print("🔍 Testing Gas Monitor...")
    
    try:
        # Initialize
        arb_rpc = os.getenv('ARBITRUM_RPC')
        if not arb_rpc:
            print("❌ ARBITRUM_RPC not configured")
            return False
            
        w3_arb = Web3(Web3.HTTPProvider(arb_rpc))
        gas_monitor = DynamicGasMonitor(w3_arb, 'arbitrum')
        
        # Test basic functionality
        base_gas = w3_arb.eth.gas_price
        print(f"✅ Basic gas price: {base_gas/1e9:.3f} gwei")
        
        # Test monitoring (short run)
        print("⏳ Running gas monitoring for 15s...")
        monitor_task = asyncio.create_task(gas_monitor.start_monitoring(interval=5.0))
        
        # Wait for some data collection
        await asyncio.sleep(10)
        
        # Check results
        metrics = gas_monitor.get_current_gas_metrics()
        if metrics:
            print(f"✅ Gas monitor working: {metrics.base_gas_price/1e9:.3f} gwei")
            print(f"   Confidence: {metrics.confidence_score:.2f}")
            print(f"   Timestamp: {metrics.timestamp}")
            return True
        else:
            print("❌ Gas monitor not collecting data")
            return False
            
    except Exception as e:
        print(f"❌ Gas monitor test failed: {e}")
        return False

async def test_network_monitor():
    """Test network monitor functionality"""
    print("\n🌐 Testing Network Monitor...")
    
    try:
        # Initialize
        arb_rpc = os.getenv('ARBITRUM_RPC')
        w3_arb = Web3(Web3.HTTPProvider(arb_rpc))
        network_monitor = NetworkMonitor(w3_arb, 'arbitrum')
        
        # Test basic functionality
        latest_block = w3_arb.eth.get_block('latest')
        print(f"✅ Latest block: {latest_block.number}")
        
        # Test monitoring (short run)
        print("⏳ Running network monitoring for 15s...")
        monitor_task = asyncio.create_task(network_monitor.start_monitoring(interval=5.0))
        
        # Wait for some data collection
        await asyncio.sleep(10)
        
        # Check results
        metrics = network_monitor.get_current_health_metrics()
        if metrics:
            print(f"✅ Network monitor working: {metrics.health_score}")
            print(f"   Block time: {metrics.avg_block_time:.2f}s")
            print(f"   Status: {metrics.status}")
            return True
        else:
            print("❌ Network monitor not collecting data")
            return False
            
    except Exception as e:
        print(f"❌ Network monitor test failed: {e}")
        return False

async def main():
    """Main diagnostic test"""
    print("🔧 Monitor Services Diagnostic Test")
    print("=" * 40)
    print(f"Start time: {datetime.now()}")
    
    # Test gas monitor
    gas_works = await test_gas_monitor()
    
    # Test network monitor
    network_works = await test_network_monitor()
    
    # Summary
    print(f"\n📊 DIAGNOSTIC SUMMARY:")
    print(f"Gas Monitor: {'✅ WORKING' if gas_works else '❌ NEEDS FIXING'}")
    print(f"Network Monitor: {'✅ WORKING' if network_works else '❌ NEEDS FIXING'}")
    
    if gas_works and network_works:
        print("\n🎉 All monitor services are working correctly!")
        print("🔄 No fixes needed - services operational")
    else:
        print("\n⚠️ Some monitor services need attention")
        print("🔧 Consider checking initialization and background processes")

if __name__ == "__main__":
    asyncio.run(main())
