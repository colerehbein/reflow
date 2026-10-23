"""Deep probe v2: assembled blocks for one page + where singles cluster.
Run: .venv/bin/python tools/probe_blocks.py fixtures/moby1922.pdf [page_no]
"""
import sys
from collections import Counter

from reflow.read import extract_pages
from reflow.layout import strip_furniture, assemble, _normalize

pdf = sys.argv[1]
pno = int(sys.argv[2]) if len(sys.argv) > 2 else 150

pages = extract_pages(pdf)

# furniture sanity for this page's head line
norms = Counter()
for p in pages:
    for l in p.lines:
        if l.text and (l.top < p.height * 0.14 or l.bottom > p.height * 0.88):
            norms[_normalize(l.text)] += 1
target = _normalize("SCHOOLS  AND  SCHOOLMASTERS  141")
print(f"normalized head {target!r} occurs {norms.get(target, 0)} times in bands")
print("top band norms on page", pno, ":",
      [_normalize(l.text) for l in pages[pno].lines if l.text and l.top < pages[pno].height * 0.14])

strip_furniture(pages)
blocks = assemble(pages)

# singles per page
singles = Counter()
totals = Counter()
for b in blocks:
    if b.kind != "paragraph":
        continue
    pg = b.lines[0].page_no if b.lines else -1
    totals[pg] += 1
    if len(b.lines) == 1:
        singles[pg] += 1
worst = sorted(singles.items(), key=lambda kv: -kv[1])[:10]
print("pages with most single-line paragraphs (page: singles/total):")
for pg, n in worst:
    print(f"  p{pg}: {n}/{totals[pg]}")

print(f"\n--- assembled blocks on page {pno} ---")
for b in blocks:
    if b.lines and b.lines[0].page_no == pno:
        print(f"  {b.kind:12s} lines={len(b.lines):2d} chars={len(b.text):4d} {b.text[:64]!r}")
