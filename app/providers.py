"""Vorkonfigurierte Mail-Anbieter (IMAP). Passwort/App-Passwort kommt in den SecretStore.

Hinweis: Anbieter mit OAuth2 (Google, Microsoft) erlauben IMAP nur mit einem
App-Passwort (bei aktivierter Zwei-Faktor-Authentifizierung). Der Assistent in den
Einstellungen erklaert das je Anbieter.
"""

PROVIDERS = [
    {"key": "gmail", "label": "Gmail / Google Workspace", "imap": "imap.gmail.com", "port": 993,
     "note": "2FA aktivieren, dann unter Google-Konto > Sicherheit > App-Passwörter eines erzeugen. "
             "Das normale Passwort funktioniert per IMAP nicht."},
    {"key": "outlook", "label": "Outlook / Microsoft 365", "imap": "outlook.office365.com", "port": 993,
     "note": "App-Passwort oder OAuth erforderlich; IMAP muss ggf. in den Postfach-Einstellungen aktiviert werden."},
    {"key": "gmx", "label": "GMX", "imap": "imap.gmx.net", "port": 993,
     "note": "Im GMX-Webmail IMAP aktivieren; ggf. ein App-Passwort erzeugen."},
    {"key": "web.de", "label": "WEB.DE", "imap": "imap.web.de", "port": 993,
     "note": "Wie GMX: IMAP aktivieren, ggf. App-Passwort."},
    {"key": "t-online", "label": "T-Online", "imap": "secureimap.t-online.de", "port": 993,
     "note": "E-Mail-Passwort aus dem Telekom-Konto verwenden."},
    {"key": "ionos", "label": "IONOS / 1&1", "imap": "imap.ionos.de", "port": 993, "note": ""},
    {"key": "strato", "label": "STRATO", "imap": "imap.strato.de", "port": 993,
     "note": "Postfach-Passwort aus der STRATO E-Mail-Verwaltung."},
    {"key": "mailbox", "label": "mailbox.org", "imap": "imap.mailbox.org", "port": 993, "note": ""},
    {"key": "posteo", "label": "Posteo", "imap": "posteo.de", "port": 993, "note": ""},
    {"key": "yahoo", "label": "Yahoo Mail", "imap": "imap.mail.yahoo.com", "port": 993,
     "note": "App-Passwort in den Yahoo-Sicherheitseinstellungen erzeugen."},
    {"key": "icloud", "label": "iCloud Mail", "imap": "imap.mail.me.com", "port": 993,
     "note": "App-spezifisches Passwort in der Apple-ID erzeugen."},
    {"key": "zoho", "label": "Zoho Mail", "imap": "imap.zoho.com", "port": 993, "note": ""},
    {"key": "fastmail", "label": "Fastmail", "imap": "imap.fastmail.com", "port": 993,
     "note": "App-Passwort empfohlen."},
    {"key": "custom", "label": "Anderer Anbieter (eigene Serverdaten)", "imap": "", "port": 993,
     "note": "IMAP-Host und Port selbst eintragen."},
]

BY_KEY = {p["key"]: p for p in PROVIDERS}


def resolve(provider_key: str, host: str = "", port: int = 993):
    preset = BY_KEY.get(provider_key)
    if preset and preset["imap"]:
        return preset["imap"], preset["port"]
    return host, port
