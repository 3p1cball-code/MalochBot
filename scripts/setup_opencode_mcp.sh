#!/usr/bin/env bash
# Richtet die fuer die Jobsuche noetigen opencode-MCP-Server ein:
#   - brave-search (Websuche)  -> benoetigt npx + BRAVE_API_KEY
#   - fetch                    -> benoetigt uvx
# Ohne Root: fehlende Laufzeiten werden, wenn moeglich, nach ~/.local/tools installiert.
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
TOOLS="$HOME/.local/tools"
BIN="$TOOLS/bin"
mkdir -p "$BIN"

need_node=0
need_uv=0
command -v npx >/dev/null 2>&1 || need_node=1
command -v uvx >/dev/null 2>&1 || need_uv=1

if [ "$need_node" = 1 ] || [ "$need_uv" = 1 ]; then
  if command -v micromamba >/dev/null 2>&1; then
    echo "Installiere nodejs + uv nach $TOOLS ..."
    micromamba install -y -p "$TOOLS" -c conda-forge nodejs uv
  fi
fi

if [ "$need_uv" = 1 ] && ! command -v uvx >/dev/null 2>&1; then
  echo "Installiere uv (fuer fetch-MCP) ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh || true
fi

export PATH="$BIN:$HOME/.local/bin:$PATH"

if ! command -v npx >/dev/null 2>&1; then
  echo "HINWEIS: 'npx' fehlt (Node.js). Bitte Node.js 20+ installieren, sonst laeuft die Websuche nicht."
fi

if [ -z "${BRAVE_API_KEY:-}" ]; then
  printf "Brave Search API-Key (Enter = ueberspringen, Websuche bleibt dann deaktiviert): "
  read -r BRAVE_API_KEY || true
fi

python3 "$DIR/mcp_config.py" "${BRAVE_API_KEY:-}"

if ! grep -qs ".local/tools/bin" "$HOME/.bashrc" 2>/dev/null; then
  echo "export PATH=\$HOME/.local/tools/bin:\$PATH" >> "$HOME/.bashrc" 2>/dev/null || true
fi
echo "Fertig. Ggf. PATH neu laden: source ~/.bashrc"
