#!/usr/bin/env python3
"""Testlauf der mail-zentrischen Auswertung OHNE Datenbank-Schreibzugriff.

Scannt das Postfach (read-only), bewertet jede Mail einzeln, aggregiert pro Job und
vergleicht die Vorschlaege mit dem aktuellen DB-Stand. Schreibt nur eine Report-Datei.

Aufruf (auf VEGA):  PYTHONPATH=. .venv/bin/python tools/tracking_test.py --since 2026-07-01
"""
import argparse
import json
import os
import sys

from app import config, db
from app.engines import tracking as t
from app.engines import tracking_mail as tm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-07-01")
    ap.add_argument("--model", default="")
    ap.add_argument("--batch", type=int, default=100)
    ap.add_argument("--out", default=str(config.DATA_DIR / "tracking_test_report.json"))
    args = ap.parse_args()

    db.init_db()
    model = args.model or db.get_setting("model", config.DEFAULT_MODEL)
    jobs = db.query("SELECT id, company, title FROM jobs")

    client = t._connect()
    try:
        mails = t._scan(client, jobs, since_iso=args.since)
    finally:
        try:
            client.logout()
        except Exception:
            pass
    for i, m in enumerate(mails):
        m["id"] = i
    date_by_id = {m["id"]: m.get("date", "") for m in mails}
    print("Mails gescannt:", len(mails), flush=True)

    raw = tm.classify(mails, jobs, model=model, batch=args.batch, run_id=None)
    assoc, cand = tm.propose(raw, date_by_id)
    print("Modell-Aussagen:", len(raw), "| zugeordnet:", len(assoc), "| Statusvorschlaege:", len(cand), flush=True)

    current = {r["job_id"]: r for r in db.query(
        "SELECT job_id, phase, response_at FROM applications")}
    job_meta = {j["id"]: j for j in db.query("SELECT id, company, status, manual FROM jobs")}

    changes = []
    same = 0
    for jid, c in cand.items():
        meta = job_meta.get(jid)
        if not meta:
            continue
        proposed = config.PHASE_TO_STATUS.get(c["phase"], "beworben")
        cur_status = meta["status"]
        cur_phase = current.get(jid, {}).get("phase", "")
        if meta["manual"]:
            changes.append({"job_id": jid, "company": meta["company"], "kind": "manual_geschuetzt",
                            "current": cur_status, "proposed_phase": c["phase"],
                            "proposed_status": proposed, "date": c["date"]})
        elif proposed == cur_status:
            same += 1
        else:
            changes.append({"job_id": jid, "company": meta["company"], "kind": "abweichung",
                            "current": cur_status, "current_phase": cur_phase,
                            "proposed_phase": c["phase"], "proposed_status": proposed,
                            "date": c["date"], "status_text": c["status_text"]})

    report = {
        "since": args.since, "model": model, "mails": len(mails),
        "assoc": len(assoc), "proposals": len(cand), "same": same,
        "changes": changes,
        "associations": {str(k): v for k, v in assoc.items()},
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)

    print("\n== Vergleich (nur Vorschlaege, nichts geschrieben) ==")
    print("gleich geblieben:", same)
    print("Abweichungen / manuell geschuetzt:", len(changes))
    print()
    for ch in changes:
        if ch["kind"] == "manual_geschuetzt":
            print("  [manuell] %-30s bleibt %s (Vorschlag waere %s)" % (
                ch["company"][:30], ch["current"], ch["proposed_phase"]))
        else:
            print("  %-30s %s -> %s (%s, %s)" % (
                ch["company"][:30], ch["current"], ch["proposed_status"],
                ch["proposed_phase"], ch["date"]))
    print("\nReport:", args.out)


if __name__ == "__main__":
    main()
