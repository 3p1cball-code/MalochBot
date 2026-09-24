import json
import os
import sqlite3
import time
from datetime import datetime, timezone

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT DEFAULT '',
    remote INTEGER DEFAULT 0,
    source TEXT DEFAULT '',
    url TEXT DEFAULT '',
    company_url TEXT DEFAULT '',
    published_at TEXT DEFAULT '',
    found_at TEXT DEFAULT '',
    run_id INTEGER,
    score INTEGER DEFAULT 0,
    fit TEXT DEFAULT '',
    rationale TEXT DEFAULT '',
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'gefunden',
    cover_letter TEXT DEFAULT '',
    raw TEXT DEFAULT '{}',
    UNIQUE(company, title, url)
);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    applied_at TEXT DEFAULT '',
    phase TEXT DEFAULT 'Ohne Rueckmeldung',
    response_at TEXT DEFAULT '',
    channel TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    updated_at TEXT DEFAULT '',
    UNIQUE(job_id),
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT DEFAULT '',
    folder TEXT DEFAULT '',
    from_addr TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    job_id INTEGER,
    classification TEXT DEFAULT '',
    confidence TEXT DEFAULT '',
    run_id INTEGER,
    created_at TEXT DEFAULT '',
    UNIQUE(date, folder, from_addr, subject)
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    model TEXT DEFAULT '',
    started_at TEXT DEFAULT '',
    finished_at TEXT DEFAULT '',
    status TEXT DEFAULT 'laeuft',
    summary TEXT DEFAULT '',
    log_path TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    kind TEXT DEFAULT 'sonstiges',
    path TEXT DEFAULT '',
    size INTEGER DEFAULT 0,
    version INTEGER DEFAULT 1,
    created_at TEXT DEFAULT '',
    notes TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
    ts TEXT DEFAULT '',
    level TEXT DEFAULT 'info',
    message TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    ts TEXT DEFAULT '',
    kind TEXT DEFAULT '',
    text TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
"""

DEFAULT_SETTINGS = {
    "model": config.DEFAULT_MODEL,
    "profile": (
        "Alexander Riedel, Berlin. 3D-/CGI- und Generative-KI-Pipeline-Spezialist mit fast "
        "20 Jahren Erfahrung. Zuletzt Lead Technical R&D (Generative KI) bei sooii: Aufbau "
        "produktiver ComfyUI-Pipelines, eigene Custom Nodes in Python/JavaScript, LoRA-Training, "
        "automatisierte Upscaling- und Refiner-Systeme, Verknuepfung von 3D-Strukturdaten mit "
        "generativen Workflows. Davor 9 Jahre CIO/Technical Director und Senior 3D Artist bei "
        "EVE Images (3ds Max, V-Ray, Corona). Sucht Lead-/Head-of-Positionen, Berlin oder remote."
    ),
    "search_extra": "Fokus auf Lead-/Head-of-Rollen im Bereich Generative AI / 3D-Pipeline, "
                    "Berlin oder remote, veroeffentlicht in den letzten 30 Tagen.",
    "preferences": (
        "Berlin oder remote. Kein Umzug. Fuehrungs-/Lead-Verantwortung gewuenscht. "
        "Fokus auf generativer KI, ComfyUI, 3D-/CGI-Pipelines und Produktvisualisierung. "
        "Kultur: kleine, schnelle Teams, Hands-on, wenig Hierarchie."
    ),
    "mail_provider": "",
    "mail_email": "",
    "mail_host": "",
    "mail_port": "993",
    "mail_folders": "INBOX",
    "mail_since": "2026-07-01",
    "last_scan": "",
    "setup_done": "0",
    "language": "de",
    "fit_threshold": "0",
    "search_doc_ids": "",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S")


def get_conn() -> sqlite3.Connection:
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    config.ensure_dirs()
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        columns = {row["name"] for row in
                   [dict(r) for r in conn.execute("PRAGMA table_info(jobs)").fetchall()]}
        if "company_url" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN company_url TEXT DEFAULT ''")
        conn.execute("UPDATE jobs SET status='gefunden' WHERE status='neu'")
        conn.execute("UPDATE jobs SET status='beworben' WHERE status='bestaetigt'")
        # Dokumentpfade portabel machen (nach Migration auf anderen Rechner/Ordner)
        for row in conn.execute("SELECT id, name, path FROM documents").fetchall():
            current = row["path"] or ""
            target = config.UPLOAD_DIR / os.path.basename(current or row["name"])
            if target.exists() and current != str(target):
                conn.execute("UPDATE documents SET path=? WHERE id=?", (str(target), row["id"]))
        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?,?)", (key, value))
        conn.commit()


def query(sql: str, params=()) -> list:
    with get_conn() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]


def one(sql: str, params=()):
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def execute(sql: str, params=()):
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid


def get_setting(key: str, default: str = "") -> str:
    row = one("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    execute("INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def all_settings() -> dict:
    return {row["key"]: row["value"] for row in query("SELECT key, value FROM settings")}


def upsert_job(job: dict):
    """Fuegt einen Job hinzu, falls neu. Gibt (id, neu_angelegt) zurueck."""
    existing = one("SELECT id FROM jobs WHERE company=? AND title=? AND url=?",
                   (job.get("company", ""), job.get("title", ""), job.get("url", "")))
    if existing:
        return existing["id"], False
    new_id = execute(
        "INSERT INTO jobs(company,title,location,remote,source,url,company_url,published_at,found_at,"
        "run_id,score,fit,rationale,description,status,raw) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            job.get("company", ""), job.get("title", ""), job.get("location", ""),
            int(bool(job.get("remote"))), job.get("source", ""), job.get("url", ""),
            job.get("company_url", ""),
            job.get("published_at", ""), job.get("found_at", now_iso()),
            job.get("run_id"), int(job.get("score") or 0), job.get("fit", ""),
            job.get("rationale", ""), job.get("description", ""),
            job.get("status", "gefunden"), json.dumps(job.get("raw", {}), ensure_ascii=False),
        ),
    )
    return new_id, True


def add_log(run_id, level: str, message: str) -> None:
    execute("INSERT INTO logs(run_id, ts, level, message) VALUES(?,?,?,?)",
            (run_id, now_iso(), level, message))


def start_run(kind: str, model: str) -> int:
    return execute("INSERT INTO runs(kind, model, started_at, status) VALUES(?,?,?,?)",
                   (kind, model, now_iso(), "laeuft"))


def finish_run(run_id: int, status: str, summary: str = "") -> None:
    execute("UPDATE runs SET status=?, finished_at=?, summary=? WHERE id=?",
            (status, now_iso(), summary, run_id))
