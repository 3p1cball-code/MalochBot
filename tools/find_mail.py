#!/usr/bin/env python3
"""Sucht im Postfach nach Mails zu einem Begriff (Kopfzeilen + Body).
Aufruf: python3 tools/find_mail.py "universal" [--since 01-Sep-2026] [--body]
"""
import email
import sys
from email.header import decode_header, make_header

from app.engines import tracking


def dec(value):
    try:
        return str(make_header(decode_header(value or "")))
    except Exception:
        return value or ""


def body_of(msg):
    parts = msg.walk() if msg.is_multipart() else [msg]
    out = []
    for p in parts:
        if p.get_content_type() in ("text/plain", "text/html"):
            try:
                out.append(p.get_payload(decode=True).decode("utf-8", "replace"))
            except Exception:
                pass
    return " ".join(out)


def main():
    term = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    since = "01-Sep-2026"
    check_body = "--body" in sys.argv
    if "--since" in sys.argv:
        since = sys.argv[sys.argv.index("--since") + 1]
    client = tracking._connect()
    hits = 0
    for folder in tracking._list_folders(client):
        try:
            client.select(folder, readonly=True)
            ok, data = client.search(None, "(SINCE %s)" % since)
        except Exception:
            continue
        if ok != "OK" or not data or not data[0]:
            continue
        for uid in data[0].split():
            ok, raw = client.fetch(uid, "(BODY.PEEK[])")
            if ok != "OK" or not raw or not isinstance(raw[0], tuple):
                continue
            msg = email.message_from_bytes(raw[0][1])
            frm = dec(msg.get("From"))
            to = dec(msg.get("To"))
            subj = dec(msg.get("Subject"))
            blob = (frm + " " + to + " " + subj).lower()
            body = body_of(msg).lower() if check_body else ""
            if term in blob or (term and term in body):
                hits += 1
                print("%s | %s | %s | %s" % (folder, dec(msg.get("Date"))[:31], frm[:34], subj[:60]))
    print("Treffer:", hits)
    client.logout()


if __name__ == "__main__":
    main()
