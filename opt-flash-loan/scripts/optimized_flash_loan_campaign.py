#!/usr/bin/env python3
"""Safe flash-loan campaign orchestrator.

Replacement for the old synthetic/random campaign path. This script does not
invent opportunities. It runs the route scanners/research handoff and then the
strict dispatcher. Live execution still requires --execute AND
REAL_TRANSACTIONS_ENABLED=true.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR if (SCRIPT_DIR / "live-flashloan").exists() else SCRIPT_DIR.parent
SCRIPT_ROOT = ROOT if (ROOT / "flashloan_research_agent.py").exists() else ROOT / "scripts"
PYTHON = ROOT / "venv" / "bin" / "python"
if not PYTHON.exists():
    PYTHON = Path(sys.executable)
LOG = ROOT / "logs" / "safe-campaign.log"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now(timezone.utc).replace(microsecond=0).isoformat()} {msg}\n"
    LOG.open("a").write(line)
    print(line, end="")


def run(cmd: List[str], timeout: int = 1200) -> Dict:
    log("run " + " ".join(cmd))
    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if proc.stdout:
        log("stdout " + proc.stdout[-2000:].replace("\n", " | "))
    if proc.stderr:
        log("stderr " + proc.stderr[-2000:].replace("\n", " | "))
    return {"returncode": proc.returncode, "stdout_tail": proc.stdout[-4000:], "stderr_tail": proc.stderr[-4000:]}


def cycle(networks: List[str], execute: bool) -> Dict:
    scan_result = run([str(PYTHON), str(SCRIPT_ROOT / "flashloan_research_agent.py"), "scan", "--networks", *networks], timeout=1800)
    dispatch_cmd = [str(PYTHON), str(SCRIPT_ROOT / "flashloan_execution_dispatcher.py")]
    if execute:
        dispatch_cmd.append("--execute")
    dispatch_result = run(dispatch_cmd, timeout=1800)
    summary_path = ROOT / "data" / "execution-handoff" / "why_not_executed_report.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    return {"scan": scan_result, "dispatch": dispatch_result, "summary": summary}


def main() -> int:
    ap = argparse.ArgumentParser(description="Safe route-scanner flash-loan campaign")
    ap.add_argument("--networks", nargs="+", default=["arbitrum", "base"], choices=["arbitrum", "base", "ethereum", "optimism"])
    ap.add_argument("--execute", action="store_true", help="Request live execution; still requires REAL_TRANSACTIONS_ENABLED=true")
    ap.add_argument("--once", action="store_true", help="Run one scan/dispatch cycle and exit")
    ap.add_argument("--interval", type=int, default=60, help="Seconds between cycles when not --once")
    args = ap.parse_args()

    load_env_file(ROOT / ".env.local")
    load_env_file(SCRIPT_ROOT / ".env.local")

    live_enabled = (
        os.getenv("REAL_TRANSACTIONS_ENABLED", "false").lower() == "true"
        and os.getenv("CONFIRM_LIVE_FLASHLOAN_EXECUTION", "no") == "YES"
    )
    log(f"safe campaign start networks={args.networks} execute_requested={args.execute} live_env_enabled={live_enabled}")
    if args.execute and not live_enabled:
        log("execute requested but REAL_TRANSACTIONS_ENABLED is false; dispatcher will dry-run/reject live gate")

    while True:
        result = cycle(args.networks, args.execute)
        print(json.dumps(result.get("summary", {}), indent=2, sort_keys=True))
        if args.once:
            return 0 if result["scan"]["returncode"] == 0 and result["dispatch"]["returncode"] == 0 else 1
        time.sleep(max(10, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
