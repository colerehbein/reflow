"""READING stage: extract text lines and images from a PDF via pymupdf.

Digital pages come out as Lines (spans keep font flags → italics survive).
Pages with little or no text are flagged for the OCR stage.
"""
from __future__ import annotations

import pymupdf

from .model import ImageRef, Line, Page, Span

MIN_TEXT_CHARS = 20  # below this a page counts as scanned


def extract_pages(pdf_path: str, max_pages: int | None = None) -> list[Page]:
    doc = pymupdf.open(pdf_path)
    pages: list[Page] = []
    for pno in range(len(doc)):
        if max_pages is not None and pno >= max_pages:
            break
        page = doc[pno]
        pages.append(_extract_page(doc, page, pno))
    doc.close()
    return pages


def _extract_page(doc, page, pno: int) -> Page:
    out = Page(number=pno, width=page.rect.width, height=page.rect.height)
    d = page.get_text("dict")
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue  # image blocks are handled via get_images
        for ln in block.get("lines", []):
            spans = [
                Span(
                    text=s.get("text", ""),
                    size=round(float(s.get("size", 0.0)), 1),
                    font=s.get("font", ""),
                    flags=int(s.get("flags", 0)),
                )
                for s in ln.get("spans", [])
            ]
            spans = [s for s in spans if s.text]
            if not spans:
                continue
            x0, y0, x1, y1 = ln["bbox"]
            out.lines.append(
                Line(spans=spans, x0=x0, y0=y0, x1=x1, y1=y1, page_no=pno)
            )
    out.lines.sort(key=lambda l: (round(l.top, 1), l.x0))
    out.images = _extract_images(doc, page, pno)
    return out


def _extract_images(doc, page, pno: int) -> list[ImageRef]:
    refs: list[ImageRef] = []
    seen: set[int] = set()
    for img in page.get_images(full=True):
        xref = img[0]
        if xref in seen:
            continue
        seen.add(xref)
        try:
            info = doc.extract_image(xref)
        except Exception:
            continue
        if not info or not info.get("image"):
            continue
        rects = page.get_image_rects(xref)
        if not rects:
            continue
        r = max(rects, key=lambda q: q.width * q.height)
        refs.append(
            ImageRef(
                xref=xref,
                ext=info.get("ext", "png"),
                bytes_=info["image"],
                x0=r.x0,
                y0=r.y0,
                x1=r.x1,
                y1=r.y1,
                page_no=pno,
            )
        )
    return refs


def pages_needing_ocr(pages: list[Page]) -> list[int]:
    return [p.number for p in pages if p.text_chars < MIN_TEXT_CHARS]


def summarize_pages(pages: list[Page]) -> dict:
    ocr = pages_needing_ocr(pages)
    return {
        "page_count": len(pages),
        "ocr_page_count": len(ocr),
        "text_chars": sum(p.text_chars for p in pages),
        "images": sum(len(p.images) for p in pages),
    }
