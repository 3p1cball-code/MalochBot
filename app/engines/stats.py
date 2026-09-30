"""Auswertung: Kennzahlen fuer die Statistikseite UND die Bewerbungsliste fuer
den Agentur-fuer-Arbeit-Nachweis (PDF-Export).

Die Datenaufbereitung liegt bewusst hier (nicht in main.py), damit Webseite und
PDF-Export exakt dieselben Zahlen verwenden.
"""

import os
import re

from .. import config, db

# Status, die als "beworben" gelten (auch wenn danach eine Absage kam).
APPLIED_STATUSES = ("beworben", "interview", "angebot", "abgelehnt")

_BEWORBEN_RE = re.compile(r"^Status(?: \(Mail\))?:\s*.*Beworben", re.IGNORECASE)


def collect(lang: str) -> dict:
    """Kennzahlen wie auf der Statistikseite (identisch zur Web-Ansicht)."""
    status_counts = {s: 0 for s in config.JOB_STATUSES}
    for row in db.query("SELECT status, COUNT(*) n FROM jobs GROUP BY status"):
        status_counts[row["status"]] = row["n"]
    phase_rows = db.query("SELECT phase, COUNT(*) n FROM applications GROUP BY phase ORDER BY n DESC")

    found_rows = db.query("SELECT substr(found_at,1,10) d, COUNT(*) n FROM jobs "
                          "WHERE found_at<>'' GROUP BY d ORDER BY d")
    daily = [{"d": r["d"], "found": r["n"]} for r in found_rows]

    fits = [(r["score"] or 0) for r in db.query("SELECT score FROM jobs") if (r["score"] or 0) > 0]
    fit = {("%d-%d" % (i, i + 9)): 0 for i in range(0, 90, 10)}
    fit["90-100"] = 0
    for s in fits:
        key = "90-100" if s >= 90 else "%d-%d" % (s // 10 * 10, s // 10 * 10 + 9)
        fit[key] = fit.get(key, 0) + 1
    fit_sorted = sorted(fits)
    fit_median = fit_sorted[len(fit_sorted) // 2] if fit_sorted else 0
    fit_avg = round(sum(fits) / len(fits)) if fits else 0

    total = sum(status_counts.values())
    applied = sum(v for k, v in status_counts.items() if k in APPLIED_STATUSES)
    # Antworten = Bewerbungen mit echter Reaktion (nicht bloss "beworben" ohne
    # Rueckmeldung). Verhindert Antwortquoten > 100 %.
    responses = db.one(
        "SELECT COUNT(*) n FROM applications "
        "WHERE phase NOT IN ('Ohne Rueckmeldung', 'Beworben')")["n"]
    interviews = status_counts.get("interview", 0)
    offers = status_counts.get("angebot", 0)
    rejections = status_counts.get("abgelehnt", 0)
    return {
        "total": total, "applied": applied, "with_response": responses,
        "interviews": interviews, "rejections": rejections, "offers": offers,
        "found": status_counts.get("gefunden", 0),
        "response_rate": round(responses / applied * 100) if applied else 0,
        "interview_rate": round(interviews / applied * 100) if applied else 0,
        "status_counts": status_counts,
        "status_labels": config.status_labels(lang),
        "status_colors": config.STATUS_COLORS,
        "phases": [{"label": r["phase"], "n": r["n"]} for r in phase_rows],
        "daily": daily,
        "fit": [{"label": k, "n": v} for k, v in fit.items()],
        "fit_avg": fit_avg, "fit_median": fit_median, "fit_n": len(fits),
        "funnel": [
            {"key": "found", "n": total},
            {"key": "applied", "n": applied},
            {"key": "response", "n": responses},
            {"key": "interview", "n": interviews},
            {"key": "offer", "n": offers},
        ],
    }


def _events_by_job() -> dict:
    out = {}
    for ev in db.query("SELECT job_id, ts, text FROM events ORDER BY ts, id"):
        out.setdefault(ev["job_id"], []).append(ev)
    return out


def _file_mtime_date(path: str) -> str:
    try:
        if path and os.path.exists(path):
            import datetime
            return datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
    except Exception:
        pass
    return ""


_SOURCE_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def applied_date(job, events) -> str:
    """Bestes aus vorhandenen Daten ableitbares Datum der Bewerbung.

    Importierte Altbestaende tragen als `source` ihr altes Lauf-/Bewerbungsdatum
    (z. B. "2026-08-04") und dazu dasselbe in `found_at`. Dieses echte Datum wird
    bevorzugt – sonst wuerden alle Alt-Jobs auf ihr spaeteres Import-/Anschreiben-
    datum zusammenfallen. Fuer in der App erfasste Jobs gilt die Kette:
      1. fruehestes Event "Status: Beworben"
      2. Dateidatum des erzeugten Anschreiben-PDFs
      3. applications.updated_at
      4. jobs.found_at
    """
    src = (job.get("source") or "").strip()
    found = (job.get("found_at") or "")[:10]
    if _SOURCE_DATE_RE.match(src):
        return found or src[:10]
    for ev in events or []:
        if _BEWORBEN_RE.match((ev.get("text") or "").strip()):
            return (ev.get("ts") or "")[:10]
    stamp = _file_mtime_date(job.get("cover_letter") or "")
    if stamp:
        return stamp
    if job.get("app_updated"):
        return (job["app_updated"] or "")[:10]
    return found


def application_months(lang: str = "de") -> list:
    """Verfuegbare Monate (YYYY-MM, aufsteigend) mit mindestens einer Bewerbung."""
    months = {(a["date"] or "")[:7] for a in applications_list(lang)}
    return sorted(m for m in months if re.match(r"^\d{4}-\d{2}$", m))


def _in_month_range(date: str, from_month: str, to_month: str) -> bool:
    """date ist YYYY-MM-DD, Monatsgrenzen YYYY-MM (jeweils inklusive)."""
    ym = (date or "")[:7]
    if from_month and (not ym or ym < from_month):
        return False
    if to_month and (not ym or ym > to_month):
        return False
    return True


def applications_list(lang: str, from_month: str = "", to_month: str = "") -> list:
    """Alle beworbenen Stellen als Liste fuer den Nachweis (aufsteigend nach Datum).

    Optional auf einen Monatsbereich (YYYY-MM, inklusive) eingeschraenkt.
    """
    marks = ",".join("?" for _ in APPLIED_STATUSES)
    rows = db.query(
        "SELECT j.id, j.company, j.title, j.location, j.source, j.url, j.company_url, "
        "j.found_at, j.status, j.cover_letter, j.remote, "
        "a.phase AS phase, a.response_at AS response_at, a.channel AS channel, "
        "a.updated_at AS app_updated "
        "FROM jobs j LEFT JOIN applications a ON a.job_id = j.id "
        "WHERE j.status IN (%s)" % marks, APPLIED_STATUSES)
    events = _events_by_job()
    labels = config.status_labels(lang)
    out = []
    for row in rows:
        row["date"] = applied_date(row, events.get(row["id"], []))
        row["status_label"] = labels.get(row["status"], row["status"])
        row["link"] = (row.get("url") or row.get("company_url") or "").strip()
        row["response_date"] = (row.get("response_at") or "")[:10]
        if not _in_month_range(row["date"], from_month, to_month):
            continue
        out.append(row)
    out.sort(key=lambda r: (r["date"] or "9999", r["company"].lower()))
    return out
