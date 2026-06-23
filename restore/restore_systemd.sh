#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Run with sudo/root" >&2; exit 1; fi
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:---dry-run}"
echo "Systemd templates are provided but NOT auto-enabled by default."
echo "Templates available:"; ls -1 "$PROJECT_ROOT/systemd" || true
if [[ "$MODE" != "--apply" ]]; then
  echo "Dry run only. To install templates without enabling: sudo ./restore/restore_systemd.sh --apply"
  exit 0
fi
for f in "$PROJECT_ROOT/systemd"/*.service.template; do
  [[ -e "$f" ]] || continue
  name="$(basename "$f" .template)"
  sed -E 's@/root/.openclaw/workspace/flash-loan-research@/opt/flash-loan@g' "$f" > "/etc/systemd/system/$name"
  echo "Installed /etc/systemd/system/$name (not enabled, not started)"
done
systemctl daemon-reload
echo "No service was started or enabled. Manually inspect then use systemctl enable/start if desired."
