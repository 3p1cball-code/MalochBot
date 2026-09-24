#!/usr/bin/env bash
# MalochBot - Start (Linux/macOS). Beendet zuerst eine laufende Instanz und startet neu.
set -e
cd "$(dirname "$0")"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

HOST="${MALOCHBOT_HOST:-127.0.0.1}"
PORT="${MALOCHBOT_PORT:-8765}"
URL="http://${HOST}:${PORT}"

if pgrep -f "uvicorn app.main" >/dev/null 2>&1; then
  echo "Beende laufende MalochBot-Instanz ..."
  pkill -f "uvicorn app.main" 2>/dev/null || true
  sleep 1
  pkill -9 -f "uvicorn app.main" 2>/dev/null || true
  sleep 1
fi

echo "MalochBot laeuft auf ${URL}"
echo "Beenden: Einstellungen > Server beenden."
( sleep 2; command -v xdg-open >/dev/null 2>&1 && xdg-open "${URL}" >/dev/null 2>&1 || true ) &

exec python -m uvicorn app.main:app --host "${HOST}" --port "${PORT}"
