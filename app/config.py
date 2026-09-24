import os
from pathlib import Path

APP_NAME = "MalochBot"
VERSION = "0.1.0"
TAGLINE = "Die Maloche der Jobsuche nimmt dir MalochBot ab."
DONATE_EMAIL = "alexander.riedel@eyedea3d.com"
DONATE_PAYPAL = "https://www.paypal.com/donate?business=alexander.riedel%40eyedea3d.com&item_name=MalochBot"

DEFAULT_MODEL = os.environ.get("TRACKER_MODEL", "deepseek/deepseek-flash")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("MALOCHBOT_DATA", str(BASE_DIR / "data")))
DB_PATH = DATA_DIR / "malochbot.sqlite3"
LOG_DIR = DATA_DIR / "logs"
UPLOAD_DIR = DATA_DIR / "documents"
GENERATED_DIR = DATA_DIR / "generated"
SECRET_FILE = DATA_DIR / "secrets.enc"
KEY_FILE = DATA_DIR / "key.bin"

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
    "Eingangsbestaetigung": "beworben",
    "Warte auf Rueckmeldung": "beworben",
    "Ohne Rueckmeldung": "gefunden",
}

# Rang fuer "nicht herabstufen": hoeher = weiter im Prozess.
STATUS_RANK = {"gefunden": 0, "vorgemerkt": 1, "beworben": 2, "interview": 3, "angebot": 4}

DOC_KINDS = ["lebenslauf", "zeugnis", "arbeitsprobe", "referenzanschreiben", "zertifikat", "sonstiges"]

DOC_LABELS = {
    "lebenslauf": "Lebenslauf",
    "zeugnis": "Zeugnis",
    "arbeitsprobe": "Arbeitsprobe",
    "referenzanschreiben": "Referenzanschreiben",
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
    "zertifikat": "Certificate",
    "sonstiges": "Other",
}


def status_labels(lang: str) -> dict:
    return STATUS_LABELS_EN if lang == "en" else STATUS_LABELS


def doc_labels(lang: str) -> dict:
    return DOC_LABELS_EN if lang == "en" else DOC_LABELS


def ensure_dirs() -> None:
    for directory in (DATA_DIR, LOG_DIR, UPLOAD_DIR, GENERATED_DIR):
        directory.mkdir(parents=True, exist_ok=True)
