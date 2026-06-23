#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-/opt/flash-loan}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ $EUID -ne 0 ]]; then
  echo "Run as root or with sudo so system packages and /opt paths can be prepared." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  git curl ca-certificates python3 python3-venv python3-pip python3-dev build-essential \
  cron sqlite3 jq

mkdir -p "$APP_DIR" /var/log/flash-loan
cp -a "$PROJECT_ROOT/opt-flash-loan/." "$APP_DIR/" 2>/dev/null || true
cp -a "$PROJECT_ROOT/flash-loan-research/." "$APP_DIR/" 2>/dev/null || true

$PYTHON_BIN -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/python" -m pip install --upgrade pip wheel setuptools
if [[ -f "$PROJECT_ROOT/flash-loan-research/requirements.txt" ]]; then
  "$APP_DIR/venv/bin/pip" install -r "$PROJECT_ROOT/flash-loan-research/requirements.txt"
elif [[ -f "$APP_DIR/requirements.txt" ]]; then
  "$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"
else
  "$APP_DIR/venv/bin/pip" install web3 requests python-dotenv pandas numpy aiohttp schedule rich tabulate pydantic click cryptography
fi

# Optional Foundry install for Solidity contract build/deploy. Skipped if already present.
if ! command -v forge >/dev/null 2>&1; then
  echo "Foundry forge not found. To install manually: curl -L https://foundry.paradigm.xyz | bash && foundryup"
fi

if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$PROJECT_ROOT/.env.example" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo "Created $APP_DIR/.env from safe template. Fill RPC URLs and wallet values before live use."
fi

echo "Dependencies installed. Next: edit $APP_DIR/.env, then run ./healthcheck.sh"
