"""WRITING stage: assemble a clean, simple EPUB3.

Deliberately boring markup — stock e-reader software (Xteink/Kindle/Kobo
default readers) parses simple XHTML best: paragraphs, <br/> verse lines,
scene-break divs, images, and a real nav TOC. No fixed pages anywhere.
"""
from __future__ import annotations

import re
from html import escape

from ebooklib import epub

from .model import Block, Book, Chapter, ImageRef

CSS = """\
body { font-family: serif; line-height: 1.5; margin: 0 5%; text-align: left; }
p { margin: 0; text-indent: 1.3em; text-align: justify; }
h1, h2 { text-align: center; font-weight: bold; font-size: 1.25em; margin: 2em 0 1.2em; text-indent: 0; }
h2.cont { font-size: 1em; margin-top: 1em; }
p.first { text-indent: 0; }
p.verse { text-indent: 0; margin: 0.8em 0 0.8em 1.5em; }
p.letter { text-indent: 0; margin: 0.8em 1em; }
p.footnote { text-indent: 0; font-size: 0.85em; margin: 0.6em 0 0.6em 1.2em; }
p.caption { text-indent: 0; text-align: center; font-size: 0.9em; margin: 0.3em 0 1em; }
.scenebreak { text-align: center; text-indent: 0; margin: 1.2em 0; letter-spacing: 0.4em; }
.sc { font-variant: small-caps; }
img { max-width: 100%; height: auto; display: block; margin: 1em auto; }
"""


def build_epub(book: Book, out_path: str, cover: ImageRef | None = None) -> str:
    eb = epub.EpubBook()
    eb.set_identifier(f"reflow-{_slug(book.source_name or book.title)}")
    eb.set_title(book.title)
    eb.set_language(book.language or "en")
    if book.author:
        eb.add_author(book.author)
    eb.add_metadata("DC", "contributor", "reflow (pdf→epub)")
    eb.add_item(epub.EpubItem(
        uid="style", file_name="style/main.css", media_type="text/css", content=CSS
    ))

    items: list[epub.EpubHtml] = []
    img_ids: dict[str, str] = {}

    for idx, chapter in enumerate(book.chapters):
        file_name = f"ch{idx:04d}-{_slug(chapter.title)[:24] or 'body'}.xhtml"
        doc = epub.EpubHtml(title=chapter.title, file_name=file_name, lang=book.language or "en")
        body_parts: list[str] = [f"<h2>{escape(chapter.title)}</h2>" if chapter.title else ""]
        first_para = True
        for block in chapter.blocks:
            html_part, _ = _block_html(block, chapter, book, idx, img_ids)
            if block.kind == "paragraph" and first_para and html_part.startswith("<p>"):
                html_part = "<p class=\"first\">" + html_part[3:]
                first_para = False
            if block.kind == "heading":
                first_para = True
            body_parts.append(html_part)
        doc.content = "\n".join(p for p in body_parts if p)
        eb.add_item(doc)
        items.append(doc)

    if not items:
        raise ValueError("no chapters to write — empty book")

    flush_image_items(eb)

    eb.toc = tuple(items)
    eb.add_item(epub.EpubNcx())
    eb.add_item(epub.EpubNav())
    eb.spine = ["nav"] + items
    epub.write_epub(out_path, eb)
    return out_path


# ---------------------------------------------------------------- blocks

def _block_html(block: Block, chapter: Chapter, book: Book, ch_idx: int, img_ids: dict) -> tuple[str, dict]:
    if block.kind == "scene_break":
        return "<p class=\"scenebreak\">* * *</p>", {}
    if block.kind == "heading":
        return "", {}  # chapter title is already the <h2>
    if block.kind == "image":
        return _image_html(block, chapter, ch_idx, img_ids)
    if block.kind == "verse":
        inner = _render_runs(block.runs, block.text)
        inner = inner.replace("\n", "<br/>")
        return f"<p class=\"verse\">{inner}</p>", {}
    css = {"paragraph": "", "letter": "letter", "footnote": "footnote", "caption": "caption"}.get(block.kind, "")
    cls = f" class=\"{css}\"" if css else ""
    return f"<p{cls}>{_render_runs(block.runs, block.text)}</p>", {}


def _image_html(block: Block, chapter: Chapter, ch_idx: int, img_ids: dict) -> tuple[str, dict]:
    xref = block.text.split(":", 1)[1] if ":" in block.text else ""
    # find the actual image bytes via the chapter's page-level stash
    img = _IMAGE_STORE.get(xref)
    if img is None:
        return "", {}
    name = f"images/ch{ch_idx:04d}-{xref}.{img.ext}"
    media = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif",
             "webp": "image/webp"}.get(img.ext, "image/png")
    item = epub.EpubItem(uid=f"img{xref}", file_name=name, media_type=media, content=img.bytes_)
    _ITEMS_TO_ADD.append(item)
    return f"<img src=\"{name}\" alt=\"illustration\"/>", {}


_ITEMS_TO_ADD: list = []
_IMAGE_STORE: dict[str, ImageRef] = {}


def register_images(images: list[ImageRef]) -> None:
    for img in images:
        _IMAGE_STORE[str(img.xref)] = img


def flush_image_items(eb) -> None:
    for item in _ITEMS_TO_ADD:
        eb.add_item(item)
    _ITEMS_TO_ADD.clear()


def _render_runs(runs: list[tuple[str, bool]], fallback_text: str) -> str:
    """Escaped XHTML with <i> around italic runs; falls back to plain text."""
    if not runs:
        return escape(fallback_text)
    out: list[str] = []
    i = 0
    while i < len(runs):
        flag = runs[i][1]
        j = i
        buf = ""
        while j < len(runs) and runs[j][1] == flag:
            buf += runs[j][0]
            j += 1
        esc = escape(buf)
        out.append(f"<i>{esc}</i>" if flag else esc)
        i = j
    return "".join(out)


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "")).strip("-").lower()
    return s or "x"
