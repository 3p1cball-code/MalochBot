"""Zusaetzliche Jobboersen-Quellen (APIs/Scraping) neben der LLM-Websuche.

Jede Quelle liefert normalisierte Job-Dicts in genau der Form, die auch die
LLM-Suche erzeugt (company, title, location, remote, url, company_url,
published_at, description, language, source). Der Suchlauf gibt diese
Kandidaten an das Modell zur Fit-Bewertung und sichert sie - falls das Modell
sie auslaesst - unbewertet, damit nichts verloren geht.

Der wichtigste Quellvorrat fuer Deutschland ist die Jobboerse der
Bundesagentur fuer Arbeit (offizielle, oeffentliche JSON-API, kein Scraping).
Zusaetzlich kann JobSpy LinkedIn/Indeed/Glassdoor/Google abfragen (optionales
Paket, siehe requirements-sources.txt).
"""

from ... import db, logbus

# Reihenfolge = Prioritaet. Quellen ohne verfuegbares Paket melden sich selbst
# und liefern eine leere Liste.
HANDLERS = {
    "arbeitsagentur": ("arbeitsagentur", "search"),
    "jobspy": ("jobspy_source", "search"),
}


def _enabled() -> list:
    raw = db.get_setting("search_sources", "") or ""
    names = [s.strip() for s in raw.split(",") if s.strip()]
    return [n for n in names if n in HANDLERS]


def _terms() -> list:
    raw = db.get_setting("search_terms", "") or ""
    terms = [t.strip() for t in raw.split(",") if t.strip()]
    return terms or [""]


def _key(job: dict) -> tuple:
    company = db.norm_company(job.get("company") or "")
    title = db.norm_title(job.get("title") or "")
    if company and title:
        return ("ct", company, title)
    return ("url", (job.get("url") or "").strip())


def collect(run_id) -> list:
    """Fragt alle aktivierten Quellen ab und liefert neue, deduplizierte Kandidaten."""
    enabled = _enabled()
    if not enabled:
        return []
    terms = _terms()
    location = db.get_setting("home_city", "Berlin") or "Berlin"
    per_term = int(db.get_setting("source_results", "10") or 10)
    max_total = int(db.get_setting("source_max_candidates", "30") or 30)
    per_source = max(1, max_total // len(enabled))
    out, seen = [], set()
    for name in enabled:
        module_name, func_name = HANDLERS[name]
        try:
            module = __import__(module_name, globals(), locals(), [func_name], level=1)
            found = getattr(module, func_name)(run_id, terms, location, per_term)
        except Exception as exc:  # nie den ganzen Lauf wegen einer Quelle abbrechen
            logbus.log(run_id, "error", "Jobboerse %s fehlgeschlagen: %s" % (name, exc))
            continue
        added = 0
        for job in found:
            if not job.get("company") or not job.get("title"):
                continue
            key = _key(job)
            if key in seen:
                continue
            seen.add(key)
            out.append(job)
            added += 1
            if added >= per_source:
                break
        logbus.log(run_id, "info", "Jobboerse %s: %d neue Kandidaten." % (name, added))
    if len(out) >= max_total:
        logbus.log(run_id, "info", "Kandidaten-Obergrenze (%d) erreicht." % max_total)
    return out
