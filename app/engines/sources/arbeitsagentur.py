"""Jobboerse der Bundesagentur fuer Arbeit (groesste Stellendatenbank DE).

Nutzt die oeffentliche JSON-API, die auch das offizielle BA-Frontend verwendet
(kein Scraping, kein API-Schluessel noetig ausser dem oeffentlichen clientId).
Ablauf: /pc/v6/jobs (Suche) -> refnr -> /pc/v4/jobdetails/{base64(refnr)}
(Beschreibung). Detailseite im Browser: /jobsuche/jobdetail/{refnr}.
"""

import base64
import json
import urllib.parse
import urllib.request

from ... import db, logbus

API = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
DETAIL_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/%s"
HEADERS = {
    "X-API-Key": "jobboerse-jobsuche",
    "Accept": "application/json",
    "User-Agent": "MalochBot/0.1 (+https://github.com/3p1cball-code/MalochBot)",
}
# Die BA liefert nur selten eine Arbeitgeber-Homepage (arbeitgeberdarstellungUrl).
# Als Ersatz verlinken wir die Firma mit einer Websuche, damit der Firmen-Button
# nicht fehlt.
DESC_CAP = 2000


def _company_search(name: str) -> str:
    return "https://duckduckgo.com/?q=" + urllib.parse.quote(name or "")


def _get(path: str, params: dict = None, timeout: int = 25) -> dict:
    url = API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def _clean(text: str) -> str:
    return (text or "").replace("**", "").replace("\\n", "\n").replace("\r", "").strip()


def _location(raw: dict) -> str:
    for loc in (raw.get("stellenlokationen") or []):
        addr = loc.get("adresse") or {}
        parts = [addr.get("plz"), addr.get("ort")]
        label = " ".join(p for p in parts if p).strip()
        if label:
            return label
    return ""


def _remote(raw: dict, title: str) -> bool:
    for key, value in raw.items():
        low = key.lower()
        if ("homeoffice" in low or "telearbeit" in low or "mobil" in low) and value:
            return True
    blob = (title or "").lower()
    return any(w in blob for w in ("homeoffice", "remote", "telearbeit", "mobiles arbeiten"))


def _published(raw: dict) -> str:
    return (raw.get("datumErsteVeroeffentlichung")
            or (raw.get("veroeffentlichungszeitraum") or {}).get("von")
            or "")


def _map(raw: dict) -> dict:
    title = _clean(raw.get("stellenangebotsTitel"))
    refnr = (raw.get("referenznummer") or "").strip()
    company = _clean(raw.get("firma"))
    if not (title and company and refnr):
        return {}
    return {
        "company": company,
        "title": title,
        "location": _location(raw),
        "remote": _remote(raw, title),
        "url": DETAIL_URL % urllib.parse.quote(refnr, safe=""),
        "company_url": _company_search(company),
        "published_at": _published(raw),
        "description": "",
        "language": "de",
        "source": "arbeitsagentur",
    }


def _enrich(job: dict, refnr: str) -> None:
    """Holt die Stellenbeschreibung ueber den Detail-Endpunkt nach."""
    encoded = base64.b64encode(refnr.encode()).decode()
    try:
        detail = _get("/pc/v4/jobdetails/" + encoded)
    except Exception:
        return
    desc = _clean(detail.get("stellenangebotsBeschreibung"))
    if desc:
        job["description"] = desc[:DESC_CAP]
    website = (detail.get("arbeitgeberdarstellungUrl") or "").strip()
    if website:
        job["company_url"] = website
    if not job.get("location"):
        job["location"] = _location(detail)
    if _remote(detail, job.get("title", "")):
        job["remote"] = True


def search(run_id, terms, location, limit) -> list:
    radius = db.get_setting("source_radius_km", "50") or "50"
    days = db.get_setting("source_max_age_days", "30") or "30"
    detail_max = int(db.get_setting("source_detail_max", "20") or 20)
    jobs, seen = [], set()
    for term in terms:
        params = {"angebotsart": "1", "page": 1, "size": max(1, min(limit, 50))}
        if term:
            params["was"] = term
        if location:
            params["wo"] = location
            params["umkreis"] = radius
        if days and days.isdigit():
            params["veroeffentlichtseit"] = min(int(days), 100)
        try:
            data = _get("/pc/v6/jobs", params)
        except Exception as exc:
            logbus.log(run_id, "debug", "Arbeitsagentur '%s': %s" % (term, exc))
            continue
        for raw in (data.get("ergebnisliste") or []):
            job = _map(raw)
            if not job:
                continue
            refnr = (raw.get("referenznummer") or "").strip()
            if job["url"] in seen:
                continue
            seen.add(job["url"])
            job["_refnr"] = refnr
            jobs.append(job)
    # Beschreibungen fuer die ersten Kandidaten nachholen (hilft der Fit-Bewertung).
    for job in jobs[:max(0, detail_max)]:
        if job.get("_refnr"):
            _enrich(job, job["_refnr"])
    for job in jobs:
        job.pop("_refnr", None)
    return jobs
