#!/usr/bin/env python3
"""Hourly flash-loan research agent and daily reporter.

Research-only by default: runs scanner scripts without --execute, records every
candidate in a persistent register, tracks when an opportunity disappears, and
can send a daily 09:00 SAST Telegram report through OpenClaw's message CLI.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR if (SCRIPT_DIR / "live-flashloan").exists() else SCRIPT_DIR.parent
SCRIPT_ROOT = BASE_DIR if (BASE_DIR / "live_flashloan_scanner.py").exists() else BASE_DIR / "scripts"
PYTHON = BASE_DIR / "venv" / "bin" / "python"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)

DATA_DIR = BASE_DIR / "data"
REGISTER_DIR = DATA_DIR / "opportunity-register"
REPORT_DIR = DATA_DIR / "reports"
HANDOFF_DIR = DATA_DIR / "execution-handoff"
LOG_DIR = BASE_DIR / "logs"
STATE_FILE = REGISTER_DIR / "flashloan_opportunity_register.json"
CSV_FILE = REGISTER_DIR / "flashloan_opportunity_register.csv"
EXECUTION_READY_FILE = HANDOFF_DIR / "execution_ready.json"
NEEDS_ROUTE_VERIFICATION_FILE = HANDOFF_DIR / "needs_route_verification.json"
SCAN_LOG = LOG_DIR / "research-agent.log"
LOCAL_TZ = ZoneInfo("Africa/Johannesburg")
STALE_AFTER_HOURS = 2
DEFAULT_NETWORKS = ["ethereum", "optimism", "arbitrum", "base"]
SCANNERS = [
    # Deployed-contract route scanners cover all configured networks with strict route support gates.
    {"name": "live", "script": "live_flashloan_scanner.py", "networks": set(DEFAULT_NETWORKS)},
    {"name": "comprehensive", "script": "comprehensive_flash_loan_scanner.py", "networks": set(DEFAULT_NETWORKS)},
    # Market-spread research scanner covers Ethereum, Optimism, Arbitrum, and Base.
    {"name": "market_spread", "script": "market_spread_flashloan_scanner.py", "networks": set(DEFAULT_NETWORKS)},
]
STABLES = {"USDC", "USDT", "DAI", "USDbC"}
TOKEN_PRICE_USD = {
    "USDC": 1.0,
    "USDT": 1.0,
    "DAI": 1.0,
    "USDbC": 1.0,
    "WETH": 1566.32,
    "ETH": 1566.32,
}


def load_env_local() -> None:
    """Minimal .env.local loader; avoids printing or exposing secrets."""
    env_path = BASE_DIR / ".env.local"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{iso(now_utc())} {msg}\n"
    with SCAN_LOG.open("a") as f:
        f.write(line)
    print(line, end="")


def load_state() -> Dict[str, Any]:
    REGISTER_DIR.mkdir(parents=True, exist_ok=True)
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            backup = STATE_FILE.with_suffix(f".broken.{int(now_utc().timestamp())}.json")
            STATE_FILE.rename(backup)
            log(f"WARN state file was invalid JSON; moved to {backup}")
    return {"version": 1, "created_at": iso(now_utc()), "opportunities": {}}


def save_state(state: Dict[str, Any]) -> None:
    state["updated_at"] = iso(now_utc())
    REGISTER_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True, default=str))
    tmp.replace(STATE_FILE)
    write_csv(state)
    write_execution_handoff(state)


def write_csv(state: Dict[str, Any]) -> None:
    rows = list(state.get("opportunities", {}).values())
    fields = [
        "id", "status", "blockchain", "wallet_address", "contract_address",
        "flashloan_path", "flashloan_category", "assets", "asset_prices_usd",
        "borrow_asset", "borrow_amount_human", "mid_asset", "estimated_net_profit_usd",
        "estimated_gross_profit_token", "estimated_gas_cost_usd", "confidence_score",
        "simulation_ok", "simulation_message", "date_time_identified_utc",
        "date_time_identified_sast", "last_seen_utc", "date_time_resolved_utc",
        "date_time_resolved_sast", "resolution_transaction_id", "resolution_type",
        "source_scanner", "notes",
    ]
    with CSV_FILE.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=lambda r: r.get("date_time_identified_utc", "")):
            out = dict(row)
            for key in ["assets", "asset_prices_usd"]:
                if not isinstance(out.get(key), str):
                    out[key] = json.dumps(out.get(key), sort_keys=True)
            writer.writerow(out)


def is_execution_ready(row: Dict[str, Any]) -> bool:
    """Only fully simulated deployed-route candidates go to execution-ready."""
    if row.get("status") != "open":
        return False
    if row.get("source_scanner") not in {"live", "comprehensive"}:
        return False
    if not row.get("simulation_ok"):
        return False
    if not row.get("contract_address"):
        return False
    try:
        gas = float(row.get("estimated_gas_cost_usd") or 999999)
        net = float(row.get("estimated_net_profit_usd") or 0)
    except Exception:
        return False
    return gas <= 2.0 and net > 0


def needs_route_verification(row: Dict[str, Any]) -> bool:
    """Research signals are not executable until route quote + eth_call pass."""
    return row.get("status") == "open" and not is_execution_ready(row)


def write_execution_handoff(state: Dict[str, Any]) -> None:
    rows = list(state.get("opportunities", {}).values())
    ready = [r for r in rows if is_execution_ready(r)]
    needs_verification = [r for r in rows if needs_route_verification(r)]
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    EXECUTION_READY_FILE.write_text(json.dumps(ready, indent=2, sort_keys=True, default=str))
    NEEDS_ROUTE_VERIFICATION_FILE.write_text(json.dumps(needs_verification, indent=2, sort_keys=True, default=str))
    summary = {
        "timestamp_utc": iso(now_utc()),
        "execution_ready_count": len(ready),
        "needs_route_verification_count": len(needs_verification),
        "policy": "BTC-volatility gate removed; execution is driven only by research register handoff.",
    }
    (HANDOFF_DIR / "handoff_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))


def run_scanner(scanner_name: str, script_name: str, network: str) -> Tuple[Optional[Dict[str, Any]], str]:
    cmd = [str(PYTHON), str(SCRIPT_ROOT / script_name), "--network", network]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(BASE_DIR),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=900,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except subprocess.TimeoutExpired:
        return None, f"timeout running {' '.join(cmd)}"

    out_file = BASE_DIR / f"{scanner_name.upper() if scanner_name != 'live' else 'LIVE'}_FLASHLOAN_SCAN_{network.upper()}.json"
    if scanner_name == "comprehensive":
        out_file = BASE_DIR / f"COMPREHENSIVE_FLASHLOAN_SCAN_{network.upper()}.json"
    elif scanner_name == "market_spread":
        out_file = BASE_DIR / f"MARKET_SPREAD_FLASHLOAN_SCAN_{network.upper()}.json"

    if proc.returncode != 0:
        return None, f"returncode={proc.returncode}; stderr={proc.stderr[-1200:]}"
    if not out_file.exists():
        return None, f"scanner finished but output file not found: {out_file}"
    try:
        data = json.loads(out_file.read_text())
        data["source_scanner"] = scanner_name
        return data, proc.stdout[-2000:]
    except Exception as exc:
        return None, f"could not read {out_file}: {exc}"


def opportunity_key(network: str, scanner: str, c: Dict[str, Any]) -> str:
    router_a = (c.get("routerA") or {}).get("name") or (c.get("routerA") or {}).get("address")
    router_b = (c.get("routerB") or {}).get("name") or (c.get("routerB") or {}).get("address")
    parts = [
        network,
        scanner,
        str(c.get("borrow")),
        str(c.get("mid")),
        str(c.get("amount_human")),
        str(router_a),
        str(router_b),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def asset_prices_for(c: Dict[str, Any]) -> Dict[str, Optional[float]]:
    assets = [c.get("borrow"), c.get("mid")]
    prices = {a: TOKEN_PRICE_USD.get(a) for a in assets if a}
    if c.get("mid") and (c.get("low_price_usd") is not None or c.get("high_price_usd") is not None):
        prices[c["mid"]] = {
            "low_price_usd": c.get("low_price_usd"),
            "high_price_usd": c.get("high_price_usd"),
        }
    return prices


def path_for(c: Dict[str, Any]) -> str:
    ra = c.get("routerA") or {}
    rb = c.get("routerB") or {}
    return (
        f"Borrow {c.get('amount_human')} {c.get('borrow')} via Aave flash loan -> "
        f"swap {c.get('borrow')} to {c.get('mid')} on {ra.get('name', 'routerA')} "
        f"({ra.get('address', 'unknown')}) -> swap {c.get('mid')} back to {c.get('borrow')} "
        f"on {rb.get('name', 'routerB')} ({rb.get('address', 'unknown')}) -> repay loan + premium"
    )


def category_for(c: Dict[str, Any]) -> str:
    ra = c.get("routerA") or {}
    rb = c.get("routerB") or {}
    if c.get("research_source") == "dexscreener token-pairs":
        return "cross-DEX market-spread research signal"
    if c.get("borrow") and c.get("mid") and ra.get("address") and rb.get("address"):
        return "cross-DEX arbitrage"
    return "flash-loan opportunity"


def normalize_candidate(scan: Dict[str, Any], c: Dict[str, Any], identified_at: datetime) -> Dict[str, Any]:
    network = scan.get("network") or c.get("network") or "unknown"
    scanner = scan.get("source_scanner", "unknown")
    oid = opportunity_key(network, scanner, c)
    identified_sast = identified_at.astimezone(LOCAL_TZ)
    wallet = os.environ.get("WALLET_ADDRESS") or "configured in .env.local"
    return {
        "id": oid,
        "status": "open",
        "blockchain": network,
        "wallet_address": wallet,
        "contract_address": scan.get("contract"),
        "flashloan_path": path_for(c),
        "flashloan_category": category_for(c),
        "assets": [a for a in [c.get("borrow"), c.get("mid")] if a],
        "asset_prices_usd": asset_prices_for(c),
        "borrow_asset": c.get("borrow"),
        "borrow_amount_human": c.get("amount_human"),
        "borrow_amount_raw": c.get("amount"),
        "mid_asset": c.get("mid"),
        "router_a": c.get("routerA"),
        "router_b": c.get("routerB"),
        "mid_out_raw": c.get("mid_out"),
        "final_out_raw": c.get("final_out"),
        "aave_premium_raw": c.get("premium"),
        "spread_bps": c.get("spread_bps"),
        "low_price_usd": c.get("low_price_usd"),
        "high_price_usd": c.get("high_price_usd"),
        "liquidity_usd_low_pool": c.get("liquidity_usd_low_pool"),
        "liquidity_usd_high_pool": c.get("liquidity_usd_high_pool"),
        "volume_24h_usd_low_pool": c.get("volume_24h_usd_low_pool"),
        "volume_24h_usd_high_pool": c.get("volume_24h_usd_high_pool"),
        "estimated_gross_profit_token": c.get("gross_profit_token"),
        "estimated_gas_cost_usd": c.get("estimated_gas_cost_usd", c.get("gas_usd")),
        "estimated_net_profit_usd": c.get("net_profit_usd"),
        "confidence_score": confidence(c),
        "simulation_ok": bool(c.get("simulation_ok")),
        "simulation_message": c.get("simulation_message"),
        "date_time_identified_utc": iso(identified_at),
        "date_time_identified_sast": identified_sast.replace(microsecond=0).isoformat(),
        "last_seen_utc": iso(identified_at),
        "last_seen_sast": identified_sast.replace(microsecond=0).isoformat(),
        "date_time_resolved_utc": None,
        "date_time_resolved_sast": None,
        "resolution_transaction_id": c.get("tx_hash"),
        "resolution_type": "executed_by_agent" if c.get("tx_hash") else None,
        "source_scanner": scanner,
        "raw": c,
        "notes": "Research-only scan. Live execution disabled unless explicitly requested and approved.",
    }


def confidence(c: Dict[str, Any]) -> float:
    score = 0.35
    if c.get("net_profit_usd", 0) and c.get("net_profit_usd", 0) > 0:
        score += 0.2
    if c.get("simulation_ok"):
        score += 0.35
    if c.get("gas_usd") is not None:
        score += 0.1
    return round(min(score, 1.0), 2)


def update_register(scans: List[Dict[str, Any]], state: Dict[str, Any], scan_time: datetime) -> Dict[str, Any]:
    seen: set[str] = set()
    new_count = 0
    updated_count = 0
    state.setdefault("opportunities", {})

    for scan in scans:
        for c in scan.get("results", []) or []:
            oid = opportunity_key(
                scan.get("network") or c.get("network") or "unknown",
                scan.get("source_scanner", "unknown"),
                c,
            )
            seen.add(oid)
            normalized = normalize_candidate(scan, c, scan_time)
            existing = state["opportunities"].get(oid)
            if existing:
                first_identified_utc = existing.get("date_time_identified_utc")
                first_identified_sast = existing.get("date_time_identified_sast")
                resolution_tx = existing.get("resolution_transaction_id")
                resolution_type = existing.get("resolution_type")
                existing.update(normalized)
                existing["date_time_identified_utc"] = first_identified_utc
                existing["date_time_identified_sast"] = first_identified_sast
                existing["status"] = "open"
                existing["date_time_resolved_utc"] = None
                existing["date_time_resolved_sast"] = None
                existing["resolution_transaction_id"] = normalized.get("resolution_transaction_id") or resolution_tx
                existing["resolution_type"] = normalized.get("resolution_type") or resolution_type
                existing["seen_count"] = int(existing.get("seen_count", 1)) + 1
                updated_count += 1
            else:
                normalized["seen_count"] = 1
                state["opportunities"][oid] = normalized
                new_count += 1

    # Resolve open opportunities that have not been seen for a while. In a research
    # register, "resolved" means the market condition disappeared unless a tx hash
    # is explicitly recorded.
    cutoff = scan_time - timedelta(hours=STALE_AFTER_HOURS)
    resolved_count = 0
    for row in state["opportunities"].values():
        if row.get("status") != "open" or row.get("id") in seen:
            continue
        last_seen_raw = row.get("last_seen_utc")
        try:
            last_seen = datetime.fromisoformat(last_seen_raw.replace("Z", "+00:00")) if last_seen_raw else scan_time
        except Exception:
            last_seen = scan_time
        if last_seen < cutoff:
            row["status"] = "resolved"
            row["date_time_resolved_utc"] = iso(scan_time)
            row["date_time_resolved_sast"] = scan_time.astimezone(LOCAL_TZ).replace(microsecond=0).isoformat()
            row["resolution_type"] = row.get("resolution_type") or "market_condition_disappeared"
            row["resolution_transaction_id"] = row.get("resolution_transaction_id") or None
            resolved_count += 1

    state["last_scan"] = {
        "timestamp_utc": iso(scan_time),
        "timestamp_sast": scan_time.astimezone(LOCAL_TZ).replace(microsecond=0).isoformat(),
        "scans_completed": len(scans),
        "candidates_seen": len(seen),
        "new_opportunities": new_count,
        "updated_opportunities": updated_count,
        "resolved_opportunities": resolved_count,
    }
    return state


def scan(networks: Iterable[str]) -> Dict[str, Any]:
    scan_time = now_utc()
    state = load_state()
    scans: List[Dict[str, Any]] = []
    errors: List[str] = []

    for network in networks:
        for scanner in SCANNERS:
            scanner_name = scanner["name"]
            script_name = scanner["script"]
            if network not in scanner["networks"]:
                log(f"scan skip scanner={scanner_name} network={network} reason=unsupported")
                continue
            log(f"scan start scanner={scanner_name} network={network}")
            data, detail = run_scanner(scanner_name, script_name, network)
            if data is None:
                err = f"scanner={scanner_name} network={network} failed: {detail}"
                errors.append(err)
                log("ERROR " + err)
                continue
            scans.append(data)
            log(
                f"scan ok scanner={scanner_name} network={network} "
                f"candidates_found={data.get('candidates_found')} results={len(data.get('results') or [])}"
            )

    state = update_register(scans, state, scan_time)
    state["last_errors"] = errors[-10:]
    save_state(state)
    log(
        "scan complete "
        + json.dumps({**state.get("last_scan", {}), "errors": len(errors)}, sort_keys=True)
    )
    return {"state": state, "errors": errors}


def opportunities_in_period(state: Dict[str, Any], start: datetime, end: datetime) -> List[Dict[str, Any]]:
    rows = []
    for row in state.get("opportunities", {}).values():
        raw = row.get("date_time_identified_utc") or row.get("last_seen_utc")
        if not raw:
            continue
        try:
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            continue
        if start <= ts <= end:
            rows.append(row)
    return rows


def build_report_text(rows: List[Dict[str, Any]], start: datetime, end: datetime, state: Dict[str, Any]) -> str:
    by_chain = Counter(r.get("blockchain", "unknown") for r in rows)
    by_type = Counter(r.get("flashloan_category", "unknown") for r in rows)
    open_rows = [r for r in state.get("opportunities", {}).values() if r.get("status") == "open"]
    resolved_rows = [r for r in rows if r.get("status") == "resolved"]
    top = sorted(rows, key=lambda r: float(r.get("estimated_net_profit_usd") or 0), reverse=True)[:5]

    lines = [
        "Flash Loan Research Daily Report",
        f"Period: {start.astimezone(LOCAL_TZ).strftime('%Y-%m-%d %H:%M')} to {end.astimezone(LOCAL_TZ).strftime('%Y-%m-%d %H:%M')} SAST",
        f"Total opportunities identified: {len(rows)}",
        f"Currently open opportunities in register: {len(open_rows)}",
        f"Resolved in period: {len(resolved_rows)}",
        "",
        "Opportunities by blockchain:",
    ]
    if by_chain:
        lines += [f"- {chain}: {count}" for chain, count in sorted(by_chain.items())]
    else:
        lines.append("- None found")

    lines += ["", "Opportunities by category:"]
    if by_type:
        lines += [f"- {typ}: {count}" for typ, count in sorted(by_type.items())]
    else:
        lines.append("- None")

    lines += ["", "Top opportunities:"]
    if top:
        for i, r in enumerate(top, 1):
            lines.append(
                f"{i}. {r.get('blockchain')} | {r.get('borrow_amount_human')} {r.get('borrow_asset')} -> "
                f"{r.get('mid_asset')} -> {r.get('borrow_asset')} | "
                f"net ${float(r.get('estimated_net_profit_usd') or 0):.4f} | "
                f"status {r.get('status')} | id {r.get('id')}"
            )
    else:
        lines.append("- No candidate opportunities found in the period.")

    ready_count = len([r for r in state.get("opportunities", {}).values() if is_execution_ready(r)])
    needs_verify_count = len([r for r in state.get("opportunities", {}).values() if needs_route_verification(r)])

    lines += [
        "",
        "Execution handoff:",
        f"- Execution-ready candidates: {ready_count}",
        f"- Needs route verification: {needs_verify_count}",
        "- BTC 2% volatility trigger: disabled/removed from active workflow",
        "",
        "Register files:",
        f"- JSON: {STATE_FILE}",
        f"- CSV: {CSV_FILE}",
        f"- Execution-ready queue: {EXECUTION_READY_FILE}",
        f"- Route-verification queue: {NEEDS_ROUTE_VERIFICATION_FILE}",
        "",
        "Notes: Research scanning is not gated by BTC movement. Execution is not performed by the research job; "
        "only verified candidates are handed to the flashloan execution dispatcher. Market-spread signals require "
        "route quote + eth_call simulation before execution. Resolved means the opportunity was no longer observed "
        "for the stale window unless a transaction id is recorded.",
    ]
    if state.get("last_errors"):
        lines += ["", "Recent scanner warnings:"]
        lines += [f"- {e[:220]}" for e in state.get("last_errors", [])[-3:]]
    return "\n".join(lines)


def write_report(rows: List[Dict[str, Any]], start: datetime, end: datetime, state: Dict[str, Any]) -> Tuple[Path, str]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "report_date_utc": iso(end),
        "report_date_sast": end.astimezone(LOCAL_TZ).replace(microsecond=0).isoformat(),
        "period_start_utc": iso(start),
        "period_end_utc": iso(end),
        "total_opportunities": len(rows),
        "opportunities_by_blockchain": dict(Counter(r.get("blockchain", "unknown") for r in rows)),
        "opportunities_by_category": dict(Counter(r.get("flashloan_category", "unknown") for r in rows)),
        "currently_open_register_count": len([r for r in state.get("opportunities", {}).values() if r.get("status") == "open"]),
        "opportunities": rows,
        "register_json": str(STATE_FILE),
        "register_csv": str(CSV_FILE),
        "execution_ready_file": str(EXECUTION_READY_FILE),
        "needs_route_verification_file": str(NEEDS_ROUTE_VERIFICATION_FILE),
        "execution_ready_count": len([r for r in state.get("opportunities", {}).values() if is_execution_ready(r)]),
        "needs_route_verification_count": len([r for r in state.get("opportunities", {}).values() if needs_route_verification(r)]),
        "btc_volatility_gate": "disabled",
        "last_scan": state.get("last_scan"),
        "last_errors": state.get("last_errors", []),
    }
    path = REPORT_DIR / f"{end.astimezone(LOCAL_TZ).strftime('%Y-%m-%d')}_flash_loan_research_report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str))
    text = build_report_text(rows, start, end, state)
    (REPORT_DIR / f"{end.astimezone(LOCAL_TZ).strftime('%Y-%m-%d')}_flash_loan_research_report.txt").write_text(text)
    return path, text


def send_telegram(text: str, target: str) -> None:
    cmd = [
        "openclaw", "message", "send",
        "--channel", "telegram",
        "--target", target,
        "--message", text[:3900],
    ]
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f"openclaw message send failed: {proc.stderr[-1000:]}")


def report(send: bool, target: Optional[str]) -> Dict[str, Any]:
    end = now_utc()
    start = end - timedelta(hours=24)
    state = load_state()
    rows = opportunities_in_period(state, start, end)
    path, text = write_report(rows, start, end, state)
    log(f"report written path={path} opportunities={len(rows)}")
    if send:
        if not target:
            raise ValueError("--target is required with --send")
        send_telegram(text, target)
        log(f"report sent target={target}")
    return {"path": str(path), "text": text, "opportunities": len(rows)}


def status() -> Dict[str, Any]:
    state = load_state()
    rows = list(state.get("opportunities", {}).values())
    return {
        "register_json": str(STATE_FILE),
        "register_csv": str(CSV_FILE),
        "execution_ready_file": str(EXECUTION_READY_FILE),
        "needs_route_verification_file": str(NEEDS_ROUTE_VERIFICATION_FILE),
        "total_registered": len(rows),
        "open": len([r for r in rows if r.get("status") == "open"]),
        "resolved": len([r for r in rows if r.get("status") == "resolved"]),
        "execution_ready": len([r for r in rows if is_execution_ready(r)]),
        "needs_route_verification": len([r for r in rows if needs_route_verification(r)]),
        "btc_volatility_gate": "disabled",
        "last_scan": state.get("last_scan"),
        "last_errors": state.get("last_errors", []),
    }


def main() -> None:
    load_env_local()
    ap = argparse.ArgumentParser(description="Flash-loan research agent")
    sub = ap.add_subparsers(dest="command", required=True)

    scan_ap = sub.add_parser("scan", help="Run one research scan")
    scan_ap.add_argument("--networks", nargs="+", default=DEFAULT_NETWORKS)

    report_ap = sub.add_parser("report", help="Generate daily report")
    report_ap.add_argument("--send", action="store_true", help="Send report via OpenClaw Telegram")
    report_ap.add_argument("--target", help="Telegram chat id or username")

    sub.add_parser("status", help="Print register status")

    args = ap.parse_args()
    if args.command == "scan":
        result = scan(args.networks)
    elif args.command == "report":
        result = report(args.send, args.target)
    elif args.command == "status":
        result = status()
    else:
        raise AssertionError(args.command)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
