#!/usr/bin/env bash
# Apex 50K v2.6 — Daily Scan + Forward Test runner
# No Mavis agent dependency. Pure shell + Python.
#
# Schedule: runs daily at 21:00 Asia/Shanghai = 13:00 UTC = 09:00 EDT
# Caller: system cron, GitHub Actions, or manual invocation
#
# Usage:
#   ./cron_runner.sh                # normal daily run
#   ./cron_runner.sh --dry-run      # scan only, no Telegram push
#   ./cron_runner.sh --test-tg      # send a test message to Telegram
#   ./cron_runner.sh --backtest     # also run 60d backtest before scan

set -euo pipefail

# --- Resolve paths ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- Load .env (literal values, no ${} expansion) ---
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
else
  echo "FATAL: .env not found at $SCRIPT_DIR/.env" >&2
  exit 1
fi

# --- Required env vars ---
: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN missing in .env}"
: "${TELEGRAM_CHAT_ID:?TELEGRAM_CHAT_ID missing in .env}"
: "${MINIMAX_API_KEY:?MINIMAX_API_KEY missing in .env}"

# --- Parse flags ---
DRY_RUN=0
TEST_TG=0
RUN_BACKTEST=0
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=1 ;;
    --test-tg)    TEST_TG=1 ;;
    --backtest)   RUN_BACKTEST=1 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# *//'
      exit 0
      ;;
  esac
done

# --- Setup venv ---
if [[ ! -d .venv ]]; then
  echo "[cron_runner] Creating venv..."
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[cron_runner] Installing deps (idempotent)..."
pip install -q -r requirements.txt 2>&1 | tail -3

# --- Time stamps (UTC-4 = apex-bootcamp standard) ---
TODAY_ET=$(TZ=America/New_York date +%Y-%m-%d)
NOW_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
echo "[cron_runner] Today ET: $TODAY_ET / Now UTC: $NOW_UTC"

# --- Optional: --test-tg (send a test message and exit) ---
if [[ $TEST_TG -eq 1 ]]; then
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -H "Content-Type: application/json" \
    -d "{\"chat_id\": \"${TELEGRAM_CHAT_ID}\", \"text\": \"🧪 cron_runner test @ ${NOW_UTC}\"}" \
    > /dev/null
  echo "[cron_runner] Test message sent"
  exit 0
fi

# --- Optional: --backtest ---
if [[ $RUN_BACKTEST -eq 1 ]]; then
  echo "[cron_runner] Running 60d backtest..."
  python src/apex_backtest.py --window 60d --out /workspace/reports/apex-backtest.json \
    || echo "[cron_runner] backtest failed (non-fatal)"
fi

# --- Run scanner (positional date arg, auto-saves to /workspace/reports/) ---
echo "[cron_runner] Running daily scanner (date: $TODAY_ET)..."
SCAN_OUT="/workspace/reports/apex-scan-${TODAY_ET}.md"
# 15-min timeout: covers MNQ worst-case (360s) + setup overhead
if timeout 900 python src/apex_scan.py "$TODAY_ET" 2>&1 | tail -30; then
  echo "[cron_runner] Scanner output: $SCAN_OUT"
else
  echo "[cron_runner] Scanner TIMED OUT or FAILED (non-fatal, continuing)"
fi

# --- Run forward test (positional date, no --append) ---
echo "[cron_runner] Running forward test..."
FORWARD_LOG="/workspace/reports/apex-forward-log.jsonl"
# 10-min timeout for forward test
if timeout 600 python src/apex_forward.py --mode=combined "$TODAY_ET" 2>&1 | tail -20; then
  echo "[cron_runner] Forward log: $FORWARD_LOG"
else
  echo "[cron_runner] Forward test TIMED OUT or FAILED (non-fatal, continuing)"
fi

# --- Build summary ---
SUMMARY_LINES=(
  "A 皮盤房 v2.6 daily scan"
  "📅 ${TODAY_ET} ET  ⏰ ${NOW_UTC}"
  ""
)

# Try to read scanner output
if [[ -f "$SCAN_OUT" ]]; then
  # Extract actionables (A/B grades) from scan markdown
  ACTIONABLES=$(grep -cE '^\|.*[AB] *\|' "$SCAN_OUT" 2>/dev/null || echo 0)
  SUMMARY_LINES+=("📊 Scanner: ${ACTIONABLES} A/B setups detected")
else
  SUMMARY_LINES+=("⚠️ Scanner: no output file")
fi

# Compute today + cumulative P&L from forward log
if [[ -f "$FORWARD_LOG" ]]; then
  TODAY_PNL=$(grep "\"date\": \"${TODAY_ET}\"" "$FORWARD_LOG" 2>/dev/null \
    | python3 -c "
import sys, json
total = 0
n = 0
for line in sys.stdin:
    try:
        d = json.loads(line)
        total += d.get('pnl_usd', 0)
        n += 1
    except: pass
print(f'{n} trades, \${total:+,.0f}')
" 2>/dev/null || echo "0 trades")
  CUM_PNL=$(python3 -c "
import json
total = 0
n = 0
with open('$FORWARD_LOG') as f:
    for line in f:
        try:
            d = json.loads(line)
            total += d.get('pnl_usd', 0)
            n += 1
        except: pass
print(f'{n} trades, \${total:+,.0f}')
")
  SUMMARY_LINES+=("💰 Today forward: ${TODAY_PNL}")
  SUMMARY_LINES+=("📈 Cumulative: ${CUM_PNL}")
else
  SUMMARY_LINES+=("⚠️ Forward log: no file")
fi

SUMMARY_LINES+=("")
SUMMARY_LINES+=("🔗 https://github.com/yip-lgtm/apex-bootcamp")

SUMMARY=$(printf '%s\n' "${SUMMARY_LINES[@]}")

# --- Send to Telegram (unless --dry-run) ---
if [[ $DRY_RUN -eq 1 ]]; then
  echo "--- DRY RUN: would send ---"
  echo "$SUMMARY"
  echo "---------------------------"
  exit 0
fi

echo "[cron_runner] Sending Telegram push..."
HTTP_CODE=$(curl -s -o /tmp/tg_resp.json -w '%{http_code}' \
  -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "import json; print(json.dumps({'chat_id': '${TELEGRAM_CHAT_ID}', 'text': '''$SUMMARY'''}))")")

if [[ "$HTTP_CODE" == "200" ]]; then
  echo "[cron_runner] ✅ Telegram push sent (HTTP 200)"
else
  echo "[cron_runner] ❌ Telegram push failed (HTTP $HTTP_CODE)"
  cat /tmp/tg_resp.json
fi

# --- Optional: git commit + push today's reports ---
if [[ -n "${GITHUB_PAT:-}" ]]; then
  cd /workspace/apex-bootcamp
  git add AUTOMATION/reports/ 2>/dev/null || true
  if ! git diff --cached --quiet 2>/dev/null; then
    git -c user.name="Apex 皮盤房 bot" -c user.email="bot@apex.local" \
      commit -m "auto: daily scan + forward report ${TODAY_ET}" -q
    git push "https://${GITHUB_PAT}@github.com/yip-lgtm/apex-bootcamp.git" main -q \
      && echo "[cron_runner] ✅ Pushed to GitHub" \
      || echo "[cron_runner] ⚠️ GitHub push failed"
  fi
fi

echo "[cron_runner] Done."
