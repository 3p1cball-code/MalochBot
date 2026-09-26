"""Job-Suche: findet neue, passende Stellen ueber opencode/LLM und legt sie in der
Datenbank ab. Bereits bekannte Jobs werden nicht doppelt aufgenommen.
"""

from .. import db, logbus
from .. import opencode_adapter as oc

PROMPT = """Du bist ein Recherche-Assistent fuer die Jobsuche. Nutze die Websuche.

Profil der Person:
{{PROFILE}}

Vorlieben / Praeferenzen:
{{PREFERENCES}}

Zusatzvorgaben:
{{EXTRA}}

Bereits bekannte Jobs. Ein Job gilt als bereits bekannt, wenn Firma UND Rollenbezeichnung
uebereinstimmen – unabhaengig von URL, Domain oder Jobboerse. Diese NICHT erneut vorschlagen:
{{EXISTING}}

Lebenslauf / Unterlagen (Auszug):
{{CV}}

Weitere abgelegte Unterlagen:
{{DOCS}}

Aufgabe:
- Finde bis zu 12 tatsaechlich aktuelle, passende und offene Stellen (Veroeffentlichung
  nicht aelter als ~2 Monate, Anzeige beim Pruefen noch aktiv).
- Keine Duplikate zu den bereits bekannten Jobs.
- Nimm nur Stellen mit einem Fit-Score von mindestens {{THRESHOLD}} auf.
- rationale: 3-5 Saetze, warum die Stelle gut passt (konkrete Anknuepfungspunkte).
- description: 5-8 Saetze mit Aufgaben, Anforderungen, Team/Kontext und eingesetzten
  Tools – so detailliert, wie es die Anzeige hergibt; nichts erfinden.
- lang: Sprache der Stellenanzeige, entweder "de" oder "en".

Antworte AUSSCHLIESSLICH mit JSON, ohne Markdown, in genau dieser Form:
{"jobs":[{"company":"...","company_url":"https://...","title":"...","location":"...","remote":true,
"url":"...","published_at":"YYYY-MM-DD","score":87,"fit":"hoch","lang":"de",
"rationale":"...","description":"..."}]}
"""


def run_search(run_id: int, model: str = "", extra: str = "") -> dict:
    profile = db.get_setting("profile", "")
    preferences = db.get_setting("preferences", "")
    extra = extra or db.get_setting("search_extra", "")
    existing_rows = db.query("SELECT company, title FROM jobs ORDER BY found_at DESC")
    existing = "\n".join("- %s – %s" % (r["company"], r["title"]) for r in existing_rows) or "(keine)"

    from . import documents as doc_engine
    docs = db.query("SELECT id, name, kind, path FROM documents ORDER BY kind, name")
    selected = [int(x) for x in (db.get_setting("search_doc_ids", "") or "").split(",")
                if x.strip().isdigit()]
    if selected:
        chosen = [d for d in docs if d["id"] in selected]
    else:
        chosen = docs or []
    parts = []
    for doc in chosen:
        text = doc_engine.extract_text(doc["path"])
        if text and not text.startswith("["):
            parts.append("### %s (%s)\n%s" % (doc["name"], doc["kind"], text[:2500]))
    context_text = "\n\n".join(parts)[:6000]
    docs_list = "\n".join("- %s (%s)" % (d["name"], d["kind"]) for d in docs) or "(keine)"

    prompt = (PROMPT.replace("{{PROFILE}}", profile)
                    .replace("{{PREFERENCES}}", preferences)
                    .replace("{{EXTRA}}", extra)
                    .replace("{{THRESHOLD}}", db.get_setting("fit_threshold", "0") or "0")
                    .replace("{{CV}}", context_text or "(keine Dokumente ausgewaehlt)")
                    .replace("{{DOCS}}", docs_list)
                    .replace("{{EXISTING}}", existing))
    logbus.log(run_id, "info", "Suche neue Jobs (%d bekannte werden ausgeschlossen) ..." % len(existing_rows))
    rc, out = oc.run(prompt, model=model, run_id=run_id)
    data = oc.extract_json(out)
    if not data:
        raise RuntimeError("Keine auswertbare JSON-Antwort vom Modell erhalten.")
    jobs = data.get("jobs", data if isinstance(data, list) else [])
    added = 0
    for job in jobs:
        if not job.get("company") or not job.get("title"):
            continue
        job["source"] = "search"
        job["run_id"] = run_id
        job["language"] = job.get("lang") or job.get("language") or ""
        job.setdefault("status", "gefunden")
        _, created = db.upsert_job(job)
        if created:
            added += 1
            logbus.log(run_id, "info", "Neu: %s – %s (Fit %s)" % (
                job.get("company"), job.get("title"), job.get("score", "?")))
    logbus.log(run_id, "info", "%d neue Jobs gefunden, %d bereits bekannt." % (added, len(jobs) - added))
    return {"gefunden": len(jobs), "neu": added}
