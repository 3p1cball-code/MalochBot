#!/usr/bin/env python3
"""Ersetzt rohe Jobboersen-Beschreibungen durch die LLM-Zusammenfassung.

Hintergrund: Aeltere Laeufe haben die (sehr lange) Original-Beschreibung der Boerse
gespeichert. Dieser Lauf bewertet solche Jobs erneut und schreibt die kurze
Zusammenfassung "Was die Position ausmacht" (plus Fit/Rationale) in die Datenbank.

Betroffen sind Jobs mit Quellen arbeitsagentur/jobspy:* und einer Beschreibung ueber
der angegebenen Laenge. Der Fit-Filter wird hier NICHT angewandt (es wird nur die
vorhandene Beschreibung ersetzt).

Aufruf:  PYTHONPATH=. .venv/bin/python tools/resummarize_board_jobs.py [mindestlaenge]
"""
import sys

from app import db, logbus
from app.engines import search


def main() -> int:
    db.init_db()
    min_len = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
    rows = db.query(
        "SELECT id, company, title, location, remote, url, company_url, published_at, "
        "description, source FROM jobs "
        "WHERE (source='arbeitsagentur' OR source LIKE 'jobspy:%') "
        "AND length(description) > ? ORDER BY id", (min_len,))
    if not rows:
        print("Nichts zu tun.")
        return 0
    print("%d Jobs werden neu zusammengefasst ..." % len(rows))

    context_text, _ = search._documents_and_context()
    model = db.get_setting("model", "")
    run_id = logbus.start("resummarize", model)
    try:
        scores = search._score_candidates([dict(r) for r in rows], db.get_setting("profile", ""),
                                          db.get_setting("preferences", ""), context_text,
                                          run_id, model)
        updated = 0
        for i, row in enumerate(rows, 1):
            s = scores.get(i)
            if not s:
                continue
            desc = (s.get("description") or "").strip()[:2500]
            db.execute(
                "UPDATE jobs SET score=?, fit=?, rationale=?, description=?, language=? WHERE id=?",
                (int(s.get("score") or 0), s.get("fit", ""), s.get("rationale", ""),
                 desc or (row["description"] or "")[:2000],
                 s.get("lang") or "", row["id"]))
            updated += 1
            print("  #%s %s – %s" % (row["id"], row["company"], row["title"]))
        logbus.finish(run_id, "ok", "%d Jobs neu zusammengefasst." % updated)
        print("Fertig: %d von %d aktualisiert." % (updated, len(rows)))
    except Exception as exc:
        logbus.log(run_id, "error", str(exc))
        logbus.finish(run_id, "fehler", str(exc))
        print("Fehler: %s" % exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
