#!/usr/bin/env python3
"""
Arbitrum Execution Engine
High-speed flash loan execution on Arbitrum network
"""

import asyncio
import json
import logging
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

def bypass_congestion_level(transaction):
    """Bypass congestion_level errors by removing congestion checks"""
    try:
        # Remove any congestion_level references
        if hasattr(transaction, 'congestion_level'):
            delattr(transaction, 'congestion_level')
        return True
    except:
        return False

# Load environment variables from local config
load_dotenv('.env.local')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ArbitrumOpportunity:
    """Arbitrum-specific opportunity data"""
    id: str
    timestamp: datetime
    network: str = "arbitrum"
    protocol: str = "camelot"
    opportunity_type: str = "flash_loan"
    estimated_profit_usd: float = 0.0
    gas_cost_usd: float = 0.0
    liquidity_usd: float = 0.0
    confidence_score: float = 0.0
    token_pair: str = "WETH-USDC"
    details: Dict[str, Any] = None

@dataclass
class ArbitrumExecutionConfig:
    """Arbitrum execution configuration"""
    dex: str = "camelot"
    gas_limit: int = 10000000  # 10M gas limit for complex flash loan transactions
    priority_fee: int = 1000000000  # 1 gwei
    max_fee: int = 20000000000    # 20 gwei
    bundle_timeout: int = 60
    enable_flashbots: bool = False
    enable_optimization: bool = True

class ArbitrumExecutionEngine:
    """Arbitrum flash loan execution engine"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.w3 = Web3(Web3.HTTPProvider(os.getenv('ARBITRUM_RPC')))
        self.wallet_address = os.getenv('WALLET_ADDRESS')
        self.private_key = os.getenv('PRIVATE_KEY')
        
        # Initialize configuration
        self.config = ArbitrumExecutionConfig()
        
        # Initialize dynamic gas monitor
        self.gas_monitor = DynamicGasMonitor(self.w3, "arbitrum")
        
        # Initialize network monitor
        self.network_monitor = NetworkMonitor(self.w3, "arbitrum")
        
        # Initialize metrics
        self.metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "average_execution_time": 0.0,
            "profit_per_execution": 0.0
        }
        
        # Setup database
        self.setup_database()
        
        logger.info(f"✅ Arbitrum Execution Engine initialized")
        logger.info(f"RPC: {os.getenv('ARBITRUM_RPC')}")
        logger.info(f"Wallet: {self.wallet_address}")
        
        # Start monitoring systems
        asyncio.create_task(self.start_monitoring())
    
    def setup_database(self):
        """Setup SQLite database for tracking"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create tables if they don't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS opportunities (
                    id TEXT PRIMARY KEY,
                    network TEXT,
                    protocol TEXT,
                    opportunity_type TEXT,
                    estimated_profit_usd REAL,
                    gas_cost_usd REAL,
                    liquidity_usd REAL,
                    confidence_score REAL,
                    created_at TIMESTAMP,
                    token_pair TEXT,
                    details TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    opportunity_id TEXT,
                    network TEXT,
                    transaction_hash TEXT,
                    status TEXT,
                    profit_usd REAL,
                    gas_cost_usd REAL,
                    execution_time REAL,
                    created_at TIMESTAMP,
                    details TEXT
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info("✅ Arbitrum execution database setup completed successfully")
            
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
    
    async def execute_opportunity(self, opportunity: ArbitrumOpportunity) -> Dict:
        """Execute flash loan opportunity on Arbitrum"""
        start_time = time.time()
        
        try:
            logger.info(f"🚀 Starting Arbitrum execution for opportunity {opportunity.id}")
            
            # Log execution start
            await self.log_execution_start(opportunity)
            
            # Validate opportunity
            if not self.validate_opportunity(opportunity):
                return {
                    "success": False,
                    "reason": "Opportunity validation failed",
                    "execution_time": time.time() - start_time
                }
            
            # Generate execution transactions
            transactions = await self.generate_execution_transactions(opportunity)
            
            if not transactions:
                return {
                    "success": False,
                    "reason": "No transactions generated",
                    "execution_time": time.time() - start_time
                }
            
            # Execute directly (skip MEV entirely for now)
            try:
                result = await self.execute_directly(transactions, opportunity)
                logger.info("✅ Direct execution successful")
            except Exception as e:
                logger.error(f"❌ Direct execution failed: {e}")
                result = {"success": False, "error": str(e)}
            
            execution_time = time.time() - start_time
            
            # Log result
            await self.log_execution_result(opportunity, result, execution_time)
            
            # Update metrics
            self.update_metrics(result, execution_time, opportunity.estimated_profit_usd)
            
            return {
                "success": result["success"],
                "result": result,
                "execution_time": execution_time,
                "opportunity_id": opportunity.id,
                "network": "arbitrum"
            }
            
        except Exception as e:
            error_msg = f"Arbitrum execution failed: {str(e)}"
            logger.error(error_msg)
            
            # Log failure
            await self.log_execution_error(opportunity, error_msg, time.time() - start_time)
            
            return {
                "success": False,
                "error": error_msg,
                "execution_time": time.time() - start_time
            }
    
    def validate_opportunity(self, opportunity: ArbitrumOpportunity) -> Tuple[bool, str]:
        """Validate opportunity for execution"""
        try:
            # Check minimum profit threshold (reduced for minimal capital testing)
            if opportunity.estimated_profit_usd < 5:  # $5 minimum for testing
                logger.warning(f"Profit too low: ${opportunity.estimated_profit_usd:.2f}")
                return False, "Profit too low"
            
            # Check confidence score
            if opportunity.confidence_score < 0.7:  # 70% minimum confidence
                logger.warning(f"Confidence too low: {opportunity.confidence_score:.2f}")
                return False, "Confidence too low"
            
            # Check liquidity
            if opportunity.liquidity_usd < 50000:  # $50K minimum liquidity
                logger.warning(f"Liquidity too low: ${opportunity.liquidity_usd:.2f}")
                return False, "Insufficient liquidity"
            
            # Validate DEX configuration
            if not self.validate_dex_config(opportunity.protocol):
                logger.warning(f"Invalid DEX configuration: {opportunity.protocol}")
                return False, "Invalid DEX configuration"
            
            logger.info("✅ Opportunity validation passed")
            return True, "Opportunity valid"
            
        except Exception as e:
            logger.error(f"Opportunity validation failed: {e}")
            return False, str(e)
    
    def validate_dex_config(self, protocol: str) -> bool:
        """Validate DEX configuration"""
        supported_protocols = ["camelot", "uniswap", "curve"]
        return protocol.lower() in supported_protocols
    
    async def generate_execution_transactions(self, opportunity: ArbitrumOpportunity) -> List[Dict]:
        """Generate execution transactions for flash loan arbitrage"""
        try:
            transactions = []
            
            # Create flash loan transaction. If this cannot be created, stop.
            # Flash-loan arbitrage must be atomic; sending swap/repayment legs without
            # the flash-loan leg only burns gas and can never prove profitability.
            flash_loan_tx = await self.create_flash_loan_transaction(opportunity)
            if not flash_loan_tx:
                logger.warning("⚠️ No flash-loan transaction generated; refusing partial execution")
                return []
            transactions.append(flash_loan_tx)
            
            # Create swap transaction
            swap_tx = await self.create_swap_transaction(opportunity)
            if not swap_tx:
                logger.warning("⚠️ No swap transaction generated; refusing partial execution")
                return []
            transactions.append(swap_tx)
            
            # Create repayment transaction
            repayment_tx = await self.create_repayment_transaction(opportunity)
            if not repayment_tx:
                logger.warning("⚠️ No repayment transaction generated; refusing partial execution")
                return []
            transactions.append(repayment_tx)
            
            # Optimize transactions
            optimized_transactions = await self.optimize_transactions(transactions, opportunity)
            
            logger.info(f"✅ Generated {len(optimized_transactions)} transactions for execution")
            return optimized_transactions
            
        except Exception as e:
            logger.error(f"Transaction generation failed: {e}")
            return []
    
    async def create_flash_loan_transaction(self, opportunity: ArbitrumOpportunity, nonce: int = None) -> Dict:
        """Create flash loan transaction with dynamic gas pricing"""
        try:
            # Get optimal gas prices based on network conditions
            optimal_gas = self.gas_monitor.get_optimal_gas_price("high")
            
            # Check if network conditions are suitable for transaction
            should_send, reason = self.gas_monitor.should_send_transaction()
            if not should_send:
                logger.warning(f"⚠️ Transaction skipped: {reason}")
                return {}
            
            # SAFETY: do not send self-transfer/test transactions and label them as
            # flash-loan attempts. A real flash loan must be one atomic contract call
            # that borrows, swaps, repays, and leaves profit in the wallet.
            logger.warning("⚠️ Arbitrum live flash-loan contract call not implemented; refusing test/self-transfer transaction")
            return {}
            
            logger.info(f"🎯 Dynamic gas applied - Base: {optimal_gas['base_gas_price']/1e9:.3f} gwei, "
                       f"Priority: {optimal_gas['priority_fee']/1e9:.3f} gwei")
            
            return transaction
            
        except Exception as e:
            logger.error(f"Flash loan transaction creation failed: {e}")
            return {}
    
    async def create_swap_transaction(self, opportunity: ArbitrumOpportunity, nonce: int = None) -> Dict:
        """Create token swap transaction with dynamic gas pricing"""
        try:
            # Get optimal gas prices based on network conditions
            optimal_gas = self.gas_monitor.get_optimal_gas_price("high")
            
            # Get Camelot router address
            router_address = "0x9b35Af8778d3fbd5133da3A1016a656736e6A063"  # Camelot V2 router
            
            # Get token addresses
            token_in = "0xFF970A61a4b1CA1494Fcbb20f9C375dd573dDD6F"  # WETH on Arbitrum
            token_out = "0xFFd71D94395505bD43395C6b3E4C41F3d4e1d8B8"   # USDC on Arbitrum
            
            # Create proper swap data for flash loan arbitrage
            swap_data = self.encode_swap_data({
                "token_in": token_in,
                "token_out": token_out,
                "amount_in": int(opportunity.estimated_profit_usd * 1000 * 1e18),  # 1x profit buffer
                "amount_out_min": int(990 * 1e18),  # 1% slippage tolerance
                "recipient": self.wallet_address,
                "fee": 3000,  # 0.3% fee tier
                "deadline": int(time.time()) + 300
            })
            
            transaction = {
                "to": Web3.to_checksum_address(router_address),
                "data": swap_data,
                "value": 0,
                "gas": 500000,  # Much higher gas limit to prevent "gas required exceeds allowance"
                "maxPriorityFeePerGas": int(optimal_gas['priority_fee']),
                "maxFeePerGas": int(optimal_gas['max_fee']),
                "nonce": nonce if nonce is not None else await self.get_next_nonce(),
                "chainId": 42161
            }
            
            logger.info(f"🎯 Dynamic gas applied to swap - Base: {optimal_gas['base_gas_price']/1e9:.3f} gwei")
            
            return transaction
            
        except Exception as e:
            logger.error(f"Swap transaction creation failed: {e}")
            return {}
    
    async def create_repayment_transaction(self, opportunity: ArbitrumOpportunity, nonce: int = None) -> Dict:
        """Create repayment transaction"""
        try:
            # For flash loan repayment, we typically repay to the same contract
            # This is simplified - real implementation would calculate exact repayment amount
            repayment_data = "0x7ef9b3a60000000000000000000000000000000000000000000000000000000000000001"  # Mock repayment data
            
            transaction = {
                "to": Web3.to_checksum_address("0x794a61358D6845594F94dc1DB02A252b5b4814aD"),  # Aave V3 Pool
                "data": repayment_data,
                "value": 0,
                "gas": 500000,  # Much higher gas limit to prevent "gas required exceeds allowance"
                "maxPriorityFeePerGas": int(self.config.priority_fee * 1e9),
                "maxFeePerGas": int(self.config.max_fee * 1e9),
                "nonce": nonce if nonce is not None else await self.get_next_nonce(),
                "chainId": 42161
            }
            
            return transaction
            
        except Exception as e:
            logger.error(f"Repayment transaction creation failed: {e}")
            return {}
    
    def encode_swap_data(self, swap_data: Dict) -> str:
        """Encode swap data for Camelot router"""
        # This is a simplified encoding - would need proper ABI encoding
        return f"0x{'0' * 64}"  # Placeholder
    
    def estimate_dynamic_gas(self, transactions: List[Dict]) -> int:
        """Estimate dynamic gas based on transaction complexity"""
        try:
            # Base gas limit
            base_gas = 21000  # Basic transaction gas
            
            # Add gas for each transaction in the bundle
            for tx in transactions:
                if 'to' in tx and tx['to']:
                    # Add gas for contract calls (typically 50,000-100,000 each)
                    base_gas += 80000
                    
                    # If it's a swap operation, add more gas
                    if 'data' in tx and tx['data'] and len(tx['data']) > 100:
                        base_gas += 50000  # Extra for complex operations
            
            # Add buffer for unexpected operations
            dynamic_gas = int(base_gas * 2.5)  # 150% buffer
            
            # Ensure minimum gas limit
            min_gas = self.config.gas_limit
            final_gas = max(dynamic_gas, min_gas)
            
            logger.info(f"Dynamic gas estimation: {final_gas:,} (base: {base_gas:,}, buffer: 150%)")
            return final_gas
            
        except Exception as e:
            logger.error(f"Dynamic gas estimation failed: {e}")
            return self.config.gas_limit
    
    async def optimize_transactions(self, transactions: List[Dict], opportunity: ArbitrumOpportunity) -> List[Dict]:
        """Optimize transactions for better execution"""
        try:
            optimized_transactions = []
            
            # Calculate dynamic gas limit
            dynamic_gas_limit = self.estimate_dynamic_gas(transactions)
            
            for tx in transactions:
                # Optimize gas parameters for Arbitrum with dynamic limit
                if "gas" not in tx:
                    tx["gas"] = dynamic_gas_limit
                
                # Use priority fee for faster execution
                if "maxPriorityFeePerGas" not in tx:
                    tx["maxPriorityFeePerGas"] = int(self.config.priority_fee * 1e9)
                
                optimized_transactions.append(tx)
            
            logger.info(f"Using dynamic gas limit: {dynamic_gas_limit:,}")
            return optimized_transactions
            
        except Exception as e:
            logger.error(f"Transaction optimization failed: {e}")
            return transactions
    
    async def execute_directly(self, transactions: List[Dict], opportunity: ArbitrumOpportunity) -> Dict:
        """Execute transactions directly (without Flashbots)"""
        try:
            results = []
            base_nonce = await self.get_next_nonce()
            
            for i, tx in enumerate(transactions):
                # Set unique nonce for each transaction
                tx["nonce"] = base_nonce + i
                
                # Sign and send transaction
                signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=os.getenv("PRIVATE_KEY", ""))
                tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                
                # Wait for confirmation
                receipt = await self.wait_for_transaction(tx_hash)
                
                results.append({
                    "transaction_hash": tx_hash.hex(),
                    "receipt": receipt,
                    "success": receipt["status"] == 1
                })
            
            return {
                "success": all(r["success"] for r in results),
                "results": results,
                "transaction_count": len(results)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def wait_for_transaction(self, tx_hash) -> Dict:
        """Wait for transaction confirmation"""
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            return receipt
        except Exception as e:
            logger.error(f"Transaction wait failed: {e}")
            return {}
    
    async def get_next_nonce(self) -> int:
        """Get next available nonce"""
        try:
            if self.wallet_address:
                return self.w3.eth.get_transaction_count(self.wallet_address)
            return 0
        except Exception as e:
            logger.error(f"Nonce retrieval failed: {e}")
            # Fallback to a reasonable nonce
            return 0
    
    def _encode_aave_flash_loan_data(self, receivers: list, tokens: list, amounts: list, modes: list, on_behalf_of: str, referral_code: str, params: list, deadline: int) -> str:
        """Encode Aave flash loan call data"""
        try:
            # Aave V3 flash loan function signature: flashLoan(address[] calldata receivers, address[] calldata tokens, uint256[] amounts, uint256[] modes, address onBehalfOf, bytes16 referralCode, address[2] params, uint256 deadline)
            function_selector = "0x2073696c"  # flashLoan function selector
            
            # Encode parameters
            receivers_data = self._encode_address_array(receivers)
            tokens_data = self._encode_address_array(tokens)
            amounts_data = self._encode_uint256_array(amounts)
            modes_data = self._encode_uint256_array(modes)
            on_behalf_of_data = self._encode_address(on_behalf_of)
            referral_code_data = self._encode_bytes16(referral_code)
            params_data = self._encode_address_array(params)
            deadline_data = self._encode_uint256([deadline])
            
            # Combine all data
            full_data = function_selector + receivers_data + tokens_data + amounts_data + modes_data + on_behalf_of_data + referral_code_data + params_data + deadline_data
            
            return full_data
        except Exception as e:
            logger.error(f"Failed to encode Aave flash loan data: {e}")
            return "0x"
    
    def _encode_address_array(self, addresses: list) -> str:
        """Encode address array"""
        if not addresses:
            return ""
        result = ""
        for addr in addresses:
            result += self._encode_address(addr)
        return result
    
    def _encode_uint256_array(self, values: list) -> str:
        """Encode uint256 array"""
        if not values:
            return ""
        result = ""
        for val in values:
            result += format(val, '064x')
        return result
    
    def _encode_address(self, address: str) -> str:
        """Encode single address"""
        if address.startswith('0x'):
            return address[2:].zfill(64)
        return address.zfill(64)
    
    def _encode_bytes16(self, value: str) -> str:
        """Encode bytes16"""
        if value.startswith('0x'):
            return value[2:].zfill(32)
        return value.zfill(32)
    
    def _encode_uint256(self, values: list) -> str:
        """Encode uint256 value"""
        if not values:
            return ""
        return format(values[0], '064x')
    
    async def log_execution_start(self, opportunity: ArbitrumOpportunity):
        """Log execution start"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO opportunities (id, network, protocol, opportunity_type, estimated_profit_usd, 
                                        gas_cost_usd, liquidity_usd, confidence_score, created_at, token_pair, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opportunity.id,
                opportunity.network,
                opportunity.protocol,
                opportunity.opportunity_type,
                opportunity.estimated_profit_usd,
                opportunity.gas_cost_usd,
                opportunity.liquidity_usd,
                opportunity.confidence_score,
                datetime.now(),
                opportunity.token_pair,
                json.dumps(opportunity.details or {})
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to log execution start: {e}")
    
    async def log_execution_result(self, opportunity: ArbitrumOpportunity, result: Dict, execution_time: float):
        """Log execution result"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO executions (id, opportunity_id, network, transaction_hash, status, 
                                      profit_usd, gas_cost_usd, execution_time, created_at, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"exec_{opportunity.id}_{int(time.time())}",
                opportunity.id,
                opportunity.network,
                result.get("transaction_hash", ""),
                "success" if result.get("success", False) else "failed",
                opportunity.estimated_profit_usd if result.get("success", False) else 0,
                0.00035,  # Estimated gas cost
                execution_time,
                datetime.now(),
                json.dumps(result)
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to log execution result: {e}")
    
    async def log_execution_error(self, opportunity: ArbitrumOpportunity, error_msg: str, execution_time: float):
        """Log execution error"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO executions (id, opportunity_id, network, transaction_hash, status, 
                                      profit_usd, gas_cost_usd, execution_time, created_at, details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"exec_{opportunity.id}_{int(time.time())}",
                opportunity.id,
                opportunity.network,
                "",
                "failed",
                0,
                0.00035,  # Estimated gas cost
                execution_time,
                datetime.now(),
                json.dumps({"error": error_msg})
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to log execution error: {e}")
    
    def update_metrics(self, result: Dict, execution_time: float, estimated_profit: float):
        """Update execution metrics"""
        try:
            self.metrics["total_executions"] += 1
            
            if result.get("success", False):
                self.metrics["successful_executions"] += 1
                self.metrics["profit_per_execution"] = (
                    (self.metrics["profit_per_execution"] * (self.metrics["successful_executions"] - 1) + estimated_profit) /
                    self.metrics["successful_executions"]
                )
            else:
                self.metrics["failed_executions"] += 1
            
            # Update average execution time
            total_time = self.metrics["average_execution_time"] * (self.metrics["total_executions"] - 1) + execution_time
            self.metrics["average_execution_time"] = total_time / self.metrics["total_executions"]
            
        except Exception as e:
            logger.error(f"Metrics update failed: {e}")
    
    def get_latest_opportunities(self, limit: int = 10) -> List[ArbitrumOpportunity]:
        """Get latest opportunities from database"""
        
        try:
            # Create a new database connection for this method
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, network, protocol, opportunity_type, estimated_profit_usd,
                       gas_cost_usd, liquidity_usd, confidence_score, created_at,
                       token_pair, details
                FROM opportunities 
                WHERE network = 'arbitrum' 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            
            opportunities = []
            for row in cursor.fetchall():
                opportunity = ArbitrumOpportunity(
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
            
            conn.close()
            return opportunities
            
        except Exception as e:
            logger.error(f"Failed to get opportunities: {str(e)}")
            return []
    
    def close(self):
        """Close database connection"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def get_engine_status(self) -> Dict:
        """Get engine status with dynamic gas and network monitoring"""
        status = {
            "network": "arbitrum",
            "config": {
                "dex": self.config.dex,
                "gas_limit": self.config.gas_limit,
                "priority_fee": self.config.priority_fee,
                "max_fee": self.config.max_fee,
                "bundle_timeout": self.config.bundle_timeout,
                "enable_flashbots": self.config.enable_flashbots,
                "enable_optimization": self.config.enable_optimization
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
        logger.info("🔍 Starting monitoring systems")
        
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
        logger.info("✅ Monitoring systems started successfully")
        
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
    
    def should_execute_opportunity(self, opportunity: ArbitrumOpportunity) -> Tuple[bool, str]:
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