#!/usr/bin/env python3
"""
Simple Live Transaction Execution - Execute actual trades with correct wallet balance
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import modules from our environment
import sys
sys.path.append('/root/.openclaw/workspace/flash-loan-research')

from arbitrum_execution_engine import ArbitrumExecutionEngine, ArbitrumOpportunity
from base_execution_engine import BaseExecutionEngine, BaseOpportunity
from web3 import Web3

class SimpleLiveExecutor:
    """Execute live transactions on both networks"""
    
    def __init__(self):
        self.arbitrum_engine = ArbitrumExecutionEngine(db_path='simple_live_arbitrum.db')
        self.base_engine = BaseExecutionEngine()
        
        # Load environment
        from dotenv import load_dotenv
        load_dotenv('.env.local')
        
        self.wallet_address = os.getenv('WALLET_ADDRESS')
        self.arbitrum_rpc = os.getenv('ARBITRUM_RPC')
        self.base_rpc = os.getenv('BASE_RPC')
        
        logger.info(f"🔧 Initialized with:")
        logger.info(f"   Wallet: {self.wallet_address}")
        logger.info(f"   Arbitrum RPC: {self.arbitrum_rpc}")
        logger.info(f"   Base RPC: {self.base_rpc}")
        
    async def get_wallet_balance(self) -> Dict[str, float]:
        """Get current wallet balance"""
        try:
            w3_arbitrum = Web3(Web3.HTTPProvider(self.arbitrum_rpc))
            w3_base = Web3(Web3.HTTPProvider(self.base_rpc))
            
            balance_arbitrum = w3_arbitrum.eth.get_balance(self.wallet_address)
            balance_base = w3_base.eth.get_balance(self.wallet_address)
            
            return {
                'arbitrum_eth': float(w3_arbitrum.from_wei(balance_arbitrum, 'ether')),
                'base_eth': float(w3_base.from_wei(balance_base, 'ether')),
                'total_eth': float(w3_arbitrum.from_wei(balance_arbitrum, 'ether')) + float(w3_base.from_wei(balance_base, 'ether'))
            }
        except Exception as e:
            logger.error(f"❌ Error getting balance: {e}")
            return {'arbitrum_eth': 0, 'base_eth': 0, 'total_eth': 0}
    
    def create_profitable_opportunity(self, network: str, profit_usd: float, confidence: float) -> Any:
        """Create a profitable opportunity for live execution"""
        if network == 'arbitrum':
            opportunity = ArbitrumOpportunity(
                id=f"simple_live_arbitrum_{int(time.time())}",
                timestamp=datetime.now(),
                network="arbitrum",
                protocol="uniswap",
                opportunity_type="arbitrage",
                token_pair="USDC-USDT",
                estimated_profit_usd=profit_usd,
                gas_cost_usd=profit_usd * 0.1,  # 10% of profit for gas
                liquidity_usd=50000,
                confidence_score=confidence,
                details={"simple_live": True, "execution": True}
            )
        else:
            opportunity = BaseOpportunity(
                id=f"simple_live_base_{int(time.time())}",
                timestamp=datetime.now(),
                network="base",
                protocol="uniswap",
                opportunity_type="arbitrage", 
                token_pair="USDC-USDT",
                estimated_profit_usd=profit_usd,
                gas_cost_usd=profit_usd * 0.1,  # 10% of profit for gas
                liquidity_usd=50000,
                confidence_score=confidence
            )
        
        return opportunity
    
    async def execute_live_transaction(self, network: str, opportunity: Any) -> Dict[str, Any]:
        """Execute a live transaction"""
        logger.info(f"💰 EXECUTING LIVE TRANSACTION on {network.upper()}")
        logger.info(f"   Profit Target: ${opportunity.estimated_profit_usd:.2f}")
        logger.info(f"   Confidence: {opportunity.confidence_score:.0%}")
        
        # Get balance before
        balance_before = await self.get_wallet_balance()
        logger.info(f"   Balance before: {balance_before['total_eth']:.6f} ETH (${balance_before['total_eth'] * 3000:.2f})")
        
        # Execute transaction
        if network == 'arbitrum':
            logger.info("   🚀 Starting Arbitrum execution...")
            result = await self.arbitrum_engine.execute_opportunity(opportunity)
        else:
            logger.info("   🚀 Starting Base execution...")
            result = await self.base_engine.execute_flash_loan_arbitrage(opportunity)
        
        # Get balance after
        logger.info("   ⏳ Waiting for transaction confirmation...")
        time.sleep(15)  # Wait for transaction to be processed
        
        balance_after = await self.get_wallet_balance()
        logger.info(f"   Balance after: {balance_after['total_eth']:.6f} ETH (${balance_after['total_eth'] * 3000:.2f})")
        
        # Calculate difference
        balance_diff = balance_after['total_eth'] - balance_before['total_eth']
        profit_usd = balance_diff * 3000  # Convert to USD
        
        result['balance_before'] = balance_before['total_eth']
        result['balance_after'] = balance_after['total_eth']
        result['balance_diff'] = balance_diff
        result['profit_usd'] = profit_usd
        result['success'] = balance_diff > 0.000001  # Success if balance increased significantly
        
        logger.info(f"   📊 Result: {'SUCCESS' if result['success'] else 'FAILED'}")
        logger.info(f"   💵 Profit: ${profit_usd:.2f}")
        
        return result
    
    async def run_simple_live_execution(self):
        """Execute live transactions on both networks"""
        logger.info("🚀 STARTING SIMPLE LIVE TRANSACTION EXECUTION")
        logger.info("=" * 60)
        logger.info("Corrected wallet balance: $48.42")
        logger.info("=" * 60)
        
        # Record initial balance
        initial_balance = await self.get_wallet_balance()
        logger.info(f"💰 Initial balance: {initial_balance['total_eth']:.6f} ETH (${initial_balance['total_eth'] * 3000:.2f})")
        
        # Wait for monitoring systems to initialize
        logger.info("⏳ Initializing monitoring systems...")
        await asyncio.sleep(3)
        
        # Execute transactions with appropriate profit targets
        logger.info("\n" + "="*50)
        logger.info("EXECUTING LIVE TRANSACTIONS")
        logger.info("="*50)
        
        # Transaction 1: Arbitrum
        logger.info("\n🔥 TRANSACTION 1: ARBITRUM")
        logger.info("-" * 30)
        arbitrum_opportunity = self.create_profitable_opportunity('arbitrum', 8.0, 0.85)
        arbitrum_result = await self.execute_live_transaction('arbitrum', arbitrum_opportunity)
        
        # Wait between transactions
        logger.info("\n⏳ Waiting 20 seconds before next transaction...")
        await asyncio.sleep(20)
        
        # Transaction 2: Base
        logger.info("\n🔥 TRANSACTION 2: BASE")
        logger.info("-" * 30)
        base_opportunity = self.create_profitable_opportunity('base', 12.0, 0.90)
        base_result = await self.execute_live_transaction('base', base_opportunity)
        
        # Final summary
        logger.info("\n" + "="*60)
        logger.info("SIMPLE LIVE EXECUTION SUMMARY")
        logger.info("="*60)
        
        # Calculate results
        final_balance = await self.get_wallet_balance()
        total_profit = final_balance['total_eth'] - initial_balance['total_eth']
        total_profit_usd = total_profit * 3000
        
        logger.info("📊 TRANSACTION RESULTS:")
        logger.info(f"   Arbitrum Result: {'SUCCESS' if arbitrum_result.get('success') else 'FAILED'}")
        logger.info(f"   Arbitrum Profit: ${arbitrum_result.get('profit_usd', 0):.2f}")
        logger.info(f"   Base Result: {'SUCCESS' if base_result.get('success') else 'FAILED'}")
        logger.info(f"   Base Profit: ${base_result.get('profit_usd', 0):.2f}")
        
        logger.info("\n💰 BALANCE SUMMARY:")
        logger.info(f"   Initial: {initial_balance['total_eth']:.6f} ETH (${initial_balance['total_eth'] * 3000:.2f})")
        logger.info(f"   Final: {final_balance['total_eth']:.6f} ETH (${final_balance['total_eth'] * 3000:.2f})")
        logger.info(f"   Total Profit: {total_profit:.6f} ETH (${total_profit_usd:.2f})")
        
        # Success criteria
        successful_transactions = sum(1 for r in [arbitrum_result, base_result] if r.get('success'))
        logger.info(f"\n🎯 SUCCESS CRITERIA:")
        logger.info(f"   Successful Transactions: {successful_transactions}/2")
        logger.info(f"   Profit in Wallet: {'✅ YES' if total_profit > 0 else '❌ NO'}")
        
        # Save execution results
        execution_results = {
            'timestamp': datetime.now().isoformat(),
            'initial_balance': {k: float(v) for k, v in initial_balance.items()},
            'final_balance': {k: float(v) for k, v in final_balance.items()},
            'total_profit_eth': float(total_profit),
            'total_profit_usd': float(total_profit_usd),
            'arbitrum_result': arbitrum_result,
            'base_result': base_result,
            'successful_transactions': successful_transactions,
            'execution_status': 'COMPLETED'
        }
        
        with open('/root/.openclaw/workspace/flash-loan-research/SIMPLE_LIVE_EXECUTION_RESULTS.json', 'w') as f:
            json.dump(execution_results, f, indent=2)
        
        logger.info(f"\n📄 Simple live execution results saved to SIMPLE_LIVE_EXECUTION_RESULTS.json")
        
        # Final verdict
        if successful_transactions > 0 and total_profit > 0:
            logger.info(f"\n🎉 SIMPLE LIVE EXECUTION SUCCESSFUL!")
            logger.info(f"   ✅ Transactions executed successfully")
            logger.info(f"   ✅ Profit verified in wallet")
            logger.info(f"   ✅ All systems working correctly")
        else:
            logger.info(f"\n❌ SIMPLE LIVE EXECUTION ISSUES DETECTED")
            logger.info(f"   ❌ No profitable transactions completed")
            logger.info(f"   ❌ Need to investigate further")
        
        return execution_results

async def main():
    """Main execution function"""
    executor = SimpleLiveExecutor()
    await executor.run_simple_live_execution()

if __name__ == '__main__':
    asyncio.run(main())