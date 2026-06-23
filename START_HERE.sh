#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
echo "BOB-FL-v3 restore bootstrap"
echo "1) sudo ./install_dependencies.sh"
echo "2) sudo nano /opt/flash-loan/.env   # add real secrets locally only"
echo "3) sudo ./restore/restore_cron.sh --dry-run"
echo "4) sudo ./healthcheck.sh"
echo "5) Start only documented manual commands from README.md; live trading is disabled by default."
