#!/usr/bin/env python3
"""
Base Execution Engine
Flash loan execution on Base network
"""

import asyncio
import json
import logging
import random
import time
import sqlite3
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from web3 import Web3
import hashlib
import aiohttp
from dotenv import load_dotenv
import os
from gas_monitor import DynamicGasMonitor, GasMetrics
from network_monitor import NetworkMonitor, NetworkHealthMetrics

# Load environment variables from local config
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class BaseOpportunity:
    """Base-specific opportunity data"""
    id: str
    timestamp: datetime
    network: str = "base"
    protocol: str = "uniswap"
    token_pair: str = "USDC-USDT"
    estimated_profit_usd: float = 0.0
    gas_cost_usd: float = 0.0
    liquidity_usd: float = 0.0
    confidence_score: float = 0.0
    opportunity_type: str = "arbitrage"
    dex_address: str = ""
    pool_address: str = ""
    steps: List[str] = None

    def __post_init__(self):
        if self.steps is None:
            self.steps = []

@dataclass
class BaseExecutionConfig:
    """Configuration for Base execution"""
    rpc_url: str = os.getenv('BASE_RPC', 'https://base-mainnet.infura.io/v3/fef2edcc615944ca816d857741ef9d5d')
    flash_loan_fee: float = 0.0009  # 0.09% typical flash loan fee
    max_gas_price_gwei: float = 50.0
    max_priority_fee_gwei: float = 2.0
    slippage_tolerance: float = 0.005  # 0.5%
    min_liquidity_usd: float = 50000.0

class BaseExecutionEngine:
    """Flash loan execution engine for Base network"""

    def __init__(self):
        self.config = BaseExecutionConfig()
        self.w3 = Web3(Web3.HTTPProvider(self.config.rpc_url))
        
        # Initialize dynamic gas monitor for Base network
        self.gas_monitor = DynamicGasMonitor(self.w3, "base")
        
        # Initialize network monitor for Base network
        self.network_monitor = NetworkMonitor(self.w3, "base")
        
        self.opportunities = []
        self.executions = []
        self.metrics = {
            'total_attempts': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_gas_cost': 0.0,
            'total_profit': 0.0,
            'average_execution_time': 0.0
        }
        
        # Start monitoring systems
        asyncio.create_task(self.start_monitoring())

        # Connect to database and ensure proper schema
        self.db_conn = sqlite3.connect('enhanced_flash_loan_research.db')
        self.cursor = self.db_conn.cursor()
        
        # Create database tables if they don't exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS executions (
                id TEXT PRIMARY KEY,
                opportunity_id TEXT,
                timestamp TEXT,  -- Added timestamp column
                success INTEGER,
                profit_usd REAL,
                gas_cost_usd REAL,
                error TEXT,
                confidence_score REAL,
                execution_time REAL,
                network TEXT,
                protocol TEXT,
                token_pair TEXT
            )
        """)
        self.db_conn.commit()

        logger.info("✅ Base Execution Engine initialized")
        logger.info(f"RPC: {self.config.rpc_url}")
        logger.info(f"Network: {self.w3.eth.chain_id}")

        # Verify connection
        if not self.w3.is_connected():
            raise Exception("Failed to connect to Base network")

        self.account = self.w3.eth.account.from_key(os.getenv('PRIVATE_KEY'))
        self.address = self.account.address

        logger.info(f"Wallet address: {self.address}")
        logger.info(f"Starting balance: {self.get_balance():.2f} ETH")

    def get_balance(self) -> float:
        """Get wallet balance in ETH"""
        balance = self.w3.eth.get_balance(self.address)
        return float(self.w3.from_wei(balance, 'ether'))

    def validate_opportunity(self, opportunity: BaseOpportunity) -> Tuple[bool, str]:
        """Validate opportunity for execution"""

        # Check confidence score
        if opportunity.confidence_score < 0.7:
            return False, "Confidence score too low"

        # Check estimated profit (reduced for minimal capital testing)
        if opportunity.estimated_profit_usd < 5:
            return False, "Estimated profit too low"

        # Check liquidity
        if opportunity.liquidity_usd < self.config.min_liquidity_usd:
            return False, "Insufficient liquidity"

        # Check gas cost
        estimated_gas_cost = self.estimate_gas_cost(opportunity)
        if estimated_gas_cost > opportunity.estimated_profit_usd * 0.1:
            return False, "Gas cost too high relative to profit"

        return True, "Opportunity valid"

    def estimate_gas_cost(self, opportunity: BaseOpportunity) -> float:
        """Estimate gas cost for the opportunity with dynamic pricing"""
        # Get optimal gas prices based on network conditions
        optimal_gas = self.gas_monitor.get_optimal_gas_price("high")
        
        # Check if network conditions are suitable
        should_send, reason = self.gas_monitor.should_send_transaction()
        if not should_send:
            logger.warning(f"⚠️ Gas cost estimation skipped: {reason}")
            return float('inf')  # Indicate that execution should not happen
        
        # Base gas estimation for different opportunity types
        base_gas = 21000  # Base transaction gas

        if opportunity.opportunity_type == "arbitrage":
            # DEX arbitrage typically requires 2-3 swaps
            gas_multiplier = 3
        elif opportunity.opportunity_type == "lending":
            # Lending protocol operations
            gas_multiplier = 4
        elif opportunity.opportunity_type == "cross_chain":
            # Cross-chain operations
            gas_multiplier = 5
        else:
            gas_multiplier = 2

        estimated_gas = base_gas * gas_multiplier
        
        # Use dynamic gas price
        gas_price_gwei = optimal_gas['base_gas_price'] / 1e9
        
        # Convert to USD (rough estimate)
        eth_price = 3000  # ETH price in USD
        gas_cost = (estimated_gas * gas_price_gwei) * eth_price
        
        logger.info(f"🎯 Dynamic gas cost - Base: {gas_price_gwei:.3f} gwei, Cost: ${gas_cost:.2f}")
        
        return gas_cost

    async def execute_flash_loan_arbitrage(self, opportunity: BaseOpportunity) -> Dict[str, Any]:
        """Execute flash loan arbitrage opportunity"""

        start_time = time.time()
        execution_id = f"base_exec_{int(time.time())}"

        try:
            logger.info(f"🚀 Starting execution: {execution_id}")
            logger.info(f"Opportunity: {opportunity.id} - ${opportunity.estimated_profit_usd:.2f}")

            # Update metrics
            self.metrics['total_attempts'] += 1

            # SAFETY: this engine previously simulated execution and returned random
            # "success" values. That is not a real flash-loan trade. Do not report
            # success unless a live on-chain transaction changes wallet balance.
            self.metrics['failed_executions'] += 1
            execution_result = {
                'id': execution_id,
                'opportunity_id': opportunity.id,
                'timestamp': datetime.now().isoformat(),
                'success': False,
                'profit_usd': 0,
                'gas_cost_usd': 0,
                'error': 'Base live execution not implemented: previous path was simulation-only. Requires atomic flash-loan contract + receipt/balance verification.',
                'confidence_score': opportunity.confidence_score,
                'execution_time': time.time() - start_time,
                'network': 'base',
                'protocol': opportunity.protocol,
                'token_pair': opportunity.token_pair,
                'simulated_only': True
            }

            logger.warning(f"❌ Base execution blocked: simulation-only path cannot count as success ({execution_id})")
            self.log_execution(execution_result)
            return execution_result

        except Exception as e:
            logger.error(f"❌ Execution error: {str(e)}")

            # Update metrics
            self.metrics['failed_executions'] += 1

            execution_result = {
                'id': execution_id,
                'opportunity_id': opportunity.id,
                'timestamp': datetime.now().isoformat(),
                'success': False,
                'profit_usd': 0,
                'gas_cost_usd': 0,
                'error': str(e),
                'execution_time': time.time() - start_time,
                'network': 'base',
                'protocol': opportunity.protocol,
                'token_pair': opportunity.token_pair
            }

            # Log error to database
            self.log_execution(execution_result)

            return execution_result

    def log_execution(self, execution_result: Dict[str, Any]):
        """Log execution result to database"""

        try:
            self.cursor.execute("""
                INSERT INTO executions (
                    id, opportunity_id, timestamp, success, profit_usd,
                    gas_cost_usd, error, confidence_score, execution_time,
                    network, protocol, token_pair
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                execution_result['id'],
                execution_result['opportunity_id'],
                execution_result['timestamp'],
                execution_result['success'],
                execution_result['profit_usd'],
                execution_result['gas_cost_usd'],
                execution_result.get('error', ''),
                execution_result['confidence_score'],
                execution_result['execution_time'],
                execution_result['network'],
                execution_result['protocol'],
                execution_result['token_pair']
            ))

            self.db_conn.commit()

        except Exception as e:
            logger.error(f"Failed to log execution: {str(e)}")

    def get_latest_opportunities(self, limit: int = 10) -> List[BaseOpportunity]:
        """Get latest opportunities from database"""

        try:
            self.cursor.execute("""
                SELECT id, network, protocol, opportunity_type, estimated_profit_usd,
                       gas_cost_usd, liquidity_usd, confidence_score, created_at,
                       token_pair, details
                FROM opportunities
                WHERE network = 'base'
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            opportunities = []
            for row in self.cursor.fetchall():
                opportunity = BaseOpportunity(
                    id=row[0],
                    network=row[1],
                    protocol=row[2],
                    opportunity_type=row[3],
                    estimated_profit_usd=row[4],
                    gas_cost_usd=row[5],
                    liquidity_usd=row[6],
                    confidence_score=row[7],
                    timestamp=datetime.fromisoformat(row[8]),
                    token_pair=row[9]
                )
                opportunities.append(opportunity)

            return opportunities

        except Exception as e:
            logger.error(f"Failed to get opportunities: {str(e)}")
            return []

    def get_metrics(self) -> Dict[str, Any]:
        """Get current execution metrics"""

        # Calculate average execution time
        if self.metrics['total_attempts'] > 0:
            self.metrics['average_execution_time'] = (
                sum(e['execution_time'] for e in self.executions[-100:]) /
                min(len(self.executions), 100)
            )

        return self.metrics

    def close(self):
        """Close database connection"""
        if self.db_conn:
            self.db_conn.close()

# Test function
    def get_engine_status(self) -> Dict:
        """Get engine status with dynamic gas and network monitoring"""
        status = {
            "network": "base",
            "config": {
                "max_gas_price_gwei": self.config.max_gas_price_gwei,
                "max_priority_fee_gwei": self.config.max_priority_fee_gwei,
                "min_liquidity_usd": self.config.min_liquidity_usd
            },
            "metrics": self.metrics,
            "timestamp": datetime.now().isoformat()
        }
        
        # Add dynamic gas monitoring status
        gas_metrics = self.gas_monitor.get_current_gas_metrics()
        if gas_metrics:
            status["gas_monitoring"] = {
                "base_gas_price": gas_metrics.base_gas_price,
                "priority_fee": gas_metrics.priority_fee,
                "max_fee": gas_metrics.max_fee,
                "congestion_level": self.gas_monitor.get_current_network_conditions().congestion_level if self.gas_monitor.get_current_network_conditions() else "unknown",
                "confidence_score": gas_metrics.confidence_score,
                "last_update": gas_metrics.timestamp.isoformat()
            }
        
        # Add network monitoring status
        network_metrics = self.network_monitor.get_current_health_metrics()
        if network_metrics:
            status["network_monitoring"] = {
                "health_score": network_metrics.health_score,
                "avg_block_time": network_metrics.avg_block_time,
                "mempool_size": network_metrics.mempool_size,
                "network_load": network_metrics.network_load,
                "status": network_metrics.status,
                "last_update": network_metrics.timestamp.isoformat(),
                "recommendations": self.network_monitor.get_network_recommendations()
            }
        
        return status
    
    async def start_monitoring(self):
        """Start dynamic gas and network monitoring"""
        logger.info("🔍 Starting monitoring systems for Base network")
        
        # Start gas monitoring
        gas_monitor_task = asyncio.create_task(
            self.gas_monitor.start_monitoring(interval=30.0)
        )
        
        # Start network monitoring
        network_monitor_task = asyncio.create_task(
            self.network_monitor.start_monitoring(interval=60.0)
        )
        
        # Wait for monitoring to start
        await asyncio.sleep(2)
        logger.info("✅ Monitoring systems started successfully for Base network")
        
        # Keep tasks running
        try:
            await asyncio.gather(gas_monitor_task, network_monitor_task)
        except asyncio.CancelledError:
            logger.info("🛑 Monitoring tasks cancelled")
    
    def get_network_recommendations(self) -> List[str]:
        """Get network recommendations"""
        return self.network_monitor.get_network_recommendations()
    
    def get_gas_analysis(self) -> Dict[str, Any]:
        """Get current gas analysis"""
        gas_metrics = self.gas_monitor.get_current_gas_metrics()
        if not gas_metrics:
            return {"error": "No gas data available"}
        
        return {
            "base_gas_price": gas_metrics.base_gas_price,
            "priority_fee": gas_metrics.priority_fee,
            "max_fee": gas_metrics.max_fee,
            "confidence_score": gas_metrics.confidence_score,
            "congestion_level": self.gas_monitor.get_current_network_conditions().congestion_level if self.gas_monitor.get_current_network_conditions() else "unknown",
            "trend_analysis": self.gas_monitor.get_historical_gas_trend(hours=1)
        }
    
    def should_execute_opportunity(self, opportunity: BaseOpportunity) -> Tuple[bool, str]:
        """Determine if opportunity should be executed based on network conditions"""
        # Check network health
        network_metrics = self.network_monitor.get_current_health_metrics()
        if network_metrics and network_metrics.health_score < 20:
            return False, "Network conditions critical - avoid execution"
        
        # Check gas cost vs profit
        gas_analysis = self.get_gas_analysis()
        if gas_analysis.get("base_gas_price", 0) > opportunity.estimated_profit_usd * 1e18:
            return False, "Gas cost exceeds profit potential"
        
        # Check opportunity validity
        is_valid, reason = self.validate_opportunity(opportunity)
        if not is_valid:
            return False, reason
        
        return True, "Opportunity suitable for execution"

def test_base_execution_engine():
    """Test the Base execution engine"""

    engine = BaseExecutionEngine()

    try:
        # Get latest opportunities
        opportunities = engine.get_latest_opportunities(5)

        if not opportunities:
            logger.warning("No opportunities found")
            return

        # Execute top opportunity
        top_opportunity = max(opportunities, key=lambda x: x.estimated_profit_usd)

        logger.info(f"Testing opportunity: {top_opportunity.id}")
        logger.info(f"Estimated profit: ${top_opportunity.estimated_profit_usd:.2f}")
        logger.info(f"Confidence score: {top_opportunity.confidence_score:.2f}")

        # Execute opportunity
        result = asyncio.run(engine.execute_flash_loan_arbitrage(top_opportunity))

        logger.info(f"Execution result: {result}")

        # Print metrics
        metrics = engine.get_metrics()
        logger.info(f"Current metrics: {metrics}")
    
    finally:
        engine.close()

    async def execute_opportunity(self, opportunity) -> Dict:
        """Execute opportunity on Base network"""
        try:
            # Create Base opportunity data structure
            from arbitrum_execution_engine import ArbitrumOpportunity
            real_opportunity = ArbitrumOpportunity(
                id=opportunity.id,
                timestamp=datetime.now(),
                network=opportunity.network,
                protocol=opportunity.protocol,
                token_pair=opportunity.token_pair,
                estimated_profit_usd=opportunity.estimated_profit_usd,
                liquidity_usd=opportunity.liquidity_usd,
                confidence_score=opportunity.confidence_score
            )
            
            # Execute flash loan arbitrage
            result = await self.execute_flash_loan_arbitrage(real_opportunity)
            return result
            
        except Exception as e:
            logger.error(f"Base execution failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

if __name__ == "__main__":
    test_base_execution_engine()