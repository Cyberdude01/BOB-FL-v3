#!/usr/bin/env python3
"""
Simple connection test without complex dependencies
"""

import requests
import json
import logging
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_infura_connection():
    """Test Infura connection with basic endpoint"""
    infura_url = "https://mainnet.infura.io/v3/fef2edcc615944ca816d857741ef9d5d"
    
    try:
        # Simple test request
        response = requests.post(
            infura_url,
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                logger.info(f"✅ Infura connection successful - Block: {data['result']}")
                return True
            else:
                logger.error(f"❌ Infura response error: {data}")
                return False
        else:
            logger.error(f"❌ Infura HTTP error: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Infura connection failed: {e}")
        return False

def test_dune_connection():
    """Test Dune Analytics connection"""
    dune_url = "https://api.dune.com/api/v1/execute"
    headers = {
        "X-Dune-Api-Key": os.getenv("DUNE_API_KEY", ""),
        "Content-Type": "application/json"
    }
    
    try:
        # Simple test query
        payload = {
            "query_id": 123,  # Sample query ID
            "performance": "medium"
        }
        
        response = requests.post(dune_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Dune Analytics connection successful")
            return True
        else:
            logger.error(f"❌ Dune Analytics HTTP error: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Dune Analytics connection failed: {e}")
        return False

def test_websocket_connection():
    """Test WebSocket connection with corrected URL"""
    websocket_url = "wss://ws.coincap.io/prices?assets=ethereum"
    
    try:
        import websockets
        
        async def test_connection():
            async with websockets.connect(websocket_url, timeout=5) as websocket:
                # Send subscription message
                await websocket.send(json.dumps({"type": "subscribe", "payload": "prices"}))
                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                logger.info("✅ WebSocket connection successful")
                return True
        
        import asyncio
        return asyncio.run(test_connection())
        
    except Exception as e:
        logger.error(f"❌ WebSocket connection failed: {e}")
        return False

def main():
    """Run all connection tests"""
    logger.info("Starting simple connection tests...")
    
    results = {}
    
    # Test Infura
    logger.info("Testing Infura connection...")
    results['infura'] = test_infura_connection()
    
    # Test Dune Analytics
    logger.info("Testing Dune Analytics connection...")
    results['dune'] = test_dune_connection()
    
    # Test WebSocket
    logger.info("Testing WebSocket connection...")
    results['websocket'] = test_websocket_connection()
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("CONNECTION TEST SUMMARY")
    logger.info("="*50)
    
    passed = 0
    total = len(results)
    
    for test, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{test.upper()}: {status}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        logger.info("🎉 All connections working!")
    else:
        logger.warning("⚠️  Some connections need attention")

if __name__ == "__main__":
    main()