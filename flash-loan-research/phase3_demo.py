#!/usr/bin/env python3
"""
Phase 3 Demo: Automated Execution System Test Harness

This script demonstrates the phase 3 execution system scaffold.
It provides a simple interface to:
- Create sample opportunities
- Plan execution for different networks
- Show the structure of the execution system
"""

import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Import the phase 3 execution system
try:
    from phase3_execution_system import Phase3Orchestrator, Opportunity
    print("✅ Successfully imported Phase 3 execution system")
except ImportError as e:
    print(f"❌ Failed to import: {e}")
    exit(1)


@dataclass
class DemoOpportunity(Opportunity):
    """Extended demo opportunity with additional metadata"""
    protocol: str = "aave"
    token_pair: str = "USDC-USDT"


def create_demo_opportunity(network: str = "arbitrum") -> DemoOpportunity:
    """Create a sample opportunity for testing"""
    profit = {
        "arbitrum": 15000.0,
        "base": 3200.0,
        "ethereum": 4500.0,
        "optimism": 2100.0,
        "cross_chain": 8000.0,
    }.get(network, 1500.0)
    
    return DemoOpportunity(
        id=f"demo_opportunity_{int(time.time())}",
        timestamp=datetime.now(timezone.utc),
        estimated_profit_usd=profit,
        liquidity_usd=150000.0,
        confidence_score=0.85,
        protocol="aave",
        token_pair="USDC-USDT",
        network=network
    )


def demonstrate_network_strategies(orchestrator: Phase3Orchestrator) -> None:
    """Demonstrate planning execution across different networks"""
    print("\n=== Network Strategy Demonstration ===")
    
    networks = ["arbitrum", "base", "ethereum", "optimism", "cross_chain"]
    
    for network in networks:
        print(f"\n🌐 Planning execution for {network.upper()}:")
        
        try:
            opportunity = create_demo_opportunity(network)
            plan = orchestrator.plan_execution(network, opportunity)
            
            if "error" in plan:
                print(f"  ❌ Error: {plan['message']}")
            else:
                strategy = plan['strategy']
                print(f"  ✅ Strategy: {strategy.get('dex', 'unknown')}")
                print(f"     Gas Limit: {strategy.get('gas_limit', 0)}")
                print(f"     Priority Fee: {strategy.get('priority_fee', 0)} gwei")
                print(f"     Max Fee: {strategy.get('max_fee', 0)} gwei")
                print(f"     Bundle Timeout: {strategy.get('bundle_timeout', 0)}s")
                if 'notes' in strategy:
                    print(f"     Notes: {strategy['notes']}")
                    
        except Exception as e:
            print(f"  ❌ Exception: {e}")


def demonstrate_bundle_creation(orchestrator: Phase3Orchestrator) -> None:
    """Demonstrate bundle creation from plans"""
    print("\n=== Bundle Creation Demo ===")
    
    opportunity = create_demo_opportunity("arbitrum")
    plan = orchestrator.plan_execution("arbitrum", opportunity)
    
    if "error" not in plan:
        # Create a sample bundle
        bundle = orchestrator.build_execution_bundle(
            plan,
            transactions=[
                {"type": "flash_loan", "amount": "1000000000000000000"},
                {"type": "swap", "dex": "camelot"},
                {"type": "repay_loan"}
            ]
        )
        
        print("📦 Bundle created successfully:")
        print(f"  Network: {bundle['network']}")
        print(f"  Strategy: {bundle['strategy']['dex']}")
        print(f"  Transactions: {len(bundle['transactions'])}")
        print(f"  Bundle Timeout: {bundle['bundle_timeout']}s")
        print(f"  Created: {bundle['created_at']}")


def demonstrate_error_handling(orchestrator: Phase3Orchestrator) -> None:
    """Demonstrate error handling for unsupported networks"""
    print("\n=== Error Handling Demo ===")
    
    # Test with unsupported network
    unsupported_opportunity = DemoOpportunity(
        id="unsupported_opportunity",
        timestamp=datetime.now(timezone.utc),
        estimated_profit_usd=1000.0,
        liquidity_usd=50000.0,
        confidence_score=0.75,
        network="unsupported_network"
    )
    
    plan = orchestrator.plan_execution("unsupported_network", unsupported_opportunity)
    
    if "error" in plan:
        print(f"✅ Error handled correctly: {plan['message']}")
    else:
        print("❌ Error not handled properly")


def show_performance_metrics() -> None:
    """Show simulated performance metrics"""
    print("\n=== Performance Metrics (Simulated) ===")
    
    metrics = {
        "arbitrum": {"avg_execution_time": 1.2, "success_rate": 0.92},
        "base": {"avg_execution_time": 1.8, "success_rate": 0.88},
        "ethereum": {"avg_execution_time": 2.1, "success_rate": 0.85},
        "optimism": {"avg_execution_time": 1.5, "success_rate": 0.90},
        "cross_chain": {"avg_execution_time": 3.5, "success_rate": 0.75},
    }
    
    for network, data in metrics.items():
        print(f"  {network.upper()}: {data['success_rate']:.0%} success, {data['avg_execution_time']:.1f}s avg")


def main():
    """Main demonstration function"""
    print("🚀 Phase 3: Automated Execution System Demo")
    print("=" * 50)
    
    # Initialize orchestrator
    orchestrator = Phase3Orchestrator()
    
    # Run demonstrations
    demonstrate_network_strategies(orchestrator)
    demonstrate_bundle_creation(orchestrator)
    demonstrate_error_handling(orchestrator)
    show_performance_metrics()
    
    print("\n✅ Phase 3 Demo completed successfully!")
    print("\n📋 Next Steps:")
    print("  1. Implement actual transaction constructors for each network")
    print("  2. Add MEV protection layers (Flashbots/Eden)")
    print("  3. Connect real on-chain data feeds")
    print("  4. Test with production API keys")
    print("  5. Add circuit breaker logic")


if __name__ == "__main__":
    main()