# NOTES — design locks and honest gaps

Reference product: rifflepages.com (see `recon/RECON.md` for the REA evidence
ledger). Test corpus: Moby-Dick (Constable 1922, U. Toronto scan, public
domain, 382 pp) + synthetic defect fixtures (`tests/run_tests.py`).

## Locks (each earned by a failure on the real book)

1. **Per-page modal column edges** — never min/max, never book-level. Scanned
   volumes change page geometry per section (body column at x≈31 in one part,
   x≈42 in another) and footnotes/marginalia sit left of body. A book-level
   statistic makes every body line look "indented" → paragraphs break per line
   (measured: median paragraph length collapsed to 54 chars).
2. **Furniture = prefix cluster (12 norm chars) over ≥2 pages, word-capped at
   8** — exact-text matching fails because page numbers and OCR markers get
   glued onto heads (`SCHOOLS AND SCHOOLMASTERS 141`), and y-position can't be
   in the key (geometry varies per section). Plus two direct rules: pure
   page-number lines anywhere, and ALL-CAPS digit-carrying top-band lines.
   Chapter/front-matter lines are exempt from both (OCR-noised numerals like
   `CHAPTER LXXXVI1I` contain digits; `chapter lxxx…` prefixes collide across
   five chapter numbers).
3. **Scan-substrate images excluded** — IA scans embed the full page as a JPX
   image under the text layer (area share 1.0). Kept only on image-only pages
   (frontispiece); otherwise they flush paragraphs at every page top and stuff
   raw page scans into the EPUB.
4. **Hyphen override beats indent** — a line ending `-` with a lowercase
   successor continues the paragraph no matter the x0 (OCR jitter can shift a
   continuation line 20pt and split "lassi-/tude").
5. **Chapter headings: three gates** —
   - `CHAPTER/CHAP.` + numeral (whole token, `(?![0-9a-z])` — otherwise
     "chapter it was…" matches roman "i") → heading, no other gate.
   - bare `CHAPTER` line ≤8 words → heading if centered, all-caps, or
     unpunctuated (isolation can't gate: cross-page gap reads 0 at page tops).
   - generic short caps/title lines → heading only if same-page isolated,
     unpunctuated, and bigger-than-body or all-caps.
6. **Heading runs** — 1–2 consecutive headings merge into one chapter title
   ("CHAPTER LXVI" + "THE SHARK MASSACRE"); a run of ≥3 is a TOC/title page and
   is dropped. A "CONTENTS" heading opens a TOC region: until the first
   numeral'd chapter heading with body behind it, headings and body both drop.
7. **Chapter validity** — a heading must have body behind it (`≥30` chars for
   numeral headings — chapters open with short extracts; ≥120 chars or two ≥40
   for generic lines). TOC entries and end stamps fail this by construction.
8. **OCR threading** — ThreadPoolExecutor, not processes: pytesseract shells
   out to the tesseract binary, so parallelism is in those child processes and
   multiprocessing spawn only causes breakage.

## Verified behavior (Moby-Dick 1922 scan, v8)

382 pp → 75 chapters (LXI…CXXXV + EPILOGUE in sequence), 111k words, 393
furniture lines removed, watermarks removed, TOC pages dropped, drop caps and
line-end hyphens resolved, cross-page paragraphs joined (24-line paragraphs
measured). Calibre round-trips the EPUB to MOBI/PDF; zip integrity clean.
Forced-OCR path verified on 20 pages (20/20 OCR'd, `scanned=true` per the
reference product's own heuristic `ocrPageCount >= pageCount/2`).

## Honest gaps vs the reference product

- **Italics on scans**: tesseract's TSV carries no font style. Born-digital
  PDFs keep italics (pymupdf font flags); scans lose them. A slant-classifier
  over word crops is the fix and is not implemented.
- **Footnote pop-ups**: kept as `p.footnote` paragraphs, not EPUB pop-up
  links.
- **OCR noise is inherited verbatim** from the source's hidden text layer
  ("CHAPTER XGIV", "THE CEOTCH"). The reference product's own FAQ says what
  you see is what you get; re-OCRing heading crops is the upgrade path.
- **Single-column assumption**; two-column scholarly layouts not handled.
- Small caps not reconstructed on scans (uppercase preserved as-is).

## Knobs if tuning is needed

`TOP_BAND/BOTTOM_BAND` (furniture bands), `0.75*em` (indent threshold),
`0.22*page.width` (centered-title test), `_has_body_ahead` length gates
(30/120/40), `MIN_CONF` (OCR word confidence), `DPI`.
