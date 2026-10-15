"""Gemeinsame Helfer der LLM-Backends.

Backend-unabhaengig: ANSI-Bereinigung und robuste JSON-Extraktion aus der
Modellantwort. Sowohl opencode als auch Claude Code liefern Text, der
Statuszeilen, Werkzeugaufrufe und erst am Ende das Ergebnis enthaelt.
"""

import json
import re

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text or "")


def extract_json(text: str):
    """Robuste JSON-Extraktion: findet das gueltige Modell-Objekt mit 'jobs'/'mails'.

    Die CLI-Ausgabe enthaelt auch die angehaengte Kontextdatei (ebenfalls mit
    'jobs'/'mails', aber ohne 'phase'/'job_id') und Tool-Aufrufe wie {"query": ...}.
    Deshalb wird bevorzugt das Objekt gewaehlt, dessen Eintraege 'phase' oder
    'job_id' tragen (= Modellantwort), vorzugsweise das letzte davon.
    """
    text = strip_ansi(text)
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
