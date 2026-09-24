"""Bewerbungs-Tracking: liest das Postfach inkrementell per IMAP (read-only),
laesst den Status von opencode/LLM bewerten und aktualisiert die Datenbank.
"""

import email
import imaplib
import re
import unicodedata
from datetime import datetime, date
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from .. import config, db, logbus, providers, secrets
from .. import opencode_adapter as oc

ATS_DOMAINS = (
    "recruitee", "ashbyhq", "greenhouse", "personio", "softgarden", "teamtailor",
    "comeet", "breezy", "smartrecruiters", "lever.co", "workday", "onlyfy",
    "homerun", "dvinci", "hrworks", "umantis", "join.com",
)
SHORT_TOKENS = {"hse", "indg", "snocks"}
STOP = {
    "gmbh", "se", "ag", "inc", "ltd", "llc", "the", "and", "co", "company",
    "group", "holding", "home", "shopping", "europe", "content", "media",
    "organics", "studios", "studio", "grip", "you", "about", "island", "mov",
    "frames", "solutions", "tech", "labs", "alexander",
}

PROMPT = """Du wertest die Bewerbungs-Mailbox aus.

Angehaengt ist context.json mit:
- "jobs": Bewerbungen (id, firma, position).
- "mails": saemtliche E-Mails aus Ein- und Ausgang (date, direction, from, to,
  subject, body). "direction" ist "in" (empfangen) oder "out" (von der Person gesendet).

Es sind ALLE Mails enthalten - viele davon betreffen keine Bewerbung (Newsletter,
Job-Alerts, privates). Ignoriere solche. Ordne eine Mail nur dann einem Job zu, wenn
Firma/Absender/Empfaenger/Kontext eindeutig passen.

Ordne JEDEM Job einen Status zu, ausschliesslich anhand der Mails.

Erlaubte Phasen (exakt so):
- "Interview-Prozess": Einladung/Interview/aktiver Austausch, kein abschliessendes Nein.
- "Absage": eindeutige Absage (auch Stelle besetzt, andere Kandidaten).
- "Beworben": eine abgeschickte Bewerbung ist belegt (z. B. gesendete Mail an das
  Unternehmen/Portal), aber noch keine Rueckmeldung.
- "Eingangsbestaetigung": nur automatische/neutrale Eingangsbestaetigung.
- "Warte auf Rueckmeldung": menschliche Antwort, aber noch keine Entscheidung.
- "Ohne Rueckmeldung": keine passende Mail gefunden.

Hinweis: Jede Mail hat "direction". "out" = von der Person gesendet, "in" = empfangen.
Eine gesendete Bewerbung (direction "out") an ein Unternehmen belegt, dass beworben wurde.
Regeln:
- Neueste maßgebliche Mail entscheidet. Bestaetigung + spaetere Absage => "Absage".
- Absagen von Termin-/Eingangsmails unterscheiden; "leider" allein ist keine Absage.
- Auch eine Benachrichtigung von Jobboersen (LinkedIn/XING), dass eine Bewerbung
  verschickt/gesendet wurde, belegt eine Bewerbung => Phase "Beworben".
- Nur zuordnen, wenn Firma/Absender/Empfaenger/Kontext eindeutig passen.

Antworte AUSSCHLIESSLICH mit JSON:
{"jobs":[{"id":1,"phase":"...","bestaetigung":"ja","antwort_am":"YYYY-MM-DD","absender":"...","betreff":"...","status_text":"...","confidence":"hoch","mail_ids":[1,4]}]}

"mail_ids" = die ids (aus "mails") der Nachrichten, die diesen Job belegen. Newsletter,
Job-Alerts und Aehnliches gehoeren NICHT dazu.
"""


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower())


def _decode(value: str) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _body(msg, limit=1200) -> str:
    parts = msg.walk() if msg.is_multipart() else [msg]
    plain, html = [], []
    for part in parts:
        if part.get_content_type() not in ("text/plain", "text/html"):
            continue
        try:
            payload = part.get_payload(decode=True)
        except Exception:
            continue
        if not payload:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", "replace")
        (plain if part.get_content_type() == "text/plain" else html).append(text)
    text = "\n".join(plain) if plain else "\n".join(html)
    text = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
    text = re.sub(r"@(import|media|font-face|charset)[^;{]*[;{][^}]*}", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z#0-9]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _tokens(jobs) -> set:
    tokens = set()
    for job in jobs:
        for tok in _norm(job["company"]).split():
            if (len(tok) > 2 and tok not in STOP) or tok in SHORT_TOKENS:
                tokens.add(tok)
    return tokens


def _is_sent(folder: str) -> bool:
    f = (folder or "").lower()
    return any(k in f for k in ("sent", "gesendet", "versenden", "outbox"))


def _connect():
    provider = db.get_setting("mail_provider", "")
    host = db.get_setting("mail_host", "")
    port = int(db.get_setting("mail_port", "993") or 993)
    address = db.get_setting("mail_email", "")
    password = secrets.store.get("mail_password", "")
    host, port = providers.resolve(provider, host, port)
    if not host or not address or not password:
        raise RuntimeError("Mailkonto unvollstaendig. Bitte in den Einstellungen verbinden.")
    client = imaplib.IMAP4_SSL(host, port)
    client.login(address, password)
    return client


def _list_folders(client):
    ok, data = client.list()
    names = []
    if ok != "OK":
        return names
    for raw in data:
        if not raw:
            continue
        text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
        match = re.search(r'("[^"]*")\s*$', text)
        if match:
            names.append(match.group(1)[1:-1])
    return names


def _scan(client, jobs=None):
    since_iso = db.get_setting("last_scan", "") or date.today().isoformat()
    since = datetime.strptime(since_iso, "%Y-%m-%d").strftime("%d-%b-%Y")
    configured = db.get_setting("mail_folders", "INBOX")
    address = (db.get_setting("mail_email", "") or "").lower()
    folders = _list_folders(client)
    wanted = [f for f in folders if f.upper().startswith("INBOX") or _is_sent(f)] + \
             [f for f in configured.split(",") if f.strip() and f.strip() not in folders]
    skip = {"Drafts", "Trash", "Spam", "Entwürfe", "Papierkorb"}
    wanted = [f for f in wanted if f not in skip]
    found = []
    for folder in wanted:
        sent = _is_sent(folder)
        try:
            client.select('"%s"' % folder.replace('"', '\\"'), readonly=True)
            ok, data = client.search(None, "(SINCE %s)" % since)
        except Exception:
            continue
        if ok != "OK" or not data or not data[0]:
            continue
        for uid in data[0].split():
            try:
                ok, raw = client.fetch(uid, "(BODY.PEEK[])")
            except Exception:
                continue
            if ok != "OK" or not raw or not isinstance(raw[0], tuple):
                continue
            msg = email.message_from_bytes(raw[0][1])
            subj = _decode(msg.get("Subject"))
            frm = _decode(msg.get("From"))
            to = _decode(msg.get("To"))
            try:
                iso = parsedate_to_datetime(msg.get("Date")).date().isoformat()
            except Exception:
                iso = ""
            is_out = sent or bool(address and address in frm.lower())
            found.append({"date": iso, "folder": folder, "from": frm, "to": to,
                          "direction": "out" if is_out else "in",
                          "subject": subj, "body": _body(msg, 250)})
    found.sort(key=lambda m: m["date"])
    return found


def _store_emails(mails, jobs, run_id):
    """Speichert alle Mails; die Zuordnung zu Jobs macht das LLM (siehe run_tracking)."""
    mapping = {}
    for i, mail in enumerate(mails):
        try:
            db.execute(
                "INSERT OR IGNORE INTO emails(date,folder,from_addr,subject,body,job_id,run_id,"
                "created_at) VALUES(?,?,?,?,?,?,?,?)",
                (mail["date"], mail["folder"], mail["from"], mail["subject"],
                 mail["body"], None, run_id, db.now_iso()))
            row = db.one(
                "SELECT id FROM emails WHERE date=? AND folder=? AND from_addr=? AND subject=?",
                (mail["date"], mail["folder"], mail["from"], mail["subject"]))
            if row:
                mapping[i] = row["id"]
        except Exception:
            pass
    return mapping


def run_tracking(run_id: int, model: str = "") -> dict:
    jobs = db.query("SELECT id, company, title FROM jobs")
    if not jobs:
        raise RuntimeError("Es sind noch keine Jobs in der Datenbank.")
    logbus.log(run_id, "info", "Verbinde mit Postfach ...")
    client = _connect()
    try:
        logbus.log(run_id, "info", "Scanne neue Mails ...")
        mails = _scan(client, jobs)
    finally:
        try:
            client.logout()
        except Exception:
            pass
    logbus.log(run_id, "info", "%d Mails gelesen (Ein-/Ausgang)." % len(mails))
    for i, m in enumerate(mails):
        m["id"] = i
    mail_rows = _store_emails(mails, jobs, run_id)

    import json
    BATCH = 100
    batches = [mails[i:i + BATCH] for i in range(0, len(mails), BATCH)]
    merged = {}
    job_mails = {}
    for idx, batch in enumerate(batches, 1):
        context_path = config.DATA_DIR / ("context_%d.json" % idx)
        context_path.write_text(
            json.dumps({"jobs": jobs, "mails": batch}, ensure_ascii=False), encoding="utf-8")
        logbus.log(run_id, "info", "Bewerte Mails %d/%d (%d Mails) ..." % (idx, len(batches), len(batch)))
        rc, out = oc.run(PROMPT, model=model, run_id=run_id, attach=[str(context_path)])
        data = oc.extract_json(out)
        if not data:
            logbus.log(run_id, "warn", "Batch %d: keine auswertbare Antwort." % idx)
            continue
        for item in data.get("jobs", []):
            jid = item.get("id")
            if not isinstance(jid, int):
                continue
            for mid in item.get("mail_ids", []) or []:
                if isinstance(mid, int):
                    job_mails.setdefault(jid, set()).add(mid)
            cur = merged.get(jid)
            if cur is None or (item.get("antwort_am") or "") >= (cur.get("antwort_am") or ""):
                merged[jid] = item
    if not merged:
        raise RuntimeError("Keine auswertbare JSON-Antwort vom Modell erhalten.")

    linked = 0
    for jid, mids in job_mails.items():
        for mid in mids:
            eid = mail_rows.get(mid)
            if eid:
                db.execute("UPDATE emails SET job_id=? WHERE id=?", (jid, eid))
                linked += 1
    logbus.log(run_id, "info", "%d Mail-Job-Zuordnungen (LLM)." % linked)

    updated = 0
    for item in merged.values():
        jid = item.get("id")
        if not isinstance(jid, int):
            continue
        phase = item.get("phase", "Ohne Rueckmeldung")
        job = db.one("SELECT id, status, manual FROM jobs WHERE id=?", (jid,))
        if not job:
            continue

        # Manuell gesetzter Status wird nie automatisch ueberschrieben.
        if job.get("manual"):
            logbus.log(run_id, "info", "Job #%d: Status manuell gesetzt - bleibt unveraendert." % jid)
            continue

        # Ohne Rueckmeldung ist KEIN Beweis fuer eine Bewerbung -> nur "gefunden".
        if phase == "Ohne Rueckmeldung":
            if job["status"] not in ("beworben", "interview", "angebot", "abgelehnt", "vorgemerkt"):
                db.execute("UPDATE jobs SET status='gefunden' WHERE id=?", (jid,))
            continue

        new_status = config.PHASE_TO_STATUS.get(phase, "beworben")
        current = job["status"]
        if current in ("angebot", "abgelehnt", "ignoriert"):
            final = current
        elif new_status == "abgelehnt":
            final = "abgelehnt"
        else:
            rank_current = config.STATUS_RANK.get(current, 0)
            rank_new = config.STATUS_RANK.get(new_status, 0)
            final = new_status if rank_new >= rank_current else current
        db.execute("UPDATE jobs SET status=? WHERE id=?", (final, jid))

        existing = db.one("SELECT id FROM applications WHERE job_id=?", (jid,))
        if existing:
            db.execute(
                "UPDATE applications SET phase=?, response_at=?, notes=?, updated_at=? WHERE job_id=?",
                (phase, item.get("antwort_am", ""), item.get("status_text", ""),
                 db.now_iso(), jid))
        else:
            db.execute(
                "INSERT INTO applications(job_id, phase, response_at, notes, channel, updated_at) "
                "VALUES(?,?,?,?,?,?)",
                (jid, phase, item.get("antwort_am", ""), item.get("status_text", ""),
                 "mail", db.now_iso()))
        updated += 1
        logbus.log(run_id, "info", "Status: Job #%d -> %s (%s)" % (jid, final, phase))

    db.set_setting("last_scan", datetime.now().strftime("%Y-%m-%d"))
    logbus.log(run_id, "info", "%d Bewerbungen aktualisiert." % updated)
    return {"mails": len(mails), "aktualisiert": updated}
