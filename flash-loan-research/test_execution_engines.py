#!/usr/bin/env python3
"""
Test all execution engines to validate functionality
"""

import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_opportunity_generation():
    """Test opportunity generation"""
    logger.info("🧪 Testing opportunity generation...")
    
    try:
        import sqlite3
        
        # Connect to database
        conn = sqlite3.connect('enhanced_flash_loan_research.db')
        cursor = conn.cursor()
        
        # Get latest opportunities
        cursor.execute("SELECT COUNT(*) FROM opportunities WHERE created_at > datetime('now', '-1 hour')")
        recent_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT network, protocol, estimated_profit_usd, confidence_score FROM opportunities ORDER BY created_at DESC LIMIT 5")
        recent_opps = cursor.fetchall()
        
        logger.info(f"✅ Recent opportunities: {recent_count}")
        logger.info("Top 5 opportunities:")
        for opp in recent_opps:
            logger.info(f"  - {opp[0]}: {opp[1]} - ${opp[2]:,.2f} ({opp[3]*100:.1f}% confidence)")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Opportunity generation test failed: {str(e)}")
        return False

def test_arbitrum_engine():
    """Test Arbitrum execution engine"""
    logger.info("🧪 Testing Arbitrum execution engine...")
    
    try:
        from arbitrum_execution_engine import ArbitrumExecutionEngine
        
        engine = ArbitrumExecutionEngine('./enhanced_flash_loan_research.db')
        
        # Get latest opportunities
        opportunities = engine.get_latest_opportunities(3)
        
        if not opportunities:
            logger.warning("No opportunities found for Arbitrum")
            return False
        
        # Test validation
        for opp in opportunities:
            valid, reason = engine.validate_opportunity(opp)
            if valid:
                logger.info(f"✅ Valid opportunity: {opp.id} - ${opp.estimated_profit_usd:.2f}")
            else:
                logger.warning(f"❌ Invalid opportunity: {opp.id} - {reason}")
        
        engine.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Arbitrum engine test failed: {str(e)}")
        return False

def test_base_engine():
    """Test Base execution engine"""
    logger.info("🧪 Testing Base execution engine...")
    
    try:
        from base_execution_engine import BaseExecutionEngine
        
        engine = BaseExecutionEngine()
        
        # Get latest opportunities
        opportunities = engine.get_latest_opportunities(3)
        
        if not opportunities:
            logger.warning("No opportunities found for Base")
            return False
        
        # Test validation
        for opp in opportunities:
            valid, reason = engine.validate_opportunity(opp)
            if valid:
                logger.info(f"✅ Valid opportunity: {opp.id} - ${opp.estimated_profit_usd:.2f}")
            else:
                logger.warning(f"❌ Invalid opportunity: {opp.id} - {reason}")
        
        engine.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Base engine test failed: {str(e)}")
        return False

def test_ethereum_engine():
    """Test Ethereum execution engine"""
    logger.info("🧪 Testing Ethereum execution engine...")
    
    try:
        from ethereum_execution_engine import EthereumExecutionEngine
        
        engine = EthereumExecutionEngine()
        
        # Get latest opportunities
        opportunities = engine.get_latest_opportunities(3)
        
        if not opportunities:
            logger.warning("No opportunities found for Ethereum")
            return False
        
        # Test validation
        for opp in opportunities:
            valid, reason = engine.validate_opportunity(opp)
            if valid:
                logger.info(f"✅ Valid opportunity: {opp.id} - ${opp.estimated_profit_usd:.2f}")
            else:
                logger.warning(f"❌ Invalid opportunity: {opp.id} - {reason}")
        
        engine.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Ethereum engine test failed: {str(e)}")
        return False

def test_database_connectivity():
    """Test database connectivity"""
    logger.info("🧪 Testing database connectivity...")
    
    try:
        import sqlite3
        
        conn = sqlite3.connect('enhanced_flash_loan_research.db')
        cursor = conn.cursor()
        
        # Check database schema
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        logger.info(f"✅ Database connected with {len(tables)} tables")
        for table in tables:
            logger.info(f"  - {table[0]}")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Database test failed: {str(e)}")
        return False

def test_environment_variables():
    """Test environment variables"""
    logger.info("🧪 Testing environment variables...")
    
    required_vars = [
        'PRIVATE_KEY',
        'WALLET_ADDRESS',
        'ARBITRUM_RPC',
        'BASE_RPC',
        'ETHEREUM_RPC'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing environment variables: {missing_vars}")
        return False
    
    logger.info("✅ All required environment variables set")
    return True

def main():
    """Run all tests"""
    logger.info("🚀 Starting execution engine tests...")
    logger.info("=" * 60)
    
    tests = [
        ("Environment Variables", test_environment_variables),
        ("Database Connectivity", test_database_connectivity),
        ("Opportunity Generation", test_opportunity_generation),
        ("Arbitrum Engine", test_arbitrum_engine),
        ("Base Engine", test_base_engine),
        ("Ethereum Engine", test_ethereum_engine)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Running {test_name}...")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"❌ Test {test_name} failed with exception: {str(e)}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} {test_name}")
        if result:
            passed += 1
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! System is ready for execution.")
        return True
    else:
        logger.warning(f"⚠️  {total - passed} tests failed. Please resolve issues before proceeding.")
        return False

if __name__ == "__main__":
    import os
    success = main()
    exit(0 if success else 1)