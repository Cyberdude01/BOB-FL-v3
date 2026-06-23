#!/usr/bin/env python3
"""
MEV Protection Integration System
Combines Flashbots, Eden Network, and Circuit Breaker for comprehensive MEV protection
"""

import asyncio
import json
import logging
import sqlite3
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from dotenv import load_dotenv
import os

# Import our MEV protection modules
from flashbots_executor import FlashbotsExecutor, MEVProtectionStrategies
from circuit_breaker import CircuitBreaker, MEVProtectionManager, ExecutionFailure

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MEVProtectionConfig:
    """MEV protection configuration"""
    preferred_provider: str = "flashbots"  # flashbots or eden
    fallback_provider: str = "eden"  # fallback if preferred fails
    gas_price_strategy: str = "priority_fee"  # priority_fee or gas_price
    bundle_timeout: int = 30  # seconds
    max_reorgs: int = 3
    enable_sandwich_protection: bool = True
    enable_bundle_optimization: bool = True
    network_specific_configs: Dict[str, Dict] = None

@dataclass
class TransactionBundle:
    """Transaction bundle for MEV protection"""
    id: str
    network: str
    transactions: List[Dict]
    estimated_profit: float
    gas_cost: float
    priority: str = "high"  # high, medium, low
    created_at: datetime = None

class MEVProtectionSystem:
    """Comprehensive MEV protection system"""
    
    def __init__(self, db_path: str, config: MEVProtectionConfig = None):
        self.db_path = db_path
        self.config = config or MEVProtectionConfig()
        
        # Initialize components
        self.flashbots_executor = FlashbotsExecutor()
        self.strategies = MEVProtectionStrategies(self.flashbots_executor)
        self.circuit_breaker = CircuitBreaker(db_path)
        self.protection_manager = MEVProtectionManager(db_path)
        
        # Setup database
        self.setup_database()
        
        # Performance metrics
        self.metrics = {
            "total_submissions": 0,
            "successful_submissions": 0,
            "failed_submissions": 0,
            "average_execution_time": 0.0,
            "provider_preference": {
                "flashbots": 0,
                "eden": 0
            }
        }
        
    def setup_database(self):
        """Setup database for MEV protection system"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create MEV protection transactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mev_protection_transactions (
                    id TEXT PRIMARY KEY,
                    network TEXT,
                    bundle_hash TEXT,
                    provider TEXT,
                    status TEXT,
                    transactions_count INTEGER,
                    total_gas_used INTEGER,
                    estimated_profit REAL,
                    actual_profit REAL,
                    execution_time REAL,
                    mev_protection_level TEXT,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create MEV performance metrics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mev_performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    metric_name TEXT,
                    metric_value REAL,
                    network TEXT,
                    provider TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create MEV strategy logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mev_strategy_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    network TEXT,
                    strategy TEXT,
                    description TEXT,
                    success BOOLEAN,
                    details TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("MEV protection database setup completed successfully")
            
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            raise
    
    async def submit_bundle_with_protection(self, bundle: TransactionBundle) -> Dict:
        """Submit transaction bundle with comprehensive MEV protection"""
        start_time = time.time()
        
        try:
            # Log strategy
            await self.log_strategy(
                bundle.network,
                "bundle_submission",
                f"Submitting {len(bundle.transactions)} transactions with MEV protection"
            )
            
            # Check circuit breaker
            if not self.circuit_breaker.should_execute(bundle.network):
                circuit_status = self.circuit_breaker.get_circuit_breaker_status(bundle.network)
                error_msg = f"Circuit breaker blocked execution for {bundle.network}"
                
                await self.log_strategy(
                    bundle.network,
                    "circuit_breaker_block",
                    error_msg
                )
                
                return {
                    "success": False,
                    "reason": error_msg,
                    "circuit_breaker_status": circuit_status,
                    "execution_time": time.time() - start_time
                }
            
            # Apply MEV protection strategies
            protected_transactions = await self.apply_protection_strategies(bundle)
            
            # Determine provider preference
            provider = self.config.preferred_provider
            fallback_provider = self.config.fallback_provider
            
            # Try preferred provider first
            result = None
            if provider == "flashbots":
                result = await self.flashbots_executor.execute_with_mev_protection(
                    self._create_opportunity_dict(bundle),
                    bundle.network,
                    protected_transactions
                )
                
                if result["success"]:
                    self.metrics["provider_preference"]["flashbots"] += 1
                else:
                    # Try fallback provider
                    logger.info(f"Flashbots failed, trying {fallback_provider} fallback")
                    if fallback_provider == "eden":
                        result = await self.strategies.create_bundle_optimization(
                            self._create_opportunity_dict(bundle),
                            bundle.network,
                            protected_transactions
                        )
                        self.metrics["provider_preference"]["eden"] += 1
            
            elif provider == "eden":
                result = await self.strategies.create_bundle_optimization(
                    self._create_opportunity_dict(bundle),
                    bundle.network,
                    protected_transactions
                )
                
                if result["success"]:
                    self.metrics["provider_preference"]["eden"] += 1
                else:
                    # Try fallback provider
                    logger.info(f"Eden failed, trying flashbots fallback")
                    result = await self.flashbots_executor.execute_with_mev_protection(
                        self._create_opportunity_dict(bundle),
                        bundle.network,
                        protected_transactions
                    )
                    self.metrics["provider_preference"]["flashbots"] += 1
            
            # Update metrics
            self.metrics["total_submissions"] += 1
            execution_time = time.time() - start_time
            
            if result["success"]:
                self.metrics["successful_submissions"] += 1
                self.circuit_breaker.register_success(bundle.network)
                
                # Log successful submission
                await self.log_mev_transaction(
                    bundle.id,
                    bundle.network,
                    result.get("bundle_hash", ""),
                    provider if result["success"] else fallback_provider,
                    "success",
                    len(protected_transactions),
                    result.get("gas_used", 0),
                    bundle.estimated_profit,
                    execution_time,
                    "high"
                )
                
                await self.log_strategy(
                    bundle.network,
                    "successful_submission",
                    f"Bundle submitted successfully via {provider if result['success'] else fallback_provider}"
                )
                
            else:
                self.metrics["failed_submissions"] += 1
                
                # Register failure
                failure = ExecutionFailure(
                    timestamp=datetime.now(),
                    network=bundle.network,
                    error_type="submission_error",
                    error_message=result.get("error", "Unknown error"),
                    opportunity_id=bundle.id
                )
                self.circuit_breaker.register_failure(bundle.network, failure)
                
                # Log failed submission
                await self.log_mev_transaction(
                    bundle.id,
                    bundle.network,
                    "",
                    provider if result.get("provider") else fallback_provider,
                    "failed",
                    len(protected_transactions),
                    0,
                    bundle.estimated_profit,
                    execution_time,
                    "high",
                    result.get("error")
                )
                
                await self.log_strategy(
                    bundle.network,
                    "failed_submission",
                    f"Bundle submission failed: {result.get('error', 'Unknown error')}"
                )
            
            # Update average execution time
            total_time = self.metrics["average_execution_time"] * (self.metrics["total_submissions"] - 1) + execution_time
            self.metrics["average_execution_time"] = total_time / self.metrics["total_submissions"]
            
            # Log performance metrics
            await self.log_performance_metric(
                "execution_time",
                execution_time,
                bundle.network,
                provider if result["success"] else fallback_provider
            )
            
            return {
                "success": result["success"],
                "result": result,
                "bundle_id": bundle.id,
                "network": bundle.network,
                "provider_used": provider if result["success"] else fallback_provider,
                "execution_time": execution_time,
                "circuit_breaker_status": self.circuit_breaker.get_circuit_breaker_status(bundle.network),
                "metrics": self.metrics
            }
            
        except Exception as e:
            error_msg = f"MEV protection submission failed: {str(e)}"
            logger.error(error_msg)
            
            # Register failure
            failure = ExecutionFailure(
                timestamp=datetime.now(),
                network=bundle.network,
                error_type="system_error",
                error_message=error_msg,
                opportunity_id=bundle.id
            )
            self.circuit_breaker.register_failure(bundle.network, failure)
            
            return {
                "success": False,
                "error": error_msg,
                "execution_time": time.time() - start_time,
                "circuit_breaker_status": self.circuit_breaker.get_circuit_breaker_status(bundle.network)
            }
    
    async def apply_protection_strategies(self, bundle: TransactionBundle) -> List[Dict]:
        """Apply MEV protection strategies to transactions"""
        protected_transactions = bundle.transactions.copy()
        
        try:
            # Apply sandwich attack protection if enabled
            if self.config.enable_sandwich_protection:
                sandwich_result = await self.strategies.create_sandwich_attack_protection(
                    self._create_opportunity_dict(bundle),
                    bundle.network
                )
                
                if sandwich_result["success"]:
                    # Add protective transactions
                    if "protective_transactions" in sandwich_result.get("result", {}):
                        protected_transactions.extend(sandwich_result["result"]["protective_transactions"])
                    
                    await self.log_strategy(
                        bundle.network,
                        "sandwich_protection",
                        "Sandwich attack protection applied"
                    )
                else:
                    logger.warning(f"Sandwich protection failed: {sandwich_result.get('error')}")
            
            # Apply bundle optimization if enabled
            if self.config.enable_bundle_optimization:
                protected_transactions = await self.strategies.create_bundle_optimization(
                    self._create_opportunity_dict(bundle),
                    bundle.network,
                    protected_transactions
                ).get("result", {}).get("optimized_transactions", protected_transactions)
                
                await self.log_strategy(
                    bundle.network,
                    "bundle_optimization",
                    "Bundle optimization applied"
                )
            
            return protected_transactions
            
        except Exception as e:
            logger.error(f"Error applying protection strategies: {e}")
            return protected_transactions
    
    def _create_opportunity_dict(self, bundle: TransactionBundle) -> Dict:
        """Create opportunity dictionary from bundle"""
        return {
            "id": bundle.id,
            "network": bundle.network,
            "estimated_profit_usd": bundle.estimated_profit,
            "gas_cost_usd": bundle.gas_cost,
            "token_pair": "MULTI",  # Multi-token opportunity
            "profit_percentage": (bundle.estimated_profit / bundle.gas_cost) * 100 if bundle.gas_cost > 0 else 0
        }
    
    async def log_mev_transaction(self, bundle_id: str, network: str, bundle_hash: str, 
                                provider: str, status: str, transactions_count: int,
                                gas_used: int, estimated_profit: float, execution_time: float,
                                protection_level: str, error_message: str = None):
        """Log MEV transaction to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO mev_protection_transactions 
                (id, network, bundle_hash, provider, status, transactions_count, 
                 total_gas_used, estimated_profit, actual_profit, execution_time, 
                 mev_protection_level, error_message, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                bundle_id,
                network,
                bundle_hash,
                provider,
                status,
                transactions_count,
                gas_used,
                estimated_profit,
                estimated_profit * 0.8,  # Estimated actual profit (20% fees)
                execution_time,
                protection_level,
                error_message,
                datetime.now()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error logging MEV transaction: {e}")
    
    async def log_strategy(self, network: str, strategy: str, description: str, success: bool = True):
        """Log strategy execution"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO mev_strategy_logs 
                (timestamp, network, strategy, description, success, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(),
                network,
                strategy,
                description,
                success,
                datetime.now()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error logging strategy: {e}")
    
    async def log_performance_metric(self, metric_name: str, value: float, network: str, provider: str):
        """Log performance metric"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO mev_performance_metrics 
                (timestamp, metric_name, metric_value, network, provider, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                datetime.now(),
                metric_name,
                value,
                network,
                provider,
                datetime.now()
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error logging performance metric: {e}")
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status"""
        return {
            "circuit_breaker_status": self.circuit_breaker.get_all_networks_status(),
            "performance_metrics": self.metrics,
            "protection_config": {
                "preferred_provider": self.config.preferred_provider,
                "fallback_provider": self.config.fallback_provider,
                "enable_sandwich_protection": self.config.enable_sandwich_protection,
                "enable_bundle_optimization": self.config.enable_bundle_optimization
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def get_network_protection_status(self, network: str) -> Dict:
        """Get protection status for specific network"""
        return {
            "circuit_breaker": self.circuit_breaker.get_circuit_breaker_status(network),
            "network": network,
            "timestamp": datetime.now().isoformat()
        }

async def main():
    """Main function to test MEV protection system"""
    db_path = '/root/.openclaw/workspace/flash-loan-research/enhanced_flash_loan_research.db'
    
    # Create MEV protection system
    config = MEVProtectionConfig(
        preferred_provider="flashbots",
        fallback_provider="eden",
        enable_sandwich_protection=True,
        enable_bundle_optimization=True,
        network_specific_configs={
            "ethereum": {
                "gas_price_strategy": "priority_fee",
                "max_reorgs": 2
            },
            "arbitrum": {
                "gas_price_strategy": "gas_price",
                "max_reorgs": 5
            }
        }
    )
    
    mev_system = MEVProtectionSystem(db_path, config)
    
    try:
        logger.info("Starting MEV protection system test...")
        
        # Test bundles
        test_bundles = [
            TransactionBundle(
                id="test_bundle_1",
                network="ethereum",
                transactions=[
                    {"type": "flash_loan", "amount": "100000"},
                    {"type": "swap", "amount": "100000"},
                    {"type": "repayment", "amount": "100000"}
                ],
                estimated_profit=500.0,
                gas_cost=50.0
            ),
            TransactionBundle(
                id="test_bundle_2", 
                network="arbitrum",
                transactions=[
                    {"type": "flash_loan", "amount": "50000"},
                    {"type": "swap", "amount": "50000"},
                    {"type": "repayment", "amount": "50000"}
                ],
                estimated_profit=300.0,
                gas_cost=30.0
            )
        ]
        
        # Submit test bundles
        for bundle in test_bundles:
            logger.info(f"Submitting bundle {bundle.id} for {bundle.network}")
            result = await mev_system.submit_bundle_with_protection(bundle)
            
            logger.info(f"Result for {bundle.id}:")
            logger.info(json.dumps(result, indent=2, default=str))
            
            # Wait between submissions
            await asyncio.sleep(2)
        
        # Get system status
        status = mev_system.get_system_status()
        logger.info("System status:")
        logger.info(json.dumps(status, indent=2, default=str))
        
    except Exception as e:
        logger.error(f"MEV protection test failed: {e}")
    
    finally:
        await mev_system.flashbots_executor.close_session()

if __name__ == "__main__":
    asyncio.run(main())