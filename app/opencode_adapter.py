"""Anbindung an die opencode-CLI. Jede Analyse laeuft ueber opencode und ein frei
waehlbares Modell. Die Ausgabe wird zeilenweise in den Live-Log gestreamt.
"""

import re
import shutil
import subprocess
import threading

from . import config, logbus
from .llm_common import ANSI, extract_json  # noqa: F401 (extract_json re-exportiert)


def available() -> bool:
    return shutil.which("opencode") is not None


def list_models():
    """Alle aktuell auf dem System in opencode verfuegbaren Modelle (provider/model)."""
    exe = shutil.which("opencode") or "opencode"
    try:
        proc = subprocess.run([exe, "models"], capture_output=True, text=True, timeout=30)
        models = sorted({line.strip() for line in (proc.stdout or "").splitlines()
                         if "/" in line and " " not in line.strip()})
    except Exception:
        models = []
    return models


def run(prompt: str, model: str = "", cwd: str = "", attach=None, run_id=None,
        timeout: int = 3600) -> tuple:
    model = model or config.DEFAULT_MODEL
    exe = shutil.which("opencode") or "opencode"
    workdir = cwd or str(config.BASE_DIR)
    # Prompt ueber stdin senden (nicht als CLI-Argument): so gibt es keine
    # ARG_MAX-Grenze (~128 KiB) und grosse Dokumente passen vollstaendig hinein.
    cmd = [exe, "run", "-m", model, "--dir", workdir]
    for path in (attach or []):
        cmd += ["-f", path]
    if run_id:
        logbus.log(run_id, "info", "opencode: run -m %s (Modell %s, Prompt %d Zeichen)"
                   % (model, model, len(prompt or "")))
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=workdir,
        )
    except FileNotFoundError:
        raise RuntimeError("opencode wurde nicht gefunden. Bitte installieren (siehe installer).")

    def _feed():
        try:
            proc.stdin.write(prompt or "")
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
            clean = ANSI.sub("", line.rstrip("\n"))
            lines.append(clean)
            if run_id and clean.strip():
                logbus.log(run_id, "debug", clean)
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError("opencode-Zeitlimit ueberschritten.")
    return proc.returncode, "\n".join(lines)


def clean_text(text: str) -> str:
    """Entfernt opencode-Chrome (Kopfzeile, Werkzeug-/Statuszeilen) aus Fliesstext-Ausgaben."""
    out = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if re.match(r"^>\s*(build|·)", stripped):
            continue
        if stripped[:1] in ("⚙", "%") or stripped.startswith("✗"):
            continue
        if stripped.startswith("> build"):
            continue
        out.append(line.rstrip())
    while out and not out[0].strip():
        out.pop(0)
    while out and not out[-1].strip():
        out.pop()
    return "\n".join(out)
