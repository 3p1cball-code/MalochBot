"""Anbindung an die Claude-Code-CLI (`claude`) als zweites LLM-Backend.

Gedacht fuer Nutzer mit Claude-Abo (Pro/Max): einmalig `claude` im Terminal
starten und anmelden (OAuth, `/login`) - danach nutzt MalochBot das Abo ueber
den Plan, ohne zusaetzlichen API-Key oder opencode-Installation.

Aufruf:  claude -p --model <alias> --output-format text  (Prompt ueber stdin)
Die Websuche laeuft ueber die eingebauten Werkzeuge WebSearch/WebFetch; alle
anderen Werkzeuge (Bash, Datei, MCP) sind absichtlich abgeschaltet, damit der
unbeaufsichtigte Lauf weder haengt noch etwas am System veraendert.
Anhaenge werden - anders als bei opencode - nicht per Flag uebergeben, sondern
in den Prompt eingebettet (die Dateiwerkzeuge sind ja aus).
"""

import os
import re
import shutil
import subprocess
import threading

from . import config, logbus
from .llm_common import extract_json, strip_ansi  # noqa: F401 (extract_json re-exportiert)

DEFAULT_MODEL = os.environ.get("MALOCHBOT_CLAUDE_MODEL", "sonnet")

# Verfuegbare Modell-Aliase (die tatsaechlich erreichbaren Modelle haengen vom
# persoenlichen Plan ab). Siehe Claude-Code-Modell-Aliase.
MODELS = ["sonnet", "opus", "haiku"]

# Eingebaute Werkzeuge, die ohne Rueckfrage laufen duerfen (leer = keine Werkzeuge).
# Ueber MALOCHBOT_CLAUDE_TOOLS anpassbar; "" schaltet die Websuche ab.
WEB_TOOLS = os.environ.get("MALOCHBOT_CLAUDE_TOOLS", "WebSearch,WebFetch")

_WAIT_NOISE = re.compile(r"^Waiting for background work to finish", re.I)


def available() -> bool:
    return shutil.which("claude") is not None


def list_models():
    """Die vom Plan abgedeckten Modell-Aliase (Claude Code kennt keine Modell-Liste)."""
    return list(MODELS)


def run(prompt: str, model: str = "", cwd: str = "", attach=None, run_id=None,
        timeout: int = 3600) -> tuple:
    model = model or DEFAULT_MODEL
    exe = shutil.which("claude") or "claude"
    workdir = cwd or str(config.BASE_DIR)
    full_prompt = _with_attachments(prompt, attach)

    cmd = [exe, "-p", "--model", model, "--output-format", "text"]
    if WEB_TOOLS:
        cmd += ["--allowedTools", WEB_TOOLS, "--tools", WEB_TOOLS]
    else:
        cmd += ["--tools", ""]
    # Keine MCP-Werkzeuge: verhindert fremde Server/Werkzeugketten im Lauf.
    cmd += ["--disallowedTools", "mcp__*"]

    if run_id:
        logbus.log(run_id, "info", "claude: -p --model %s (Prompt %d Zeichen)"
                   % (model, len(full_prompt or "")))
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1, cwd=workdir,
        )
    except FileNotFoundError:
        raise RuntimeError("claude (Claude Code) wurde nicht gefunden. Bitte installieren "
                           "und einmal anmelden (siehe README).")

    def _feed():
        try:
            proc.stdin.write(full_prompt or "")
            proc.stdin.flush()
        except Exception:
            pass
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass

    threading.Thread(target=_feed, daemon=True).start()
    lines = []
    try:
        for line in proc.stdout:
            clean = strip_ansi(line.rstrip("\n"))
            lines.append(clean)
            if run_id and clean.strip():
                logbus.log(run_id, "debug", clean)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError("Claude-Code-Zeitlimit ueberschritten.")

    out = "\n".join(lines)
    # Klarer Hinweis statt kryptischem "keine auswertbare JSON-Antwort", wenn
    # Claude Code gar nicht erst laeuft (z. B. nicht angemeldet).
    if proc.returncode not in (0, None) and not out.strip():
        raise RuntimeError("Claude Code meldete einen Fehler (rc=%s). Bitte pruefen, ob "
                           "'claude' eingerichtet und angemeldet ist." % proc.returncode)
    return proc.returncode, out


def _with_attachments(prompt: str, attach) -> str:
    """Bettet angehaengte Dateien in den Prompt ein (statt `-f` wie bei opencode)."""
    if not attach:
        return prompt or ""
    chunks = [prompt or ""]
    for path in attach:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                content = fh.read()
        except OSError as exc:
            content = "[Anhang konnte nicht gelesen werden: %s]" % exc
        chunks.append("\n\n--- Angehaengte Datei: %s ---\n%s"
                      % (os.path.basename(path), content))
    return "\n".join(chunks)


def clean_text(text: str) -> str:
    """Entfernt ANSI-Reste und Rand-Leerzeilen; Text-Ausgabe ist sonst bereits sauber."""
    out = [line.rstrip() for line in strip_ansi(text).splitlines()
           if not _WAIT_NOISE.match(line.strip())]
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)
