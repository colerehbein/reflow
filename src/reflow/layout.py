"""LAYOUT stage: turn per-page lines into clean reading blocks and chapters.

Handles exactly the defects the reference product advertises fixing:
  * running heads and page numbers removed
  * paragraphs joined across pages (including across the page gutter)
  * line-end hyphens resolved (de-hyphenated when the word continues lowercase)
  * decorated first letters (drop caps) rejoined into their word
  * chapter openings become real TOC entries; TOC pages themselves dropped
  * verse / letters keep line breaks; * * * becomes a scene break
"""
from __future__ import annotations

import re
import statistics
from collections import Counter

from .model import Block, Chapter, ImageRef, Line, Page

ROMAN = r"(?:[ivxlcdm]+)"
PAGE_NUM_RE = re.compile(rf"^\s*[-–—·•*]?\s*(?:{ROMAN}|\d+)\s*[-–—·•*]?\s*$", re.I)
# "chapter"/"chap." may stand alone (…but only when isolated, checked later);
# "part/book/canto/section" demand a numeral so body lines like
# "part of the tail…" or "book of Kings." can never match. The (?![0-9a-z])
# makes the numeral a whole token — without it "chapter it was…" matches
# the roman "i" and gets treated as a heading.
CHAPTER_RE = re.compile(
    r"^\s*(?:(?:chapter|chap\.?)\s*([0-9]+|[ivxlcdm]+)?(?![0-9a-z])\.?"
    r"|(?:part|book|canto|section)\s+([0-9]+|[ivxlcdm]+)(?![0-9a-z]))\s*"
    r"[-–—.:]?\s*(?P<title>.*)$".format(roman=ROMAN),
    re.I,
)
FRONT_MATTER_RE = re.compile(
    r"^\s*(contents|table of contents|preface|foreword|introduction|prologue|epilogue|"
    r"etymology|extracts|appendix|notes|bibliography|index|glossary|acknowledg?ments|"
    r"dedication|epigraph|afterword|postscript|argument|title page|copyright)\s*[:.]?\s*$",
    re.I,
)
FRONT_TOC_RE = re.compile(r"^\s*(contents|table of contents)\s*[:.]?\s*$", re.I)
WATERMARK_RE = re.compile(
    r"^\s*(digitized by (the )?internet archive|in \d{4} with funding from|"
    r"microsoft corporation|internet archive|archive\.org)\s*[:.]?\s*$",
    re.I,
)
SCENE_BREAK_RE = re.compile(r"^\s*([-–—*·•◦○⁂_]\s*){2,}\s*$")
TOC_LINE_RE = re.compile(r"^\s*.{0,70}?[\s.·‧…]{4,}\s*\d+\s*$")
DROP_CAP_RE = re.compile(r"^[A-Z0-9('“'\"‘]$|^[A-Z]{1,2}$")

TOP_BAND = 0.10   # share of page height where running heads live
BOTTOM_BAND = 0.12


# ---------------------------------------------------------------- furniture

def strip_furniture(pages: list[Page]) -> int:
    """Mark running heads / footers / page numbers as dropped. Returns count.

    Running furniture repeats across pages at a stable y with near-identical
    text — but not identical: page numbers and stray OCR markers get glued on
    ("SCHOOLS AND SCHOOLMASTERS 141" vs "…142 2"). Cluster by text prefix +
    vertical position instead of exact text.
    """
    clusters: dict[tuple[str, int], dict] = {}
    numeric: list[Line] = []

    for page in pages:
        for line in page.lines:
            if not line.text:
                continue
            # scan watermarks are furniture wherever they sit
            if WATERMARK_RE.match(line.text):
                numeric.append(line)
                continue
            in_head = line.top < page.height * TOP_BAND
            in_foot = line.bottom > page.height * (1 - BOTTOM_BAND)
            if not (in_head or in_foot):
                continue
            if PAGE_NUM_RE.match(line.text):
                numeric.append(line)
                continue
            # an ALL-CAPS band line carrying digits is a running head with the
            # printed page number glued on ("SCHOOLS AND SCHOOLMASTERS 141"):
            # it can never repeat as a cluster, so drop it directly. Chapter
            # and front-matter lines are exempt — OCR-noised numerals like
            # "CHAPTER LXXXVI1I" contain digits but are structure, not furniture.
            structural = bool(CHAPTER_RE.match(line.text) or FRONT_MATTER_RE.match(line.text))
            if in_head and not structural and re.search(r"\d", line.text) and line.text == line.text.upper():
                numeric.append(line)
                continue
            if structural:
                continue  # never cluster chapter/front-matter lines as heads
            norm = _normalize(line.text)
            # heads are short; body lines almost never share a 12-char prefix
            # across 2+ pages. Word cap keeps prose out of the clusters; y is
            # not part of the key because page geometry varies per section.
            if len(norm.split()) > 8:
                continue
            key = (norm[:12], 0)
            rec = clusters.setdefault(key, {"pages": set(), "lines": []})
            rec["pages"].add(page.number)
            rec["lines"].append(line)

    n_pages = max(1, len(pages))
    min_pages = min(2, max(2, n_pages))
    dropped = 0
    for line in numeric:
        line.kind = "dropped"
        dropped += 1
    for rec in clusters.values():
        if len(rec["pages"]) >= min_pages:
            for line in rec["lines"]:
                if line.kind == "body":
                    line.kind = "dropped"
                    dropped += 1
    return dropped


def _normalize(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"\d+", "#", t)
    t = re.sub(r"\s+", " ", t)
    return t


# ---------------------------------------------------------------- assembly

def body_size_of(pages: list[Page]) -> float:
    sizes = [
        line.max_size
        for page in pages
        for line in page.lines
        if line.kind == "body" and len(line.text) > 40
    ]
    return statistics.median(sizes) if sizes else 10.0


def assemble(pages: list[Page]) -> list[Block]:
    """Join cleaned lines into semantic blocks across the whole book."""
    body_size = body_size_of(pages)
    em = body_size
    body_lines = [l for p in pages for l in p.lines if l.kind == "body" and l.text]
    if not body_lines:
        return []
    # robust column edges: page geometry varies inside a scanned volume (the
    # Moby-Dick 1922 two-volume scan has body columns at different x per
    # section), and footnotes/marginalia skew any book-level statistic. Use
    # each page's own modal line start/end, falling back to the book mode.
    def modal_edge(vals: list[float], step: float = 2.0) -> float:
        bins: Counter[int] = Counter()
        samples: dict[int, list[float]] = {}
        for v in vals:
            b = int(v // step)
            bins[b] += 1
            samples.setdefault(b, []).append(v)
        best = bins.most_common(1)[0][0]
        return statistics.median(samples[best])

    book_left = modal_edge([l.x0 for l in body_lines])
    book_right = modal_edge([l.x1 for l in body_lines])

    def page_edges(page: Page) -> tuple[float, float]:
        lines = [l for l in page.lines if l.kind == "body" and l.text]
        if len(lines) < 5:
            return book_left, book_right
        lft = modal_edge([l.x0 for l in lines])
        rgt = modal_edge([l.x1 for l in lines])
        if rgt <= lft:
            rgt = max(l.x1 for l in lines)
        return lft, rgt

    blocks: list[Block] = []
    cur: list[Line] = []
    cur_kind = "paragraph"
    prev: Line | None = None

    def flush():
        nonlocal cur, cur_kind
        if not cur:
            return
        blocks.append(_make_block(cur, cur_kind, body_size))
        cur = []
        cur_kind = "paragraph"

    for page in pages:
        # reading-order event stream: text lines and real images interleaved by y
        left, right = page_edges(page)
        col_width = right - left
        page_lines = [l for l in page.lines if l.kind == "body" and l.text]
        events: list[tuple[float, int, object]] = [
            (l.top, 1, l) for l in page_lines
        ]
        for img in page.images:
            share = img.area / max(1.0, page.width * page.height)
            if share >= 0.6 and page.text_chars >= 40:
                continue  # full-page scan substrate, not a content illustration
            if img.area >= 0.02 * page.width * page.height:
                events.append((img.y0, 0, img))
        events.sort(key=lambda e: (e[0], e[1]))
        for _y, _k, obj in events:
            if isinstance(obj, ImageRef):
                flush()
                blocks.append(Block(kind="image", text=f"img:{obj.xref}"))
                cur_kind = "paragraph"
                prev = None
                continue
            if not isinstance(obj, Line):
                continue
            line = obj
            text = line.text
            # scene break
            if SCENE_BREAK_RE.match(text):
                flush()
                blocks.append(Block(kind="scene_break", text="* * *"))
                prev = line
                continue
            # heading?
            head_kind = _heading_kind(line, body_size, prev, page, em)
            if head_kind:
                flush()
                blocks.append(_make_block([line], head_kind, body_size))
                prev = line
                continue

            same_page = prev is not None and prev.page_no == line.page_no
            gap = (line.top - prev.bottom) if (prev is not None and same_page) else 0.0
            line_h = max(1.0, line.bottom - line.top)
            indent = line.x0 - left
            indented = indent > 0.75 * em  # 1em+ indents; OCR jitter stays under this
            big_gap = same_page and gap > 1.9 * line_h
            # a word split across the boundary can never start a new paragraph
            hyphenated = (
                prev is not None
                and prev.text.endswith(("-", "\u2010", "\u2011", "\u00ad"))
                and text[:1].islower()
            )
            breaks_para = (indented or big_gap) and not hyphenated

            if not cur:
                cur = [line]
                cur_kind = "paragraph"
            elif breaks_para:
                # paragraph break (indent) or block change (gap)
                flush()
                cur = [line]
                cur_kind = "paragraph"
            elif (
                prev is not None
                and _verse_line(line, left, col_width, em)
                and _verse_line(prev, left, col_width, em)
            ):
                if cur_kind != "verse":
                    flush()
                    cur_kind = "verse"
                cur.append(line)
            else:
                if cur_kind == "verse":
                    flush()
                    cur_kind = "paragraph"
                cur.append(line)
            prev = line
    flush()

    blocks = _join_paragraphs(blocks, body_size)
    blocks = _rejoin_dropcaps(blocks, body_size)
    return blocks


def _verse_line(line: Line, left: float, col_width: float, em: float) -> bool:
    return (line.x0 - left) > 1.6 * em and line.width < 0.72 * col_width


def _heading_kind(line: Line, body_size: float, prev: Line | None, page: Page, em: float) -> str | None:
    text = line.text.strip()
    if not text or len(text) > 90:
        return None
    same_page = prev is not None and prev.page_no == line.page_no
    gap_before = (line.top - prev.bottom) if (prev is not None and same_page) else 0.0
    isolated = gap_before > 1.4 * max(1.0, line.bottom - line.top)

    m = CHAPTER_RE.match(text)
    if m:
        has_numeral = bool(m.group(1) or m.group(2))
        if has_numeral:
            return "heading"
        # bare "CHAPTER"/"CHAP." heading (incl. OCR-noised numerals like
        # "CHAPTER XGIV."). Isolation can't gate these: at a page top the
        # cross-page gap reads 0. Style does the work instead — real openers
        # are centered or all-caps; body lines that start with "chapter" are
        # long sentences ("chapter it was, headed 'Smeer'…").
        if len(text.split()) <= 8:
            centered = line.x0 > 0.22 * page.width
            caps_line = text == text.upper()
            unpunctuated = not text.endswith((".", ",", ";", "!", "?"))
            if unpunctuated or caps_line or centered:
                return "heading"
        return None
    if FRONT_MATTER_RE.match(text):
        return "heading"
    # short isolated line, larger than body (digital) — chapter-ish title.
    # Isolation must hold ON the page: a line merely starting a new page is
    # not a heading (that mistake splits paragraphs at every page break).
    # Body fragments end in sentence punctuation; titles don't.
    bigger = line.max_size >= body_size * 1.08
    caps = text == text.upper() and re.search(r"[A-Z]", text)
    titleish = len(text.split()) <= 8 and len(text) <= 60
    unpunctuated = not text.endswith((".", ",", ";", ":", "!", "?"))
    if isolated and titleish and unpunctuated and (bigger or caps):
        return "heading"
    return None


def _make_block(lines: list[Line], kind: str, body_size: float) -> Block:
    if kind in ("verse", "letter"):
        joined = "\n".join(l.text.strip() for l in lines if l.text.strip())
    else:
        joined = _join_lines([l.text for l in lines])
    italics = sum(1 for l in lines if l.has_italic) / max(1, len(lines))
    size = max((l.max_size for l in lines), default=body_size)
    return Block(kind=kind, text=joined, lines=lines, size=size, italic_ratio=italics)


def _join_lines(parts: list[str]) -> str:
    """Join lines into flowing text: hyphen resolution + single spaces."""
    out = ""
    for raw in parts:
        t = raw.strip()
        if not t:
            continue
        if not out:
            out = t
            continue
        if out.endswith(("-", "\u2010", "\u2011", "\u00ad")):
            head = out[:-1]
            if t[:1].islower():
                out = head + t          # de-hyphenate: "Moby-\nDick" stays "Moby-Dick" case
            else:
                out = head + "-" + t    # keep genuine hyphen
        elif t[:1] in ".,;:!?%)]}'’”":
            out += t
        elif out.endswith(("(", "[", "{", "‘", "“", "/")):
            out += t
        else:
            out += " " + t
    return re.sub(r"\s+", " ", out).strip()


def _join_paragraphs(blocks: list[Block], body_size: float) -> list[Block]:
    return blocks  # assembly already joins; kept for pipeline clarity


def _rejoin_dropcaps(blocks: list[Block], body_size: float) -> list[Block]:
    """Rejoin decorated first letters (drop caps) into their word."""
    out: list[Block] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        nxt = blocks[i + 1] if i + 1 < len(blocks) else None
        if (
            b.kind == "paragraph"
            and nxt is not None
            and nxt.kind == "paragraph"
            and len(b.text) <= 2
            and DROP_CAP_RE.match(b.text.strip())
            and (b.size >= body_size * 1.15 or len(b.text) == 1)
        ):
            letter = b.text.strip()
            tail = nxt.text
            if tail[:1].islower() or tail[:1].isupper():
                nxt.text = letter + tail
                out.append(nxt)
                i += 2
                continue
        out.append(b)
        i += 1
    return out


# ---------------------------------------------------------------- chapters

def detect_chapters(blocks: list[Block]) -> list[Chapter]:
    """Group blocks into chapters around heading runs.

    Heading-run rules (verified against the Moby-Dick 1922 scan):
      run of 1-2 headings  → one chapter, titles joined with " — "
                             ("CHAPTER LXVI" + "THE SHARK MASSACRE")
      run of >=3 headings  → TOC page or title page, drop the whole run
                             (dotted-leader TOC lines drop separately)

    TOC region: after a "CONTENTS" heading, nothing opens a chapter until a
    real numeral'd chapter heading with body text behind it.
    """
    # pass 1: resolve heading runs
    resolved: list[Block] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b.kind != "heading":
            resolved.append(b)
            i += 1
            continue
        run = [b]
        j = i + 1
        while j < len(blocks) and blocks[j].kind == "heading":
            run.append(blocks[j])
            j += 1
        if len(run) >= 3:
            i = j  # TOC/title-page noise: drop the run
            continue
        title = " — ".join(r.text.strip() for r in run if r.text.strip())
        resolved.append(Block(kind="heading", text=title, size=run[0].size))
        i = j

    # pass 2: attach body to chapters, suppressing TOC regions.
    chapters: list[Chapter] = []
    cur: Chapter | None = None
    seen_first_heading = False
    in_toc = False
    for k, b in enumerate(resolved):
        if b.kind == "heading":
            if FRONT_TOC_RE.match(b.text):
                in_toc = True
                continue
            numeral = _numeral_heading(b.text)
            if in_toc and not (numeral and _has_body_ahead(resolved, k)):
                continue  # TOC entry or title page
            if TOC_LINE_RE.match(b.text):
                continue
            if not _has_body_ahead(resolved, k):
                continue  # TOC entry / title page / end stamp
            in_toc = False
            cur = Chapter(title=b.text.strip() or "Untitled")
            chapters.append(cur)
            seen_first_heading = True
            continue
        if cur is None:
            cur = Chapter(title="Front Matter")
            chapters.append(cur)
        if in_toc:
            continue  # TOC region body: entries and column headers
        if TOC_LINE_RE.match(b.text):
            continue
        cur.blocks.append(b)

    if not seen_first_heading and chapters:
        chapters[0].title = "Body"
    chapters = [c for c in chapters if c.blocks]
    return chapters or [Chapter(title="Body", blocks=[b for b in resolved if b.kind != "heading"])]


def _has_body_ahead(blocks: list[Block], k: int, look: int = 6) -> bool:
    """Does real body text follow this heading?

    Numeral'd chapter headings ("CHAPTER 42", "PART II") get the lenient test:
    any paragraph of substance at all, because chapters may open with short
    extracts. Generic caps/title lines get the strict test: substantial text,
    because TOC entries and title pages are followed by short lines only.
    """
    numeral_heading = _numeral_heading(blocks[k].text)
    paras = []
    for b in blocks[k + 1:]:
        if b.kind == "heading":
            break
        if b.kind == "paragraph":
            paras.append(len(b.text))
        if len(paras) >= look:
            break
    if numeral_heading:
        return any(n >= 30 for n in paras)
    return any(n >= 120 for n in paras) or sum(n >= 40 for n in paras) >= 2


def _numeral_heading(text: str) -> bool:
    m = CHAPTER_RE.match(text)
    return bool(m and (m.group(1) or m.group(2)))


def chapterize(blocks: list[Block]) -> list[Chapter]:
    return detect_chapters(blocks)
