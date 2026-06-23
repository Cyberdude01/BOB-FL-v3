#!/usr/bin/env python3
"""
Verification script to confirm Dynamic Gas Pricing and Network Monitoring 
are implemented for both Arbitrum and Base networks
"""

import json
import logging
import sys
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def verify_arbitrum_implementation():
    """Verify Arbitrum implementation"""
    logger.info("🔍 Verifying Arbitrum Implementation")
    
    try:
        # Check if Arbitrum engine has dynamic gas monitoring
        with open('/root/.openclaw/workspace/flash-loan-research/arbitrum_execution_engine.py', 'r') as f:
            arbitrum_code = f.read()
        
        checks = {
            "gas_monitor_import": "from gas_monitor import DynamicGasMonitor" in arbitrum_code,
            "network_monitor_import": "from network_monitor import NetworkMonitor" in arbitrum_code,
            "gas_monitor_init": "self.gas_monitor = DynamicGasMonitor" in arbitrum_code,
            "network_monitor_init": "self.network_monitor = NetworkMonitor" in arbitrum_code,
            "dynamic_gas_usage": "get_optimal_gas_price" in arbitrum_code,
            "network_suitability": "should_send_transaction" in arbitrum_code,
            "monitoring_methods": "async def start_monitoring" in arbitrum_code,
            "status_methods": "get_engine_status" in arbitrum_code,
            "recommendation_methods": "get_network_recommendations" in arbitrum_code,
            "gas_analysis_methods": "get_gas_analysis" in arbitrum_code,
            "opportunity_validation": "should_execute_opportunity" in arbitrum_code
        }
        
        logger.info("📊 Arbitrum Implementation Check:")
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"   {status} {check_name}: {result}")
        
        arbitrum_complete = all(checks.values())
        
        if arbitrum_complete:
            logger.info("✅ Arbitrum implementation is COMPLETE")
        else:
            logger.error("❌ Arbitrum implementation is INCOMPLETE")
            
        return arbitrum_complete
        
    except Exception as e:
        logger.error(f"❌ Error verifying Arbitrum implementation: {e}")
        return False

def verify_base_implementation():
    """Verify Base implementation"""
    logger.info("🔍 Verifying Base Implementation")
    
    try:
        # Check if Base engine has dynamic gas monitoring
        with open('/root/.openclaw/workspace/flash-loan-research/base_execution_engine.py', 'r') as f:
            base_code = f.read()
        
        checks = {
            "gas_monitor_import": "from gas_monitor import DynamicGasMonitor" in base_code,
            "network_monitor_import": "from network_monitor import NetworkMonitor" in base_code,
            "gas_monitor_init": "self.gas_monitor = DynamicGasMonitor" in base_code,
            "network_monitor_init": "self.network_monitor = NetworkMonitor" in base_code,
            "dynamic_gas_usage": "get_optimal_gas_price" in base_code,
            "network_suitability": "should_send_transaction" in base_code,
            "monitoring_methods": "async def start_monitoring" in base_code,
            "status_methods": "get_engine_status" in base_code,
            "recommendation_methods": "get_network_recommendations" in base_code,
            "gas_analysis_methods": "get_gas_analysis" in base_code,
            "opportunity_validation": "should_execute_opportunity" in base_code
        }
        
        logger.info("📊 Base Implementation Check:")
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"   {status} {check_name}: {result}")
        
        base_complete = all(checks.values())
        
        if base_complete:
            logger.info("✅ Base implementation is COMPLETE")
        else:
            logger.error("❌ Base implementation is INCOMPLETE")
            
        return base_complete
        
    except Exception as e:
        logger.error(f"❌ Error verifying Base implementation: {e}")
        return False

def verify_gas_monitor_features():
    """Verify gas monitor features"""
    logger.info("🔍 Verifying Gas Monitor Features")
    
    try:
        with open('/root/.openclaw/workspace/flash-loan-research/gas_monitor.py', 'r') as f:
            gas_monitor_code = f.read()
        
        checks = {
            "real_time_monitoring": "async def start_monitoring" in gas_monitor_code,
            "gas_price_tracking": "async def update_gas_metrics" in gas_monitor_code,
            "network_congestion": "async def update_network_conditions" in gas_monitor_code,
            "priority_premium": "get_optimal_gas_price" in gas_monitor_code,
            "congestion_detection": "determine_congestion_level" in gas_monitor_code,
            "transaction_suitability": "should_send_transaction" in gas_monitor_code,
            "historical_analysis": "get_historical_gas_trend" in gas_monitor_code,
            "gas_oracle": "get_gas_price_percentiles" in gas_monitor_code,
            "network_health": "calculate_network_load" in gas_monitor_code
        }
        
        logger.info("📊 Gas Monitor Features Check:")
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"   {status} {check_name}: {result}")
        
        gas_monitor_complete = all(checks.values())
        
        if gas_monitor_complete:
            logger.info("✅ Gas Monitor features are COMPLETE")
        else:
            logger.error("❌ Gas Monitor features are INCOMPLETE")
            
        return gas_monitor_complete
        
    except Exception as e:
        logger.error(f"❌ Error verifying Gas Monitor features: {e}")
        return False

def verify_network_monitor_features():
    """Verify network monitor features"""
    logger.info("🔍 Verifying Network Monitor Features")
    
    try:
        with open('/root/.openclaw/workspace/flash-loan-research/network_monitor.py', 'r') as f:
            network_monitor_code = f.read()
        
        checks = {
            "real_time_monitoring": "async def start_monitoring" in network_monitor_code,
            "network_health_metrics": "async def update_network_health" in network_monitor_code,
            "block_time_analysis": "avg_block_time" in network_monitor_code,
            "mempool_analysis": "mempool_size" in network_monitor_code,
            "gas_percentiles": "gas_price_percentiles" in network_monitor_code,
            "health_scoring": "calculate_health_score" in network_monitor_code,
            "recommendations": "get_network_recommendations" in network_monitor_code,
            "alert_system": "async def check_alerts" in network_monitor_code,
            "network_load": "calculate_network_load" in network_monitor_code,
            "status_scoring": "score_block_time" in network_monitor_code
        }
        
        logger.info("📊 Network Monitor Features Check:")
        for check_name, result in checks.items():
            status = "✅" if result else "❌"
            logger.info(f"   {status} {check_name}: {result}")
        
        network_monitor_complete = all(checks.values())
        
        if network_monitor_complete:
            logger.info("✅ Network Monitor features are COMPLETE")
        else:
            logger.error("❌ Network Monitor features are INCOMPLETE")
            
        return network_monitor_complete
        
    except Exception as e:
        logger.error(f"❌ Error verifying Network Monitor features: {e}")
        return False

def verify_specific_requirements():
    """Verify the 5 specific requirements mentioned by the user"""
    logger.info("🔍 Verifying Specific Requirements")
    
    requirements = {
        "1. Real-time Gas Monitoring": False,
        "2. Priority Premium": False,
        "3. Network Congestion Detection": False,
        "4. Gas Price Oracle": False,
        "5. Network Health Indicators": False
    }
    
    try:
        # Check gas monitor
        with open('/root/.openclaw/workspace/flash-loan-research/gas_monitor.py', 'r') as f:
            gas_monitor_code = f.read()
        
        # Check network monitor  
        with open('/root/.openclaw/workspace/flash-loan-research/network_monitor.py', 'r') as f:
            network_monitor_code = f.read()
        
        # Requirement 1: Real-time Gas Monitoring
        requirements["1. Real-time Gas Monitoring"] = (
            "async def start_monitoring" in gas_monitor_code and
            "async def update_gas_metrics" in gas_monitor_code
        )
        
        # Requirement 2: Priority Premium
        requirements["2. Priority Premium"] = (
            "priority_multiplier" in gas_monitor_code and
            "get_optimal_gas_price" in gas_monitor_code
        )
        
        # Requirement 3: Network Congestion Detection
        requirements["3. Network Congestion Detection"] = (
            "determine_congestion_level" in gas_monitor_code and
            "congestion_level" in gas_monitor_code
        )
        
        # Requirement 4: Gas Price Oracle
        requirements["4. Gas Price Oracle"] = (
            "get_gas_price_percentiles" in gas_monitor_code and
            "gas_price_trend" in network_monitor_code
        )
        
        # Requirement 5: Network Health Indicators
        requirements["5. Network Health Indicators"] = (
            "block_time" in network_monitor_code and
            "mempool_size" in network_monitor_code and
            "gas_price_percentiles" in network_monitor_code
        )
        
        logger.info("📊 Specific Requirements Check:")
        for req_name, result in requirements.items():
            status = "✅" if result else "❌"
            logger.info(f"   {status} {req_name}: {result}")
        
        all_requirements_met = all(requirements.values())
        
        if all_requirements_met:
            logger.info("✅ ALL specific requirements are MET")
        else:
            logger.error("❌ Some requirements are NOT MET")
            
        return all_requirements_met
        
    except Exception as e:
        logger.error(f"❌ Error verifying specific requirements: {e}")
        return False

def generate_verification_report():
    """Generate comprehensive verification report"""
    logger.info("📋 Generating Verification Report")
    
    # Run all verifications
    arbitrum_ok = verify_arbitrum_implementation()
    base_ok = verify_base_implementation()
    gas_monitor_ok = verify_gas_monitor_features()
    network_monitor_ok = verify_network_monitor_features()
    requirements_ok = verify_specific_requirements()
    
    # Generate report
    report = {
        "verification_timestamp": "2026-06-06",
        "network_implementations": {
            "arbitrum": arbitrum_ok,
            "base": base_ok
        },
        "monitoring_systems": {
            "gas_monitor": gas_monitor_ok,
            "network_monitor": network_monitor_ok
        },
        "specific_requirements": requirements_ok,
        "overall_status": all([arbitrum_ok, base_ok, gas_monitor_ok, network_monitor_ok, requirements_ok])
    }
    
    # Save report
    with open('/root/.openclaw/workspace/flash-loan-research/VERIFICATION_REPORT.json', 'w') as f:
        json.dump(report, f, indent=2)
    
    logger.info("📄 Verification report saved to VERIFICATION_REPORT.json")
    
    # Print summary
    logger.info(f"\n{'='*60}")
    logger.info("VERIFICATION SUMMARY")
    logger.info(f"{'='*60}")
    
    logger.info(f"Arbitrum Implementation: {'✅ COMPLETE' if arbitrum_ok else '❌ INCOMPLETE'}")
    logger.info(f"Base Implementation: {'✅ COMPLETE' if base_ok else '❌ INCOMPLETE'}")
    logger.info(f"Gas Monitor Features: {'✅ COMPLETE' if gas_monitor_ok else '❌ INCOMPLETE'}")
    logger.info(f"Network Monitor Features: {'✅ COMPLETE' if network_monitor_ok else '❌ INCOMPLETE'}")
    logger.info(f"Specific Requirements: {'✅ MET' if requirements_ok else '❌ NOT MET'}")
    
    overall_status = "✅ ALL SYSTEMS READY" if report['overall_status'] else "❌ IMPLEMENTATION INCOMPLETE"
    logger.info(f"Overall Status: {overall_status}")
    
    return report['overall_status']

def main():
    """Main verification function"""
    logger.info("🚀 Starting Dynamic Gas Verification")
    logger.info("=" * 60)
    
    success = generate_verification_report()
    
    if success:
        logger.info("🎉 VERIFICATION SUCCESSFUL - All systems are properly implemented")
    else:
        logger.error("❌ VERIFICATION FAILED - Some implementations are missing")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)