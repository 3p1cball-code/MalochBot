#!/usr/bin/env python3
"""Rendert eine Markdown-Datei als saubere PDF-Arbeitsprobe (ohne LibreOffice).

Verwendet fpdf2 und die mit MalochBot gebuendelten DejaVu-Schriften.
"""
import os
import re
import sys

from fpdf import FPDF

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = os.path.join(ROOT, "app", "fonts")
LOGO = os.path.join(ROOT, "assets", "logo.png")


def main(md_path: str, out_path: str, title: str, subtitle: str, date: str):
    text = open(md_path, encoding="utf-8").read()
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(22, 20, 22)
    pdf.add_font("body", "", os.path.join(FONTS, "DejaVuSans.ttf"))
    pdf.add_font("body", "B", os.path.join(FONTS, "DejaVuSans-Bold.ttf"))
    left = pdf.l_margin

    # Titelseite
    pdf.add_page()
    if os.path.exists(LOGO):
        pdf.image(LOGO, x=(210 - 34) / 2, y=64, w=34)
    pdf.set_y(112)
    pdf.set_font("body", "B", 26)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 12, title, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("body", "", 12)
    pdf.set_text_color(90, 100, 120)
    pdf.ln(2)
    pdf.multi_cell(0, 7, subtitle, align="C")
    pdf.ln(4)
    pdf.set_font("body", "", 10)
    pdf.cell(0, 6, date, align="C")
    pdf.set_text_color(30, 41, 59)

    # Inhalt (Titelseite im Markdown ueberspringen: bis zum ersten '---')
    lines = text.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip() == "---":
            start = i + 1
            break
    pdf.add_page()
    pdf.set_font("body", "", 11)

    # Markdown in Bloecke zerlegen (Absaetze zusammenfuehren)
    body_lines = lines[start:]
    # eingerueckte Fortsetzungen von Listenpunkten an den Punkt anhaengen
    merged_lines = []
    for ln in body_lines:
        prev = merged_lines[-1] if merged_lines else ""
        if merged_lines and re.match(r"^\s{2,}\S", ln) and (
                prev.startswith("- ") or prev.startswith("* ")
                or re.match(r"^\d+\.\s", prev.strip())):
            merged_lines[-1] = prev.rstrip() + " " + ln.strip()
        else:
            merged_lines.append(ln)
    body_lines = merged_lines
    blocks = []
    buf = []

    def flush():
        if buf:
            blocks.append(("P", " ".join(buf)))
            buf.clear()

    i = 0
    while i < len(body_lines):
        ln = body_lines[i]
        if ln.startswith("```"):
            flush()
            code = []
            i += 1
            while i < len(body_lines) and not body_lines[i].startswith("```"):
                code.append(body_lines[i])
                i += 1
            blocks.append(("CODE", code))
            i += 1
            continue
        if not ln.strip():
            flush()
            i += 1
            continue
        if ln.startswith("!["):
            flush()
            blocks.append(("IMG", ln))
            i += 1
            continue
        if ln.startswith(("#", "- ", "* ", "> ")) or re.match(r"^\d+\.\s", ln.strip()) \
                or ln.strip() == "---":
            flush()
            blocks.append(("LINE", ln))
            i += 1
            continue
        buf.append(ln.strip())
        i += 1
    flush()

    content_w = 210 - left - pdf.r_margin

    for kind, payload in blocks:
        pdf.set_x(left)
        if kind == "IMG":
            m = re.match(r"!\[[^\]]*\]\(([^)]+)\)", payload)
            if m:
                img = m.group(1)
                if not os.path.isabs(img):
                    img = os.path.join(os.path.dirname(os.path.abspath(md_path)), img)
                if os.path.exists(img):
                    pdf.ln(2)
                    pdf.image(img, w=content_w)
                    pdf.ln(2)
            continue
        if kind == "CODE":
            pdf.ln(1)
            pdf.set_text_color(60, 70, 90)
            pdf.set_left_margin(left + 3)
            for cl in payload:
                pdf.set_font("body", "", 9)
                pdf.multi_cell(0, 4.6, cl if cl.strip() else " ",
                               new_x="LMARGIN", new_y="NEXT")
            pdf.set_left_margin(left)
            pdf.set_text_color(30, 41, 59)
            pdf.ln(1)
            continue
        if kind == "P":
            pdf.set_font("body", "", 11)
            pdf.multi_cell(content_w, 6.2, payload, markdown=True,
                           new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            continue
        stripped = payload.strip()
        if stripped == "---":
            pdf.ln(2)
            pdf.set_draw_color(210, 216, 226)
            y = pdf.get_y()
            pdf.line(left, y, 210 - pdf.r_margin, y)
            pdf.ln(4)
        elif payload.startswith("### "):
            pdf.set_font("body", "B", 12.5)
            pdf.ln(2)
            pdf.multi_cell(content_w, 6.4, payload[4:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif payload.startswith("## "):
            pdf.set_font("body", "B", 15)
            pdf.ln(3)
            pdf.multi_cell(content_w, 7.5, payload[3:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)
        elif payload.startswith("# "):
            pdf.set_font("body", "B", 19)
            pdf.ln(3)
            pdf.multi_cell(content_w, 9, payload[2:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            pdf.set_font("body", "", 11)
            pdf.set_left_margin(left + 4)
            pdf.set_x(left + 4)
            pdf.multi_cell(0, 6, "\u2022  " + stripped[2:], markdown=True,
                           new_x="LMARGIN", new_y="NEXT")
            pdf.set_left_margin(left)
            pdf.ln(0.8)
        elif re.match(r"^\d+\.\s", stripped):
            pdf.set_font("body", "", 11)
            pdf.set_left_margin(left + 4)
            pdf.set_x(left + 4)
            pdf.multi_cell(0, 6, stripped, markdown=True,
                           new_x="LMARGIN", new_y="NEXT")
            pdf.set_left_margin(left)
            pdf.ln(0.8)
        elif stripped.startswith("> "):
            pdf.set_font("body", "", 10.5)
            pdf.set_text_color(90, 100, 120)
            pdf.set_left_margin(left + 5)
            pdf.multi_cell(0, 6, stripped[2:], markdown=True,
                           new_x="LMARGIN", new_y="NEXT")
            pdf.set_left_margin(left)
            pdf.set_text_color(30, 41, 59)
            pdf.ln(1)
        else:
            pdf.set_font("body", "", 11)
            pdf.multi_cell(content_w, 6.2, payload, markdown=True,
                           new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

    pdf.output(out_path)
    print("PDF:", out_path, os.path.getsize(out_path), "bytes")


if __name__ == "__main__":
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3] if len(sys.argv) > 3 else "MalochBot",
        sys.argv[4] if len(sys.argv) > 4 else "",
        sys.argv[5] if len(sys.argv) > 5 else "",
    )
