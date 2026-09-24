"""Import bestehender MalochBot-Daten (jobs.json / tracking_state.json / mail_dump.json),
damit die Oberflaeche sofort gefuellt ist."""

import json
import os
import re

from . import config, db


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")


def _load(path, default):
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return default
    return default


def find_legacy_dir() -> str:
    candidates = [
        os.environ.get("MALOCHBOT_LEGACY", ""),
        os.path.join(str(config.BASE_DIR.parent), "mail"),
        os.path.join(str(config.BASE_DIR), "mail"),
    ]
    for path in candidates:
        if path and os.path.exists(os.path.join(path, "jobs.json")):
            return path
    return ""


def import_legacy(run_id: int = None) -> dict:
    src = find_legacy_dir()
    if not src:
        raise RuntimeError("Keine bestehenden Daten gefunden (mail/jobs.json).")
    jobs = _load(os.path.join(src, "jobs.json"), [])
    state = _load(os.path.join(src, "tracking_state.json"), {})
    overrides = _load(os.path.join(src, "manual_overrides.json"), {})
    created = 0
    for i, job in enumerate(jobs, start=1):
        entry = {
            "company": job.get("company", ""),
            "title": job.get("title", ""),
            "url": job.get("link", ""),
            "source": job.get("run", "import"),
            "found_at": job.get("run", "") if re.match(r"\d{4}-\d{2}-\d{2}", job.get("run", "")) else "",
        }
        jid, is_new = db.upsert_job(entry)
        if is_new:
            created += 1
        st = dict(state.get("J%02d" % i, {}))
        st.update(overrides.get(_slug(job.get("company", "")), {}))
        if st:
            phase = st.get("phase", "Ohne Rueckmeldung")
            status = config.PHASE_TO_STATUS.get(phase, "beworben")
            db.execute("UPDATE jobs SET status=? WHERE id=?", (status, jid))
            if not db.one("SELECT id FROM applications WHERE job_id=?", (jid,)):
                db.execute(
                    "INSERT INTO applications(job_id, phase, response_at, notes, channel, updated_at) "
                    "VALUES(?,?,?,?,?,?)",
                    (jid, phase, st.get("antwort_am", ""), st.get("status_text", ""),
                     "import", db.now_iso()))
    if run_id:
        from . import logbus
        logbus.log(run_id, "info", "%d Jobs importiert (%d neu)." % (len(jobs), created))
    return {"importiert": len(jobs), "neu": created, "quelle": src}
