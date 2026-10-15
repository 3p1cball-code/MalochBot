"""Benutzerverwaltung: Registrierung, Login, Sitzungen und Datenmigration.

Aufbau (zwei Ebenen):
  * `accounts.sqlite3` im Wurzel-Datenordner - nur Konten und Sitzungen.
  * je Benutzer ein eigener Ordner `users/<slug>/` mit der bisherigen
    `malochbot.sqlite3`, Unterlagen, generierten Dateien und Geheimnissen.

Passwoerter werden mit scrypt (stdlib) und zufaelligem Salt gehasht; niemals im
Klartext gespeichert. Sitzungen sind undurchsichtige Zufallstoken (im Cookie),
in der Account-DB liegt nur deren SHA-256-Hash.
"""

import argparse
import base64
import getpass
import hashlib
import hmac
import os
import re
import secrets as pysecrets
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timezone

from . import config

SESSION_COOKIE = "mb_session"
SESSION_DAYS = 30

# scrypt-Parameter (Speicher ~16 MB, ausreichend fuer eine lokale App).
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DKLEN = 32

USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
_ready_lock = threading.Lock()
_ready: set = set()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    data_dir TEXT NOT NULL,
    password TEXT NOT NULL,
    created_at TEXT DEFAULT '',
    lang TEXT DEFAULT 'de'
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


# ---------------------------------------------------------------- Account-DB
def get_conn() -> sqlite3.Connection:
    config.ROOT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.ACCOUNTS_DB, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_accounts_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S")


def _row(row) -> dict:
    return dict(row) if row else None


# ---------------------------------------------------------------- Passwoerter
def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt,
                            n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_DKLEN)
    return "scrypt$%d$%d$%d$%s$%s" % (
        _SCRYPT_N, _SCRYPT_R, _SCRYPT_P,
        base64.b64encode(salt).decode(), base64.b64encode(digest).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, hash_b64 = (stored or "").split("$")
        if algo != "scrypt":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        digest = hashlib.scrypt(password.encode("utf-8"), salt=salt,
                                n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


# ---------------------------------------------------------------- Benutzer
def slugify(username: str) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", (username or "").lower()).strip("-")
    return slug or "user"


def valid_username(username: str) -> bool:
    return bool(USERNAME_RE.match(username or ""))


def get_user_by_name(username: str):
    with get_conn() as conn:
        return _row(conn.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE",
                                 (username,)).fetchone())


def get_user_by_id(user_id: int):
    with get_conn() as conn:
        return _row(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())


def list_users() -> list:
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY id")]


def _context(user: dict) -> dict:
    return {"id": user["id"], "username": user["username"],
            "dir": str(config.user_home(user["data_dir"]))}


def init_user_data(user: dict) -> None:
    """Legt den Benutzerordner an und initialisiert dessen Datenbank."""
    home = config.user_home(user.get("data_dir") or slugify(user["username"]))
    home.mkdir(parents=True, exist_ok=True)
    previous = config.current_user()
    config.set_current_user(_context(user))
    try:
        from . import db
        config.ensure_dirs()
        db.init_db()
    finally:
        config.set_current_user(previous)


def create_user(username: str, password: str) -> int:
    if not valid_username(username):
        raise ValueError("Ungueltiger Benutzername (3-32 Zeichen: A-Z, a-z, 0-9, . _ -).")
    if not password or len(password) < 6:
        raise ValueError("Das Passwort muss mindestens 6 Zeichen haben.")
    if get_user_by_name(username):
        raise ValueError("Dieser Benutzername ist bereits vergeben.")
    slug = slugify(username)
    # Eindeutigen Ordner sicherstellen, falls sich Slugs gleichen.
    base_slug, counter = slug, 1
    while config.user_home(slug).exists():
        counter += 1
        slug = "%s-%d" % (base_slug, counter)
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO users(username, data_dir, password, created_at) VALUES(?,?,?,?)",
            (username, slug, hash_password(password), _now_iso()))
        uid = cur.lastrowid
        conn.commit()
    init_user_data(get_user_by_id(uid))
    return uid


def set_password(username: str, password: str) -> None:
    if not password or len(password) < 6:
        raise ValueError("Das Passwort muss mindestens 6 Zeichen haben.")
    user = get_user_by_name(username)
    if not user:
        raise ValueError("Benutzer nicht gefunden: %s" % username)
    with get_conn() as conn:
        conn.execute("UPDATE users SET password=? WHERE id=?",
                     (hash_password(password), user["id"]))
        conn.commit()


def authenticate(username: str, password: str):
    user = get_user_by_name(username)
    if user and verify_password(password or "", user["password"]):
        return user
    return None


def ensure_user_ready(user: dict) -> None:
    """Initialisiert die Benutzer-Datenbank einmal je Prozess (idempotent)."""
    with _ready_lock:
        if user["id"] in _ready:
            return
        _ready.add(user["id"])
    from . import db
    db.init_db()


def activate(username: str = None) -> dict:
    """Aktiviert einen Benutzer fuer Kommandozeilen-Werkzeuge (ohne HTTP).

    Quelle: Argument, sonst `MALOCHBOT_USER`, sonst der einzige vorhandene
    Benutzer. Gibt den Kontext zurueck und initialisiert die Datenbank.
    """
    init_accounts_db()
    name = username or os.environ.get("MALOCHBOT_USER") or ""
    if name:
        user = get_user_by_name(name)
    else:
        users = list_users()
        user = users[0] if len(users) == 1 else None
    if not user:
        raise RuntimeError("Kein Benutzer gewaehlt. MALOCHBOT_USER setzen oder "
                           "Benutzername uebergeben (python -m app.auth list-users).")
    context = _context(user)
    config.set_current_user(context)
    ensure_user_ready(user)
    return context


# ---------------------------------------------------------------- Sitzungen
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: int) -> str:
    token = pysecrets.token_urlsafe(32)
    now = int(time.time())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES(?,?,?,?)",
            (_hash_token(token), user_id, now, now + SESSION_DAYS * 86400))
        conn.commit()
    return token


def user_for_token(token: str):
    if not token:
        return None
    now = int(time.time())
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE token_hash=?",
                           (_hash_token(token),)).fetchone()
        if not row:
            return None
        if int(row["expires_at"]) < now:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (row["token_hash"],))
            conn.commit()
            return None
        user = conn.execute("SELECT * FROM users WHERE id=?", (row["user_id"],)).fetchone()
        return _row(user)


def destroy_session(token: str) -> None:
    if not token:
        return
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (_hash_token(token),))
        conn.commit()


def purge_expired() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
        conn.commit()


# ---------------------------------------------------------------- Migration
_LEGACY_GLOBS = ("context*.json", "mc_context*.json", "tracking_test_report*.json")
_LEGACY_FILES = ("malochbot.sqlite3", "malochbot.sqlite3-shm", "malochbot.sqlite3-wal",
                 "secrets.enc", "key.bin")
_LEGACY_DIRS = ("documents", "generated", "logs")


def legacy_data_present() -> bool:
    root = config.ROOT_DATA_DIR
    if (root / "malochbot.sqlite3").exists():
        return True
    return any((root / d).is_dir() for d in _LEGACY_DIRS)


def migrate_legacy(username: str) -> dict:
    """Verschiebt den bisherigen (benutzerlosen) Bestand in den Benutzerordner.

    Der Altbestand hat Vorrang: er ersetzt die beim Anlegen frisch erzeugte,
    leere Benutzer-Datenbank und ueberschreibt vorhandene Geheimnisse. Ordner
    werden zusammengefuehrt. Einmalige Aktion - nur bei gestopptem Server.
    """
    user = get_user_by_name(username)
    if not user:
        raise ValueError("Benutzer nicht gefunden: %s" % username)
    home = config.user_home(user["data_dir"])
    home.mkdir(parents=True, exist_ok=True)
    root = config.ROOT_DATA_DIR
    moved = []

    def _move_file(src, dst):
        if not src.exists():
            return
        if dst.exists():
            if dst.is_dir():
                return
            dst.unlink()
        shutil.move(str(src), str(dst))
        moved.append(src.name)

    def _merge_dir(src, dst):
        if not src.is_dir():
            return
        dst.mkdir(parents=True, exist_ok=True)
        for child in sorted(src.iterdir()):
            _move_file(child, dst / child.name)
        try:
            src.rmdir()
        except OSError:
            pass

    for name in _LEGACY_FILES:
        _move_file(root / name, home / name)
    for name in _LEGACY_DIRS:
        _merge_dir(root / name, home / name)
    for pattern in _LEGACY_GLOBS:
        for src in sorted(root.glob(pattern)):
            if src.is_file():
                _move_file(src, home / src.name)

    # Dokumentpfade in der verschobenen Datenbank an den neuen Ordner anpassen.
    previous = config.current_user()
    config.set_current_user(_context(user))
    try:
        from . import db
        config.ensure_dirs()
        db.init_db()
    finally:
        config.set_current_user(previous)
    return {"user": username, "verschoben": moved, "ziel": str(home)}


# ---------------------------------------------------------------- CLI
def _read_password(prompt: str = "Passwort: ") -> str:
    env = os.environ.get("MALOCHBOT_PW")
    if env:
        return env
    return getpass.getpass(prompt)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.auth",
                                     description="MalochBot Benutzerverwaltung")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add-user", help="Benutzer anlegen")
    p_add.add_argument("username")

    p_pw = sub.add_parser("passwd", help="Passwort setzen")
    p_pw.add_argument("username")

    sub.add_parser("list-users", help="Benutzer auflisten")

    p_mig = sub.add_parser("migrate", help="Bisherigen Bestand in einen Benutzerordner verschieben")
    p_mig.add_argument("username")

    args = parser.parse_args(argv)
    init_accounts_db()

    if args.cmd == "add-user":
        pw = _read_password("Neues Passwort fuer %s: " % args.username)
        uid = create_user(args.username, pw)
        print("Benutzer %s angelegt (id=%d)." % (args.username, uid))
    elif args.cmd == "passwd":
        pw = _read_password("Neues Passwort fuer %s: " % args.username)
        set_password(args.username, pw)
        print("Passwort aktualisiert.")
    elif args.cmd == "list-users":
        for u in list_users():
            print("%3d  %-24s  %s" % (u["id"], u["username"], u["data_dir"]))
    elif args.cmd == "migrate":
        result = migrate_legacy(args.username)
        print("Migriert nach %s:" % result["ziel"])
        for name in result["verschoben"]:
            print("  - %s" % name)
        if not result["verschoben"]:
            print("  (nichts zu verschieben)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
