"""Bewerbungs-Tracking: liest das Postfach inkrementell per IMAP (read-only),
laesst den Status von opencode/LLM bewerten und aktualisiert die Datenbank.
"""

import email
import imaplib
import json
import re
import time
import unicodedata
from datetime import datetime, date
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

from .. import config, db, logbus, providers, secrets

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


ATS_HOSTS = ("softgarden.io", "personio.de", "personio.com", "greenhouse.io", "recruitee.com",
             "comeet.com", "ashbyhq.com", "myworkdayjobs.com", "workday.com", "lever.co",
             "teamtailor.com", "join.com", "onlyfy.com", "breezy.hr", "smartrecruiters.com",
             "umantis.com", "rexx-systems.com", "haufe.de")


def _hint(frm: str, body: str) -> str:
    """Rauer Firmen-Hinweis aus Links/Absender (fuer Bewerbungsportale)."""
    text = ((frm or "") + " " + (body or "")).lower()
    for host in re.findall(r"([a-z0-9-]+(?:\.[a-z0-9-]+){1,3})", text):
        parts = host.split(".")
        base = ".".join(parts[-2:])
        if base in ATS_HOSTS and len(parts) >= 3:
            sub = parts[-3]
            if sub not in ("www", "app", "jobs", "job", "career", "careers", "mail", "email", "noreply"):
                return sub
        elif base not in ATS_HOSTS and base not in ("gmail.com", "eyedea3d.com", "google.com",
                                                    "microsoft.com", "outlook.com", "linkedin.com"):
            return parts[0]
    return ""


_URL_RE = re.compile(r"https?://[^\s<>\"'\)\]]+", re.I)
_LINK_NOISE = re.compile(
    r"(unsubscribe|abmelden|abmeldung|opt-?out|datenschutz|privacy|impressum|"
    r"twitter\.com|facebook\.com|instagram\.com|linkedin\.com|xing\.com|youtube\.com|"
    r"mailchimp|list-manage|sendgrid|mandrill|doubleclick|mailtrack|"
    r"powered-?by|googleusercontent|licdn\.com|gstatic|ui-avatars|w3\.org|zenprospect|"
    r"amazonaws\.com|"
    r"track(ing)?[./?=]|/open\b|/click\b|pixel\.|\.(png|jpe?g|gif|svg|webp|css|js)(\?|$))",
    re.I)
_SCHEDULE_HINTS = ("calendly", "cal.com/", "doodle", "savvycal", "zcal", "tidycal",
                   "meetings.hubspot", "outlook.office.com/book", "outlook.office365.com/book",
                   "bookings.microsoft", "bookings.office", "/book", "calendar.appointments",
                   "/appointments/booking")
_MEETING_HINTS = ("teams.microsoft", "teams.live", "zoom.us", "meet.google", "gotomeeting",
                  "webex", "whereby")
_FORM_HINTS = ("docs.google.com/forms", "forms.office.com", "typeform", "forms.gle",
               "surveymonkey")
_APPLY_HINTS = tuple(ATS_HOSTS) + (
    "greenhouse", "lever.co", "workday", "softgarden", "personio", "comeet", "recruitee",
    "ashby", "smartrecruiters", "teamtailor", "onlyfy", "breezy", "umantis", "jobvite",
    "icims", "/apply", "bewerbung", "application", "dvinci", "hrworks", "homerun",
    "rexx-systems", "haufe")


def _link_label(url: str) -> str:
    u = url.lower()
    if any(k in u for k in _SCHEDULE_HINTS):
        return "Termin finden"
    if any(k in u for k in _MEETING_HINTS):
        return "Meeting-Link"
    if any(k in u for k in _APPLY_HINTS):
        return "Bewerbung/Portal"
    if any(k in u for k in _FORM_HINTS):
        return "Formular"
    return "Link"


def _extract_links(msg, limit: int = 10) -> list:
    """Wichtige Links einer Mail aus Text- und HTML-Teil (inkl. href-Attribute)."""
    urls = []
    parts = msg.walk() if msg.is_multipart() else [msg]
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
        text = text.replace("&amp;", "&").replace("&#38;", "&")
        for match in _URL_RE.findall(text):
            url = match.rstrip(".,;:)]}\"'")
            if url and url not in urls:
                urls.append(url)
    out = []
    for url in urls:
        if _LINK_NOISE.search(url):
            continue
        label = _link_label(url)
        if label == "Link":  # nur wichtige Links behalten
            continue
        out.append({"url": url, "label": label, "imp": True})
        if len(out) >= limit:
            break
    return out


def _clean_phase(value) -> str:
    text = (str(value) if value is not None else "").strip()
    norm = (text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
                .replace("Ä", "ae").replace("Ö", "oe").replace("Ü", "ue").replace("ß", "ss"))
    if norm.lower() in ("ohne rueckmeldung", "ohne ruckmeldung", ""):
        return "Ohne Rueckmeldung"
    for key in config.PHASE_TO_STATUS:
        if key.lower() == norm.lower():
            return key
    return "Ohne Rueckmeldung"


def _clean_date(value) -> str:
    text = (str(value) if value is not None else "").strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text
    return ""


def _connect(account=None):
    if account is None:
        accounts = db.list_mail_accounts()
        if not accounts:
            raise RuntimeError("Kein Mailkonto eingerichtet. Bitte in den Einstellungen verbinden.")
        account = accounts[0]
    provider = account.get("provider", "")
    host = account.get("host", "")
    port = int(account.get("port", "993") or 993)
    address = account.get("email", "")
    password = (account.get("_password")
                or secrets.store.get("mail_password_%s" % account.get("id", ""), "")
                or secrets.store.get("mail_password", ""))
    host, port = providers.resolve(provider, host, port)
    if not host or not address or not password:
        raise RuntimeError("Mailkonto '%s' unvollstaendig. Bitte in den Einstellungen ergaenzen."
                           % (address or "(ohne Adresse)"))
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


def _scan(client, account=None, since_iso=None, jobs=None):
    account = account or {}
    since_iso = since_iso or db.get_setting("last_scan", "") or date.today().isoformat()
    since = datetime.strptime(since_iso, "%Y-%m-%d").strftime("%d-%b-%Y")
    configured = account.get("folders") or db.get_setting("mail_folders", "INBOX")
    address = (account.get("email") or db.get_setting("mail_email", "") or "").lower()
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
            body = _body(msg, 1200)
            found.append({"date": iso, "folder": folder, "from": frm, "to": to,
                          "direction": "out" if is_out else "in",
                          "subject": subj, "body": body, "hint": _hint(frm, body),
                          "links": _extract_links(msg)})
    found.sort(key=lambda m: m["date"])
    return found


def _store_emails(mails, jobs, run_id):
    """Speichert alle Mails; die Zuordnung zu Jobs macht das LLM (siehe run_tracking)."""
    mapping = {}
    for i, mail in enumerate(mails):
        try:
            db.execute(
                "INSERT INTO emails(date,folder,from_addr,subject,body,links,job_id,run_id,"
                "created_at) VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(date,folder,from_addr,subject) DO UPDATE SET "
                "links=excluded.links, body=excluded.body, run_id=excluded.run_id",
                (mail["date"], mail["folder"], mail["from"], mail["subject"],
                 mail["body"], json.dumps(mail.get("links", []), ensure_ascii=False),
                 None, run_id, db.now_iso()))
            row = db.one(
                "SELECT id FROM emails WHERE date=? AND folder=? AND from_addr=? AND subject=?",
                (mail["date"], mail["folder"], mail["from"], mail["subject"]))
            if row:
                mapping[i] = row["id"]
        except Exception:
            pass
    return mapping


def _apply_merged(merged, run_id):
    """Wendet die je Job ermittelten Phasen an - mit allen Schutzregeln."""
    updated = 0
    for item in merged.values():
        jid = item.get("id")
        if not isinstance(jid, int):
            continue
        phase = _clean_phase(item.get("phase"))
        antwort = _clean_date(item.get("antwort_am"))
        job = db.one("SELECT id, status, manual FROM jobs WHERE id=?", (jid,))
        if not job:
            continue
        app_row = db.one("SELECT phase FROM applications WHERE job_id=?", (jid,))
        prev_phase = app_row["phase"] if app_row else ""

        # Manuell gesetzter Status wird nie automatisch ueberschrieben.
        if job.get("manual"):
            # Faellt hier ein echter Aenderungsvorschlag an, markieren wir das rot.
            if phase != "Ohne Rueckmeldung" and phase != prev_phase:
                db.execute("UPDATE jobs SET hl='locked' WHERE id=?", (jid,))
            logbus.log(run_id, "info", "Job #%d: Status manuell gesetzt - bleibt unveraendert." % jid)
            continue

        # Nur mit Beleg anwenden; ohne Mail unveraendert lassen.
        if phase == "Ohne Rueckmeldung":
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
                (phase, antwort, item.get("status_text", ""), db.now_iso(), jid))
        else:
            db.execute(
                "INSERT INTO applications(job_id, phase, response_at, notes, channel, updated_at) "
                "VALUES(?,?,?,?,?,?)",
                (jid, phase, antwort, item.get("status_text", ""), "mail", db.now_iso()))
        updated += 1
        if phase != prev_phase:
            db.execute("UPDATE jobs SET hl='changed' WHERE id=?", (jid,))
            note = item.get("status_text", "")
            db.execute("INSERT INTO events(job_id, ts, kind, text) VALUES(?,?,?,?)",
                       (jid, db.now_iso(), "status",
                        "Status (Mail): " + phase + ((" – " + note) if note else "")))
        logbus.log(run_id, "info", "Status: Job #%d -> %s (%s)" % (jid, final, phase))
    return updated


def recheck_job(job_id: int, run_id: int, model: str = "") -> dict:
    """Re-Check aus der DB: bewertet die bereits gespeicherten Mails eines Jobs neu.

    Wird beim Entsperren genutzt, damit eine waehrend der Sperre eingegangene Mail
    nicht verloren geht (der inkrementelle Scan wuerde sie nie wieder sehen).
    """
    job = db.one("SELECT id, company, title FROM jobs WHERE id=?", (job_id,))
    if not job:
        raise RuntimeError("Job #%d nicht gefunden." % job_id)
    rows = db.query("SELECT id, date, from_addr, subject, body FROM emails "
                    "WHERE job_id=? ORDER BY date", (job_id,))
    logbus.log(run_id, "info", "Re-Check: %d gespeicherte Mails zu Job #%d." % (len(rows), job_id))
    if not rows:
        logbus.log(run_id, "warn", "Keine gespeicherten Mails zu diesem Job - nichts zu tun.")
        return {"aktualisiert": 0}
    account = (db.get_setting("mail_email", "") or "").lower()
    mails = []
    for i, r in enumerate(rows):
        frm = r["from_addr"] or ""
        body = r["body"] or ""
        mails.append({"id": i, "date": r["date"] or "",
                      "direction": "out" if account and account in frm.lower() else "in",
                      "from": frm, "to": "", "subject": r["subject"] or "",
                      "body": body, "hint": _hint(frm, body)})
    from . import tracking_mail as tm
    items, _, _ = tm.classify(mails, [job], model=model, run_id=run_id)
    assoc, cand = tm.propose(items, {m["id"]: m["date"] for m in mails})
    merged = {jid: {"id": jid, "phase": c["phase"], "antwort_am": c["date"],
                    "status_text": c["status_text"], "mail_ids": []} for jid, c in cand.items()}
    if not merged:
        logbus.log(run_id, "warn", "Keine verwertbare Aussage aus den gespeicherten Mails.")
        return {"aktualisiert": 0}
    db.execute("UPDATE jobs SET hl='' WHERE id=?", (job_id,))
    updated = _apply_merged(merged, run_id)
    logbus.log(run_id, "info", "%d Bewerbungen aktualisiert (Re-Check)." % updated)
    return {"aktualisiert": updated}


def test_account(run_id: int, account: dict) -> dict:
    """Verbindungstest fuer ein einzelnes (ggf. noch nicht gespeichertes) Konto."""
    client = _connect(account)
    try:
        folders = _list_folders(client)
        logbus.log(run_id, "info", "%s: Verbindung erfolgreich. Ordner: %s"
                   % (account.get("email", ""), ", ".join(folders[:12])))
    finally:
        try:
            client.logout()
        except Exception:
            pass
    return {"status": "ok", "ordner": len(folders), "email": account.get("email", "")}


def run_tracking(run_id: int, model: str = "") -> dict:
    jobs = db.query("SELECT id, company, title FROM jobs")
    if not jobs:
        raise RuntimeError("Es sind noch keine Jobs in der Datenbank.")
    accounts = db.list_mail_accounts()
    if not accounts:
        raise RuntimeError("Kein Mailkonto eingerichtet. Bitte in den Einstellungen verbinden.")

    since_iso = db.get_setting("last_scan", "") or None
    mails = []
    ok_accounts = 0
    failed_accounts = []
    for account in accounts:
        label = account.get("email") or "?"
        logbus.log(run_id, "info", "Verbinde Postfach %s ..." % label)
        client, last_exc = None, None
        for attempt in (1, 2, 3):
            try:
                client = _connect(account)
                break
            except Exception as exc:
                last_exc = exc
                if attempt < 3:
                    logbus.log(run_id, "warn", "Verbindung zu %s fehlgeschlagen (%s) - "
                               "Versuch %d/3." % (label, exc, attempt + 1))
                    time.sleep(3)
        if client is None:
            # Postfach nicht erreichbar (z. B. transienter DNS-/Netzfehler): klar
            # markieren, aber die uebrigen Konten weiter auswerten.
            failed_accounts.append(label)
            logbus.log(run_id, "error", "Postfach %s NICHT erreichbar: %s" % (label, last_exc))
            continue
        ok_accounts += 1
        try:
            found = _scan(client, account, since_iso)
            mails.extend(found)
            logbus.log(run_id, "info", "%d Mails gelesen (%s)." % (len(found), label))
        finally:
            try:
                client.logout()
            except Exception:
                pass
    if ok_accounts == 0:
        raise RuntimeError("Keines der Postfaecher war erreichbar.")
    if failed_accounts:
        logbus.log(run_id, "warn",
                   "ACHTUNG: %d Postfach(er) nicht erreichbar (%s) - deren Mails wurden NICHT "
                   "geprueft. Bitte Status aktualisieren wiederholen."
                   % (len(failed_accounts), ", ".join(failed_accounts)))

    logbus.log(run_id, "info", "%d Mails gelesen (alle Postfaecher)." % len(mails))
    for i, m in enumerate(mails):
        m["id"] = i
    mail_rows = _store_emails(mails, jobs, run_id)

    from . import tracking_mail as tm
    logbus.log(run_id, "info", "Auswertung: mail-zentrisch.")
    items, n_batches, ok_batches = tm.classify(mails, jobs, model=model, run_id=run_id)
    if n_batches and ok_batches == 0:
        raise RuntimeError("Keine auswertbare JSON-Antwort des Modells "
                           "(alle %d Mail-Batches fehlgeschlagen)." % n_batches)
    if ok_batches < n_batches:
        logbus.log(run_id, "warn", "%d von %d Mail-Batches ohne auswertbare Antwort - "
                   "Ergebnis unvollstaendig." % (n_batches - ok_batches, n_batches))
    mail_date = {m["id"]: m.get("date", "") for m in mails}
    assoc, cand = tm.propose(items, mail_date)
    merged = {}
    for jid, c in cand.items():
        merged[jid] = {"id": jid, "phase": c["phase"], "antwort_am": c["date"],
                       "status_text": c["status_text"], "mail_ids": []}

    # Bewerbungsmails ohne bekannten Job (z. B. Absage ueber ein Portal) -> neuer Job.
    for c in tm.extract_new_jobs(items):
        jid, created = db.upsert_job({"company": c["company"], "title": c["title"],
                                      "source": "mail", "status": "gefunden"})
        assoc[c["mail_id"]] = jid
        if created:
            logbus.log(run_id, "info", "Neuer Job aus Mail: %s – %s (%s)"
                       % (c["company"], c["title"], c["phase"]))
        prev = merged.get(jid)
        if prev is None or (c["date"] or "") >= (prev.get("antwort_am") or ""):
            merged[jid] = {"id": jid, "phase": c["phase"], "antwort_am": c["date"],
                           "status_text": c["status_text"], "mail_ids": []}

    job_mails = {}
    for mid, jid in assoc.items():
        job_mails.setdefault(jid, set()).add(mid)

    if merged:
        linked = 0
        for jid, mids in job_mails.items():
            for mid in mids:
                eid = mail_rows.get(mid)
                if eid:
                    db.execute("UPDATE emails SET job_id=? WHERE id=?", (jid, eid))
                    linked += 1
        logbus.log(run_id, "info", "%d Mail-Job-Zuordnungen (LLM)." % linked)
        db.execute("UPDATE jobs SET hl=''")
    else:
        logbus.log(run_id, "info", "Keine statusrelevante Mail - nichts zu aktualisieren.")

    updated = _apply_merged(merged, run_id)
    if not failed_accounts:
        db.set_setting("last_scan", datetime.now().strftime("%Y-%m-%d"))
    else:
        # Marker NICHT vorziehen, damit das nicht erreichbare Postfach beim
        # naechsten Lauf erneut gescannt wird.
        logbus.log(run_id, "warn", "Scan-Marker bleibt stehen (nicht erreichbares Postfach).")
    logbus.log(run_id, "info", "%d Bewerbungen aktualisiert." % updated)
    return {"mails": len(mails), "aktualisiert": updated,
            "konten_fehler": failed_accounts}
