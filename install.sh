#!/usr/bin/env bash
# MalochBot - Installer (Linux/macOS)
set -e
cd "$(dirname "$0")"

echo "== MalochBot Installer =="

PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
  echo "FEHLER: Python 3.10+ nicht gefunden. Bitte installieren." >&2
  exit 1
fi
echo "Python: $($PY --version)"

if ! command -v opencode >/dev/null 2>&1; then
  echo "opencode nicht gefunden - Installation versuchen ..."
  if command -v npm >/dev/null 2>&1; then
    npm install -g opencode-ai || true
  fi
  if ! command -v opencode >/dev/null 2>&1; then
    curl -fsSL https://opencode.ai/install | bash || true
  fi
fi
if command -v opencode >/dev/null 2>&1; then
  echo "opencode: $(command -v opencode)"
else
  echo "HINWEIS: opencode konnte nicht automatisch installiert werden."
  echo "         Bitte manuell installieren: https://opencode.ai/docs"
fi

echo "Erstelle virtuelle Umgebung ..."
"$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "Initialisiere Datenbank ..."
python -c "from app import db; db.init_db(); print('OK:', db.get_setting('model'))"

chmod +x run.sh 2>/dev/null || true

echo
echo "Fertig. Starten mit: ./run.sh"
echo "Danach im Browser öffnen und unter 'Einstellungen' Modell + Mailkonto einrichten."
