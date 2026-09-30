"""Job-Suche: findet neue, passende Stellen ueber opencode/LLM und legt sie in der
Datenbank ab. Bereits bekannte Jobs werden nicht doppelt aufgenommen.

Zwei Zubringer, getrennt bewertet (bewusst zwei getrennte Modell-Schritte):
  1. Externe Jobboersen (Bundesagentur fuer Arbeit, JobSpy: LinkedIn/Indeed/…)
     liefern vorrecherchierte Kandidaten (app/engines/sources/). Diese werden in
     einem eigenen, werkzeugfreien Modellschritt bewertet und IMMER gespeichert –
     auch wenn die Bewertung fehlschlaegt (dann unbewertet).
  2. Die Websuche nach weiteren Stellen ist ein zweiter, unabhaengiger Schritt.
     Faellt sie aus, sind die Jobboersen-Kandidaten bereits gesichert.

Die Trennung ist Absicht: Ein einzelner Riesen-Prompt mit 30 Kandidaten UND
Websuche verleitet das Modell zu langen Werkzeugketten ohne JSON-Ausgabe.
"""

import json
import re

from .. import db, logbus
from .. import opencode_adapter as oc
from . import sources

WEB_PROMPT = """Du bist ein Recherche-Assistent fuer die Jobsuche. Nutze die Websuche.

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

Arbeitsweise (wichtig):
- Fuehre hoechstens 8 Websuchen durch. Nutze fuer Suchen count hoechstens 20.
- Beende deine Antwort ZWINGEND mit dem JSON-Objekt weiter unten, ohne Text danach.

Antworte AUSSCHLIESSLICH mit JSON, ohne Markdown, in genau dieser Form:
{"jobs":[{"company":"...","company_url":"https://...","title":"...","location":"...","remote":true,
"url":"...","published_at":"YYYY-MM-DD","score":87,"fit":"hoch","lang":"de",
"rationale":"...","description":"..."}]}
"""

SCORE_PROMPT = """Du bewertest vorrecherchierte Stellenanzeigen fuer eine Person. Du hast
KEINE Werkzeuge und KEINE Websuche – bewerte ausschliesslich anhand der Angaben hier.

Profil:
{{PROFILE}}

Vorlieben:
{{PREFERENCES}}

Lebenslauf / Unterlagen (Auszug):
{{CV}}

Fit-Schwelle: {{THRESHOLD}} (bewerte trotzdem alle, die Schwelle wendet der Aufrufer an)

Kandidaten (nummeriert):
{{CANDIDATES}}

Aufgabe: Gib fuer JEDEN Kandidaten
- score: Fit 0-100,
- fit: "hoch", "mittel" oder "niedrig",
- rationale: 3-5 Saetze mit konkreten Anknuepfungspunkten,
- description: 5-8 Saetze, "was die Position ausmacht" (Aufgaben, Anforderungen,
  Team/Kontext, eingesetzte Tools) – nur aus den Angaben, nichts erfinden,
- lang: Sprache der Anzeige, "de" oder "en".
Bewerte alle Kandidaten; die Fit-Schwelle wendet der Aufrufer an.

Antworte AUSSCHLIESSLICH mit JSON, ohne Markdown, in genau dieser Form:
{"jobs":[{"i":1,"score":87,"fit":"hoch","lang":"de","rationale":"...","description":"..."}]}
"""


SUGGEST_PROMPT = """Du hilfst bei der Jobsuche. Erzeuge aus den folgenden Unterlagen
(Lebenslauf, Zeugnisse, Arbeitsproben) kurze Suchbegriffe fuer Jobboersen.

Profil:
{{PROFILE}}

Vorlieben:
{{PREFERENCES}}

Unterlagen:
{{CONTEXT}}

Regeln:
- 5 bis 8 Begriffe, die Rollen und Technologien der Person treffen (z. B. "Generative AI",
  "3D Pipeline", "Technical Director", "ComfyUI").
- Deutsch oder Englisch, je nachdem, wie die Begriffe in Stellenanzeigen ueblich sind.
- Keine Firmennamen, keine Orte, keine ganzen Saetze.
- Antworte AUSSCHLIESSLICH mit einer einzigen Zeile, kommagetrennt, ohne Nummerierung,
  ohne Anfuehrungszeichen und ohne Erklaerung.
"""


def _documents_and_context() -> tuple:
    """Liefert (Textauszug der verwendeten Unterlagen, Liste aller Unterlagen)."""
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
            parts.append("### %s (%s)\n%s" % (doc["name"], doc["kind"], text))
    # Kein kuenstliches Kuerzen hier: extract_text respektiert das Limit aus den
    # Einstellungen (0 = unbegrenzt), und der Prompt geht per stdin an opencode.
    context_text = "\n\n".join(parts)
    docs_list = "\n".join("- %s (%s)" % (d["name"], d["kind"]) for d in docs) or "(keine)"
    return context_text, docs_list


def _candidates_block(candidates: list) -> str:
    items = []
    for i, cand in enumerate(candidates, 1):
        items.append({
            "i": i,
            "company": cand.get("company", ""),
            "title": cand.get("title", ""),
            "location": cand.get("location", ""),
            "remote": bool(cand.get("remote")),
            "published_at": cand.get("published_at", ""),
            "source": cand.get("source", ""),
            "description": (cand.get("description") or "")[:800],
        })
    return json.dumps(items, ensure_ascii=False, indent=1)


def _parse_keywords(text: str) -> list:
    """Zieht die Begriffsliste aus der Modellantwort (kommagetrennt oder zeilenweise)."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    sep_lines = [ln for ln in lines if "," in ln or ";" in ln]
    chunks = re.split(r"[,;]+", sep_lines[-1]) if sep_lines else lines
    out = []
    for chunk in chunks:
        chunk = re.sub(r"^\s*(?:[-*\u2022]|\d+[\.\)])\s*", "", chunk).strip().strip("\"'`").strip()
        if chunk and chunk.lower() not in {o.lower() for o in out}:
            out.append(chunk)
    return out[:10]


def suggest_terms(run_id: int, model: str = "") -> dict:
    """Schlaegt Suchbegriffe aus den verwendeten Unterlagen vor (per LLM)."""
    context_text, _ = _documents_and_context()
    if not context_text.strip():
        raise RuntimeError("Keine auswertbaren Unterlagen vorhanden – bitte zuerst Dokumente hochladen.")
    prompt = (SUGGEST_PROMPT
              .replace("{{PROFILE}}", db.get_setting("profile", ""))
              .replace("{{PREFERENCES}}", db.get_setting("preferences", ""))
              .replace("{{CONTEXT}}", context_text))
    logbus.log(run_id, "info", "Erzeuge Suchbegriff-Vorschlag aus den Unterlagen ...")
    rc, out = oc.run(prompt, model=model, run_id=run_id)
    keywords = _parse_keywords(oc.clean_text(out))
    if not keywords:
        raise RuntimeError("Keine auswertbare Begriffsliste vom Modell erhalten.")
    logbus.log(run_id, "info", "Vorschlag: %s" % ", ".join(keywords))
    return {"keywords": ", ".join(keywords)}


def _score_candidates(candidates: list, profile: str, preferences: str,
                      context_text: str, run_id: int, model: str) -> dict:
    """Bewertet die Kandidaten in einem werkzeugfreien Schritt. Liefert {index: score_dict}."""
    prompt = (SCORE_PROMPT
              .replace("{{PROFILE}}", profile)
              .replace("{{PREFERENCES}}", preferences)
              .replace("{{CV}}", context_text or "(keine Dokumente ausgewaehlt)")
              .replace("{{THRESHOLD}}", db.get_setting("fit_threshold", "0") or "0")
              .replace("{{CANDIDATES}}", _candidates_block(candidates)))
    logbus.log(run_id, "info", "Bewerte %d Jobboersen-Kandidaten ..." % len(candidates))
    rc, out = oc.run(prompt, model=model, run_id=run_id)
    data = oc.extract_json(out)
    if not data:
        raise RuntimeError("Keine auswertbare JSON-Antwort der Kandidaten-Bewertung.")
    scores = {}
    for item in data.get("jobs", data if isinstance(data, list) else []):
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("i"))
        except (TypeError, ValueError):
            continue
        if 1 <= index <= len(candidates):
            scores[index] = item
    if not scores:
        raise RuntimeError("Kandidaten-Bewertung lieferte keine verwertbaren Zuordnungen.")
    return scores


def _save_candidates(candidates: list, scores: dict, run_id: int) -> tuple:
    """Speichert die Kandidaten. Bewertete unter der Fit-Schwelle werden verworfen;
    unbewertete (Bewertung fehlgeschlagen) werden gesichert, damit nichts verloren geht.

    Gibt (neu, bewertet, verworfen) zurueck.
    """
    threshold = int(db.get_setting("fit_threshold", "0") or 0)
    added, scored, skipped = 0, 0, 0
    for i, cand in enumerate(candidates, 1):
        s = scores.get(i)
        if s:
            score = int(s.get("score") or 0)
            if threshold and score < threshold:
                skipped += 1
                continue
            cand["score"] = score
            cand["fit"] = s.get("fit", "")
            cand["rationale"] = s.get("rationale", "")
            cand["language"] = s.get("lang") or cand.get("language", "")
            if (s.get("description") or "").strip():
                cand["description"] = s["description"].strip()[:2500]
            scored += 1
        if not (s and (s.get("description") or "").strip()):
            # Rohe Boersen-Beschreibung als Sicherheitsnetz begrenzen.
            cand["description"] = (cand.get("description") or "")[:2000]
        cand["status"] = "gefunden"
        cand["run_id"] = run_id
        _, created = db.upsert_job(cand)
        if created:
            added += 1
            note = "Fit %s" % cand.get("score") if s else "ohne Bewertung"
            logbus.log(run_id, "info", "Neu: %s – %s (%s, %s)" % (
                cand.get("company"), cand.get("title"), note, cand.get("source", "")))
    if skipped:
        logbus.log(run_id, "info", "%d Kandidaten unter Fit-Schwelle %d verworfen."
                   % (skipped, threshold))
    return added, scored, skipped


def _web_search(run_id: int, model: str, extra: str, profile: str, preferences: str,
                context_text: str, docs_list: str, existing: str, existing_count: int) -> int:
    """Websuche nach zusaetzlichen Stellen. Gibt die Zahl neu angelegter Jobs zurueck."""
    prompt = (WEB_PROMPT
              .replace("{{PROFILE}}", profile)
              .replace("{{PREFERENCES}}", preferences)
              .replace("{{EXTRA}}", extra)
              .replace("{{THRESHOLD}}", db.get_setting("fit_threshold", "0") or "0")
              .replace("{{CV}}", context_text or "(keine Dokumente ausgewaehlt)")
              .replace("{{DOCS}}", docs_list)
              .replace("{{EXISTING}}", existing))
    logbus.log(run_id, "info", "Websuche nach weiteren Stellen (%d bekannte ausgeschlossen) ..."
               % existing_count)
    rc, out = oc.run(prompt, model=model, run_id=run_id)
    data = oc.extract_json(out)
    if not data:
        raise RuntimeError("Keine auswertbare JSON-Antwort der Websuche.")
    jobs = data.get("jobs", data if isinstance(data, list) else [])
    threshold = int(db.get_setting("fit_threshold", "0") or 0)
    added = skipped = 0
    for job in jobs:
        if not job.get("company") or not job.get("title"):
            continue
        if threshold and int(job.get("score") or 0) < threshold:
            skipped += 1
            continue
        job["source"] = job.get("source") or "search"
        job["run_id"] = run_id
        job["language"] = job.get("lang") or job.get("language") or ""
        job.setdefault("status", "gefunden")
        _, created = db.upsert_job(job)
        if created:
            added += 1
            logbus.log(run_id, "info", "Neu (Web): %s – %s (Fit %s)" % (
                job.get("company"), job.get("title"), job.get("score", "?")))
    if skipped:
        logbus.log(run_id, "info", "%d Web-Treffer unter Fit-Schwelle %d verworfen."
                   % (skipped, threshold))
    return added


def run_search(run_id: int, model: str = "", extra: str = "") -> dict:
    profile = db.get_setting("profile", "")
    preferences = db.get_setting("preferences", "")
    extra = extra or db.get_setting("search_extra", "")
    existing_rows = db.query("SELECT company, title FROM jobs ORDER BY found_at DESC")
    existing = "\n".join("- %s – %s" % (r["company"], r["title"]) for r in existing_rows) or "(keine)"
    context_text, docs_list = _documents_and_context()
    warnings = []

    # --- Phase 1: Jobboersen -> Kandidaten bewerten und immer speichern ---
    logbus.log(run_id, "info", "Frage Jobboersen ab (zusaetzlich zur Websuche) ...")
    try:
        candidates = sources.collect(run_id)
    except Exception as exc:
        candidates = []
        warnings.append("Jobboersen fehlgeschlagen: %s" % exc)
    candidates = [c for c in candidates if not db.is_known(c.get("company"), c.get("title"), c.get("url"))]
    logbus.log(run_id, "info", "%d unbekannte Kandidaten von Jobboersen." % len(candidates))

    scores = {}
    if candidates:
        try:
            scores = _score_candidates(candidates, profile, preferences, context_text, run_id, model)
        except Exception as exc:
            warnings.append("Kandidaten-Bewertung fehlgeschlagen: %s" % exc)
            logbus.log(run_id, "error", "Kandidaten-Bewertung fehlgeschlagen (%s) – "
                       "Kandidaten werden unbewertet gesichert." % exc)
    cand_new, cand_scored, cand_skipped = _save_candidates(candidates, scores, run_id)

    # --- Phase 2: Websuche (unabhaengig; Kandidaten sind bereits gesichert) ---
    web_new = 0
    try:
        web_new = _web_search(run_id, model, extra, profile, preferences,
                              context_text, docs_list, existing, len(existing_rows))
    except Exception as exc:
        warnings.append("Websuche fehlgeschlagen: %s" % exc)
        logbus.log(run_id, "error", "Websuche fehlgeschlagen: %s" % exc)

    if not candidates and web_new == 0 and warnings:
        raise RuntimeError("; ".join(warnings))
    if warnings:
        logbus.log(run_id, "info", "Teilweise abgeschlossen: %s" % "; ".join(warnings))
    logbus.log(run_id, "info", "%d neue Jobs (%d von Jobboersen, davon %d bewertet; %d aus Websuche; "
               "%d unter der Fit-Schwelle verworfen)."
               % (cand_new + web_new, cand_new, cand_scored, web_new, cand_skipped))
    return {"gefunden": len(candidates) + web_new, "neu": cand_new + web_new,
            "kandidaten": len(candidates), "bewertet": cand_scored,
            "jobboersen_neu": cand_new, "web_neu": web_new,
            "unter_schwelle": cand_skipped, "warnungen": warnings}
