"""OCR stage: run tesseract on scanned pages, producing the same Line model.

Renders at 300 dpi, gets word-level boxes from tesseract's TSV, groups words
into lines by (block, par, line) and converts pixels back to PDF points.

Threading, not processes: pytesseract shells out to the tesseract binary, so
real parallelism happens in those child processes and the GIL is not a limit.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pymupdf
import pytesseract
from PIL import Image

from .model import Line, Page, Span

DPI = 300
MIN_CONF = 35


def ocr_pages(pdf_path: str, page_numbers: list[int], dpi: int = DPI, workers: int = 4) -> dict[int, Page]:
    """OCR the given 0-based page numbers; returns {page_no: Page}."""
    if not page_numbers:
        return {}
    workers = max(1, min(workers, len(page_numbers)))
    if workers == 1:
        results = [_ocr_one(pdf_path, pno, dpi) for pno in page_numbers]
    else:
        args = [(pdf_path, pno, dpi) for pno in page_numbers]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_ocr_star, args))
    return {p.number: p for p in results}


def _ocr_star(args):
    return _ocr_one(*args)


def _ocr_one(pdf_path: str, pno: int, dpi: int) -> Page:
    doc = pymupdf.open(pdf_path)
    page = doc[pno]
    page_w, page_h = page.rect.width, page.rect.height
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    doc.close()
    scale = 72.0 / dpi  # px → PDF points

    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config="--psm 3")
    groups: dict[tuple, list[dict]] = {}
    for i in range(len(data["text"])):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < MIN_CONF:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        groups.setdefault(key, []).append(
            {
                "t": txt,
                "x0": data["left"][i] * scale,
                "y0": data["top"][i] * scale,
                "x1": (data["left"][i] + data["width"][i]) * scale,
                "y1": (data["top"][i] + data["height"][i]) * scale,
            }
        )

    lines: list[Line] = []
    for words in groups.values():
        words.sort(key=lambda w: w["x0"])
        text = _join_words([w["t"] for w in words])
        if not text:
            continue
        x0 = min(w["x0"] for w in words)
        y0 = min(w["y0"] for w in words)
        x1 = max(w["x1"] for w in words)
        y1 = max(w["y1"] for w in words)
        # OCR has no font metadata: synthesize a size from the glyph box height.
        size = round(max(1.0, (y1 - y0) * 0.72), 1)
        lines.append(
            Line(
                spans=[Span(text=text, size=size, font="ocr", flags=0)],
                x0=x0,
                y0=y0,
                x1=x1,
                y1=y1,
                page_no=pno,
            )
        )
    lines.sort(key=lambda l: (round(l.top, 1), l.x0))
    return Page(number=pno, width=page_w, height=page_h, lines=lines)


def _join_words(words: list[str]) -> str:
    out = ""
    for w in words:
        if not out:
            out = w
        elif w in ".,;:!?%)]}'’”":
            out += w
        elif out.endswith(("(", "[", "{", "‘", "“")):
            out += w
        else:
            out += " " + w
    return out
