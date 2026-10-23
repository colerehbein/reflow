"""Pipeline: READING → OCR → LAYOUT → WRITING, plus a conversion report."""
from __future__ import annotations

import os

import pymupdf

from .layout import assemble, chapterize, strip_furniture
from .model import Book
from .ocr import ocr_pages
from .read import extract_pages, pages_needing_ocr, summarize_pages
from .write import build_epub, register_images


def convert(
    pdf_path: str,
    out_path: str | None = None,
    *,
    title: str | None = None,
    author: str | None = None,
    language: str = "en",
    dpi: int = 300,
    workers: int = 4,
    max_pages: int | None = None,
    do_ocr: bool = True,
    force_ocr: bool = False,
) -> dict:
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)
    out_path = out_path or os.path.splitext(pdf_path)[0] + ".epub"

    meta_title, meta_author = _pdf_metadata(pdf_path)

    # READING
    pages = extract_pages(pdf_path, max_pages=max_pages)
    stats = summarize_pages(pages)

    # OCR
    ocr_count = 0
    if do_ocr:
        need = pages_needing_ocr(pages) if not force_ocr else [p.number for p in pages]
        if need:
            ocr_result = ocr_pages(pdf_path, need, dpi=dpi, workers=workers)
            for pno, page in ocr_result.items():
                pages[pno] = page
            ocr_count = len(need)

    # LAYOUT
    dropped = strip_furniture(pages)
    blocks = assemble(pages)
    chapters = chapterize(blocks)

    # WRITING
    register_images([img for p in pages for img in p.images])
    book = Book(
        title=title or meta_title or os.path.splitext(os.path.basename(pdf_path))[0],
        author=author or meta_author,
        language=language,
        chapters=chapters,
        source_name=os.path.basename(pdf_path),
        page_count=len(pages),
        ocr_page_count=ocr_count,
    )
    build_epub(book, out_path)

    return {
        "status": "READY",
        "stage": "DONE",
        "out": out_path,
        "title": book.title,
        "author": book.author,
        "pageCount": book.page_count,
        "ocrPageCount": book.ocr_page_count,
        "scanned": book.is_scanned,
        "wordCount": book.word_count,
        "chapterCount": len(book.chapters),
        "chapters": [c.title for c in book.chapters],
        "furnitureDropped": dropped,
        "images": stats["images"],
    }


def _pdf_metadata(pdf_path: str) -> tuple[str, str]:
    try:
        doc = pymupdf.open(pdf_path)
        md = doc.metadata or {}
        doc.close()
        return (md.get("title") or "").strip(), (md.get("author") or "").strip()
    except Exception:
        return "", ""
