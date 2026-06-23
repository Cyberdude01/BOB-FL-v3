#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/flash-loan}"
FAIL=0
check(){ if eval "$2"; then echo "✅ $1"; else echo "❌ $1"; FAIL=1; fi; }
check "app directory exists" "test -d '$APP_DIR'"
check "python venv exists" "test -x '$APP_DIR/venv/bin/python'"
check "env file exists and private" "test -f '$APP_DIR/.env' && [[ \$(stat -c %a '$APP_DIR/.env') == 600 ]]"
check "live scanner present" "test -f '$APP_DIR/scripts/live_flashloan_scanner.py' || test -f '$APP_DIR/live_flashloan_scanner.py'"
check "dispatcher present" "test -f '$APP_DIR/scripts/flashloan_execution_dispatcher.py' || test -f '$APP_DIR/flashloan_execution_dispatcher.py'"
if [[ -x "$APP_DIR/venv/bin/python" ]]; then
  "$APP_DIR/venv/bin/python" - <<'PY' || FAIL=1
mods=['web3','requests','dotenv','pandas','numpy','aiohttp']
missing=[]
for m in mods:
    try: __import__(m)
    except Exception as e: missing.append(f'{m}: {e}')
if missing:
    print('❌ python imports missing:', '; '.join(missing)); raise SystemExit(1)
print('✅ required python imports ok')
PY
fi
if git -C "$(dirname "$0")" ls-files >/tmp/bobfl_files 2>/dev/null; then
  if grep -E '(^|/)(node_modules|venv|venv_enhanced|__pycache__|logs)(/|$)|\.env($|\.)|\.db$|\.sqlite' /tmp/bobfl_files; then
    echo "❌ unsafe/generated files are tracked"; FAIL=1
  else
    echo "✅ no obvious generated/dependency/secret paths tracked"
  fi
fi
if "$(dirname "$0")/scripts/secret_scan.sh" "$(dirname "$0")" | grep -q .; then
  echo "❌ potential real secret strings found in repo"; FAIL=1
else
  echo "✅ no obvious real secret strings in committed tree"
fi
exit "$FAIL"
