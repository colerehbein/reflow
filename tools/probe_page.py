"""Deep probe: per-page event stream + paragraph line counts.
Run: .venv/bin/python tools/probe_page.py fixtures/moby1922.pdf [page_no]
"""
import statistics
import sys
from collections import Counter

from reflow.read import extract_pages
from reflow.layout import strip_furniture, assemble

pdf = sys.argv[1]
pno = int(sys.argv[2]) if len(sys.argv) > 2 else 150

pages = extract_pages(pdf)
strip_furniture(pages)

para_lines = Counter()
for b in assemble(pages):
    if b.kind == "paragraph":
        para_lines[len(b.lines)] += 1
print("paragraph line-count histogram:", dict(sorted(para_lines.items())))

p = pages[pno]
print(f"\n--- page {pno}: {len(p.lines)} lines, {len(p.images)} images, "
      f"{p.width:.0f}x{p.height:.0f}pt ---")
for img in p.images[:6]:
    share = img.area / (p.width * p.height)
    print(f"  image xref={img.xref} y0={img.y0:.0f} area_share={share:.2f} ext={img.ext}")
lines = sorted(p.lines, key=lambda l: l.top)
for l in lines[:22]:
    print(f"  L x0={l.x0:6.1f} top={l.top:6.1f} h={l.bottom-l.top:5.1f} kind={l.kind:8s} {l.text[:48]!r}")
