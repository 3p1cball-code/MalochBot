"""Bereinigt Stellen-URLs.

Hintergrund: Die LLM-Websuche liefert hin und wieder keine Direktadresse einer
Stellenanzeige, sondern die URL einer Boersen-Such- oder Uebersichtsseite
(z. B. Glassdoor ".../Job/berlin-technical-artist-jobs-SRCH_..." oder Indeed
".../q-comfyui-jobs.html"). Solche Links fuehren nicht zur Stelle.

Diese Funktionen erkennen solche Seiten und ersetzen sie durch eine gezielte
Suche exakt nach Firma und Rolle auf derselben Boerse (bzw. als Rueckfall eine
Websuche) - damit landet man bei der Stelle statt auf einer leeren Liste.
Direkte Stellenanzeigen-URLs bleiben unveraendert.

Die Bewertung ist absichtlich konservativ: nur bekannte Boersen-Suchmuster
werden angefasst; unbekannte URLs bleiben, wie sie sind.
"""

from urllib.parse import quote_plus, urlsplit

__all__ = ["is_direct_job_url", "is_search_url", "fix_job_url", "apply"]


def _url(value) -> str:
    return (value or "").strip()


def _host(url: str) -> str:
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def is_search_url(url: str) -> bool:
    """True, wenn die URL eine Boersen-Such-/Uebersichtsseite statt einer
    konkreten Stellenanzeige ist."""
    u = _url(url).lower()
    if not u:
        return False
    if "glassdoor." in u:
        # Direktlink enthaelt "/job-listing/". Alles andere (Suche, Firma,
        # Overview) ist keine Stellenanzeige.
        return "/job-listing/" not in u and "/joblisting" not in u
    if "linkedin." in u:
        # Direktlink: "/jobs/view/<id>". Suche/Sammlungen: alles andere unter /jobs/.
        return "/jobs/" in u and "/jobs/view/" not in u
    if "indeed." in u:
        if any(k in u for k in ("jk=", "/viewjob", "/rc/clk", "/pagead/clk", "/m/base/job")):
            return False
        return "/jobs" in u or "/q-" in u
    if "jooble." in u:
        return "/stellenangebote" in u or "/searchresult" in u
    if "dasauge.de" in u:
        return "/jobs/stellenangebote" in u
    if "xing." in u:
        return "/jobs/suche" in u or u.rstrip("/").endswith("/jobs")
    if "stepstone." in u:
        return "/jobs/suche" in u or "/jobs?" in u or u.rstrip("/").endswith("/jobs")
    if "arbeitsagentur.de" in u:
        return "/jobsuche/jobdetail/" not in u
    return False


def is_direct_job_url(url: str) -> bool:
    """True, wenn die URL keine bekannte Such-/Uebersichtsseite ist."""
    u = _url(url)
    return bool(u) and not is_search_url(u)


def _fallback(url: str, company: str, title: str) -> str:
    """Gezielte Suche nach Firma + Rolle auf derselben Boerse (sonst Websuche)."""
    u = _url(url).lower()
    host = _host(url).lower()
    german = host.endswith(".de") or host.startswith("de.")
    company = (company or "").strip()
    title = (title or "").strip()
    text = " ".join(x for x in (company, title) if x)
    if not text:
        return ""
    q = quote_plus(text)
    if "glassdoor." in u:
        host = "glassdoor.de" if german else "glassdoor.com"
        return "https://www.%s/Job/jobs.htm?sc.keyword=%s" % (host, q)
    if "linkedin." in u:
        return "https://www.linkedin.com/jobs/search/?keywords=%s" % q
    if "indeed." in u:
        host = "de.indeed.com" if german else "www.indeed.com"
        return "https://%s/jobs?q=%s" % (host, q)
    if "jooble." in u:
        host = "de.jooble.org" if german else "jooble.org"
        return "https://%s/SearchResult?ukw=%s" % (host, q)
    if "xing." in u:
        return "https://www.xing.com/jobs/search?keywords=%s" % q
    if "stepstone." in u:
        return "https://www.stepstone.de/jobs?what=%s" % q
    # Unbekannte Boerse: exakte Websuche nach Firma und Rolle.
    return "https://www.google.com/search?q=%s" % quote_plus('"%s" "%s"' % (company, title))


def fix_job_url(url: str, company: str = "", title: str = "") -> str:
    """Ersetzt eine Boersen-Such-URL durch eine gezielte Suche; laesst direkte
    Stellenanzeigen unveraendert."""
    url = _url(url)
    if not url or not is_search_url(url):
        return url
    return _fallback(url, company, title)


def apply(job: dict) -> dict:
    """Ersetzt job["url"] in-place, falls es keine direkte Stellenanzeige ist."""
    if not isinstance(job, dict):
        return job
    fixed = fix_job_url(job.get("url", ""), job.get("company", ""), job.get("title", ""))
    if fixed != _url(job.get("url")):
        job["url"] = fixed
    return job
