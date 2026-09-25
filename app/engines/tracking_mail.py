"""Mail-zentrisches Tracking (Prototyp, separat von tracking.py).

Idee: Statt "ordne jedem Job einen Status zu" wird JEDE Mail einzeln bewertet:
"aendert diese Mail den Status eines bekannten Jobs?". Jobs ohne Mail tauchen
nicht auf. Ergebnis wird pro Job auf die neueste maessgebliche Mail reduziert.

Diese Datei schreibt NICHT in die Datenbank - sie liefert nur Vorschlaege.
"""

import json

from .. import config, logbus
from .. import opencode_adapter as oc
from . import tracking as t

MAIL_PROMPT = """Du wertest eine Mailbox aus.

Angehaengt context.json mit:
- "jobs": bekannte Jobs (id, firma, titel).
- "mails": Mails (id, date, direction, from, to, subject, body, hint).
  "direction" ist "in" (empfangen) oder "out" (von der Person gesendet).
  "hint" ist ggf. ein aus Links/Signatur abgeleiteter Firmen-Hinweis.

Aufgabe: Gehe JEDE Mail einzeln durch und entscheide, ob sie den Status eines
bekannten Jobs aendert oder belegt. Jobs ohne passende Mail NICHT erwaehnen.

Gib pro relevanter Mail zurueck:
- mail_id  (id aus "mails")
- job_id   (id des zugeordneten Jobs oder null)
- phase   eine von: "Beworben", "Eingangsbestaetigung", "Interview-Prozess",
          "Absage", "Warte auf Rueckmeldung" - ODER "keine", wenn die Mail zwar
          zum Job gehoert, den Status aber nicht aendert.
- antwort_am  YYYY-MM-DD oder ""
- status_text  kurzer deutscher Satz
- confidence  hoch/mittel/niedrig

Regeln:
- "out" (gesendete Bewerbung) belegt: beworben wurde => "Beworben".
- Jobboersen-Benachrichtigung (LinkedIn/XING) "Bewerbung wurde gesendet" => "Beworben".
- Firmenbezug steht oft erst im Body/Signatur (hint nutzen).
- Newsletter/Job-Alerts/privates => job_id null und phase "keine".
- Absage (auch "Stelle besetzt"/andere Kandidaten) => "Absage"; "leider" allein ist keine Absage.

Antworte AUSSCHLIESSLICH mit JSON:
{"mails":[{"mail_id":1,"job_id":34,"phase":"Beworben","antwort_am":"2026-09-25","status_text":"...","confidence":"hoch"}]}
"""


def classify(mails, jobs, model: str = "", batch: int = 100, run_id=None):
    """Bewertet alle Mails in Batches. Gibt die rohe 'mails'-Liste des Modells zurueck."""
    out_items = []
    batches = [mails[i:i + batch] for i in range(0, len(mails), batch)]
    for idx, batch_mails in enumerate(batches, 1):
        context = {"jobs": jobs, "mails": batch_mails}
        path = config.DATA_DIR / ("mc_context_%d.json" % idx)
        path.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
        if run_id:
            logbus.log(run_id, "info", "Mail-Batch %d/%d (%d Mails) ..." % (idx, len(batches), len(batch_mails)))
        else:
            print("Mail-Batch %d/%d (%d Mails) ..." % (idx, len(batches), len(batch_mails)), flush=True)
        rc, out = oc.run(MAIL_PROMPT, model=model, run_id=run_id, attach=[str(path)])
        data = oc.extract_json(out)
        if not data:
            if run_id:
                logbus.log(run_id, "warn", "Batch %d: keine auswertbare Antwort." % idx)
            else:
                print("Batch %d: keine auswertbare Antwort." % idx, flush=True)
            continue
        out_items.extend(data.get("mails", []) or [])
    return out_items


def propose(out_items, mail_date_by_id: dict):
    """Aggregiert: pro Job die neueste maessgebliche Mail + Mail->Job-Zuordnungen."""
    assoc = {}
    cand = {}
    for item in out_items:
        mid = item.get("mail_id")
        if not isinstance(mid, int):
            continue
        jid = item.get("job_id")
        if isinstance(jid, int):
            assoc[mid] = jid
        phase = t._clean_phase(item.get("phase"))
        if phase == "Ohne Rueckmeldung":
            continue
        if not isinstance(jid, int):
            continue
        date = t._clean_date(item.get("antwort_am")) or (mail_date_by_id.get(mid) or "")
        cur = cand.get(jid)
        if cur is None or date >= cur["date"]:
            cand[jid] = {"phase": phase, "date": date,
                         "status_text": item.get("status_text", ""), "mail_id": mid}
    return assoc, cand
