#!/usr/bin/env python3
"""Traegt die MCP-Server (brave-search, fetch) in die opencode-Config ein."""
import json
import os
import sys

cfg_path = os.environ.get("OPENCODE_CONFIG") or os.path.expanduser("~/.config/opencode/opencode.json")
key = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BRAVE_API_KEY", "")) or ""

os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
cfg = json.load(open(cfg_path)) if os.path.exists(cfg_path) else {}
mcp = cfg.setdefault("mcp", {})
mcp["fetch"] = {"type": "local", "command": ["uvx", "mcp-server-fetch"], "enabled": True}
if key:
    mcp["brave-search"] = {
        "type": "local",
        "command": ["npx", "-y", "@brave/brave-search-mcp-server", "--transport", "stdio"],
        "enabled": True,
        "environment": {"BRAVE_API_KEY": key},
    }
json.dump(cfg, open(cfg_path, "w"), indent=2)
try:
    os.chmod(cfg_path, 0o600)
except OSError:
    pass
print("opencode-MCP konfiguriert: " + ", ".join(mcp.keys()))
print("Websuche aktiv: " + ("ja" if key else "nein"))
