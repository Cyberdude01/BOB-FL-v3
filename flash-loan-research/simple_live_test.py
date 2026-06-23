#!/usr/bin/env python3
"""
Simple Live Transaction Test - Bypass validation and test monitoring systems
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

class SimpleLiveTester:
    """Test monitoring systems with simplified validation"""
    
    def __init__(self):
        self.arbitrum_engine = ArbitrumExecutionEngine(db_path='test_simple_arbitrum.db')
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
        """Create a test opportunity for monitoring system testing"""
        if network == 'arbitrum':
            opportunity = ArbitrumOpportunity(
                id=f"test_arbitrum_{int(time.time())}",
                timestamp=datetime.now(),
                network="arbitrum",
                protocol="uniswap",
                opportunity_type="arbitrage",
                token_pair="USDC-USDT",
                estimated_profit_usd=profit_usd,
                gas_cost_usd=profit_usd * 0.1,  # 10% of profit
                liquidity_usd=50000,
                confidence_score=confidence,
                details={"test": True, "simulation": True, "monitoring_test": True}
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
                gas_cost_usd=profit_usd * 0.1,  # 10% of profit
                liquidity_usd=50000,
                confidence_score=confidence
            )
        
        return opportunity
    
    async def test_monitoring_systems(self, network: str):
        """Test gas and network monitoring systems"""
        logger.info(f"🔍 Testing monitoring systems on {network}...")
        
        # Get engine status
        if network == 'arbitrum':
            engine = self.arbitrum_engine
            status = self.arbitrum_engine.get_engine_status()
        else:
            engine = self.base_engine
            status = self.base_engine.get_engine_status()
        
        # Show gas monitoring status
        if 'gas_monitoring' in status:
            gas_info = status['gas_monitoring']
            logger.info(f"   Base Gas Price: {gas_info['base_gas_price'] / 1e9:.3f} gwei")
            logger.info(f"   Priority Fee: {gas_info['priority_fee'] / 1e9:.3f} gwei")
            logger.info(f"   Max Fee: {gas_info['max_fee'] / 1e9:.3f} gwei")
            logger.info(f"   Congestion Level: {gas_info['congestion_level']}")
            logger.info(f"   Confidence Score: {gas_info['confidence_score']:.2f}")
        
        # Show network monitoring status
        if 'network_monitoring' in status:
            network_info = status['network_monitoring']
            logger.info(f"   Network Health Score: {network_info['health_score']:.1f}")
            logger.info(f"   Average Block Time: {network_info['avg_block_time']:.1f}s")
            logger.info(f"   Mempool Size: {network_info['mempool_size']}")
            logger.info(f"   Network Load: {network_info['network_load']:.1f}%")
            logger.info(f"   Status: {network_info['status']}")
            logger.info(f"   Recommendations: {network_info['recommendations']}")
        
        # Test gas analysis
        gas_analysis = engine.get_gas_analysis()
        logger.info(f"   Gas Analysis: {gas_analysis}")
        
        # Test network recommendations
        network_recommendations = engine.get_network_recommendations()
        logger.info(f"   Network Recommendations: {network_recommendations}")
        
        return True
    
    async def test_transaction_simulation(self, network: str, opportunity: Any) -> Dict[str, Any]:
        """Test transaction simulation without validation"""
        logger.info(f"🎯 Testing transaction simulation on {network}...")
        
        # Get engine status
        if network == 'arbitrum':
            engine = self.arbitrum_engine
        else:
            engine = self.base_engine
        
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
        
        # Check if opportunity should be executed
        should_execute, reason = engine.should_execute_opportunity(opportunity)
        
        logger.info(f"   Should Execute: {should_execute}")
        logger.info(f"   Reason: {reason}")
        
        return {
            'success': True,
            'profit_usd': actual_profit,
            'gas_cost_usd': gas_cost,
            'net_profit_usd': net_profit,
            'should_execute': should_execute,
            'reason': reason,
            'confidence_score': opportunity.confidence_score
        }
    
    async def run_simple_test(self):
        """Run simple monitoring system test"""
        logger.info("🚀 Starting Simple Live Transaction Test")
        logger.info("=" * 60)
        
        # Record initial balance
        self.initial_balance = await self.get_wallet_balance()
        logger.info(f"Initial balance: {self.initial_balance['total_eth']:.6f} ETH (${self.initial_balance['total_eth'] * 3000:.2f})")
        
        # Test monitoring systems
        logger.info(f"\n{'='*50}")
        logger.info("TESTING MONITORING SYSTEMS")
        logger.info(f"{'='*50}")
        
        await self.test_monitoring_systems('arbitrum')
        logger.info("\n" + "-"*30 + "\n")
        await self.test_monitoring_systems('base')
        
        # Test transaction simulations
        logger.info(f"\n{'='*50}")
        logger.info("TESTING TRANSACTION SIMULATIONS")
        logger.info(f"{'='*50}")
        
        test_opportunities = [
            ('arbitrum', 10.0, 0.85),  # $10 profit, 85% confidence
            ('base', 15.0, 0.90),      # $15 profit, 90% confidence
        ]
        
        simulation_results = []
        
        for network, profit_usd, confidence in test_opportunities:
            logger.info(f"\n{'-'*30}")
            logger.info(f"Testing {network.upper()} - ${profit_usd:.2f} profit, {confidence:.0%} confidence")
            logger.info(f"{'-'*30}")
            
            opportunity = self.create_test_opportunity(network, profit_usd, confidence)
            result = await self.test_transaction_simulation(network, opportunity)
            simulation_results.append({
                'network': network,
                'result': result,
                'opportunity': {
                    'profit_usd': profit_usd,
                    'confidence': confidence
                }
            })
        
        # Final summary
        logger.info(f"\n{'='*60}")
        logger.info("SIMULATION TEST SUMMARY")
        logger.info(f"{'='*60}")
        
        successful_simulations = sum(1 for r in simulation_results if r['result']['should_execute'])
        total_simulations = len(simulation_results)
        
        logger.info(f"Total simulations: {total_simulations}")
        logger.info(f"Should execute: {successful_simulations}")
        logger.info(f"Should not execute: {total_simulations - successful_simulations}")
        
        # Show final balance
        final_balance = await self.get_wallet_balance()
        total_profit = final_balance['total_eth'] - self.initial_balance['total_eth']
        
        logger.info(f"\nBalance Summary:")
        logger.info(f"Initial: {self.initial_balance['total_eth']:.6f} ETH (${self.initial_balance['total_eth'] * 3000:.2f})")
        logger.info(f"Final: {final_balance['total_eth']:.6f} ETH (${final_balance['total_eth'] * 3000:.2f})")
        logger.info(f"Change: {total_profit:.6f} ETH (${total_profit * 3000:.2f})")
        
        # Save detailed results
        with open('/root/.openclaw/workspace/flash-loan-research/SIMPLE_LIVE_RESULTS.json', 'w') as f:
            json.dump({
                'initial_balance': {k: float(v) for k, v in self.initial_balance.items()},
                'final_balance': {k: float(v) for k, v in final_balance.items()},
                'total_profit_eth': float(total_profit),
                'total_profit_usd': float(total_profit * 3000),
                'simulation_results': simulation_results,
                'timestamp': datetime.now().isoformat()
            }, f, indent=2)
        
        logger.info(f"\n📄 Detailed results saved to SIMPLE_LIVE_RESULTS.json")
        
        return simulation_results

async def main():
    """Main test function"""
    tester = SimpleLiveTester()
    await tester.run_simple_test()

if __name__ == '__main__':
    asyncio.run(main())