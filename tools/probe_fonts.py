"""Probe: what font metadata does the source text layer actually carry?
Run: .venv/bin/python tools/probe_fonts.py fixtures/moby1922.pdf [first_page] [last_page]
"""
import sys
from collections import Counter

import pymupdf

pdf = sys.argv[1]
a = int(sys.argv[2]) if len(sys.argv) > 2 else 140
b = int(sys.argv[3]) if len(sys.argv) > 3 else 160

d = pymupdf.open(pdf)
fonts = Counter()
flags = Counter()
italic_names = Counter()
for pno in range(a, min(b, len(d))):
    for blk in d[pno].get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for line in blk.get("lines", []):
            for s in line.get("spans", []):
                f = s.get("font", "")
                fonts[f] += 1
                flags[s.get("flags", 0)] += 1
                if "italic" in f.lower() or "oblique" in f.lower():
                    italic_names[f] += 1
print("fonts in text layer:", dict(fonts))
print("span flags:", dict(flags))
print("italic-named fonts:", dict(italic_names))
