"""Gemeinsamer PDF-Export im Web-Design.

Alle von MalochBot erzeugten PDFs (Statistik/ Nachweis, Anschreiben, verbesserte
Dokumente) werden als HTML im Stil der Webseite gebaut und anschliessend via
WeasyPrint nach PDF gerendert. Ist WeasyPrint nicht verfuegbar, faellt der Export
auf das bisherige fpdf-Layout zurueck (siehe engines/documents.text_to_pdf).
"""

import html as html_mod
import math
import os
import re
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config

_EXPORT_DIR = config.BASE_DIR / "app" / "templates" / "export"
_env = Environment(
    loader=FileSystemLoader(str(_EXPORT_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

# Design-Tokens der Webseite (app/static/app.css), reduziert auf das, was im
# PDF gebraucht wird. So bleiben Web und Export im selben Stil.
THEME = {
    "hell": {
        "bg": "#f6f6f7", "panel": "#ffffff", "panel2": "#fafafa",
        "ink": "#1b1b1f", "ink_strong": "#09090b", "muted": "#71717a", "faint": "#a1a1aa",
        "line": "#e4e4e7", "line_strong": "#d4d4d8",
        "accent": "#cf9414", "accent_soft": "#fbf1da", "accent_ink": "#1b1400",
        "ok": "#15803d", "warn": "#b45309", "err": "#dc2626", "track": "#ececee",
    },
    "dunkel": {
        "bg": "#0a0a0a", "panel": "#141414", "panel2": "#1a1a1a",
        "ink": "#e4e4e7", "ink_strong": "#fafafa", "muted": "#8b8b90", "faint": "#5c5c61",
        "line": "#262626", "line_strong": "#3a3a3a",
        "accent": "#e0a82e", "accent_soft": "#2a2210", "accent_ink": "#17130a",
        "ok": "#4ade80", "warn": "#f0b93a", "err": "#f87171", "track": "#232323",
    },
}


def _norm_theme(theme: str) -> str:
    return "dunkel" if str(theme or "").lower().startswith("dunk") else "hell"


def available() -> bool:
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception:
        return False


def render_pdf(html_doc: str, out_path) -> bool:
    """HTML -> PDF via WeasyPrint. False, wenn nicht verfuegbar/fehlgeschlagen."""
    try:
        from weasyprint import HTML
        HTML(string=html_doc, base_url=str(config.BASE_DIR)).write_pdf(str(out_path))
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False


def _fmt_date(value: str) -> str:
    value = (value or "")[:10]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        y, m, d = value.split("-")
        return "%s.%s.%s" % (d, m, y)
    return value or "—"


_env.filters["de_date"] = _fmt_date


def _footer_context() -> dict:
    return {
        "credit": config.PDF_CREDIT,
        "github_url": config.GITHUB_URL,
        "author": config.AUTHOR_NAME,
        "app_name": config.APP_NAME,
        "version": config.VERSION,
        "generated_at": datetime.now().strftime("%d.%m.%Y"),
    }


# ---------------------------------------------------------------- Markdown -> HTML
def md_to_html(text: str) -> str:
    """Schlanker Markdown-Renderer fuer Anschreiben/Dokumente (Absaetze, Listen,
    Ueberschriften, fett/kursiv, Zitate). Kein vollstaendiges Markdown."""
    lines = (text or "").replace("\r\n", "\n").split("\n")
    out, para, list_type = [], [], None

    def inline(s: str) -> str:
        s = html_mod.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
        return s

    def flush_para():
        nonlocal para
        if para:
            # Zeilenumbrueche innerhalb eines Absatzes erhalten (Adressbloecke,
            # Grussformeln) – wie im bisherigen PDF-Renderer.
            out.append("<p>%s</p>" % "<br>".join(inline(x) for x in para))
            para = []

    def close_list():
        nonlocal list_type
        if list_type:
            out.append("</ul>" if list_type == "ul" else "</ol>")
            list_type = None

    for raw in lines:
        s = raw.rstrip()
        if not s.strip():
            flush_para(); close_list(); continue
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush_para(); close_list()
            level = min(len(m.group(1)) + 1, 4)
            out.append("<h%d>%s</h%d>" % (level, inline(m.group(2)), level))
            continue
        if re.match(r"^\s*[-*]\s+", s):
            flush_para()
            if list_type != "ul":
                close_list(); out.append("<ul>"); list_type = "ul"
            out.append("<li>%s</li>" % inline(re.sub(r"^\s*[-*]\s+", "", s)))
            continue
        if re.match(r"^\s*\d+[.)]\s+", s):
            flush_para()
            if list_type != "ol":
                close_list(); out.append("<ol>"); list_type = "ol"
            out.append("<li>%s</li>" % inline(re.sub(r"^\s*\d+[.)]\s+", "", s)))
            continue
        if s.lstrip().startswith("> "):
            flush_para(); close_list()
            out.append("<blockquote>%s</blockquote>" % inline(s.lstrip()[2:]))
            continue
        if re.match(r"^\s*([-*_])\1{2,}\s*$", s):
            flush_para(); close_list(); out.append("<hr>"); continue
        para.append(s.strip())
    flush_para(); close_list()
    return "\n".join(out)


# ---------------------------------------------------------------- Diagramme (SVG/HTML)
def _hex_lerp(a: str, b: str, t: float) -> str:
    def h(x):
        return x.lstrip("#")
    ar, ag, ab = int(h(a)[0:2], 16), int(h(a)[2:4], 16), int(h(a)[4:6], 16)
    br, bg, bb = int(h(b)[0:2], 16), int(h(b)[2:4], 16), int(h(b)[4:6], 16)
    return "#%02x%02x%02x" % (round(ar + (br - ar) * t), round(ag + (bg - ag) * t),
                              round(ab + (bb - ab) * t))


def donut_svg(items, center: str, theme: dict, stack: bool = False) -> str:
    total = sum(i["n"] for i in items)
    if not total:
        return "<p class='muted'>—</p>"
    r, cx, cy, width = 42, 55, 55, 13
    circ = 2 * math.pi * r
    parts = []
    acc = 0.0
    for it in items:
        frac = it["n"] / total
        dash = max(frac * circ - 1.5, 0)
        offset = -acc * circ
        parts.append(
            '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="%s" '
            'stroke-dasharray="%.3f %.3f" stroke-dashoffset="%.3f" transform="rotate(-90 %s %s)"/>'
            % (cx, cy, r, it.get("color", theme["faint"]), width, dash, circ - dash, offset, cx, cy))
        acc += frac
    legend = "".join(
        '<tr><td class="lg-dot"><span class="dot" style="background:%s"></span></td>'
        '<td class="lg-lbl">%s</td><td class="lg-pct">%d%%</td><td class="lg-n">%s</td></tr>'
        % (it.get("color", theme["faint"]), html_mod.escape(str(it["label"])),
           round(it["n"] / total * 100), it["n"])
        for it in items)
    wrap = "donut-stack" if stack else "donut-wrap"
    legend_cls = "legend legend-stacked" if stack else "legend"
    return (
        '<div class="%s"><svg class="donut-svg" viewBox="0 0 110 110" width="116" height="116">'
        '%s<text x="55" y="53" text-anchor="middle" class="donut-num">%s</text>'
        '<text x="55" y="66" text-anchor="middle" class="donut-lbl">%s</text></svg>'
        '<table class="%s">%s</table></div>'
        % (wrap, "".join(parts), total, html_mod.escape(str(center or "").upper()),
           legend_cls, legend)
    )


def bars_html(items, theme: dict, color=None, color_fn=None) -> str:
    if not items:
        return "<p class='muted'>—</p>"
    mx = max([1] + [i["n"] for i in items])
    rows = []
    for idx, it in enumerate(items):
        c = color_fn(it, idx, len(items)) if color_fn else (color or theme["accent"])
        rows.append(
            '<tr><td class="bar-label">%s</td>'
            '<td class="bar"><span class="bar-fill" style="width:%.1f%%;background:%s"></span></td>'
            '<td class="bar-num">%s</td></tr>'
            % (html_mod.escape(str(it["label"])), it["n"] / mx * 100, c, it["n"]))
    return '<table class="bars">%s</table>' % "".join(rows)


def funnel_html(items) -> str:
    if not items:
        return "<p class='muted'>—</p>"
    top = max(1, items[0]["n"] if items else 1)
    rows = []
    for it in items:
        pct = it["n"] / top * 100
        width = max(8, pct) if it["n"] else 0
        rows.append(
            '<tr><td class="funnel-label">%s</td>'
            '<td class="funnel-track"><span class="funnel-bar" style="width:%.1f%%;background:%s">'
            '<b>%s</b></span></td><td class="funnel-pct">%d%%</td></tr>'
            % (html_mod.escape(str(it["label"])), width, it.get("color", "#94a3b8"),
               it["n"], round(pct)))
    return '<table class="funnel">%s</table>' % "".join(rows)


def line_chart_svg(daily, theme: dict, height=190) -> str:
    if not daily:
        return "<p class='muted'>—</p>"
    w, h = 700, height
    pad_l, pad_r, pad_t, pad_b = 34, 30, 14, 26
    vals = [d.get("found", 0) for d in daily]
    mx = max(vals) or 1
    n = len(daily)
    plot_w, plot_h = w - pad_l - pad_r, h - pad_t - pad_b

    def x(i):
        return pad_l + (plot_w * (i / (n - 1)) if n > 1 else plot_w / 2)

    def y(v):
        return pad_t + plot_h * (1 - v / mx)

    pts = [(x(i), y(v)) for i, v in enumerate(vals)]
    line = " ".join("%.1f,%.1f" % p for p in pts)
    area = "M %.1f,%.1f L " % (pts[0][0], pad_t + plot_h) + " L ".join(
        "%.1f,%.1f" % p for p in pts) + " L %.1f,%.1f Z" % (pts[-1][0], pad_t + plot_h)
    grid = []
    for k in range(4):
        gy = pad_t + plot_h * k / 3
        val = round(mx * (1 - k / 3))
        grid.append('<line class="grid" x1="%s" y1="%.1f" x2="%s" y2="%.1f"/>'
                    % (pad_l, gy, w - pad_r, gy))
        grid.append('<text class="axis y" x="%s" y="%.1f">%s</text>' % (pad_l - 6, gy + 3, val))
    step = max(1, n // 7)
    xt = []
    for i in range(0, n, step):
        tx = min(max(x(i), pad_l + 12), w - pad_r - 14)
        xt.append('<text class="axis x" x="%.1f" y="%d">%s</text>'
                  % (tx, h - 8, html_mod.escape(str(daily[i]["d"])[5:])))
    dots = "".join('<circle class="dot-a" cx="%.1f" cy="%.1f" r="2.6"/>' % (px, py) for px, py in pts) \
        if n <= 40 else ""
    return (
        '<svg class="chart-svg" viewBox="0 0 %d %d" width="100%%" height="%d" '
        'preserveAspectRatio="xMidYMid meet">%s'
        '<path class="area" d="%s" fill="%s" opacity="0.14"/>'
        '<polyline class="line-a" fill="none" stroke="%s" points="%s"/>%s%s</svg>'
        % (w, h, h, "".join(grid), area, theme["accent"], theme["accent"], line, dots, "".join(xt)))


# ---------------------------------------------------------------- Dokumente
def _render(template: str, **ctx) -> str:
    return _env.get_template(template).render(**ctx)


def _base_ctx(theme: str, lang: str, **extra) -> dict:
    name = _norm_theme(theme)
    ctx = {
        "theme_name": name,
        "c": THEME[name],
        "lang": lang,
        "footer": _footer_context(),
    }
    ctx.update(extra)
    return ctx


def build_report_html(theme: str, lang: str, from_month: str = "", to_month: str = "") -> str:
    from .engines import stats as stats_engine
    data = stats_engine.collect(lang)
    apps = stats_engine.applications_list(lang, from_month, to_month)

    def _mlabel(ym: str) -> str:
        if re.match(r"^\d{4}-\d{2}$", ym or ""):
            return "%s/%s" % (ym[5:7], ym[:4])
        return ym or ""

    if from_month or to_month:
        period_label = "%s – %s" % (_mlabel(from_month) or "Anfang",
                                    _mlabel(to_month) or "heute")
    else:
        period_label = ""
    labels = data["status_labels"]
    status_items = [{"label": labels.get(k, k), "n": v, "color": data["status_colors"].get(k, "#94a3b8")}
                    for k, v in data["status_counts"].items() if v > 0]
    phase_colors = {"Interview-Prozess": "#14b8a6", "Absage": "#ef4444",
                    "Eingangsbestaetigung": "#6366f1", "Warte auf Rueckmeldung": "#eab308",
                    "Ohne Rueckmeldung": "#71717a"}
    phase_names = {"Eingangsbestaetigung": "Eingangsbestätigung",
                   "Warte auf Rueckmeldung": "Warte auf Rückmeldung",
                   "Ohne Rueckmeldung": "Ohne Rückmeldung"}
    phase_items = [{"label": phase_names.get(p["label"], p["label"]), "n": p["n"],
                    "color": phase_colors.get(p["label"], "#71717a")}
                   for p in data["phases"]]
    funnel_labels = {"found": "Gefunden", "applied": "Beworben", "response": "Antwort",
                     "interview": "Interview", "offer": "Angebot"}
    funnel_colors = {"found": "#71717a", "applied": "#6366f1", "response": "#cf9414",
                     "interview": "#14b8a6", "offer": "#15803d"}
    funnel = [{"label": funnel_labels.get(f["key"], f["key"]), "n": f["n"],
               "color": funnel_colors.get(f["key"], "#cf9414")} for f in data["funnel"]]
    theme_dict = THEME[_norm_theme(theme)]
    fit_items = data["fit"]
    fit_html = bars_html(
        fit_items, theme_dict,
        color_fn=lambda it, i, ln: _hex_lerp(theme_dict["faint"], theme_dict["accent"],
                                            0 if ln <= 1 else i / (ln - 1)))
    return _render(
        "stats.html", **_base_ctx(
            theme, lang,
            title="Bewerbungs- & Bemühungsnachweis",
            subtitle="Auswertung aller erfassten Stellen und Bewerbungen",
            data=data, apps=apps, period_label=period_label,
            donut_status=donut_svg(status_items, data["status_labels"].get("gesamt", "Jobs"),
                                   theme_dict),
            donut_phase=donut_svg(phase_items, "Antworten", theme_dict, stack=True),
            funnel_html=funnel_html(funnel),
            fit_html=fit_html,
            line_svg=line_chart_svg(data["daily"], theme_dict)))


def build_letter_html(text: str, job: dict, theme: str, lang: str, photo: str = "") -> str:
    photo_uri = ""
    if photo and os.path.exists(photo):
        try:
            from pathlib import Path
            photo_uri = Path(photo).as_uri()
        except Exception:
            photo_uri = ""
    return _render(
        "letter.html", **_base_ctx(
            theme, lang,
            title=job.get("title") or "",
            company=job.get("company") or "",
            location=job.get("location") or "",
            body=md_to_html(text),
            photo=photo_uri))


def build_document_html(text: str, title: str, theme: str, lang: str) -> str:
    return _render(
        "document.html", **_base_ctx(
            theme, lang, title=title, body=md_to_html(text)))
