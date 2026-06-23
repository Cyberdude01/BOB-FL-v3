#!/usr/bin/env python3
"""
Flashloan Execution Script - Real Transaction Execution
This script properly loads environment variables and executes real flashloan transactions.
"""

import asyncio
import json
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables first
load_dotenv('.env.local')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('flashloan_execution.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from arbitrum_execution_engine import ArbitrumExecutionEngine, ArbitrumOpportunity
    print("✅ All imports successful")
except ImportError as e:
    logger.error(f"❌ Import failed: {e}")
    sys.exit(1)

async def test_wallet_connection():
    """Test wallet connectivity and balance"""
    try:
        from web3 import Web3
        
        w3 = Web3(Web3.HTTPProvider(os.getenv('ARBITRUM_RPC')))
        wallet_address = os.getenv('WALLET_ADDRESS')
        
        # Check balance
        balance = w3.eth.get_balance(wallet_address)
        eth_balance = w3.from_wei(balance, 'ether')
        
        logger.info(f"🔍 Wallet Address: {wallet_address}")
        logger.info(f"💰 ETH Balance: {eth_balance} ETH")
        
        if eth_balance < 0.01:  # Less than 0.01 ETH
            logger.warning("⚠️ Low ETH balance - transactions may fail")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Wallet connection test failed: {e}")
        return False

async def create_test_opportunity():
    """Create a test opportunity for execution"""
    return ArbitrumOpportunity(
        id=f"test_flashloan_{int(datetime.now().timestamp())}",
        timestamp=datetime.now(),
        estimated_profit_usd=1500.0,
        gas_cost_usd=75.0,
        liquidity_usd=100000.0,
        confidence_score=0.85,
        protocol="camelot",
        token_pair="WETH-USDC"
    )

async def execute_single_opportunity():
    """Execute a single flashloan opportunity"""
    try:
        logger.info("🚀 Starting Flashloan Execution")
        logger.info("=" * 50)
        
        # Initialize execution engine
        db_path = './enhanced_flash_loan_research.db'
        engine = ArbitrumExecutionEngine(db_path)
        logger.info("✅ Execution engine initialized")
        
        # Test wallet connection
        if not await test_wallet_connection():
            logger.error("❌ Wallet connection test failed - aborting execution")
            return False
        
        # Create test opportunity
        opportunity = await create_test_opportunity()
        logger.info(f"🎯 Created test opportunity: {opportunity.id}")
        logger.info(f"   Estimated Profit: ${opportunity.estimated_profit_usd:.2f}")
        logger.info(f"   Confidence: {opportunity.confidence_score:.2%}")
        logger.info(f"   Protocol: {opportunity.protocol}")
        
        # Validate opportunity
        is_valid, validation_message = engine.validate_opportunity(opportunity)
        if not is_valid:
            logger.error(f"❌ Opportunity validation failed: {validation_message}")
            return False
        
        logger.info("✅ Opportunity validation passed")
        
        # Execute opportunity
        logger.info("🔄 Executing opportunity...")
        result = await engine.execute_opportunity(opportunity)
        
        logger.info("📊 Execution Result:")
        logger.info(f"   Success: {result.get('success', False)}")
        logger.info(f"   Execution Time: {result.get('execution_time', 0):.2f}s")
        logger.info(f"   Opportunity ID: {result.get('opportunity_id', 'N/A')}")
        
        if result.get('success'):
            logger.info("🎉 Transaction executed successfully!")
            
            # Log transaction details if available
            if 'result' in result and 'results' in result['result']:
                for tx_result in result['result']['results']:
                    logger.info(f"   Transaction Hash: {tx_result.get('transaction_hash', 'N/A')}")
                    logger.info(f"   Success: {tx_result.get('success', False)}")
        else:
            logger.error(f"❌ Execution failed: {result.get('error', 'Unknown error')}")
            logger.error(f"Full result: {json.dumps(result, indent=2, default=str)}")
        
        return result.get('success', False)
        
    except Exception as e:
        logger.error(f"❌ Execution failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main execution function"""
    logger.info("🔧 Flashloan Execution Script")
    logger.info("=" * 50)
    
    # Check environment variables
    required_env_vars = [
        'PRIVATE_KEY', 'WALLET_ADDRESS', 'ARBITRUM_RPC',
        'REAL_TRANSACTIONS_ENABLED', 'DRY_RUN_MODE'
    ]
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Missing required environment variables: {missing_vars}")
        return False
    
    logger.info("✅ All required environment variables are set")
    logger.info(f"REAL_TRANSACTIONS_ENABLED: {os.getenv('REAL_TRANSACTIONS_ENABLED')}")
    logger.info(f"DRY_RUN_MODE: {os.getenv('DRY_RUN_MODE')}")
    
    # Execute opportunity
    success = await execute_single_opportunity()
    
    if success:
        logger.info("🎯 Execution completed successfully!")
    else:
        logger.error("❌ Execution failed!")
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)