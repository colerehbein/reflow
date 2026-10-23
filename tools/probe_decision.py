"""Micro-probe: why does each line start a new block? Prints the decision.
Run: .venv/bin/python tools/probe_decision.py fixtures/moby1922.pdf 150
"""
import sys

from reflow.read import extract_pages
from reflow.layout import strip_furniture, body_size_of, _heading_kind, _verse_line
from reflow.model import Line

pdf = sys.argv[1]
pno = int(sys.argv[2]) if len(sys.argv) > 2 else 150

pages = extract_pages(pdf)
strip_furniture(pages)

body_size = body_size_of(pages)
em = body_size
body_lines = [l for p in pages for l in p.lines if l.kind == "body" and l.text]

from collections import Counter
import statistics

def modal_edge(vals, step=2.0):
    bins = Counter(); samples = {}
    for v in vals:
        b = int(v // step); bins[b] += 1; samples.setdefault(b, []).append(v)
    best = bins.most_common(1)[0][0]
    return statistics.median(samples[best]), bins.most_common(3)

left, top_bins = modal_edge([l.x0 for l in body_lines])
right, right_bins = modal_edge([l.x1 for l in body_lines])
print(f"body_size={body_size:.2f} left={left:.2f} right={right:.2f} col_width={right-left:.2f}")
print("x0 modal bins:", top_bins)
print("x1 modal bins:", right_bins)

p = pages[pno]
lines = sorted([l for l in p.lines if l.kind == "body"], key=lambda l: l.top)
prev = None
for line in lines[:12]:
    head = _heading_kind(line, body_size, prev, p, em)
    same_page = prev is not None and prev.page_no == line.page_no
    gap = (line.top - prev.bottom) if (prev is not None and same_page) else 0.0
    line_h = max(1.0, line.bottom - line.top)
    indent = line.x0 - left
    indented = indent > 0.75 * em
    big_gap = same_page and gap > 1.9 * line_h
    verse = prev is not None and _verse_line(line, left, right - left, em) and _verse_line(prev, left, right - left, em)
    print(f"top={line.top:6.1f} x0={line.x0:6.2f} indent={indent:5.2f} gap={gap:5.2f} "
          f"lh={line_h:4.1f} indented={indented} big_gap={big_gap} head={head} verse={verse} "
          f"{line.text[:32]!r}")
    prev = line
