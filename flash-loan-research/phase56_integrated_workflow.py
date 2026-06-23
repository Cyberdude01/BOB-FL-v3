#!/usr/bin/env python3
"""
Phase 5/6 Integrated Workflow

This module integrates Phase 5 metrics collection with Phase 3 execution and 
Phase 4 pattern recognition, then gates through Phase 6 production controls.

- Integrates: execution, pattern recognition, performance monitoring, and production gate
- Captures: live metrics to SQLite and JSONL
- Exposes: dashboard endpoints and snapshot exports
- Gates: deployment through risk policies and canary rollbacks

Note: This is a full-stack integration of all phases. For production, 
real on-chain execution and live data feeds would replace the simulation.
"""

from __future__ import annotations

import asyncio
import time
import random
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load all phases
try:
    from phase3_execution_system import Opportunity, ExecutionStrategies
    from phase4_pattern_recognition import PatternRecognizer, PatternPlaybooks
    from phase5_optimization import TimeframeConfig, PerformanceMonitor, TimeframeMonitor
    from phase5_data_store import MetricsStore, ExecutionMetricRecord, PatternRecord
    from phase6_production_controls import RiskPolicy, DeploymentVersion, ProductionGate
    from arbitrum_execution_engine import ArbitrumExecutionEngine
    from base_execution_engine import BaseExecutionEngine
    from ethereum_execution_engine import EthereumExecutionEngine
except ImportError as e:
    print(f"⚠️  Phase import failed: {e}")
    exit(1)


class IntegratedPhase56Workflow:
    """Full integration of Phase 5/6 with Phase 3/4."""

    def __init__(self):
        self.execution_strategies = ExecutionStrategies()
        self.pattern_recognizer = PatternRecognizer()
        self.pattern_playbooks = PatternPlaybooks()
        self.performance_monitor = PerformanceMonitor()
        
        # Timeframe config: detection window is 13 minutes
        self.timeframe_config = TimeframeConfig()
        self.timeframe_config.update(detection_target_min=13)
        self.timeframe_monitor = TimeframeMonitor(self.timeframe_config)
        
        # Metrics and storage
        self.metrics_store = MetricsStore()
        
        # Production controls
        self.risk_policy = RiskPolicy(
            max_daily_loss_usd=10000.0,
            max_consecutive_failures=5,
            min_success_rate=0.8
        )
        self.production_gate = ProductionGate(self.risk_policy)
        
        # Simulation and execution engines
        self.real_execution_enabled = os.getenv('REAL_TRANSACTIONS_ENABLED', 'false').lower() == 'true'
        self.dry_run_mode = os.getenv('DRY_RUN_MODE', 'true').lower() == 'true'
        
        # Initialize simulation engine (always available)
        self.simulation_engine = ArbitrumSimulationEngine()
        
        # Initialize execution engines if real execution is enabled
        self.execution_engines = {}
        if self.real_execution_enabled and not self.dry_run_mode:
            self.execution_engines['arbitrum'] = ArbitrumExecutionEngine('./enhanced_flash_loan_research.db')
            self.execution_engines['base'] = BaseExecutionEngine()
            self.execution_engines['ethereum'] = EthereumExecutionEngine()
            print("🚀 Real execution enabled for Arbitrum, Base, and Ethereum")
        else:
            print("🔧 Simulation mode enabled")
        
        # Mock version tracking
        self.current_version = DeploymentVersion(
            version="phase56-v1.0.0",
            built_at=datetime.now(timezone.utc),
            notes="Initial integrated workflow"
        )
        self.production_gate.deploy(self.current_version)
        
        print("✅ Phase 5/6 Integrated Workflow initialized")

    async def process_opportunity(self, opportunity: Opportunity) -> Dict[str, Any]:
        """Process an opportunity through the full workflow."""
        result = {
            'success': False,
            'network': opportunity.network,
            'opportunity_id': opportunity.id,
            'workflow_steps': [],
            'pattern': None,
            'playbook': None,
            'risk_decision': None,
            'metrics': None,
            'error_message': None
        }
        
        start_time = time.time()
        
        try:
            # Step 1: Pattern recognition (Phase 4)
            result['workflow_steps'].append('pattern_recognition')
            pattern = self.pattern_recognizer.identify(opportunity)
            result['pattern'] = pattern
            
            # Log pattern recognition
            pattern_record = PatternRecord(
                network=opportunity.network,
                opportunity_id=opportunity.id,
                pattern=pattern,
                details={'protocol': opportunity.protocol, 'token_pair': opportunity.token_pair}
            )
            self.metrics_store.record_pattern(pattern_record)
            
            # Step 2: Get playbook
            result['workflow_steps'].append('playbook_selection')
            playbook_func = self.pattern_playbooks.patterns.get(pattern)
            if playbook_func:
                playbook = playbook_func(opportunity)
                result['playbook'] = playbook.name
                result['playbook_steps'] = playbook.steps
                result['playbook_estimated_time'] = playbook.estimated_time
            
            # Step 3: Risk evaluation (Phase 6)
            result['workflow_steps'].append('risk_evaluation')
            risk_pass = self._evaluate_risk(opportunity, pattern)
            result['risk_decision'] = risk_pass
            
            if not risk_pass:
                result['error_message'] = "Risk evaluation failed"
                return result
            
            # Step 4: Get execution strategy (Phase 3)
            result['workflow_steps'].append('strategy_selection')
            execution_plan = self.execution_strategies.strategies[opportunity.network](opportunity)
            result['execution_plan'] = execution_plan
            
            # Step 5: Simulation Phase - Verify profitability before execution
            result['workflow_steps'].append('simulation')
            
            if self.real_execution_enabled and not self.dry_run_mode:
                # Always simulate first to verify profitability
                simulation_result = await self._simulate_opportunity(opportunity)
                
                if simulation_result.profitable:
                    print(f"✅ Simulation profitable: ${simulation_result.estimated_profit:.6f} - Executing on mainnet")
                    execution_success = await self._execute_real_transaction(opportunity, execution_plan)
                else:
                    print(f"❌ Simulation not profitable: ${simulation_result.estimated_profit:.6f} - Skipping execution")
                    execution_success = False
                    result['simulation_result'] = simulation_result.dict() if hasattr(simulation_result, 'dict') else simulation_result.__dict__
            else:
                # Dry run mode - only simulation
                execution_success = await self._simulate_execution(opportunity, execution_plan)
                
            result['success'] = execution_success
            
            # Step 6: Record metrics (Phase 5)
            result['workflow_steps'].append('metrics_recording')
            detection_latency = time.time() - start_time  # Simulated
            execution_latency = random.uniform(0.5, 2.0)  # Simulated
            
            metric_record = ExecutionMetricRecord(
                network=opportunity.network,
                opportunity_id=opportunity.id,
                detection_latency=detection_latency,
                execution_latency=execution_latency,
                profit=opportunity.estimated_profit_usd if execution_success else 0.0,
                success=execution_success,
                pattern=pattern,
                playbook=result.get('playbook'),
                risk_decision='allow',
                error_message=None if execution_success else "Simulated failure"
            )
            
            self.metrics_store.record_execution(metric_record)
            self.performance_monitor.track(detection_latency, execution_latency, 
                                          opportunity.estimated_profit_usd, execution_success)
            
            # Step 7: Update production gate if successful
            if execution_success:
                self.production_gate.record_rollback("Simulated successful execution")
            
            result['metrics'] = {
                'detection_latency': detection_latency,
                'execution_latency': execution_latency,
                'profit': opportunity.estimated_profit_usd if execution_success else 0.0
            }
            
        except Exception as e:
            result['error_message'] = str(e)
            result['workflow_steps'].append('error')
        
        return result
    
    def _evaluate_risk(self, opportunity: Opportunity, pattern: str) -> bool:
        """Evaluate if opportunity passes risk criteria."""
        # Check profit threshold
        if opportunity.estimated_profit_usd < 100:
            return False
        
        # Check confidence
        if opportunity.confidence_score < 0.7:
            return False
        
        # Check pattern-specific risks
        if pattern == 'cross_chain' and opportunity.liquidity_usd < 50000:
            return False
        
        # Check production gate
        forecast_profit = opportunity.estimated_profit_usd
        forecast_risk = opportunity.confidence_score
        failures = self.performance_monitor.attempts - self.performance_monitor.successes
        
        return self.production_gate.can_deploy(forecast_profit, forecast_risk, failures)
    
    async def _simulate_execution(self, opportunity: Opportunity, execution_plan: Dict[str, Any]) -> bool:
        """Simulate execution with network-specific success rates."""
        success_rates = {
            'arbitrum': 0.92,
            'base': 0.88,
            'ethereum': 0.85,
            'optimism': 0.90,
            'cross_chain': 0.75
        }
        
        success_rate = success_rates.get(opportunity.network, 0.8)
        return random.random() < success_rate
    
    async def _execute_real_transaction(self, opportunity: Opportunity, execution_plan: Dict[str, Any]) -> bool:
        """Execute real on-chain transaction."""
        try:
            print(f"🚀 Executing real transaction for opportunity: {opportunity.id}")
            
            # Get execution engine for the network
            engine = self.execution_engines.get(opportunity.network)
            if not engine:
                print(f"❌ No execution engine available for {opportunity.network}")
                return False
            
            # Create opportunity data structure
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
            
            # Execute the opportunity
            result = await engine.execute_opportunity(real_opportunity)
            
            print(f"📊 Real execution result: {result}")
            return result.get('success', False)
            
        except Exception as e:
            print(f"❌ Real execution failed: {e}")
            return False
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get dashboard data summary."""
        return {
            'summary': self.metrics_store.summary(),
            'network_summary': self.metrics_store.network_summary(),
            'recent_executions': self.metrics_store.recent_executions(10),
            'recent_patterns': self.metrics_store.recent_patterns(10),
            'performance_summary': self.performance_monitor.summary(),
            'production_status': {
                'current_version': self.current_version.version,
                'risk_policy': {
                    'max_daily_loss_usd': self.risk_policy.max_daily_loss_usd,
                    'max_consecutive_failures': self.risk_policy.max_consecutive_failures,
                    'min_success_rate': self.risk_policy.min_success_rate
                },
                'last_rollback': self.production_gate.last_rollback()
            }
        }
    
    def export_snapshot(self) -> Dict[str, Any]:
        """Export full system snapshot."""
        snapshot = self.metrics_store.export_snapshot()
        snapshot['production_controls'] = {
            'current_version': self.current_version.version,
            'risk_policy': asdict(self.risk_policy),
            'rollback_history': [asdict(r) for r in self.production_gate._rollbacks]
        }
        snapshot['performance_monitor'] = self.performance_monitor.summary()
        return snapshot


# Demonstration entry point
async def main():
    """Demonstrate the integrated workflow."""
    print("🚀 Phase 5/6 Integrated Workflow Demo")
    print("=" * 50)
    
    workflow = IntegratedPhase56Workflow()
    
    # Create test opportunities
    opportunities = [
        Opportunity(
            id=f"integrated_test_{int(time.time())}_{i}",
            timestamp=datetime.now(timezone.utc),
            estimated_profit_usd=1500.0 + i * 200,
            liquidity_usd=100000.0 + i * 10000,
            confidence_score=0.85,
            protocol="aave",
            token_pair="USDC-USDT",
            network="arbitrum"
        ) for i in range(3)
    ] + [
        Opportunity(
            id=f"integrated_test_{int(time.time())}_{i+3}",
            timestamp=datetime.now(timezone.utc),
            estimated_profit_usd=800.0,
            liquidity_usd=60000.0,
            confidence_score=0.72,
            protocol="bridge",
            token_pair="ETH-USDC",
            network="base"
        ) for i in range(2)
    ]
    
    # Process opportunities
    results = []
    for opp in opportunities:
        print(f"\n🔍 Processing {opp.network.upper()}: {opp.id}")
        result = await workflow.process_opportunity(opp)
        results.append(result)
        
        if result['success']:
            print(f"  ✅ Success: ${result['metrics']['profit']:.2f}")
        else:
            print(f"  ❌ Failed: {result['error_message']}")
        
        # Small delay
        await asyncio.sleep(0.1)
    
    # Show dashboard summary
    print("\n" + "=" * 50)
    print("📊 Dashboard Summary:")
    dashboard = workflow.get_dashboard_data()
    print(f"  Total Attempts: {dashboard['summary']['total_attempts']}")
    print(f"  Success Rate: {dashboard['summary']['success_rate']:.0%}")
    print(f"  Total Profit: ${dashboard['summary']['total_profit']:.2f}")
    print(f"  Current Version: {dashboard['production_status']['current_version']}")
    
    # Export snapshot
    snapshot = workflow.export_snapshot()
    snapshot_path = '/root/.openclaw/workspace/flash-loan-research/phase56_snapshot.json'
    with open(snapshot_path, 'w') as f:
        json.dump(snapshot, f, indent=2, default=str)
    print(f"\n📁 Snapshot exported to: {snapshot_path}")
    
    async def _execute_real_transaction(self, opportunity: Opportunity, execution_plan: Dict[str, Any]) -> bool:
        """Execute real on-chain transaction."""
        try:
            print(f"🚀 Executing real transaction for opportunity: {opportunity.id}")
            
            # Get execution engine for the network
            engine = self.execution_engines.get(opportunity.network)
            if not engine:
                print(f"❌ No execution engine available for {opportunity.network}")
                return False
            
            # Create opportunity data structure
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
            
            # Execute the opportunity
            result = await engine.execute_opportunity(real_opportunity)
            
            print(f"📊 Real execution result: {result}")
            return result.get('success', False)
            
        except Exception as e:
            print(f"❌ Real execution failed: {e}")
            return False
    
    async def _simulate_opportunity(self, opportunity: Opportunity) -> SimulationResult:
        """Simulate opportunity to verify profitability before real execution"""
        try:
            # Use the simulation engine to verify profitability
            simulation_result = await self.simulation_engine.simulate_flash_loan_arbitrage(
                opportunity.id, 
                opportunity.token_pair
            )
            return simulation_result
        except Exception as e:
            print(f"❌ Simulation failed: {e}")
            # Return a non-profitable result on simulation failure
            return SimulationResult(
                profitable=False,
                estimated_profit=0.0,
                gas_cost_est=0.00035,
                success_rate=0.0,
                arbitrage_path="Simulation failed",
                error_message=str(e)
            )


if __name__ == '__main__':
    # Note: asdict is not imported, we'll define it here for the demo
    def asdict(obj):
        if hasattr(obj, '__dict__'):
            return {k: v for k, v in obj.__dict__.items()}
        return str(obj)
    
    asyncio.run(main())