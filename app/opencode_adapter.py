"""Anbindung an die opencode-CLI. Jede Analyse laeuft ueber opencode und ein frei
waehlbares Modell. Die Ausgabe wird zeilenweise in den Live-Log gestreamt.
"""

import json
import re
import shutil
import subprocess

from . import config, logbus

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


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
    cmd = [exe, "run", "-m", model, "--dir", workdir, prompt]
    for path in (attach or []):
        cmd += ["-f", path]
    if run_id:
        logbus.log(run_id, "info", "opencode: %s (Modell %s)" % (" ".join(cmd[:4]), model))
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=workdir,
        )
    except FileNotFoundError:
        raise RuntimeError("opencode wurde nicht gefunden. Bitte installieren (siehe installer).")
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


def extract_json(text: str):
    """Robuste JSON-Extraktion: findet das gueltige Modell-Objekt mit 'jobs'/'mails'.

    Die opencode-Ausgabe enthaelt auch die angehaengte Kontextdatei (ebenfalls mit
    'jobs'/'mails', aber ohne 'phase'/'job_id') und Tool-Aufrufe wie {"query": ...}.
    Deshalb wird bevorzugt das Objekt gewaehlt, dessen Eintraege 'phase' oder
    'job_id' tragen (= Modellantwort), vorzugsweise das letzte davon.
    """
    text = ANSI.sub("", text or "")
    decoder = json.JSONDecoder()
    objects = []
    index = 0
    while True:
        start = text.find("{", index)
        if start == -1:
            break
        try:
            obj, end = decoder.raw_decode(text[start:])
        except Exception:
            index = start + 1
            continue
        objects.append(obj)
        index = start + end

    def _model_shaped(obj) -> bool:
        if not isinstance(obj, dict):
            return False
        for key in ("jobs", "mails"):
            lst = obj.get(key)
            if isinstance(lst, list):
                for item in lst:
                    if isinstance(item, dict) and ("phase" in item or "job_id" in item):
                        return True
        return False

    candidates = [o for o in objects
                  if isinstance(o, dict) and ("jobs" in o or "mails" in o)]
    shaped = [o for o in candidates if _model_shaped(o)]
    if shaped:
        return shaped[-1]
    if candidates:
        return candidates[-1]
    for obj in objects:
        if isinstance(obj, list) and obj and isinstance(obj[0], dict) and "company" in obj[0]:
            return {"jobs": obj}
    return None
