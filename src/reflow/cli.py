"""CLI: reflow book.pdf [-o book.epub]"""
from __future__ import annotations

import argparse
import json
import sys

from .pipeline import convert


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="reflow",
        description="Convert a PDF (scanned or digital) into a clean, reflowable EPUB.",
    )
    ap.add_argument("pdf", help="input PDF")
    ap.add_argument("-o", "--out", help="output EPUB path (default: alongside the PDF)")
    ap.add_argument("--title", help="override book title")
    ap.add_argument("--author", help="override author")
    ap.add_argument("--lang", default="en", help="language code (default: en)")
    ap.add_argument("--dpi", type=int, default=300, help="OCR render dpi (default: 300)")
    ap.add_argument("--workers", type=int, default=4, help="parallel OCR workers")
    ap.add_argument("--max-pages", type=int, default=None, help="limit pages processed")
    ap.add_argument("--no-ocr", action="store_true", help="skip OCR for scanned pages")
    ap.add_argument("--force-ocr", action="store_true",
                    help="OCR every page, ignoring any embedded text layer")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    args = ap.parse_args(argv)

    try:
        report = convert(
            args.pdf,
            args.out,
            title=args.title,
            author=args.author,
            language=args.lang,
            dpi=args.dpi,
            workers=args.workers,
            max_pages=args.max_pages,
            do_ocr=not args.no_ocr,
            force_ocr=args.force_ocr,
        )
    except Exception as e:  # surfaced as a real failure, never swallowed
        print(f"reflow: FAILED: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"reflow: {report['status']} → {report['out']}")
        print(
            f"  pages={report['pageCount']} ocr={report['ocrPageCount']} "
            f"scanned={report['scanned']} words={report['wordCount']} "
            f"chapters={report['chapterCount']} furniture_dropped={report['furnitureDropped']}"
        )
        for t in report["chapters"]:
            print(f"    · {t}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
