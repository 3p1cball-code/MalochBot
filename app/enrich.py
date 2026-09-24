"""Einmalige Anreicherung bestehender Jobs aus den Job-Ranking-PDFs.

Liest die Ranking-Texte, laesst das Modell strukturierte Felder extrahieren und
aktualisiert leere Felder in der Datenbank.
"""

import glob
import json
import os
import re
import subprocess

from . import config, db, logbus
from . import opencode_adapter as oc

PROMPT = """Du hilfst, eine Job-Datenbank zu befuellen.

Unten stehen die gesammelten Job-Ranking-Texte aus den Bewerbungsordnern.
Zusaetzlich die Liste der Jobs, die in der Datenbank stehen.

Extrahiere fuer JEDEN in der Datenbank gelisteten Job (match ueber Firma + Position)
die folgenden Felder, ausschliesslich aus den Ranking-Texten. Wenn eine Angabe fehlt,
lass das Feld leer.

- location: Standort (z. B. "Berlin, hybrid")
- remote: true/false
- published_at: Veroeffentlichungsdatum YYYY-MM-DD oder ""
- fit: Einschaetzung als Text (z. B. "sehr hoch", "hoch", "gut", "mittel")
- score: 0-100; sehr hoch=90, hoch=80, gut=70, mittel=55, niedrig=40
- rationale: warum der Job passt (2-4 Saetze, aus dem Text)
- description: was die Position ausmacht (2-4 Saetze)
- company_url: offizielle Firmen-Website, falls im Text genannt, sonst ""

Datenbank-Jobs:
{{JOBS}}

Ranking-Texte:
{{TEXT}}

Antworte AUSSCHLIESSLICH mit JSON:
{"jobs":[{"company":"...","title":"...","location":"...","remote":false,"published_at":"","fit":"","score":0,"rationale":"","description":"","company_url":""}]}
"""


def _ranking_text() -> str:
    base = config.BASE_DIR.parent
    files = sorted(glob.glob(os.path.join(str(base), "*", "Job-Ranking_Alexander_Riedel.pdf")))
    parts = []
    for path in files:
        try:
            out = subprocess.run(["pdftotext", "-layout", path, "-"],
                                 capture_output=True, text=True, timeout=60).stdout
            parts.append("\n\n=== %s ===\n%s" % (os.path.basename(os.path.dirname(path)), out))
        except Exception:
            continue
    return "".join(parts)[:120000]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def run_enrich(run_id: int, model: str = "") -> dict:
    db.init_db()
    jobs = db.query("SELECT id, company, title FROM jobs")
    job_list = "\n".join("- %s | %s" % (j["company"], j["title"]) for j in jobs)
    text = _ranking_text()
    logbus.log(run_id, "info", "Ranking-Texte gelesen (%d Zeichen)." % len(text))
    prompt = PROMPT.replace("{{JOBS}}", job_list).replace("{{TEXT}}", text)
    rc, out = oc.run(prompt, model=model, run_id=run_id)
    data = oc.extract_json(out)
    if not data:
        raise RuntimeError("Keine JSON-Antwort vom Modell erhalten.")
    items = data.get("jobs", data if isinstance(data, list) else [])
    updated = 0
    for item in items:
        target = None
        for j in jobs:
            if _norm(item.get("company")) and _norm(item.get("company")) in _norm(j["company"]):
                target = j
                break
        if target is None:
            continue
        sets, params = [], []
        mapping = [
            ("location", item.get("location")),
            ("remote", 1 if item.get("remote") else 0),
            ("published_at", item.get("published_at")),
            ("fit", item.get("fit")),
            ("score", int(item.get("score") or 0)),
            ("rationale", item.get("rationale")),
            ("description", item.get("description")),
            ("company_url", item.get("company_url")),
        ]
        for col, val in mapping:
            if val not in (None, "", 0):
                sets.append("%s=?" % col)
                params.append(val)
        if sets:
            params.append(target["id"])
            db.execute("UPDATE jobs SET %s WHERE id=?" % ",".join(sets), tuple(params))
            updated += 1
            logbus.log(run_id, "info", "Angereichert: %s" % target["company"])
    logbus.log(run_id, "info", "%d Jobs aktualisiert." % updated)
    return {"aktualisiert": updated, "treffer": len(items)}
