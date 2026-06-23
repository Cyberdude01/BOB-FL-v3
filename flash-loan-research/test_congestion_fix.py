#!/usr/bin/env python3
"""
Test congestion fix on Arbitrum
"""

import asyncio
import json
import logging
import random
import time
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import modules from our environment
import sys
sys.path.append('/root/.openclaw/workspace/flash-loan-research')

from arbitrum_execution_engine import ArbitrumExecutionEngine, ArbitrumOpportunity

class CongestionFixTest:
    """Test congestion fix"""
    
    def __init__(self):
        self.engine = ArbitrumExecutionEngine(db_path='test_fix.db')
        logger.info(f"🧪 CONGESTION FIX TEST INITIALIZED")
        
    def create_test_opportunity(self) -> ArbitrumOpportunity:
        """Create test opportunity"""
        return ArbitrumOpportunity(
            id=f"test_fix_{int(time.time())}",
            timestamp=datetime.now(),
            network="arbitrum",
            protocol="uniswap",
            opportunity_type="flash_loan",
            token_pair="USDC-USDT",
            estimated_profit_usd=random.uniform(10.0, 25.0),
            gas_cost_usd=1.0,
            liquidity_usd=50000,
            confidence_score=0.98,
            details={"test": True, "congestion_fix": True}
        )
    
    async def test_congestion_fix(self):
        """Test congestion fix"""
        logger.info("🔧 TESTING CONGESTION FIX")
        logger.info("=" * 50)
        
        # Create test opportunity
        opportunity = self.create_test_opportunity()
        
        logger.info(f"📊 Test Opportunity Details:")
        logger.info(f"   ID: {opportunity.id}")
        logger.info(f"   Profit Target: ${opportunity.estimated_profit_usd:.2f}")
        logger.info(f"   Confidence: {opportunity.confidence_score:.0%}")
        
        try:
            logger.info("🚀 Starting test execution with congestion fix...")
            result = await self.engine.execute_opportunity(opportunity)
            
            if result.get('success'):
                logger.info("✅ CONGESTION FIX SUCCESSFUL!")
                logger.info(f"   Result: {result}")
                return True
            else:
                logger.info("❌ Still failing, but error might be different now")
                logger.info(f"   Result: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Test failed with error: {e}")
            return False

async def main():
    """Test congestion fix"""
    test = CongestionFixTest()
    success = await test.test_congestion_fix()
    
    if success:
        logger.info("\n🎉 CONGESTION FIX TEST PASSED!")
    else:
        logger.info("\n❌ CONGESTION FIX TEST FAILED - Need further investigation")

if __name__ == '__main__':
    asyncio.run(main())