#!/usr/bin/env python3
"""Flash-loan execution handoff dispatcher.

Consumes the research agent handoff queues and enforces live-execution gates.
This is intentionally conservative: every candidate gets an explicit
why_not_executed list; live tx submission requires BOTH --execute and
REAL_TRANSACTIONS_ENABLED=true.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR if (SCRIPT_DIR / "live-flashloan").exists() else SCRIPT_DIR.parent
SCRIPT_ROOT = BASE_DIR if (BASE_DIR / "live_flashloan_scanner.py").exists() else BASE_DIR / "scripts"
HANDOFF_DIR = BASE_DIR / "data" / "execution-handoff"
READY_FILE = HANDOFF_DIR / "execution_ready.json"
NEEDS_VERIFICATION_FILE = HANDOFF_DIR / "needs_route_verification.json"
WHY_NOT_FILE = HANDOFF_DIR / "why_not_executed_report.json"
DISPATCH_LOG = HANDOFF_DIR / "dispatch_log.jsonl"
SUPPORTED_EXECUTION_SCANNERS = {"live", "comprehensive"}
MAX_GAS_USD = 2.0
MIN_NET_PROFIT_USD = 0.0


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def append_log(row: Dict[str, Any]) -> None:
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    with DISPATCH_LOG.open("a") as f:
        f.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def load_live_scanner():
    spec = importlib.util.spec_from_file_location("live_flashloan_scanner", SCRIPT_ROOT / "live_flashloan_scanner.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load live_flashloan_scanner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def candidate_raw(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("raw")
    if isinstance(raw, dict):
        return raw
    # Fallback for older handoff files; enough to explain blockers, not execute.
    return {
        "network": row.get("blockchain"),
        "borrow": row.get("borrow_asset"),
        "mid": row.get("mid_asset"),
        "amount": row.get("borrow_amount_raw"),
        "amount_human": row.get("borrow_amount_human"),
        "routerA": row.get("router_a"),
        "routerB": row.get("router_b"),
        "mid_out": row.get("mid_out_raw"),
        "final_out": row.get("final_out_raw"),
        "premium": row.get("aave_premium_raw"),
        "net_profit_usd": row.get("estimated_net_profit_usd"),
        "gas_usd": row.get("estimated_gas_cost_usd"),
    }


def gate_report(row: Dict[str, Any], execute_requested: bool, live_enabled: bool) -> Tuple[Dict[str, bool], List[str]]:
    source = row.get("source_scanner")
    raw = candidate_raw(row)
    gas = row.get("estimated_gas_cost_usd")
    if gas is None:
        gas = raw.get("estimated_gas_cost_usd", raw.get("gas_usd"))
    profit = row.get("estimated_net_profit_usd")
    if profit is None:
        profit = raw.get("net_profit_usd")

    try:
        gas_f = float(gas)
    except Exception:
        gas_f = 999999.0
    try:
        profit_f = float(profit)
    except Exception:
        profit_f = 0.0

    gates = {
        "source_allowed": source in SUPPORTED_EXECUTION_SCANNERS,
        "simulation_ok": bool(row.get("simulation_ok") or raw.get("simulation_ok")),
        "contract_address_present": bool(row.get("contract_address")),
        "gas_under_2_usd": gas_f <= MAX_GAS_USD,
        "net_profit_positive": profit_f > MIN_NET_PROFIT_USD,
        "live_flag_requested": bool(execute_requested),
        "live_env_enabled": bool(live_enabled),
    }
    why_not = [name for name, ok in gates.items() if not ok]
    return gates, why_not


def dispatch(execute: bool = False) -> Dict[str, Any]:
    ready_rows: List[Dict[str, Any]] = load_json(READY_FILE, [])
    needs_rows: List[Dict[str, Any]] = load_json(NEEDS_VERIFICATION_FILE, [])
    live_enabled = (
        os.getenv("REAL_TRANSACTIONS_ENABLED", "false").lower() == "true"
        and os.getenv("CONFIRM_LIVE_FLASHLOAN_EXECUTION", "no") == "YES"
    )
    live_mod = None
    scanners: Dict[str, Any] = {}
    decisions: List[Dict[str, Any]] = []

    all_rows = [("execution_ready", r) for r in ready_rows] + [("needs_route_verification", r) for r in needs_rows]

    for queue, row in all_rows:
        raw = candidate_raw(row)
        network = row.get("blockchain") or raw.get("network")
        gates, why_not = gate_report(row, execute, live_enabled)
        decision = {
            "timestamp_utc": now_iso(),
            "queue": queue,
            "opportunity_id": row.get("id"),
            "blockchain": network,
            "source_scanner": row.get("source_scanner"),
            "execute_requested": execute,
            "live_enabled": live_enabled,
            "gates": gates,
            "why_not_executed": why_not,
            "action": "not_executed",
            "tx_hash": None,
        }

        # Only rows that pass the static gates are eligible for dynamic revalidation.
        if not why_not:
            try:
                if live_mod is None:
                    live_mod = load_live_scanner()
                if network not in scanners:
                    scanners[network] = live_mod.Scanner(network, execute=False)
                scanner = scanners[network]
                sim_ok, sim_msg = scanner.simulate(raw)
                gas_units, gas_usd, gas_error = scanner.estimate_gas_usd(raw)
                decision["resimulation_ok"] = sim_ok
                decision["resimulation_message"] = sim_msg
                decision["reestimated_gas_units"] = gas_units
                decision["reestimated_gas_cost_usd"] = gas_usd
                decision["reestimated_gas_error"] = gas_error
                if not sim_ok:
                    decision["why_not_executed"].append("resimulation_failed")
                if gas_error:
                    decision["why_not_executed"].append("gas_reestimate_failed")
                if gas_usd is None or gas_usd > MAX_GAS_USD:
                    decision["why_not_executed"].append("reestimated_gas_over_2_usd")

                if not decision["why_not_executed"] and execute and live_enabled:
                    tx_hash = scanner.execute_live(raw)
                    decision["action"] = "executed"
                    decision["tx_hash"] = tx_hash
                elif not decision["why_not_executed"]:
                    decision["action"] = "validated_dry_run"
            except Exception as exc:
                decision["why_not_executed"].append("dispatcher_exception")
                decision["exception"] = str(exc)[:1000]

        append_log(decision)
        decisions.append(decision)

    summary = {
        "timestamp_utc": now_iso(),
        "ready_count": len(ready_rows),
        "needs_route_verification_count": len(needs_rows),
        "executed_count": len([d for d in decisions if d.get("action") == "executed"]),
        "validated_dry_run_count": len([d for d in decisions if d.get("action") == "validated_dry_run"]),
        "not_executed_count": len([d for d in decisions if d.get("action") == "not_executed"]),
        "decisions": decisions,
        "ready_file": str(READY_FILE),
        "needs_route_verification_file": str(NEEDS_VERIFICATION_FILE),
        "why_not_report_file": str(WHY_NOT_FILE),
    }
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    WHY_NOT_FILE.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Dispatch verified flash-loan opportunities")
    ap.add_argument("--execute", action="store_true", help="Request live execution; still requires REAL_TRANSACTIONS_ENABLED=true")
    args = ap.parse_args()
    print(json.dumps(dispatch(args.execute), indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
