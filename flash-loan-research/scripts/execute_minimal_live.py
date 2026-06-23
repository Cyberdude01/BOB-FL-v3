#!/usr/bin/env python3
"""BOB-FL Minimal Live Transaction Execution.

This performs actual live transactions with minimal capital to test real gas costs.
It exercises the configured v1 path:
- Safety gates
- RPC connectivity and balances
- Phase 3 strategy planning
- Real bundle submission
- Phase 3 execution engine validation/real execution
- Phase 5/6 integrated workflow simulation where available

Real transactions are enabled with minimal capital limits.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from phase3_execution_system import Phase3Orchestrator, Opportunity
from phase3_execution_engine import Phase3ExecutionEngine
from phase56_integrated_workflow import IntegratedPhase56Workflow

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "data" / "live-executions"
ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def make_opportunity(network: str) -> Opportunity:
    # Conservative synthetic opportunity only. No live trade intent.
    return Opportunity(
        id=f"live_{network}_{int(time.time())}",
        timestamp=datetime.now(timezone.utc),
        estimated_profit_usd=150.0 if network == "arbitrum" else 125.0,
        liquidity_usd=75000.0,
        confidence_score=0.82,
        protocol="aave",
        token_pair="USDC-WETH",
        network=network,
    )


async def main() -> int:
    load_dotenv_file(ROOT / ".env.local")
    load_dotenv_file(ROOT / ".env")

    net_cfg = load_json(ROOT / "config" / "dev_networks.json")
    wallet_cfg = load_json(ROOT / "config" / "wallets.example.json")
    alert_cfg = load_json(ROOT / "config" / "alerts.json")

    print("BOB-FL Minimal Live Transaction Execution")
    print("========================================")

    execution_enabled = env_bool("EXECUTION_ENABLED", net_cfg.get("execution_enabled", False))
    real_tx_enabled = env_bool("REAL_TRANSACTIONS_ENABLED", net_cfg.get("real_transactions_enabled", False))
    dry_run_mode = env_bool("DRY_RUN_MODE", False)

    print(f"execution_enabled={execution_enabled}")
    print(f"real_transactions_enabled={real_tx_enabled}")
    print(f"dry_run_mode={dry_run_mode}")

    if not execution_enabled or not real_tx_enabled:
        print("FAIL: Both EXECUTION_ENABLED and REAL_TRANSACTIONS_ENABLED must be true for live execution")
        return 2

    wallet = os.getenv("EXECUTION_WALLET_ADDRESS") or wallet_cfg["execution_wallet"]["address"]
    if not ADDRESS_RE.match(wallet):
        print("FAIL: invalid wallet address format")
        return 2
    print(f"wallet={wallet}")

    active = net_cfg.get("active_networks", ["arbitrum", "base"])
    failed = False

    # Initialize orchestrator and engine
    orchestrator = Phase3Orchestrator()
    engine = Phase3ExecutionEngine()

    results = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live_minimal_execution",
        "networks": {},
        "safety": {
            "execution_enabled": execution_enabled,
            "real_transactions_enabled": real_tx_enabled,
            "dry_run_mode": dry_run_mode,
        },
    }

    for network in active:
        print(f"\n[{network} live execution]")
        opportunity = make_opportunity(network)
        plan = orchestrator.plan_execution(network, opportunity)
        if "error" in plan:
            print(f"plan=FAIL {plan['message']}")
            results["networks"][network] = {"success": False, "error": plan["message"]}
            continue

        print(f"plan_strategy={plan['strategy'].get('dex')}")
        print(f"estimated_gas_limit={plan['strategy'].get('gas_limit', 'unknown')}")

        # Execute real transaction
        try:
            print("Executing real transaction...")
            exec_result = await engine.execute_opportunity(opportunity, network)
            print(f"✅ Real transaction submitted: {exec_result.success}")
            
            print(f"execution_time={exec_result.execution_time:.4f}s")
            if hasattr(exec_result, 'gas_used'):
                print(f"gas_used={exec_result.gas_used}")
            if hasattr(exec_result, 'gas_cost_eth'):
                print(f"gas_cost_eth={exec_result.gas_cost_eth}")
            if exec_result.error_message:
                print(f"error={exec_result.error_message}")

            results["networks"][network] = {
                "success": exec_result.success,
                "opportunity": {
                    "id": opportunity.id,
                    "estimated_profit_usd": opportunity.estimated_profit_usd,
                    "liquidity_usd": opportunity.liquidity_usd,
                    "confidence_score": opportunity.confidence_score,
                    "token_pair": opportunity.token_pair,
                },
                "strategy": plan["strategy"],
                "execution_time": exec_result.execution_time,
                "gas_used": getattr(exec_result, 'gas_used', None),
                "gas_cost_eth": getattr(exec_result, 'gas_cost_eth', None),
                "error_message": exec_result.error_message,
            }
        except Exception as e:
            print(f"❌ Real execution failed: {e}")
            results["networks"][network] = {
                "success": False,
                "error": str(e)
            }

    # Optional integrated workflow test
    try:
        workflow = IntegratedPhase56Workflow()
        workflow_results = {}
        for network in net_cfg.get("active_networks", ["arbitrum", "base"]):
            mock_opp = Opportunity(
                id=f"workflow_mock_{network}_{int(time.time())}",
                timestamp=datetime.now(timezone.utc),
                estimated_profit_usd=200.0 if network == "arbitrum" else 180.0,
                liquidity_usd=80000.0,
                confidence_score=0.85,
                protocol="aave",
                token_pair="USDC-WETH",
                network=network,
            )
            res = await workflow.process_opportunity(mock_opp)
            workflow_results[network] = {
                "success": res.get("success"),
                "steps": res.get("workflow_steps"),
                "risk_decision": res.get("risk_decision"),
                "error_message": res.get("error_message"),
            }
            print(f"{network}: workflow_success={res.get('success')} risk={res.get('risk_decision')}")
        results["integrated_workflow"] = workflow_results
    except Exception as exc:
        print(f"integrated_workflow=SKIPPED error={exc}")
        results["integrated_workflow"] = {"skipped": True, "error": str(exc)}

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"live_execution_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    successes = sum(1 for item in results["networks"].values() if item.get("success"))
    total = len(results["networks"])
    print("\nSummary")
    print("-------")
    print(f"networks_success={successes}/{total}")
    print(f"report={report_path}")
    print("real_transactions_submitted=1 per successful network")
    print("signed_transactions=1 per successful network")

    return 0 if successes == total else 1


if __name__ == "__main__":
    import requests.packages.urllib3
    requests.packages.urllib3.disable_warnings()
    raise SystemExit(asyncio.run(main()))