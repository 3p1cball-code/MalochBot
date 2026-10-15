#!/usr/bin/env python3
"""Repariert Stellen-URLs in der Datenbank.

Ersetzt Boersen-Such- und Uebersichtsseiten (z. B. Glassdoor
".../Job/berlin-technical-artist-jobs-SRCH_..." oder Indeed
".../q-comfyui-jobs.html") durch eine gezielte Suche nach Firma + Rolle, damit
der Link nicht ins Leere fuehrt. Direkte Stellenanzeigen bleiben unveraendert.

Mit --set ID=URL lassen sich einzelne Jobs auf eine verifizierte Direktadresse
setzen (z. B. den echten Glassdoor-Direktlink). Standard ist ein Trockenlauf;
erst --apply schreibt.

Aufruf:
  .venv/bin/python tools/fix_job_urls.py                     # Trockenlauf
  .venv/bin/python tools/fix_job_urls.py --apply             # Such-URLs ersetzen
  .venv/bin/python tools/fix_job_urls.py --set 127=https://... --apply
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import auth, db  # noqa: E402
from app.engines import urlfix  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Stellen-URLs bereinigen/reparieren.")
    parser.add_argument("--apply", action="store_true",
                        help="Aenderungen schreiben (sonst nur anzeigen)")
    parser.add_argument("--set", action="append", default=[], metavar="ID=URL",
                        help="Direktadresse fuer einen Job setzen (mehrfach moeglich)")
    args = parser.parse_args()

    overrides = {}
    for item in args.set:
        jid, sep, url = item.partition("=")
        if not sep or not jid.strip().isdigit():
            print("Ungueltiges --set: %r (erwartet ID=URL)" % item)
            return 2
        overrides[int(jid)] = url.strip()

    auth.activate()
    db.init_db()
    rows = db.query("SELECT id, company, title, url FROM jobs")
    changed = 0
    for row in rows:
        current = (row["url"] or "").strip()
        if row["id"] in overrides:
            new = overrides[row["id"]]
        elif urlfix.is_search_url(current):
            new = urlfix.fix_job_url(current, row["company"], row["title"])
        else:
            continue
        if new == current:
            continue
        changed += 1
        print("Job %d  %s – %s" % (row["id"], row["company"], row["title"]))
        print("  alt: %s" % (current or "(leer)"))
        print("  neu: %s" % (new or "(leer)"))
        if args.apply:
            db.execute("UPDATE jobs SET url=? WHERE id=?", (new, row["id"]))

    print("\n%d URL(s) %s." % (changed, "aktualisiert" if args.apply else "zu aendern (Trockenlauf)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
