"""Unterlagen: zentrale Ablage, LLM-Bewertung/-Verbesserung und Erzeugung von
massgeschneiderten Anschreiben.
"""

import glob
import html as html_mod
import os
import re
import shutil
import subprocess

from .. import config, db, logbus
from .. import opencode_adapter as oc

EVAL_PROMPT = """Bewerte das folgende Dokument kurz und konkret auf Deutsch.

Profil (zur Einordnung):
{profile}

Dokumentart: {kind} · Dateiname: {name}

Inhalt:
---
{content}
---

Antworte in HOECHSTENS 8 kurzen Zeilen, exakt in diesem Format, ohne Einleitung:
Note: x/10
Stärken:
- ...
- ...
- ...
Verbesserungen:
- ...
- ...
- ...
"""

IMPROVE_PROMPT = """Erstelle eine verbesserte Fassung des folgenden Dokuments auf Deutsch.

Regeln:
- Alle Fakten, Daten, Stationen und Kontaktdaten beibehalten (nichts erfinden).
- Struktur, Formulierungen und Wirkung verbessern, praegnanter und professioneller.
- Gib NUR den vollstaendigen, ueberarbeiteten Text zurueck, ohne Kommentar oder Erklaerung.

Dokumentart: {kind}
Profil (zur Einordnung):
{profile}

Original:
---
{content}
---
"""

COVER_PROMPT = """Schreibe ein sehr persoenliches, ueberzeugendes Anschreiben auf Deutsch als Markdown.

Bewerberprofil:
{profile}

Vorlieben / Praeferenzen:
{preferences}

Auszug aus dem Lebenslauf:
{cv}

Referenz-Anschreiben (dient als Stil- und Tonvorbild, NICHT wortwoertlich kopieren):
{reference}

Stelle:
- Firma: {company}
- Position: {title}
- Ort: {location}
- Beschreibung: {description}
- Link: {url}

Verbinde die Eckdaten der Firma glaubwuerdig mit dem Profil: konkrete Stationen, Erfolge und
die Passung zur Rolle. Klinge persoenlich und individuell, nicht schablonenhaft, und orientiere
dich am Ton des Referenz-Anschreibens. Maximal eine Seite. Gib ausschliesslich das Anschreiben zurueck.
"""


def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n".join((page.extract_text() or "") for page in reader.pages)[:20000]
        if ext in (".txt", ".md", ".markdown", ".csv"):
            return open(path, encoding="utf-8", errors="replace").read()[:20000]
        if ext == ".docx":
            import re
            import zipfile
            with zipfile.ZipFile(path) as z:
                xml = z.read("word/document.xml").decode("utf-8", "replace")
            text = re.sub(r"<[^>]+>", " ", xml)
            return re.sub(r"\s+", " ", text)[:20000]
    except Exception as exc:
        return "[Text konnte nicht gelesen werden: %s]" % exc
    return "[Dateityp nicht extrahierbar - bitte Inhalt manuell pruefen.]"


def resolve_path(doc) -> str:
    """Liefert einen existierenden Pfad – auch nach Migration auf einen anderen Rechner."""
    path = (doc.get("path") if isinstance(doc, dict) else doc) or ""
    if path and os.path.exists(path):
        return path
    name = os.path.basename(path) if path else ""
    return str(config.UPLOAD_DIR / name)


def evaluate_document(doc_id: int, run_id: int, model: str = "") -> str:
    doc = db.one("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not doc:
        raise RuntimeError("Dokument nicht gefunden.")
    content = extract_text(resolve_path(doc))
    prompt = EVAL_PROMPT.format(
        profile=db.get_setting("profile", ""), kind=doc["kind"],
        name=doc["name"], content=content)
    logbus.log(run_id, "info", "Bewerte '%s' ..." % doc["name"])
    rc, out = oc.run(prompt, model=model, run_id=run_id)
    result = out.strip()
    out_path = config.GENERATED_DIR / ("bewertung_%s_%d.md" % (doc_id, run_id))
    out_path.write_text(result, encoding="utf-8")
    db.execute("UPDATE documents SET notes=? WHERE id=?", (result[:4000], doc_id))
    logbus.log(run_id, "info", "Bewertung gespeichert.")
    return result


def improve_document(doc_id: int, run_id: int, model: str = "") -> dict:
    doc = db.one("SELECT * FROM documents WHERE id=?", (doc_id,))
    if not doc:
        raise RuntimeError("Dokument nicht gefunden.")
    content = extract_text(resolve_path(doc))
    if content.startswith("["):
        raise RuntimeError("Inhalt dieses Dateityps kann nicht automatisch verbessert werden.")
    prompt = IMPROVE_PROMPT.format(
        kind=doc["kind"], profile=db.get_setting("profile", ""), content=content)
    logbus.log(run_id, "info", "Erzeuge verbesserte Fassung von '%s' ..." % doc["name"])
    rc, out = oc.run(prompt, model=model, run_id=run_id)
    improved = out.strip()
    if not improved:
        raise RuntimeError("Keine verbesserte Fassung erhalten.")

    stem, ext = os.path.splitext(doc["name"])
    ext = ext.lower()
    if ext in (".pdf", ".docx"):
        html_path = config.GENERATED_DIR / ("%s_verbessert_%d.html" % (stem, run_id))
        html_path.write_text(
            "<html><body><pre style='font-family:Arial;font-size:12pt;white-space:pre-wrap'>%s</pre></body></html>"
            % html_mod.escape(improved), encoding="utf-8")
        subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir",
                        str(config.GENERATED_DIR), str(html_path)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        produced_pdf = html_path.with_suffix(".pdf")
        target = config.UPLOAD_DIR / ("%s_verbessert.pdf" % stem)
        if produced_pdf.exists():
            shutil.move(str(produced_pdf), str(target))
        else:
            target.write_text(improved, encoding="utf-8")
            target = target.with_suffix(".md")
    else:
        target = config.UPLOAD_DIR / ("%s_verbessert.md" % stem)
        target.write_text(improved, encoding="utf-8")

    new_id = db.execute(
        "INSERT INTO documents(name, kind, path, size, version, created_at, notes) "
        "VALUES(?,?,?,?,?,?,?)",
        (target.name, doc["kind"], str(target),
         target.stat().st_size if target.exists() else 0,
         (doc["version"] or 1) + 1, db.now_iso(),
         "Verbesserte Kopie von %s (aus Bewertung #%d)" % (doc["name"], doc_id)))
    logbus.log(run_id, "info", "Neue Datei angelegt: %s" % target.name)
    return {"neues_dokument": new_id, "datei": target.name}


def _context_texts() -> tuple:
    """(lebenslauf_text, referenz_anschreiben_text) aus den Unterlagen."""
    docs = db.query("SELECT id, name, kind, path FROM documents ORDER BY created_at DESC")
    selected = [int(x) for x in (db.get_setting("search_doc_ids", "") or "").split(",")
                if x.strip().isdigit()]
    cv_docs = [d for d in docs if d["id"] in selected and d["kind"] == "lebenslauf"] or \
              [d for d in docs if d["kind"] == "lebenslauf"]
    ref_docs = [d for d in docs if d["kind"] == "referenzanschreiben"]
    cv_text, ref_text = "", ""
    for doc in cv_docs[:2]:
        text = extract_text(resolve_path(doc))
        if text and not text.startswith("["):
            cv_text = (cv_text + "\n\n" + text)[:4000]
    for doc in ref_docs[:1]:
        text = extract_text(resolve_path(doc))
        if text and not text.startswith("["):
            ref_text = text[:2500]
    return cv_text.strip(), ref_text.strip()


def _find_fonts():
    """(regular, bold) TTF-Pfade mit Unicode-Unterstuetzung, falls vorhanden."""
    bundled = config.BASE_DIR / "app" / "fonts"
    candidates = [
        (str(bundled / "DejaVuSans.ttf"), str(bundled / "DejaVuSans-Bold.ttf")),
        ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf", "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/liberation-sans-fonts/LiberationSans-Regular.ttf", "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        ("/usr/share/fonts/adwaita-sans-fonts/AdwaitaSans-Regular.ttf", None),
        ("/usr/share/fonts/google-noto-vf/NotoSans[wght].ttf", None),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg):
            return reg, (bold if bold and os.path.exists(bold) else None)
    hits = glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True)
    if hits:
        bold = glob.glob("/usr/share/fonts/**/DejaVuSans-Bold.ttf", recursive=True)
        return hits[0], (bold[0] if bold else None)
    return None, None


def text_to_pdf(text: str, path) -> bool:
    """Schreibt Markdown-aehnlichen Text als sauberes PDF (fpdf2, ohne LibreOffice)."""
    try:
        from fpdf import FPDF
    except Exception:
        return False
    lines = []
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("#"):
            line = stripped.lstrip("#").strip()
        lines.append(line)
    body = "\n".join(lines).strip()
    reg, bold = _find_fonts()
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(25, 22, 25)
    pdf.add_page()
    if reg:
        pdf.add_font("body", "", reg)
        if bold:
            pdf.add_font("body", "B", bold)
            pdf.set_font("body", size=11)
            pdf.multi_cell(0, 6, body, markdown=True)
        else:
            pdf.set_font("body", size=11)
            pdf.multi_cell(0, 6, body.replace("**", ""))
    else:
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 6, body.replace("**", "").encode("latin-1", "replace").decode("latin-1"))
    pdf.output(str(path))
    return os.path.exists(path)


def generate_cover_letter(job_id: int, run_id: int, model: str = "") -> str:
    job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not job:
        raise RuntimeError("Job nicht gefunden.")
    cv_text, ref_text = _context_texts()
    prompt = COVER_PROMPT.format(
        profile=db.get_setting("profile", ""), preferences=db.get_setting("preferences", ""),
        cv=cv_text or "(kein Lebenslauf hinterlegt)",
        reference=ref_text or "(kein Referenz-Anschreiben hinterlegt)",
        company=job["company"], title=job["title"],
        location=job["location"], description=job["description"] or job["rationale"],
        url=job["url"])
    logbus.log(run_id, "info", "Erzeuge Anschreiben fuer %s ..." % job["company"])
    rc, out = oc.run(prompt, model=model, run_id=run_id)
    return _save_cover_letter(job, out.strip(), run_id)


def _cover_md_path(job) -> "object":
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in job["company"])[:40]
    return config.GENERATED_DIR / ("anschreiben_%s_%d.md" % (safe, job["id"]))


def _save_cover_letter(job, text: str, run_id: int) -> str:
    md_path = _cover_md_path(job)
    md_path.write_text(text, encoding="utf-8")
    html_path = md_path.with_suffix(".html")
    body = "<pre style='font-family:Arial;white-space:pre-wrap'>%s</pre>" % html_mod.escape(text)
    html_path.write_text("<html><body>%s</body></html>" % body, encoding="utf-8")
    pdf_path = md_path.with_suffix(".pdf")
    made_pdf = text_to_pdf(text, pdf_path)
    result = str(pdf_path if made_pdf else (html_path if html_path.exists() else md_path))
    db.execute("UPDATE jobs SET cover_letter=? WHERE id=?", (result, job["id"]))
    logbus.log(run_id, "info", "Anschreiben gespeichert: %s" % os.path.basename(result))
    return result


IMPROVE_COVER_PROMPT = """Ueberarbeite das folgende Anschreiben gemaess dem Feedback.

Feedback der Person:
{feedback}

Aktuelles Anschreiben:
---
{letter}
---

Behalte alle Fakten bei, setze das Feedback praezise um (Ton, Inhalt, Struktur) und gib
NUR das vollstaendige, ueberarbeitete Anschreiben zurueck (Deutsch, Markdown, eine Seite).
"""


def improve_cover_letter(job_id: int, feedback: str, run_id: int, model: str = "") -> str:
    job = db.one("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not job:
        raise RuntimeError("Job nicht gefunden.")
    letter = ""
    md_path = _cover_md_path(job)
    if md_path.exists():
        letter = md_path.read_text(encoding="utf-8")
    elif job["cover_letter"] and os.path.exists(job["cover_letter"]):
        letter = extract_text(job["cover_letter"])
    if not letter.strip():
        raise RuntimeError("Kein vorhandenes Anschreiben zum Verbessern gefunden.")
    prompt = IMPROVE_COVER_PROMPT.format(feedback=feedback, letter=letter[:6000])
    logbus.log(run_id, "info", "Ueberarbeite Anschreiben gemaess Feedback ...")
    rc, out = oc.run(prompt, model=model, run_id=run_id)
    text = out.strip()
    if not text:
        raise RuntimeError("Keine ueberarbeitete Fassung erhalten.")
    return _save_cover_letter(job, text, run_id)

