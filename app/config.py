import contextvars
import os
from pathlib import Path

APP_NAME = "MalochBot"
VERSION = "0.2.0"
TAGLINE = "Die Maloche der Jobsuche nimmt dir MalochBot ab."
DONATE_EMAIL = "alexander.riedel@eyedea3d.com"
DONATE_PAYPAL = "https://www.paypal.com/donate?business=alexander.riedel%40eyedea3d.com&item_name=MalochBot"

# Fussnote auf allen exportierten PDFs (Herkunftsnachweis).
GITHUB_URL = "https://github.com/3p1cball-code/MalochBot"
AUTHOR_NAME = "Alexander Riedel"
PDF_CREDIT = "Erstellt mit MalochBot"

DEFAULT_MODEL = os.environ.get("TRACKER_MODEL", "deepseek/deepseek-flash")

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Benutzerverwaltung -----------------------------------------------------
# Die Datenbank ist in zwei Ebenen geteilt:
#   * global: Konten + Sitzungen liegen in der Account-Datenbank (accounts.sqlite3).
#   * je Benutzer: der komplette bisherige Bestand (Jobs, Einstellungen,
#     Unterlagen, Geheimnisse) liegt in einem eigenen Ordner unter users/<slug>/
#     mit eigener malochbot.sqlite3 - jeweils identische Struktur wie zuvor.
# Der aktive Benutzer kommt aus einem ContextVar; ohne Kontext zeigen die Pfade
# auf das Wurzelverzeichnis (nur fuer Aufbau/Verwaltung und die Account-DB).
ROOT_DATA_DIR = Path(os.environ.get("MALOCHBOT_DATA", str(BASE_DIR / "data")))
USERS_DIR = ROOT_DATA_DIR / "users"
ACCOUNTS_DB = ROOT_DATA_DIR / "accounts.sqlite3"

_user_var: contextvars.ContextVar = contextvars.ContextVar("malochbot_user", default=None)

# Pfade relativ zum Benutzerordner (Namen bleiben kompatibel zum bisherigen Code).
_SCOPED = {
    "DATA_DIR": "",
    "DB_PATH": "malochbot.sqlite3",
    "LOG_DIR": "logs",
    "UPLOAD_DIR": "documents",
    "GENERATED_DIR": "generated",
    "SECRET_FILE": "secrets.enc",
    "KEY_FILE": "key.bin",
}


def set_current_user(user: dict) -> None:
    """Setzt den aktiven Benutzer fuer den aktuellen Kontext (Thread/Task)."""
    _user_var.set(user or None)


def current_user():
    return _user_var.get()


def current_user_dir() -> Path:
    user = _user_var.get()
    if user and user.get("dir"):
        return Path(user["dir"])
    return ROOT_DATA_DIR


def user_home(slug: str) -> Path:
    return USERS_DIR / slug


def __getattr__(name: str):
    """Loest die benutzerbezogenen Pfade dynamisch aus dem aktuellen Kontext auf."""
    if name in _SCOPED:
        return current_user_dir() / _SCOPED[name]
    raise AttributeError("Modul %r hat kein Attribut %r" % (__name__, name))


HOST = os.environ.get("MALOCHBOT_HOST", "127.0.0.1")
PORT = int(os.environ.get("MALOCHBOT_PORT", "8765"))

JOB_STATUSES = [
    "gefunden", "vorgemerkt", "beworben", "interview", "angebot", "abgelehnt", "ignoriert",
]

STATUS_LABELS = {
    "gefunden": "Gefunden",
    "vorgemerkt": "Vorgemerkt",
    "beworben": "Beworben",
    "interview": "Interview",
    "angebot": "Angebot",
    "abgelehnt": "Abgelehnt",
    "ignoriert": "Ignoriert",
}

STATUS_COLORS = {
    "gefunden": "#94a3b8",
    "vorgemerkt": "#3b82f6",
    "beworben": "#6366f1",
    "interview": "#14b8a6",
    "angebot": "#eab308",
    "abgelehnt": "#ef4444",
    "ignoriert": "#cbd5e1",
}

# Phasen aus der Mail-Auswertung -> Job-Status.
# Wichtig: "Ohne Rueckmeldung" bedeutet NICHT beworben, sondern nur gefunden.
PHASE_TO_STATUS = {
    "Interview-Prozess": "interview",
    "Absage": "abgelehnt",
    "Beworben": "beworben",
    "Eingangsbestaetigung": "beworben",
    "Warte auf Rueckmeldung": "beworben",
    "Ohne Rueckmeldung": "gefunden",
}

# Rang fuer "nicht herabstufen": hoeher = weiter im Prozess.
STATUS_RANK = {"gefunden": 0, "vorgemerkt": 1, "beworben": 2, "interview": 3, "angebot": 4}

DOC_KINDS = ["lebenslauf", "zeugnis", "arbeitsprobe", "referenzanschreiben", "portrait", "zertifikat", "sonstiges"]

DOC_LABELS = {
    "lebenslauf": "Lebenslauf",
    "zeugnis": "Zeugnis",
    "arbeitsprobe": "Arbeitsprobe",
    "referenzanschreiben": "Referenzanschreiben",
    "portrait": "Bewerbungsfoto",
    "zertifikat": "Zertifikat",
    "sonstiges": "Sonstiges",
}

STATUS_LABELS_EN = {
    "gefunden": "Found",
    "vorgemerkt": "Shortlisted",
    "beworben": "Applied",
    "interview": "Interview",
    "angebot": "Offer",
    "abgelehnt": "Rejected",
    "ignoriert": "Ignored",
}

DOC_LABELS_EN = {
    "lebenslauf": "CV",
    "zeugnis": "Reference",
    "arbeitsprobe": "Work sample",
    "referenzanschreiben": "Reference cover letter",
    "portrait": "Photo",
    "zertifikat": "Certificate",
    "sonstiges": "Other",
}


def status_labels(lang: str) -> dict:
    return STATUS_LABELS_EN if lang == "en" else STATUS_LABELS


def doc_labels(lang: str) -> dict:
    return DOC_LABELS_EN if lang == "en" else DOC_LABELS


def ensure_dirs() -> None:
    """Legt Wurzel- und Benutzerordner an (je nach aktivem Kontext)."""
    ROOT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    user = _user_var.get()
    if user:
        base = current_user_dir()
        for directory in (base, base / "logs", base / "documents", base / "generated"):
            directory.mkdir(parents=True, exist_ok=True)
