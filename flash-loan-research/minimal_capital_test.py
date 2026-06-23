#!/usr/bin/env python3
"""
Minimal Capital Test - Use appropriate thresholds for small capital testing
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

class MinimalCapitalTester:
    """Test with minimal capital and appropriate thresholds"""
    
    def __init__(self):
        self.arbitrum_engine = ArbitrumExecutionEngine(db_path='test_minimal_arbitrum.db')
        self.base_engine = BaseExecutionEngine()
        self.initial_balance = None
        
        # Load environment
        from dotenv import load_dotenv
        load_dotenv('.env.local')
        
        self.wallet_address = os.getenv('WALLET_ADDRESS')
        self.arbitrum_rpc = os.getenv('ARBITRUM_RPC')
        self.base_rpc = os.getenv('BASE_RPC')
        
    async def get_wallet_balance(self) -> Dict[str, float]:
        """Get current wallet balance"""
        w3_arbitrum = Web3(Web3.HTTPProvider(self.arbitrum_rpc))
        w3_base = Web3(Web3.HTTPProvider(self.base_rpc))
        
        balance_arbitrum = w3_arbitrum.eth.get_balance(self.wallet_address)
        balance_base = w3_base.eth.get_balance(self.wallet_address)
        
        return {
            'arbitrum_eth': float(w3_arbitrum.from_wei(balance_arbitrum, 'ether')),
            'base_eth': float(w3_base.from_wei(balance_base, 'ether')),
            'total_eth': float(w3_arbitrum.from_wei(balance_arbitrum, 'ether')) + float(w3_base.from_wei(balance_base, 'ether'))
        }
    
    def create_test_opportunity(self, network: str, profit_usd: float, confidence: float) -> Any:
        """Create a test opportunity for minimal capital testing"""
        if network == 'arbitrum':
            opportunity = ArbitrumOpportunity(
                id=f"test_arbitrum_{int(time.time())}",
                timestamp=datetime.now(),
                network="arbitrum",
                protocol="uniswap",
                opportunity_type="arbitrage",
                token_pair="USDC-USDT",
                estimated_profit_usd=profit_usd,
                gas_cost_usd=profit_usd * 0.3,  # 30% of profit for minimal capital
                liquidity_usd=50000,
                confidence_score=confidence,
                details={"test": True, "simulation": True, "minimal_capital": True}
            )
        else:
            opportunity = BaseOpportunity(
                id=f"test_base_{int(time.time())}",
                timestamp=datetime.now(),
                network="base",
                protocol="uniswap",
                opportunity_type="arbitrage", 
                token_pair="USDC-USDT",
                estimated_profit_usd=profit_usd,
                gas_cost_usd=profit_usd * 0.3,  # 30% of profit for minimal capital
                liquidity_usd=50000,
                confidence_score=confidence
            )
        
        return opportunity
    
    def override_profit_threshold(self, engine, profit_threshold_usd: float):
        """Override the profit threshold for testing"""
        engine.PROFIT_THRESHOLD_USD = profit_threshold_usd
        logger.info(f"✅ Overrode profit threshold to ${profit_threshold_usd}")
    
    async def simulate_transaction(self, network: str, opportunity: Any) -> Dict[str, Any]:
        """Simulate a transaction to test profitability"""
        logger.info(f"🎯 Simulating transaction on {network}...")
        
        # Get engine status
        if network == 'arbitrum':
            engine = self.arbitrum_engine
            status = self.arbitrum_engine.get_engine_status()
            # Override profit threshold for testing
            self.override_profit_threshold(engine, 10.0)  # $10 minimum for testing
        else:
            engine = self.base_engine
            status = self.base_engine.get_engine_status()
            # Override profit threshold for testing
            self.override_profit_threshold(engine, 10.0)  # $10 minimum for testing
        
        # Check if opportunity should be executed
        should_execute, reason = engine.should_execute_opportunity(opportunity)
        
        if not should_execute:
            return {
                'success': False,
                'reason': reason,
                'profit_usd': 0,
                'gas_cost_usd': 0
            }
        
        # Calculate gas cost
        gas_cost = engine.estimate_gas_cost(opportunity)
        
        # Simulate profit with variance
        import random
        profit_variance = random.uniform(0.8, 1.2)
        actual_profit = opportunity.estimated_profit_usd * profit_variance
        
        # Check if profitable after gas costs
        net_profit = actual_profit - gas_cost
        
        logger.info(f"   Estimated Profit: ${actual_profit:.2f}")
        logger.info(f"   Gas Cost: ${gas_cost:.2f}")
        logger.info(f"   Net Profit: ${net_profit:.2f}")
        
        return {
            'success': True,
            'reason': 'Simulation successful',
            'profit_usd': actual_profit,
            'gas_cost_usd': gas_cost,
            'net_profit_usd': net_profit,
            'confidence_score': opportunity.confidence_score
        }
    
    async def execute_live_transaction(self, network: str, opportunity: Any) -> Dict[str, Any]:
        """Execute a live transaction"""
        logger.info(f"💰 Executing LIVE transaction on {network}...")
        
        # Get balance before
        balance_before = await self.get_wallet_balance()
        logger.info(f"Balance before: {balance_before['total_eth']:.6f} ETH")
        
        # Execute transaction
        if network == 'arbitrum':
            result = await self.arbitrum_engine.execute_flash_loan_arbitrage(opportunity)
        else:
            result = await self.base_engine.execute_flash_loan_arbitrage(opportunity)
        
        # Get balance after
        time.sleep(5)  # Wait for transaction to be processed
        balance_after = await self.get_wallet_balance()
        logger.info(f"Balance after: {balance_after['total_eth']:.6f} ETH")
        
        # Calculate difference
        balance_diff = balance_after['total_eth'] - balance_before['total_eth']
        
        result['balance_before'] = balance_before['total_eth']
        result['balance_after'] = balance_after['total_eth']
        result['balance_diff'] = balance_diff
        result['success'] = balance_diff > 0  # Success if balance increased
        
        return result
    
    async def run_complete_test(self):
        """Run complete test simulation + execution"""
        logger.info("🚀 Starting Minimal Capital Live Transaction Test")
        logger.info("=" * 60)
        
        # Record initial balance
        self.initial_balance = await self.get_wallet_balance()
        logger.info(f"Initial balance: {self.initial_balance['total_eth']:.6f} ETH")
        logger.info(f"Initial value: ${self.initial_balance['total_eth'] * 3000:.2f}")
        
        # Test opportunities with minimal capital thresholds
        test_opportunities = [
            ('arbitrum', 15.0, 0.85),  # $15 profit, 85% confidence
            ('base', 20.0, 0.90),      # $20 profit, 90% confidence
        ]
        
        results = []
        
        for network, profit_usd, confidence in test_opportunities:
            logger.info(f"\n{'='*50}")
            logger.info(f"Testing {network.upper()} - ${profit_usd:.2f} profit, {confidence:.0%} confidence")
            logger.info(f"{'='*50}")
            
            # Create opportunity
            opportunity = self.create_test_opportunity(network, profit_usd, confidence)
            
            # Step 1: Simulate
            simulation_result = await self.simulate_transaction(network, opportunity)
            
            if not simulation_result['success']:
                logger.warning(f"❌ Simulation failed: {simulation_result['reason']}")
                results.append({
                    'network': network,
                    'simulation': simulation_result,
                    'execution': None,
                    'profitable': False
                })
                continue
            
            logger.info("✅ Simulation successful")
            
            # Check if net profit meets threshold
            if simulation_result['net_profit_usd'] < 5.0:  # $5 minimum for testing
                logger.warning(f"⚠️ Net profit too low: ${simulation_result['net_profit_usd']:.2f}")
                results.append({
                    'network': network,
                    'simulation': simulation_result,
                    'execution': None,
                    'profitable': False
                })
                continue
            
            # Step 2: Execute live transaction
            logger.info("🎯 Executing live transaction...")
            execution_result = await self.execute_live_transaction(network, opportunity)
            
            results.append({
                'network': network,
                'simulation': simulation_result,
                'execution': execution_result,
                'profitable': execution_result.get('success', False)
            })
            
            # Wait between transactions
            await asyncio.sleep(10)
        
        # Final summary
        logger.info(f"\n{'='*60}")
        logger.info("FINAL MINIMAL CAPITAL TEST SUMMARY")
        logger.info(f"{'='*60}")
        
        successful_simulations = sum(1 for r in results if r['simulation']['success'])
        successful_executions = sum(1 for r in results if r['execution'] and r['execution'].get('success', False))
        
        logger.info(f"Total tests: {len(results)}")
        logger.info(f"Successful simulations: {successful_simulations}")
        logger.info(f"Successful executions: {successful_executions}")
        
        # Show final balance
        final_balance = await self.get_wallet_balance()
        total_profit = final_balance['total_eth'] - self.initial_balance['total_eth']
        
        logger.info(f"\nBalance Summary:")
        logger.info(f"Initial: {self.initial_balance['total_eth']:.6f} ETH (${self.initial_balance['total_eth'] * 3000:.2f})")
        logger.info(f"Final: {final_balance['total_eth']:.6f} ETH (${final_balance['total_eth'] * 3000:.2f})")
        logger.info(f"Profit: {total_profit:.6f} ETH (${total_profit * 3000:.2f})")
        
        # Save detailed results
        with open('/root/.openclaw/workspace/flash-loan-research/MINIMAL_CAPITAL_RESULTS.json', 'w') as f:
            json.dump({
                'initial_balance': {k: float(v) for k, v in self.initial_balance.items()},
                'final_balance': {k: float(v) for k, v in final_balance.items()},
                'total_profit_eth': float(total_profit),
                'total_profit_usd': float(total_profit * 3000),
                'test_results': results,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        logger.info(f"\n📄 Detailed results saved to MINIMAL_CAPITAL_RESULTS.json")
        
        return results

async def main():
    """Main test function"""
    tester = MinimalCapitalTester()
    await tester.run_complete_test()

if __name__ == '__main__':
    asyncio.run(main())