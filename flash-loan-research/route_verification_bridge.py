#!/usr/bin/env python3
"""Promote Dexscreener market-spread signals only after real route verification.

Reads data/execution-handoff/needs_route_verification.json, attempts to convert
research-only signals into executable FlashLoanArbGeneric routes, and writes:
- data/execution-handoff/route_verification_report.json
- data/execution-handoff/execution_ready.json (merged, only passed rows)
- data/execution-handoff/needs_route_verification.json (remaining/rejected rows)

No live transactions are sent. This bridge only quotes, builds calldata, runs
eth_call/gas estimation through live_flashloan_scanner, and records decisions.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR if (SCRIPT_DIR / "live-flashloan").exists() else SCRIPT_DIR.parent
SCRIPT_ROOT = BASE_DIR if (BASE_DIR / "live_flashloan_scanner.py").exists() else BASE_DIR / "scripts"
HANDOFF_DIR = BASE_DIR / "data" / "execution-handoff"
READY_FILE = HANDOFF_DIR / "execution_ready.json"
NEEDS_FILE = HANDOFF_DIR / "needs_route_verification.json"
REPORT_FILE = HANDOFF_DIR / "route_verification_report.json"
LOG_FILE = HANDOFF_DIR / "route_verification_log.jsonl"

MAX_GAS_USD = 2.0
MIN_NET_PROFIT_USD = 0.0

# DEX names used by Dexscreener do not always map to routers. Only map names
# whose calldata style and router address are explicitly supported by
# live_flashloan_scanner.Scanner.build_params().
SWAAP_LABELS = {
    "0xd315a9c38ec871068fec378e4ce78af528c76293": "swaap_vault",
    "0x03c01acae3d0173a93d819efdc832c7c4f153b06": "swaap_safeguard_factory",
    "swaap": "swaap",
    "swaap finance": "swaap",
    "supernova": "swaap_or_supernova_unknown",
}

SUPPORTED_NAME_ALIASES = {
    "ethereum": {
        "uniswap": "UniswapV3",
        "uniswapv3": "UniswapV3",
        "sushiswap": "UniswapV3",  # unsupported exact pool; try dominant V3 quote before rejection
    },
    "optimism": {
        "uniswap": "UniswapV3",
        "uniswapv3": "UniswapV3",
        "velodrome": "VelodromeV2",
        "velodromev2": "VelodromeV2",
    },
    "arbitrum": {
        "camelot": "CamelotV2",
        "camelotv2": "CamelotV2",
        "sushi": "SushiSwapV2",
        "sushiswap": "SushiSwapV2",
        "sushiswapv2": "SushiSwapV2",
        "uniswap": "UniswapV3",
        "uniswapv3": "UniswapV3",
    },
    "base": {
        "aerodrome": "Aerodrome",
        "aerodrome finance": "Aerodrome",
        "aero": "Aerodrome",
        "uniswap": "UniswapV3",
        "uniswapv3": "UniswapV3",
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str))


def append_log(row: Dict[str, Any]) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def load_live_scanner_module():
    spec = importlib.util.spec_from_file_location("live_flashloan_scanner", SCRIPT_ROOT / "live_flashloan_scanner.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load live_flashloan_scanner.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_flashloan_scanner"] = mod
    spec.loader.exec_module(mod)
    return mod


def norm_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def compact_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def raw_candidate(row: Dict[str, Any]) -> Dict[str, Any]:
    raw = row.get("raw")
    if isinstance(raw, dict):
        return deepcopy(raw)
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


def route_label(row_or_raw: Dict[str, Any], leg: str) -> str:
    router = row_or_raw.get(leg) or {}
    if not isinstance(router, dict):
        return ""
    return router.get("name") or router.get("address") or ""


def unsupported_protocol_label(label: str) -> Optional[str]:
    keys = {norm_name(label), compact_name(label)}
    for key in keys:
        if key in SWAAP_LABELS:
            return SWAAP_LABELS[key]
    return None


def router_options_by_name(scanner: Any, network: str, label: str) -> List[Any]:
    aliases = SUPPORTED_NAME_ALIASES.get(network, {})
    keys = {norm_name(label), compact_name(label)}
    mapped = None
    for key in keys:
        if key in aliases:
            mapped = aliases[key]
            break
    if mapped is None:
        return []
    options = [router for router in scanner.cfg.get("routers", []) if router.name == mapped]
    # Dexscreener labels both Aerodrome V2 and Aerodrome Slipstream as "aerodrome".
    # Try both encoders on Base; final promotion still requires live quote + eth_call.
    if network == "base" and mapped == "Aerodrome":
        options.extend([router for router in scanner.cfg.get("routers", []) if router.name == "AerodromeSlipstream"])
    return options


def supported_router_by_name(scanner: Any, network: str, label: str):
    opts = router_options_by_name(scanner, network, label)
    return opts[0] if opts else None

def router_desc(router: Any) -> Optional[Dict[str, Any]]:
    if router is None:
        return None
    return {"name": router.name, "address": router.address, "kind": router.kind, "factory": getattr(router, "factory", None)}


def get_token(scanner: Any, symbol: str):
    try:
        return scanner.cfg["tokens"][symbol]
    except KeyError:
        return None


def float_or(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def leg_quotes(scanner: Any, router: Any, amount_in: int, token_in: Any, token_out: Any, leg_tag: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if router.kind == "v2":
        q = scanner.quote_v2(router, int(amount_in), [token_in.address, token_out.address])
        if q:
            out.append({"amount_out": int(q[-1]), "extra": {f"{leg_tag}_route_kind": "v2"}})
    elif router.kind == "aerodrome":
        for stable in [True, False]:
            q = scanner.quote_aero(int(amount_in), token_in.address, token_out.address, stable, router)
            if q:
                out.append({"amount_out": int(q[-1]), "extra": {f"stable{leg_tag.upper()}": stable, f"{leg_tag}_route_kind": "aerodrome"}})
    elif router.kind == "univ3":
        for fee in [100, 500, 3000, 10000]:
            q = scanner.quote_univ3(int(amount_in), token_in.address, token_out.address, fee)
            if q:
                out.append({"amount_out": int(q), "extra": {f"fee{leg_tag.upper()}": fee, f"{leg_tag}_route_kind": "univ3"}})
    elif router.kind == "slipstream":
        for tick_spacing in [1, 50, 100, 200, 2000]:
            q = scanner.quote_slipstream(int(amount_in), token_in.address, token_out.address, tick_spacing)
            if q:
                out.append({"amount_out": int(q), "extra": {f"tickSpacing{leg_tag.upper()}": tick_spacing, f"{leg_tag}_route_kind": "slipstream"}})
    return out


def candidate_variants(scanner: Any, row: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    raw = raw_candidate(row)
    network = row.get("blockchain") or raw.get("network")
    borrow_sym = row.get("borrow_asset") or raw.get("borrow")
    mid_sym = row.get("mid_asset") or raw.get("mid")
    amount = row.get("borrow_amount_raw") or raw.get("amount")
    amount_human = row.get("borrow_amount_human") or raw.get("amount_human")
    reasons: List[str] = []

    if network not in ("ethereum", "optimism", "arbitrum", "base"):
        reasons.append("unsupported_network_for_deployed_route")
    borrow = get_token(scanner, borrow_sym) if borrow_sym else None
    mid = get_token(scanner, mid_sym) if mid_sym else None
    if borrow is None or mid is None:
        reasons.append("unsupported_token_pair")
    if not amount:
        reasons.append("missing_borrow_amount")
    if reasons:
        return [], reasons

    label_a = route_label(raw, "routerA") or route_label(row, "router_a")
    label_b = route_label(raw, "routerB") or route_label(row, "router_b")
    routers_a = router_options_by_name(scanner, network, label_a)
    routers_b = router_options_by_name(scanner, network, label_b)
    if not routers_a:
        proto = unsupported_protocol_label(label_a)
        reasons.append(f"unsupported_protocol_a:{proto}" if proto else f"unsupported_router_a:{label_a or 'unknown'}")
    if not routers_b:
        proto = unsupported_protocol_label(label_b)
        reasons.append(f"unsupported_protocol_b:{proto}" if proto else f"unsupported_router_b:{label_b or 'unknown'}")
    if reasons:
        return [], reasons

    variants: List[Dict[str, Any]] = []
    any_qas = False
    any_qbs = False
    for router_a in routers_a:
        qas = leg_quotes(scanner, router_a, int(amount), borrow, mid, "A")
        if qas:
            any_qas = True
        for qa in qas:
            for router_b in routers_b:
                qbs = leg_quotes(scanner, router_b, int(qa["amount_out"]), mid, borrow, "B")
                if qbs:
                    any_qbs = True
                for qb in qbs:
                    extra = {}
                    extra.update(qa["extra"])
                    extra.update(qb["extra"])
                    route_kind = "mixed"
                    if extra.get("A_route_kind") == extra.get("B_route_kind"):
                        route_kind = extra.get("A_route_kind")
                    extra["route_kind"] = route_kind
                    before = len(variants)
                    scanner.add_candidate(
                        variants,
                        borrow_sym,
                        mid_sym,
                        float_or(amount_human),
                        int(amount),
                        router_a,
                        router_b,
                        int(qa["amount_out"]),
                        int(qb["amount_out"]),
                        **extra,
                    )
                    if len(variants) > before:
                        variants[-1].update({
                            "network": network,
                            "research_bridge_source_id": row.get("id"),
                            "research_source": "route_verification_bridge",
                        })
    if not variants:
        if not any_qas:
            return [], ["router_a_quote_failed"]
        if not any_qbs:
            return [], ["router_b_quote_failed"]
        return [], ["no_profitable_supported_route_quote"]
    variants.sort(key=lambda c: float_or(c.get("net_profit_usd")), reverse=True)
    return variants, []

def row_from_verified(row: Dict[str, Any], c: Dict[str, Any], scanner: Any, gas_units: Optional[int], gas_usd: Optional[float], sim_msg: str) -> Dict[str, Any]:
    out = deepcopy(row)
    ts = now_iso()
    out.update({
        "status": "open",
        "contract_address": scanner.contract_addr,
        "flashloan_category": "cross-DEX arbitrage",
        "borrow_asset": c.get("borrow"),
        "borrow_amount_human": c.get("amount_human"),
        "borrow_amount_raw": c.get("amount"),
        "mid_asset": c.get("mid"),
        "router_a": c.get("routerA"),
        "router_b": c.get("routerB"),
        "mid_out_raw": c.get("mid_out"),
        "final_out_raw": c.get("final_out"),
        "aave_premium_raw": c.get("premium"),
        "estimated_gross_profit_token": c.get("gross_profit_token"),
        "estimated_gas_cost_usd": gas_usd,
        "estimated_net_profit_usd": c.get("net_profit_usd"),
        "simulation_ok": True,
        "simulation_message": sim_msg,
        "source_scanner": "live",
        "route_verified_by": "route_verification_bridge",
        "route_verified_at_utc": ts,
        "estimated_gas_units": gas_units,
        "raw": c,
        "notes": "Promoted by route_verification_bridge after on-chain quote, gas estimate, and eth_call simulation. No live transaction was sent by verifier.",
    })
    out["id"] = f"{row.get('id', 'unknown')}-rv"
    ra = c.get("routerA") or {}
    rb = c.get("routerB") or {}
    out["flashloan_path"] = (
        f"Borrow {c.get('amount_human')} {c.get('borrow')} via Aave flash loan -> "
        f"swap {c.get('borrow')} to {c.get('mid')} on {ra.get('name')} ({ra.get('address')}) -> "
        f"swap {c.get('mid')} back to {c.get('borrow')} on {rb.get('name')} ({rb.get('address')}) -> repay loan + premium"
    )
    return out


def verify(limit: int = 20, min_profit: float = 0.0, write: bool = True) -> Dict[str, Any]:
    live_mod = load_live_scanner_module()
    rows: List[Dict[str, Any]] = load_json(NEEDS_FILE, [])
    ready_existing: List[Dict[str, Any]] = load_json(READY_FILE, [])

    # Highest reported research profit first, then recent-ish original order.
    rows_sorted = sorted(rows, key=lambda r: float_or(r.get("estimated_net_profit_usd")), reverse=True)
    selected = rows_sorted[: max(0, int(limit))]

    scanners: Dict[str, Any] = {}
    decisions: List[Dict[str, Any]] = []
    promoted: List[Dict[str, Any]] = []
    selected_ids = {r.get("id") for r in selected}

    for row in selected:
        network = row.get("blockchain") or (row.get("raw") or {}).get("network")
        decision = {
            "timestamp_utc": now_iso(),
            "opportunity_id": row.get("id"),
            "blockchain": network,
            "reported_net_profit_usd": row.get("estimated_net_profit_usd"),
            "action": "not_promoted",
            "why_not_promoted": [],
        }
        try:
            if network not in ("ethereum", "optimism", "arbitrum", "base"):
                decision["why_not_promoted"].append("unsupported_network_for_deployed_route")
            else:
                if network not in scanners:
                    scanners[network] = live_mod.Scanner(network, execute=False)
                scanner = scanners[network]
                variants, reasons = candidate_variants(scanner, row)
                if reasons:
                    decision["why_not_promoted"].extend(reasons)
                best_detail = None
                for c in variants:
                    if float_or(c.get("net_profit_usd")) <= min_profit:
                        continue
                    gas_units, gas_usd, gas_error = scanner.estimate_gas_usd(c)
                    sim_ok, sim_msg = scanner.simulate(c)
                    detail = {
                        "route_kind": c.get("route_kind"),
                        "routerA": c.get("routerA"),
                        "routerB": c.get("routerB"),
                        "net_profit_usd": c.get("net_profit_usd"),
                        "gas_units": gas_units,
                        "gas_usd": gas_usd,
                        "gas_error": gas_error,
                        "simulation_ok": sim_ok,
                        "simulation_message": sim_msg,
                    }
                    best_detail = detail
                    blockers = []
                    if gas_error:
                        blockers.append("gas_estimate_failed")
                    if gas_usd is None or float_or(gas_usd, 999999.0) > MAX_GAS_USD:
                        blockers.append("gas_over_2_usd")
                    if not sim_ok:
                        blockers.append("simulation_failed")
                    if float_or(c.get("net_profit_usd")) <= MIN_NET_PROFIT_USD:
                        blockers.append("net_profit_not_positive")
                    if not blockers:
                        promoted_row = row_from_verified(row, c, scanner, gas_units, gas_usd, sim_msg)
                        promoted.append(promoted_row)
                        decision.update({
                            "action": "promoted",
                            "promoted_id": promoted_row.get("id"),
                            "verified_detail": detail,
                            "why_not_promoted": [],
                        })
                        break
                    if blockers and not decision["why_not_promoted"]:
                        decision["why_not_promoted"].extend(blockers)
                if decision["action"] != "promoted" and best_detail is not None:
                    decision["best_attempt"] = best_detail
                if decision["action"] != "promoted" and not decision["why_not_promoted"]:
                    decision["why_not_promoted"].append("no_supported_profitable_route_variant")
        except Exception as exc:
            msg = str(exc)[:1200]
            low = msg.lower()
            if "429" in low or "too many requests" in low:
                decision["why_not_promoted"].append("rpc_rate_limited")
            elif "rpc not connected" in low:
                decision["why_not_promoted"].append("rpc_not_connected")
            elif "gas_price_fetch_failed" in low:
                decision["why_not_promoted"].append("rpc_gas_price_fetch_failed")
            else:
                decision["why_not_promoted"].append("bridge_exception")
            decision["exception"] = msg
        decisions.append(decision)
        append_log(decision)

    promoted_source_ids = {p.get("research_bridge_source_id") or (p.get("raw") or {}).get("research_bridge_source_id") for p in promoted}
    if write:
        # Merge promoted rows with existing ready rows, replacing older promoted rows
        # for the same source id to keep repeated verifier runs idempotent.
        existing_filtered = []
        for r in ready_existing:
            src = r.get("research_bridge_source_id") or (r.get("raw") or {}).get("research_bridge_source_id")
            if src not in promoted_source_ids:
                existing_filtered.append(r)
        ready_out = existing_filtered + promoted
        remaining_needs = [r for r in rows if r.get("id") not in promoted_source_ids]
        write_json(READY_FILE, ready_out)
        write_json(NEEDS_FILE, remaining_needs)
    else:
        ready_out = ready_existing + promoted
        remaining_needs = rows

    summary = {
        "timestamp_utc": now_iso(),
        "mode": "write" if write else "dry_run",
        "selected_count": len(selected),
        "input_needs_count": len(rows),
        "promoted_count": len(promoted),
        "ready_count_after": len(ready_out),
        "needs_route_verification_count_after": len(remaining_needs),
        "max_gas_usd": MAX_GAS_USD,
        "min_net_profit_usd": MIN_NET_PROFIT_USD,
        "decisions": decisions,
        "ready_file": str(READY_FILE),
        "needs_route_verification_file": str(NEEDS_FILE),
        "report_file": str(REPORT_FILE),
    }
    if write:
        write_json(REPORT_FILE, summary)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify/promote Dexscreener research signals into route-verified handoff rows")
    ap.add_argument("--limit", type=int, default=20, help="max top-profit needs_route_verification rows to test")
    ap.add_argument("--min-profit", type=float, default=0.0, help="minimum verified net profit in USD")
    ap.add_argument("--dry-run", action="store_true", help="do not rewrite handoff files")
    args = ap.parse_args()
    out = verify(limit=args.limit, min_profit=args.min_profit, write=not args.dry_run)
    print(json.dumps({k: v for k, v in out.items() if k != "decisions"}, indent=2, sort_keys=True, default=str))
    for d in out["decisions"][:10]:
        print(json.dumps(d, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
