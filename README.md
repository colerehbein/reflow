# reflow

PDF → clean, reflowable EPUB. Built for small e-ink screens (4.3″ Xteink-class
devices, Kindles, Kobos) where a PDF page becomes unreadable mush but an EPUB
reflows to the font size you pick.

Reverse-engineered reference: **rifflepages.com** (PDF→EPUB service). Recon and
evidence ledger in [`recon/RECON.md`](recon/RECON.md) — REA passive CDP analysis
of their shipped client recovered the full product contract, including the
pipeline's own stage enum (`READING → OCR → LAYOUT → WRITING`) and the conversion
data model. The server-side algorithms remain their trade secret; this project
rebuilds the published behavior spec independently.

## What it fixes (the published contract)

- Scanned PDFs go through **OCR** first (tesseract @ 300 dpi) → real text
- **Running heads and page numbers removed**
- **Paragraphs joined across pages** (and across line-end hyphens)
- **Drop caps rejoined** into their word
- **Chapters become a real TOC** (nav), TOC pages themselves dropped
- Verse, letters and scene breaks (`* * *`) kept as such
- Drawings kept as images
- Output is deliberately simple XHTML — stock e-reader software parses it best

## Status of each promise

| promise | born-digital PDFs | scanned PDFs |
|---|---|---|
| OCR text recovery | n/a | tesseract 300 dpi |
| running heads / page numbers | yes | yes |
| paragraphs joined across pages | yes | yes |
| hyphen resolution | yes | yes |
| drop caps rejoined | yes (size-based) | yes (shape-based, best effort) |
| chapter TOC | yes | yes |
| italics kept | yes — inline `<i>` runs | no (OCR has no font data) |
| verse / scene breaks | yes | yes (indent-based) |
| images kept | yes (embedded figures) | no — figures live inside the page bitmap and are not extracted |

Known honest gaps vs the reference product:

- **Footnotes: not yet separated.** Footnote text currently flows into body
  paragraphs (roadmap: marker/rule detection + endnote or pop-up handling).
  Do not convert footnote-heavy scholarly editions yet.
- **Italics on scans**: tesseract's TSV carries no font style. Born-digital
  PDFs keep inline `<i>` runs; scans lose them (~1.7 italic phrases per 1,000
  words measured in Moby-Dick — scholarly words, foreign terms, book titles).
- **Scanned figures**: figures live inside the page bitmap and are not
  extracted (image-only pages such as frontispieces are kept whole).
- **Two-column layouts** are not handled (single-column assumption).
- Small caps not reconstructed on scans (uppercase preserved as-is).

## Use

```bash
# system requirement: tesseract (macOS: brew install tesseract | Debian: apt install tesseract-ocr)
git clone https://github.com/colerehbein/reflow && cd reflow
uv venv && uv pip install -e .        # or: python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/reflow book.pdf -o book.epub
.venv/bin/reflow scan.pdf --json      # machine-readable report
```

No PDF handy? `reflow fixtures/synthetic.pdf -o demo.epub` runs the demo book
(2 chapters with planted defects: running heads, page numbers, drop cap,
hyphenation, scene break, cross-page paragraph).

Options: `--title --author --lang --dpi --workers --max-pages --no-ocr --force-ocr`.

The report mirrors the reference product's conversion model
(`pageCount, ocrPageCount, wordCount, chapterCount, scanned, …`) so outputs are
comparable.

## Layout

```
src/reflow/model.py      data model (spans → lines → pages → blocks → chapters)
src/reflow/read.py       READING: pymupdf text+layout extraction, scan detection
src/reflow/ocr.py        OCR: parallel tesseract, word boxes → lines
src/reflow/layout.py     LAYOUT: furniture strip, paragraph join, drop caps, chapters
src/reflow/write.py      WRITING: EPUB3 (ebooklib), one file per chapter
src/reflow/pipeline.py   READING → OCR → LAYOUT → WRITING + report
tests/run_tests.py       synthetic-fixture tests for every promise above
recon/RECON.md           REA evidence ledger for rifflepages.com
```

## Tests

```bash
env -u PYTHONPATH PYTHONPATH=src .venv/bin/python tests/run_tests.py
```

## License

Apache-2.0 — see [LICENSE](LICENSE). The REA recon artifacts under
`recon/scripts/` are third-party shipped assets kept out of version control
(see `recon/RECON.md`); they are not covered by this license.
