#!/usr/bin/env python3
"""Prueft die Job-Datenbank auf Duplikate (nur lesend).

Gruppiert nach normalisierter Firma + Rolle (und nach URL). Zeigt Kandidaten,
die dieselbe Stelle sein koennten, damit man sie manuell zusammenfuehren kann.

Aufruf:  PYTHONPATH=. .venv/bin/python tools/check_dupes.py
"""
import sys
from collections import defaultdict

from app import db


def main() -> int:
    db.init_db()
    rows = db.query("SELECT id, company, title, url, found_at, status FROM jobs ORDER BY id")

    by_key = defaultdict(list)
    by_url = defaultdict(list)
    for r in rows:
        by_key[(db.norm_company(r["company"]), db.norm_title(r["title"]))].append(r)
        if (r["url"] or "").strip():
            by_url[r["url"].strip()].append(r)

    found = False
    for key, group in sorted(by_key.items()):
        if len(group) > 1:
            found = True
            print("Gleiche Firma+Rolle:", " | ".join(key))
            for r in group:
                print("   #%s [%s] %s – %s" % (r["id"], r["found_at"][:10], r["company"], r["title"]))
                print("        %s" % (r["url"] or "(keine URL)"))
    for url, group in by_url.items():
        if len(group) > 1:
            found = True
            print("Gleiche URL:")
            for r in group:
                print("   #%s %s – %s" % (r["id"], r["company"], r["title"]))

    if not found:
        print("Keine Duplikate gefunden (%d Jobs geprueft)." % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
