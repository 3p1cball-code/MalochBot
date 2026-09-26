"""Zusaetzliche Boersen ueber JobSpy (LinkedIn, Indeed, Glassdoor, Google).

JobSpy ist ein optionales Paket (siehe requirements-sources.txt). Ist es nicht
installiert, meldet die Quelle das freundlich und liefert eine leere Liste -
der restliche Suchlauf laeuft normal weiter.
"""

import math

from ... import db, logbus


def available() -> bool:
    try:
        import jobspy  # noqa: F401
        return True
    except Exception:
        return False


def _s(value) -> str:
    """Robuste String-Konvertierung (None/NaN -> leer)."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in ("nan", "none", "nat") else text


def _is_true(value) -> bool:
    if isinstance(value, bool):
        return value
    return _s(value).lower() in ("true", "1", "yes")


def _search_location(location: str, country: str) -> str:
    override = (db.get_setting("jobspy_location", "") or "").strip()
    if override:
        return override
    location = (location or "").strip()
    if not location:
        return country
    if "," in location or not country:
        return location
    return "%s, %s" % (location, country)


def search(run_id, terms, location, limit) -> list:
    try:
        from jobspy import scrape_jobs
    except Exception:
        logbus.log(run_id, "info",
                   "JobSpy nicht installiert - LinkedIn/Indeed/Google uebersprungen "
                   "(Installation siehe requirements-sources.txt).")
        return []

    sites = [s.strip() for s in (db.get_setting("jobspy_sites", "indeed,linkedin") or "").split(",")
             if s.strip()]
    if not sites:
        return []
    country = db.get_setting("jobspy_country", "Germany") or "Germany"
    try:
        hours = int(db.get_setting("jobspy_hours_old", "168") or 168)
    except ValueError:
        hours = 168
    loc = _search_location(location, country)
    jobs, seen = [], set()
    for term in terms:
        try:
            frame = scrape_jobs(
                site_name=sites,
                search_term=term or "",
                location=loc,
                results_wanted=max(1, limit),
                hours_old=hours,
                country_indeed=country,
                linkedin_fetch_description=True,
                verbose=0,
            )
        except Exception as exc:
            logbus.log(run_id, "debug", "JobSpy '%s': %s" % (term, exc))
            continue
        if frame is None or len(frame) == 0:
            continue
        for _, row in frame.iterrows():
            job = _map(row)
            if not job or job["url"] in seen:
                continue
            seen.add(job["url"])
            jobs.append(job)
    return jobs


def _map(row) -> dict:
    title = _s(row.get("title"))
    company = _s(row.get("company"))
    if not (title and company):
        return {}
    url = _s(row.get("job_url_direct")) or _s(row.get("job_url"))
    site = _s(row.get("site")) or "board"
    return {
        "company": company,
        "title": title,
        "location": _s(row.get("location")),
        "remote": _is_true(row.get("is_remote")),
        "url": url,
        "company_url": _s(row.get("company_url")),
        "published_at": _s(row.get("date_posted"))[:10],
        "description": _s(row.get("description"))[:2000],
        "language": "",
        "source": "jobspy:" + site,
    }
