#!/usr/bin/env python3
"""
Circuit Breaker Implementation
MEV Protection and Risk Management System
"""

import asyncio
import time
import logging
import sqlite3
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 3  # Number of failures before tripping
    recovery_time: int = 300  # 5 minutes recovery time
    half_open_max_requests: int = 5  # Requests allowed in half-open state
    cool_down_time: int = 60  # 1 minute cool down after recovery
    network_specific_thresholds: Dict[str, int] = None

@dataclass
class ExecutionFailure:
    """Execution failure record"""
    timestamp: datetime
    network: str
    error_type: str
    error_message: str
    opportunity_id: Optional[str] = None
    gas_used: Optional[int] = None
    execution_time: Optional[float] = None

class CircuitBreaker:
    """Circuit breaker for MEV protection and risk management"""
    
    def __init__(self, db_path: str, config: CircuitBreakerConfig = None):
        self.db_path = db_path
        self.config = config or CircuitBreakerConfig()
        
        # Circuit breaker state
        self.state = {}  # Network-specific states
        self.last_failure_time = {}  # Network-specific failure times
        self.failure_count = {}  # Network-specific failure counts
        self.recovery_start_time = {}  # Network-specific recovery times
        self.half_open_request_count = {}  # Network-specific half-open counts
        
        # Setup database
        self.setup_database()
        
    def setup_database(self):
        """Setup database for circuit breaker tracking"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create circuit breaker state table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS circuit_breaker_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    network TEXT,
                    state TEXT,
                    failure_count INTEGER,
                    last_failure_time DATETIME,
                    recovery_start_time DATETIME,
                    half_open_request_count INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create execution failures table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS execution_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    network TEXT,
                    error_type TEXT,
                    error_message TEXT,
                    opportunity_id TEXT,
                    gas_used INTEGER,
                    execution_time REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create circuit breaker events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS circuit_breaker_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    network TEXT,
                    event_type TEXT,
                    description TEXT,
                    state_before TEXT,
                    state_after TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Circuit breaker database setup completed successfully")
            
        except Exception as e:
            logger.error(f"Database setup failed: {e}")
            raise
    
    def _get_network_state(self, network: str) -> str:
        """Get current circuit breaker state for a network"""
        # Load state from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT state FROM circuit_breaker_state 
            WHERE network = ? 
            ORDER BY updated_at DESC LIMIT 1
        ''', (network,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
        
        # Default state
        return "closed"
    
    def _set_network_state(self, network: str, state: str):
        """Set circuit breaker state for a network"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_state = self._get_network_state(network)
        
        cursor.execute('''
            INSERT INTO circuit_breaker_state 
            (network, state, failure_count, last_failure_time, recovery_start_time, half_open_request_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            network,
            state,
            self.failure_count.get(network, 0),
            self.last_failure_time.get(network),
            self.recovery_start_time.get(network),
            self.half_open_request_count.get(network, 0),
            datetime.now()
        ))
        
        # Log state change
        cursor.execute('''
            INSERT INTO circuit_breaker_events 
            (timestamp, network, event_type, description, state_before, state_after, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now(),
            network,
            "state_change",
            f"Circuit breaker state changed from {current_state} to {state}",
            current_state,
            state,
            datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"🔌 Circuit breaker state for {network}: {state}")
    
    def register_failure(self, network: str, failure: ExecutionFailure):
        """Register an execution failure"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert failure record
            cursor.execute('''
                INSERT INTO execution_failures 
                (timestamp, network, error_type, error_message, opportunity_id, gas_used, execution_time, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                failure.timestamp,
                network,
                failure.error_type,
                failure.error_message,
                failure.opportunity_id,
                failure.gas_used,
                failure.execution_time,
                datetime.now()
            ))
            
            # Update failure count
            current_count = self.failure_count.get(network, 0)
            new_count = current_count + 1
            self.failure_count[network] = new_count
            
            # Update last failure time
            self.last_failure_time[network] = failure.timestamp
            
            # Check if circuit breaker should trip
            threshold = self.config.network_specific_thresholds.get(network, self.config.failure_threshold) if self.config.network_specific_thresholds else self.config.failure_threshold
            
            if new_count >= threshold:
                self._set_network_state(network, "open")
                logger.warning(f"🔌 Circuit breaker TRIPPED for {network} after {new_count} failures")
            else:
                logger.warning(f"🔌 Failure registered for {network}: {new_count}/{threshold} failures")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error registering failure: {e}")
    
    def register_success(self, network: str):
        """Register a successful execution"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            current_state = self._get_network_state(network)
            
            if current_state == "open":
                # Move to half-open state
                self._set_network_state(network, "half-open")
                self.half_open_request_count[network] = 0
                logger.info(f"🔌 Circuit breaker for {network} moved to half-open state")
            
            elif current_state == "half-open":
                # Increment half-open request count
                current_count = self.half_open_request_count.get(network, 0)
                new_count = current_count + 1
                
                if new_count >= self.config.half_open_max_requests:
                    # Move to closed state (recovered)
                    self._set_network_state(network, "closed")
                    self.failure_count[network] = 0
                    self.recovery_start_time[network] = None
                    self.half_open_request_count[network] = 0
                    logger.info(f"🔌 Circuit breaker for {network} RECOVERED and closed")
                else:
                    self.half_open_request_count[network] = new_count
                    logger.info(f"🔌 Success registered for {network}: {new_count}/{self.config.half_open_max_requests} in half-open state")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error registering success: {e}")
    
    def should_execute(self, network: str) -> bool:
        """Check if execution should be allowed"""
        current_state = self._get_network_state(network)
        
        if current_state == "closed":
            return True
        
        elif current_state == "open":
            # Check if recovery time has passed
            last_failure = self.last_failure_time.get(network)
            if last_failure:
                recovery_elapsed = (datetime.now() - last_failure).seconds
                if recovery_elapsed >= self.config.recovery_time:
                    # Move to half-open state
                    self._set_network_state(network, "half-open")
                    self.half_open_request_count[network] = 0
                    logger.info(f"🔌 Recovery time elapsed for {network}, moving to half-open state")
                    return True
            
            logger.warning(f"🔌 Execution blocked for {network}: circuit breaker is open")
            return False
        
        elif current_state == "half-open":
            # Allow execution but track request count
            current_count = self.half_open_request_count.get(network, 0)
            if current_count < self.config.half_open_max_requests:
                return True
            
            logger.warning(f"🔌 Execution blocked for {network}: half-open state limit reached")
            return False
        
        else:
            logger.warning(f"🔌 Unknown circuit breaker state for {network}: {current_state}")
            return False
    
    def get_circuit_breaker_status(self, network: str) -> Dict:
        """Get detailed circuit breaker status for a network"""
        current_state = self._get_network_state(network)
        failure_count = self.failure_count.get(network, 0)
        
        status = {
            "network": network,
            "state": current_state,
            "failure_count": failure_count,
            "last_failure_time": self.last_failure_time.get(network),
            "recovery_start_time": self.recovery_start_time.get(network),
            "half_open_request_count": self.half_open_request_count.get(network, 0),
            "should_execute": self.should_execute(network)
        }
        
        # Add recovery time estimate if in open state
        if current_state == "open" and self.last_failure_time.get(network):
            time_since_failure = (datetime.now() - self.last_failure_time[network]).seconds
            recovery_remaining = max(0, self.config.recovery_time - time_since_failure)
            status["recovery_time_remaining"] = recovery_remaining
        
        return status
    
    def get_all_networks_status(self) -> Dict[str, Dict]:
        """Get circuit breaker status for all networks"""
        # Get all networks from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT network FROM circuit_breaker_state
            UNION
            SELECT DISTINCT network FROM execution_failures
        ''')
        
        networks = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return {network: self.get_circuit_breaker_status(network) for network in networks}
    
    def reset_circuit_breaker(self, network: str):
        """Manually reset circuit breaker for a network"""
        self._set_network_state(network, "closed")
        self.failure_count[network] = 0
        self.last_failure_time[network] = None
        self.recovery_start_time[network] = None
        self.half_open_request_count[network] = 0
        
        logger.info(f"🔌 Circuit breaker manually reset for {network}")
    
    def get_failure_statistics(self, network: str, hours: int = 24) -> Dict:
        """Get failure statistics for a network"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            since_time = datetime.now() - timedelta(hours=hours)
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_failures,
                    AVG(gas_used) as avg_gas_used,
                    AVG(execution_time) as avg_execution_time,
                    error_type,
                    COUNT(*) as error_type_count
                FROM execution_failures 
                WHERE network = ? AND timestamp > ?
                GROUP BY error_type
                ORDER BY error_type_count DESC
            ''', (network, since_time))
            
            failures = cursor.fetchall()
            conn.close()
            
            stats = {
                "network": network,
                "time_period_hours": hours,
                "total_failures": len(failures),
                "failure_details": []
            }
            
            for failure in failures:
                stats["failure_details"].append({
                    "error_type": failure[3],
                    "count": failure[4],
                    "avg_gas_used": failure[1],
                    "avg_execution_time": failure[2]
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting failure statistics: {e}")
            return {"network": network, "error": str(e)}

class MEVProtectionManager:
    """MEV protection manager using circuit breaker"""
    
    def __init__(self, db_path: str):
        self.circuit_breaker = CircuitBreaker(db_path)
        self.db_path = db_path
    
    async def execute_with_protection(self, network: str, opportunity_id: str, execution_func) -> Dict:
        """Execute with MEV protection and circuit breaker"""
        # Check if execution should proceed
        if not self.circuit_breaker.should_execute(network):
            return {
                "success": False,
                "reason": "Circuit breaker blocked execution",
                "circuit_breaker_status": self.circuit_breaker.get_circuit_breaker_status(network)
            }
        
        try:
            # Execute the function
            result = await execution_func()
            
            # Register success
            self.circuit_breaker.register_success(network)
            
            return {
                "success": True,
                "result": result,
                "circuit_breaker_status": self.circuit_breaker.get_circuit_breaker_status(network)
            }
            
        except Exception as e:
            # Register failure
            failure = ExecutionFailure(
                timestamp=datetime.now(),
                network=network,
                error_type="execution_error",
                error_message=str(e),
                opportunity_id=opportunity_id
            )
            
            self.circuit_breaker.register_failure(network, failure)
            
            return {
                "success": False,
                "reason": str(e),
                "circuit_breaker_status": self.circuit_breaker.get_circuit_breaker_status(network)
            }
    
    def get_protection_status(self) -> Dict:
        """Get overall MEV protection status"""
        return {
            "circuit_breaker_status": self.circuit_breaker.get_all_networks_status(),
            "timestamp": datetime.now().isoformat()
        }

async def main():
    """Main function to test circuit breaker"""
    db_path = '/root/.openclaw/workspace/flash-loan-research/enhanced_flash_loan_research.db'
    
    # Create circuit breaker with custom configuration
    config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_time=300,  # 5 minutes
        half_open_max_requests=5,
        network_specific_thresholds={
            "ethereum": 2,  # More strict for Ethereum
            "arbitrum": 4   # More lenient for Arbitrum
        }
    )
    
    circuit_breaker = CircuitBreaker(db_path, config)
    protection_manager = MEVProtectionManager(db_path)
    
    try:
        # Test circuit breaker functionality
        logger.info("Testing circuit breaker...")
        
        # Simulate some failures
        test_networks = ["ethereum", "arbitrum", "base"]
        
        for network in test_networks:
            logger.info(f"Testing circuit breaker for {network}")
            
            # Get initial status
            status = circuit_breaker.get_circuit_breaker_status(network)
            logger.info(f"Initial status for {network}: {status}")
            
            # Simulate failures
            for i in range(2):
                failure = ExecutionFailure(
                    timestamp=datetime.now(),
                    network=network,
                    error_type="test_error",
                    error_message=f"Test failure {i+1}",
                    opportunity_id=f"test_opportunity_{i+1}"
                )
                
                circuit_breaker.register_failure(network, failure)
                status = circuit_breaker.get_circuit_breaker_status(network)
                logger.info(f"Status after failure {i+1} for {network}: {status}")
            
            # Test execution should be blocked after threshold
            should_execute = circuit_breaker.should_execute(network)
            logger.info(f"Should execute for {network}: {should_execute}")
        
        # Get overall protection status
        protection_status = protection_manager.get_protection_status()
        logger.info("Overall protection status:")
        logger.info(json.dumps(protection_status, indent=2, default=str))
        
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())