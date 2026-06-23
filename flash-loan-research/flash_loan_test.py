#!/usr/bin/env python3
"""
Flash Loan Opportunity Test
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

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from arbitrum_execution_engine import ArbitrumExecutionEngine, ArbitrumOpportunity
from web3 import Web3

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('flash_loan_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

async def test_flash_loan_opportunity():
    """Test flash loan opportunity with realistic parameters"""
    logger.info("🎯 Testing Flash Loan Opportunity")
    logger.info("=" * 50)
    
    try:
        # Initialize execution engine
        engine = ArbitrumExecutionEngine('./flash_loan_test.db')
        
        # Create realistic flash loan opportunity
        opportunity = ArbitrumOpportunity(
            id=f'profitable_flashloan_{int(datetime.now().timestamp())}',
            timestamp=datetime.now(),
            estimated_profit_usd=3500.0,  # High profit target
            gas_cost_usd=120.0,            # Realistic gas cost
            liquidity_usd=200000.0,         # Sufficient liquidity
            confidence_score=0.92,         # High confidence
            protocol='camelot',
            token_pair='WETH-USDC',
            details={
                "strategy": "cross_dex_arbitrage",
                "source_dex": "camelot",
                "target_dex": "uniswap_v3",
                "expected_profit_usd": 3650.0,
                "gas_estimate": 120000,
                "slippage_tolerance": 0.5,
                "deadline_minutes": 15,
                "tokens": ["WETH", "USDC"],
                "path": ["WETH", "USDC"],
                "expected_rates": {
                    "WETH_to_USDC": 3200.0,
                    "USDC_to_WETH": 0.0003125
                }
            }
        )
        
        logger.info("📊 Opportunity Details:")
        logger.info(f"   ID: {opportunity.id}")
        logger.info(f"   Estimated Profit: ${opportunity.estimated_profit_usd:,.2f}")
        logger.info(f"   Gas Cost: ${opportunity.gas_cost_usd:,.2f}")
        logger.info(f"   Net Profit: ${opportunity.estimated_profit_usd - opportunity.gas_cost_usd:,.2f}")
        logger.info(f"   Liquidity: ${opportunity.liquidity_usd:,.2f}")
        logger.info(f"   Confidence: {opportunity.confidence_score * 100:.1f}%")
        logger.info(f"   Protocol: {opportunity.protocol}")
        logger.info(f"   Token Pair: {opportunity.token_pair}")
        
        # Test 1: Opportunity Validation
        logger.info("\n🔍 Test 1: Opportunity Validation")
        is_valid, reason = engine.validate_opportunity(opportunity)
        
        if is_valid:
            logger.info(f"✅ Opportunity VALID: {reason}")
        else:
            logger.error(f"❌ Opportunity INVALID: {reason}")
            return False
        
        # Test 2: Transaction Generation
        logger.info("\n🔍 Test 2: Transaction Generation")
        transactions = await engine.generate_execution_transactions(opportunity)
        
        if transactions:
            logger.info(f"✅ Generated {len(transactions)} transactions:")
            for i, tx in enumerate(transactions):
                logger.info(f"   Transaction {i+1}:")
                logger.info(f"     To: {tx.get('to', 'N/A')}")
                logger.info(f"     Gas: {tx.get('gas', 'N/A')}")
                logger.info(f"     Nonce: {tx.get('nonce', 'N/A')}")
        else:
            logger.error("❌ No transactions generated")
            return False
        
        # Test 3: Transaction Execution
        logger.info("\n🔍 Test 3: Transaction Execution")
        result = await engine.execute_directly(transactions, opportunity)
        
        logger.info(f"Execution Result: {result}")
        
        if result.get('success'):
            logger.info("✅ EXECUTION SUCCESSFUL!")
            
            # Log success details
            if 'result' in result and 'results' in result['result']:
                for i, tx_result in enumerate(result['result']['results']):
                    logger.info(f"   Transaction {i+1} Hash: {tx_result.get('transaction_hash', 'N/A')}")
                    logger.info(f"   Transaction {i+1} Success: {tx_result.get('success', False)}")
            
            return True
        else:
            logger.error(f"❌ EXECUTION FAILED: {result.get('error', 'Unknown error')}")
            
            # Analyze failure reason
            error_msg = result.get('error', '')
            if 'gas' in error_msg.lower():
                logger.error("   Issue: Gas-related error")
            elif 'nonce' in error_msg.lower():
                logger.error("   Issue: Nonce conflict")
            elif 'balance' in error_msg.lower():
                logger.error("   Issue: Insufficient balance")
            else:
                logger.error("   Issue: Unknown error")
            
            return False
        
    except Exception as e:
        logger.error(f"❌ Flash loan test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def check_network_conditions():
    """Check current network conditions"""
    logger.info("🌐 Checking Network Conditions")
    logger.info("=" * 50)
    
    try:
        # Check Arbitrum
        w3_arb = Web3(Web3.HTTPProvider(os.getenv('ARBITRUM_RPC')))
        wallet_address = os.getenv('WALLET_ADDRESS')
        
        if w3_arb.is_connected():
            block_num = w3_arb.eth.block_number
            balance = w3_arb.from_wei(w3_arb.eth.get_balance(wallet_address), 'ether')
            gas_price = w3_arb.from_wei(w3_arb.eth.gas_price, 'gwei')
            
            logger.info(f"✅ Arbitrum:")
            logger.info(f"   Block: {block_num:,}")
            logger.info(f"   Wallet Balance: {balance} ETH")
            logger.info(f"   Gas Price: {gas_price} gwei")
            
            # Check if we can afford transactions
            estimated_gas_cost = 50000 * w3_arb.eth.gas_price  # 50k gas estimate
            eth_cost = w3_arb.from_wei(estimated_gas_cost, 'ether')
            can_afford = float(balance) > float(eth_cost) * 2  # 2x buffer
            
            logger.info(f"   Can afford transactions: {'✅' if can_afford else '❌'}")
            logger.info(f"   Estimated cost: {eth_cost} ETH")
            
        # Check Base
        w3_base = Web3(Web3.HTTPProvider(os.getenv('BASE_RPC')))
        
        if w3_base.is_connected():
            block_num = w3_base.eth.block_number
            gas_price = w3_base.from_wei(w3_base.eth.gas_price, 'gwei')
            
            logger.info(f"✅ Base:")
            logger.info(f"   Block: {block_num:,}")
            logger.info(f"   Gas Price: {gas_price} gwei")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Network check failed: {e}")
        return False

async def main():
    """Main function"""
    logger.info("🚀 Flash Loan Opportunity Test")
    logger.info("=" * 60)
    
    # Check network conditions first
    if not await check_network_conditions():
        logger.error("❌ Network conditions check failed")
        return 1
    
    # Test flash loan opportunity
    success = await test_flash_loan_opportunity()
    
    if success:
        logger.info("\n🎉 FLASH LOAN OPPORTUNITY TEST SUCCESSFUL!")
        logger.info("✅ System can identify and execute profitable flash loans")
        return 0
    else:
        logger.error("\n❌ FLASH LOAN OPPORTUNITY TEST FAILED")
        logger.info("🔧 System needs adjustments for profitable execution")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)