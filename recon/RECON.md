# RECON — rifflepages.com (PDF → EPUB service)

Method: REA (Reverse Engineer Anything) passive CDP observation of the shipped web
client on 2026-10-22, plus static string analysis of the captured bundle bytes.
Evidence classes: **observed** (shipped artifact bytes) / **inferred** (bounded) /
**unknown** (server-side, not in any shipped artifact).

Evidence IDs (REA session):
- `ev_d2249e06…` list_browser_targets (Chrome 155 headless, target `48B64DEF…`)
- `ev_44caf4d4…` inspect_web_page (DOM/scripts/resources; 818 KB, full capture in
  Hermes spillover `call_fc7fbcfa0b504bc9a8685aee.txt`, sha256 05c6e098…)
- `ev_a2d55666…` analyze_web_bundle (chunk graph, endpoints, vendor fingerprints)
- `ev_a5c49349…` export_web_scripts → `recon/scripts/` (manifest + 2 sources)
- `ev_bb15b9ec…` / `ev_72cdfdd8…` analyze_javascript_application + summary view

Note: `recon/scripts/files/` (the exported third-party bundle bytes) is
deliberately NOT in version control — those are rifflepages' shipped assets,
not ours to relicense. The manifest keeps the digests; the exports are
regenerable from the capture described above.

## Observed

**Client**: React SPA, single Vite bundle `assets/index-DPa5_UvQ.js` (748,677 B,
sha256 34faf834…). Cloudflare Turnstile in front (`X-Turnstile-Token` header on
upload). UI copy embedded in bundle (i18n: en/id — `locale`, `/api/translations/*`).

**API surface** (all string-built; observed in bundle):
- `GET  /api/limits` (no auth) — preview page count etc.
- `GET  /api/pricing?region=` (no auth)
- `GET|POST /api/conversions`, `GET|DELETE /api/conversions/{id}`
- `POST /api/conversions/{id}/checkout` `{email, voucherCode}`; `GET …/orders`
- `GET  /api/conversions/{id}/preview` → blob (arrayBuffer) — free preview
- `GET  /api/conversions/{id}/cover` → blob
- `GET  /api/conversions/{id}/epub` → full EPUB download (paid gate)
- `PUT  /api/conversions/{id}/notify` `{email, lang}`; `…/feedback`; `…/access`
- `POST /api/conversions/{id}/reports` (multipart)
- `POST /api/vouchers/check` `{conversionId|translationId, code}`
- `/api/sessions`, `/api/sessions/me`
- Second product line: **translation** — `POST /api/conversions/{id}/translations`,
  `/api/translations/{id}/copy|preview|cover|epub`, `/api/translations/quote?lang=`,
  `/api/translations/examples`, `/api/translations/languages`

**Upload**: `FormData{file, accept_terms:"true", …metadata}` → `POST /api/conversions`,
optional `X-Turnstile-Token` header. Dedupe: response carries `duplicate` flag.

**Conversion model** (class fields, verbatim from bundle):
`id, status, stage, progress, fileName, fileSize, title, author, language,
pageCount, ocrPageCount, wordCount, chapterCount, hasPreview, hasCover, paid,
errorCode, errorMessage, createdAt, startedAt, finishedAt, expiresAt, notifyEmail,
queue, report, feedback`

- `status ∈ PENDING | PROCESSING | READY | FAILED | EXPIRED`
- **`stage ∈ QUEUED | READING | OCR | LAYOUT | WRITING | DONE`** ← the pipeline
- `isScanned ⇔ ocrPageCount > 0 && ocrPageCount >= pageCount/2` (their scan heuristic)
- report categories: `MISSING_TEXT | WRONG_TEXT | CHAPTERS | LAYOUT | IMAGES | OTHER`

**Published behavior spec** (their own copy — the contract we build against):
OCR first for scans; running heads + page numbers removed; paragraphs joined
across pages; decorated first letters (drop caps) rejoined into their word;
chapter openings → real TOC; italics/small caps/scene breaks/letters/verse/
footnotes kept (footnotes as pop-ups where supported); drawings kept as images
with captions as text; pages that are only a picture (frontispiece) stay whole.

## Inferred (bounded)

- Conversion is **server-side**: zero client OCR/PDF/EPUB libraries in the bundle
  (no tesseract.js / pdf.js / epub.js / jszip). Client only uploads, polls
  `status/stage/progress`, and fetches preview/cover/epub blobs.
- "Your books live in this browser" = local shelf via `indexedDB`/`localStorage`.
- `READY`/`FAILED`/`EXPIRED` + `expiresAt` matches "files deleted after 24 h".

## Unknown (not answerable from shipped artifacts)

- Server OCR engine, layout algorithm, chapter-detection rules, EPUB writer.
  (A live upload requires solving Turnstile — deliberately not attempted.)
- Preview paging logic beyond `GET /api/limits`; payment provider (QRIS + card).

## What we build (design taken from the observed contract)

Pipeline stages mirroring `READING → OCR → LAYOUT → WRITING`:
1. **READING** — pymupdf page/text extraction; scan detection (`ocrPageCount >= pageCount/2`).
2. **OCR** — tesseract on scanned pages (300 dpi render).
3. **LAYOUT** — running heads/page numbers out, paragraphs joined across pages,
   drop caps rejoined, hyphens fixed, chapters detected → TOC, verse/letters
   preserved, images + captions.
4. **WRITING** — clean EPUB3, one file per chapter, real nav TOC.
