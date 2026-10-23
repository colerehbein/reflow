"""End-to-end italic proof: real italic font -> pymupdf flags -> EPUB <i>.
Run: .venv/bin/python tools/probe_italic_e2e.py
"""
import glob
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pymupdf

from reflow.pipeline import convert

candidates = glob.glob("/System/Library/Fonts/Supplemental/*Italic*.ttf")
if not candidates:
    candidates = glob.glob("/System/Library/Fonts/*Italic*.ttf")
assert candidates, "no system italic font found"
fontfile = candidates[0]
print("using font:", fontfile)

pdf = os.path.join(os.path.dirname(__file__), "..", "fixtures", "italic_e2e.pdf")
doc = pymupdf.open()
page = doc.new_page()
page.insert_font(fontname="Ital", fontfile=fontfile)
page.insert_text((72, 100), "Call me ", fontsize=11)
tw = pymupdf.TextWriter(page.rect)
tw.append((72, 116), "Ishmael", font=pymupdf.Font(fontfile=fontfile), fontsize=11)
tw.append((72 + 45, 116), ". Some years ago, never mind how long.", fontsize=11,
          font=pymupdf.Font("helv"))
tw.write_text(page)
doc.save(pdf)
doc.close()

# verify pymupdf reports the italic flag
d = pymupdf.open(pdf)
flag_italics = 0
for b in d[0].get_text("dict")["blocks"]:
    for l in b.get("lines", []):
        for s in l.get("spans", []):
            if s.get("flags", 0) & 2:
                flag_italics += 1
print("spans with italic flag:", flag_italics)
d.close()

out = pdf.replace(".pdf", ".epub")
convert(pdf, out, title="Italic E2E")
with zipfile.ZipFile(out) as z:
    xhtml = "".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
m = re.search(r"<i>[^<]*</i>", xhtml)
print("epub <i> runs:", xhtml.count("<i>"), "| sample:", m.group(0) if m else "NONE")
