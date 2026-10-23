"""Debug: furniture clustering + raw chapter head inspection.
Run: .venv/bin/python tools/probe_furniture.py fixtures/moby1922.pdf out/moby1922.epub
"""
import re
import sys
import zipfile
from collections import Counter

from reflow.read import extract_pages
from reflow.layout import strip_furniture, _normalize, TOP_BAND, BOTTOM_BAND, PAGE_NUM_RE

pdf = sys.argv[1]
epub_path = sys.argv[2] if len(sys.argv) > 2 else None

pages = extract_pages(pdf)

# replicate the clustering to see why the head survives
clusters = {}
for page in pages:
    for line in page.lines:
        if not line.text:
            continue
        in_head = line.top < page.height * TOP_BAND
        in_foot = line.bottom > page.height * (1 - BOTTOM_BAND)
        if not (in_head or in_foot):
            continue
        if PAGE_NUM_RE.match(line.text):
            continue
        norm = _normalize(line.text)
        if len(norm.split()) > 8:
            continue
        key = (norm[:12], 0)
        rec = clusters.setdefault(key, {"pages": set(), "lines": []})
        rec["pages"].add(page.number)
        rec["lines"].append(line)

print("clusters whose prefix mentions schools/chapter/moby:")
for key, rec in clusters.items():
    if any(w in key[0] for w in ("schools", "chapter", "moby", "whale")):
        print(f"  {key!r} pages={len(rec['pages'])} sample={rec['lines'][0].text[:50]!r}")

strip_furniture(pages)
head = [l for l in pages[150].lines if l.text.startswith("SCHOOLS")]
for l in head:
    print(f"page150 head after strip: kind={l.kind!r} text={l.text[:50]!r}")

if epub_path:
    z = zipfile.ZipFile(epub_path)
    names = sorted(n for n in z.namelist() if n.endswith(".xhtml") and "nav" not in n)
    raw = z.read(names[5]).decode("utf-8", "replace")
    print("\n--- raw head of", names[5], "(first 600 chars) ---")
    print(raw[:600])
