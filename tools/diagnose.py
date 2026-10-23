"""Diagnostic probe: block-length distribution on a real book.
Run: .venv/bin/python tools/diagnose.py fixtures/moby1922.pdf
"""
import statistics
import sys
from collections import Counter

from reflow.read import extract_pages, pages_needing_ocr
from reflow.ocr import ocr_pages
from reflow.layout import strip_furniture, assemble, chapterize, body_size_of

pdf = sys.argv[1] if len(sys.argv) > 1 else "fixtures/moby1922.pdf"

pages = extract_pages(pdf)
need = pages_needing_ocr(pages)
if need:
    for pno, pg in ocr_pages(pdf, need, workers=4).items():
        pages[pno] = pg
strip_furniture(pages)
print("body_size:", round(body_size_of(pages), 2))

blocks = assemble(pages)
kinds = Counter(b.kind for b in blocks)
print("blocks:", len(blocks), dict(kinds))

paras = sorted(len(b.text) for b in blocks if b.kind == "paragraph")
if paras:
    print("paragraph len: min", paras[0], "| p25", paras[len(paras) // 4],
          "| median", statistics.median(paras), "| p75", paras[3 * len(paras) // 4],
          "| max", paras[-1])
    print("share <40:", round(sum(n < 40 for n in paras) / len(paras), 2),
          "| share <120:", round(sum(n < 120 for n in paras) / len(paras), 2))

short = [b for b in blocks if b.kind == "paragraph" and len(b.text) < 60][:8]
for b in short:
    print("  short:", repr(b.text[:70]), "| lines:", len(b.lines))

chs = chapterize(blocks)
print("chapters:", len(chs))
for c in chs[:14]:
    print("  ·", c.title[:70])
