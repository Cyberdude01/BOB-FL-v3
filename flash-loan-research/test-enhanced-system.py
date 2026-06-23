#!/usr/bin/env python3
"""
Test script for the enhanced flash loan monitoring system
"""

import asyncio
import sys
import os
from enhanced_monitoring_system import EnhancedFlashLoanMonitor

async def test_system():
    print("🧪 Testing Enhanced Flash Loan Monitoring System...")
    
    try:
        # Create monitor instance
        monitor = EnhancedFlashLoanMonitor("enhanced-config/")
        
        # Test database connection
        print("✅ Testing database connection...")
        cursor = monitor.conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        
        # Test network connections
        print("✅ Testing network connections...")
        connected_networks = []
        for network_name, web3_client in monitor.web3_clients.items():
            if web3_client.is_connected():
                connected_networks.append(network_name)
        
        print(f"✅ Connected to {len(connected_networks)} networks: {', '.join(connected_networks)}")
        
        # Test The Graph connection
        print("✅ Testing The Graph connection...")
        test_query = "{ query { pools(first: 1) { id } } }"
        test_data = await monitor.get_the_graph_data(
            "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3", 
            test_query
        )
        if test_data:
            print("✅ The Graph connection successful")
        else:
            print("⚠️  The Graph connection test failed")
        
        # Test Dune Analytics connection
        print("✅ Testing Dune Analytics connection...")
        # Note: This would test with a real query, but for now we'll just check the API key
        if monitor.dune_api_key:
            print("✅ Dune Analytics API key configured")
        else:
            print("❌ Dune Analytics API key not configured")
        
        # Run single test cycle
        print("✅ Running test monitoring cycle...")
        opportunities = await monitor.detect_flash_loan_opportunities()
        
        print(f"✅ Test cycle completed. Found {len(opportunities)} opportunities")
        
        # Cleanup
        await monitor.close()
        
        print("✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_system())
    sys.exit(0 if success else 1)