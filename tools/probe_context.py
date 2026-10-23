"""Context probe: what does the source actually contain near a phrase?
Run: .venv/bin/python tools/probe_context.py fixtures/moby1922.pdf SQUEEZE [RADIUS]
"""
import sys

from reflow.read import extract_pages
from reflow.layout import strip_furniture, assemble

pdf = sys.argv[1]
needle = sys.argv[2].upper()
radius = int(sys.argv[3]) if len(sys.argv) > 3 else 4

pages = extract_pages(pdf)
strip_furniture(pages)

hits = []
for p in pages:
    for i, l in enumerate(p.lines):
        if needle in l.text.upper():
            hits.append((p, i))

for p, i in hits[:4]:
    print(f"\n=== page {p.number} line {i} ===")
    for l in sorted(p.lines, key=lambda x: x.top)[max(0, i - radius): i + radius + 1]:
        mark = ">>" if l in (sorted(p.lines, key=lambda x: x.top)[i],) else "  "
        print(f"{mark} top={l.top:6.1f} x0={l.x0:6.1f} kind={l.kind:8s} {l.text[:72]!r}")

blocks = assemble(pages)
print("\n=== assembled blocks touching the needle ===")
for b in blocks:
    if needle in b.text.upper():
        print(f"  {b.kind:12s} lines={len(b.lines)} {b.text[:110]!r}")
