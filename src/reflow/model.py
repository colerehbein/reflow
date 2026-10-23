"""reflow — PDF → clean reflowable EPUB.

Data model: spans → lines → pages → blocks → chapters → book.
Mirrors the observed pipeline contract: READING → OCR → LAYOUT → WRITING.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# pymupdf font flag bits
FLAG_SUPERSCRIPT = 1
FLAG_ITALIC = 2
FLAG_SERIF = 4
FLAG_MONO = 8
FLAG_BOLD = 16


@dataclass
class Span:
    text: str
    size: float
    font: str = ""
    flags: int = 0

    @property
    def italic(self) -> bool:
        return bool(self.flags & FLAG_ITALIC)

    @property
    def bold(self) -> bool:
        return bool(self.flags & FLAG_BOLD)

    @property
    def superscript(self) -> bool:
        return bool(self.flags & FLAG_SUPERSCRIPT)


@dataclass
class Line:
    spans: list[Span]
    x0: float
    y0: float
    x1: float
    y1: float
    page_no: int = -1
    kind: str = "body"  # body | head | foot | dropped

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans).strip()

    @property
    def top(self) -> float:
        return self.y0

    @property
    def bottom(self) -> float:
        return self.y1

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def max_size(self) -> float:
        return max((s.size for s in self.spans), default=0.0)

    @property
    def has_italic(self) -> bool:
        return any(s.italic for s in self.spans)


@dataclass
class ImageRef:
    """A raster image with its position on the page (PDF points)."""
    xref: int
    ext: str
    bytes_: bytes
    x0: float
    y0: float
    x1: float
    y1: float
    page_no: int

    @property
    def area(self) -> float:
        return max(0.0, self.x1 - self.x0) * max(0.0, self.y1 - self.y0)


@dataclass
class Page:
    number: int  # 0-based
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)

    @property
    def text_chars(self) -> int:
        return sum(len(l.text) for l in self.lines)


@dataclass
class Block:
    kind: str  # paragraph | verse | letter | scene_break | heading | image | footnote | caption
    text: str = ""
    lines: list[Line] = field(default_factory=list)
    size: float = 0.0
    italic_ratio: float = 0.0
    smallcaps: bool = False
    # inline runs (text, italic): single source for markup; text == "".join(runs)
    runs: list[tuple[str, bool]] = field(default_factory=list)


@dataclass
class Chapter:
    title: str
    blocks: list[Block] = field(default_factory=list)
    images: list[ImageRef] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return sum(len(b.text) for b in self.blocks)


@dataclass
class Book:
    title: str
    author: str = ""
    language: str = "en"
    chapters: list[Chapter] = field(default_factory=list)
    source_name: str = ""
    scanned: bool = False
    page_count: int = 0
    ocr_page_count: int = 0

    @property
    def is_scanned(self) -> bool:
        """Scan heuristic mirrors rifflepages' client model."""
        return self.ocr_page_count > 0 and self.ocr_page_count >= self.page_count / 2

    @property
    def word_count(self) -> int:
        return sum(len(b.text.split()) for c in self.chapters for b in c.blocks)
