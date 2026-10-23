"""Self-contained tests for reflow. Run: .venv/bin/python tests/run_tests.py

Builds a synthetic PDF with known defects (running heads, page numbers,
drop caps, hyphenated line breaks, chapters, verse, scene breaks) and
asserts the pipeline fixes each one.
"""
from __future__ import annotations

import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pymupdf  # noqa: E402

from reflow.layout import assemble, chapterize, strip_furniture, _join_lines, _rejoin_dropcaps  # noqa: E402
from reflow.model import Block, Book, Chapter, FLAG_ITALIC, Line, Page, Span  # noqa: E402
from reflow.pipeline import convert  # noqa: E402
from reflow.write import build_epub  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "..", "fixtures")
os.makedirs(FIX, exist_ok=True)

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f"FAIL  {name}  {detail}")


def line(text: str, top: float, x0: float = 72.0, size: float = 10.0, page: int = 0,
         width: float = 300.0, flags: int = 0) -> Line:
    return Line(spans=[Span(text=text, size=size, flags=flags)],
                x0=x0, y0=top, x1=x0 + width, y1=top + size * 1.2, page_no=page)


# ------------------------------------------------------------------ unit level
def test_line_join():
    print("— line joining / hyphens")
    check("dehyphenate lowercase", _join_lines(["Call me Ish-", "mael."]) == "Call me Ishmael.",
          _join_lines(["Call me Ish-", "mael."]))
    check("keep real hyphen before capital", _join_lines(["Moby-", "Dick"]) == "Moby-Dick",
          _join_lines(["Moby-", "Dick"]))
    check("punct attaches", _join_lines(["word", ", more."]) == "word, more.")
    check("plain join", _join_lines(["Call me", "Ishmael."]) == "Call me Ishmael.")


def test_dropcaps():
    print("— drop caps")
    blocks = [
        Block(kind="paragraph", text="M", size=22.0),
        Block(kind="paragraph", text="oby-Dick is a whale of a tale."),
    ]
    out = _rejoin_dropcaps(blocks, 10.0)
    check("big-letter drop cap rejoined", len(out) == 1 and out[0].text.startswith("Moby-Dick"),
          out[0].text if out else "none")
    blocks2 = [
        Block(kind="paragraph", text="C", size=10.0),
        Block(kind="paragraph", text="all me Ishmael."),
    ]
    out2 = _rejoin_dropcaps(blocks2, 10.0)
    check("single-letter OCR drop cap rejoined",
          bool(out2 and out2[0].text == "Call me Ishmael."),
          out2[0].text if out2 else "none")


def test_furniture():
    print("— running heads / page numbers")
    pages = []
    for p in range(60):
        pg = Page(number=p, width=500, height=800)
        pg.lines = [
            line("MOBY-DICK", 30, x0=200, page=p),
            line(f"{p + 1}", 760, x0=250, page=p),
            line(f"Chapter text line one of page {p} continues the story forward.", 300, page=p),
            line(f"Chapter text line two of page {p} continues further along.", 315, page=p),
        ]
        pages.append(pg)
    dropped = strip_furniture(pages)
    kinds = [l.kind for pg in pages for l in pg.lines if l.text == "MOBY-DICK"]
    check("repeated running head dropped", all(k == "dropped" for k in kinds), str(kinds[:3]))
    nums = [l.kind for pg in pages for l in pg.lines if re.fullmatch(r"\d+", l.text)]
    check("page numbers dropped", all(k == "dropped" for k in nums), str(nums[:3]))
    check("body kept", dropped >= 120, f"dropped={dropped}")


def test_assembly():
    print("— paragraph assembly across pages")
    pages = []
    p1 = Page(number=0, width=500, height=800)
    p1.lines = [
        line("MOBY-DICK", 30, x0=200, page=0),
        line("Call me Ishmael. Some years ago, never mind how long", 300, page=0),
        line("precisely, having little or no money in my purse,", 315, page=0),
    ]
    p2 = Page(number=1, width=500, height=800)
    p2.lines = [
        line("MOBY-DICK", 30, x0=200, page=1),
        line("and nothing particular to interest me on shore,", 300, page=1),
        line("   I thought I would sail about a little.", 315, x0=82.0, page=1),
    ]
    pages = [p1, p2]
    strip_furniture(pages)
    blocks = assemble(pages)
    paras = [b for b in blocks if b.kind == "paragraph"]
    check("cross-page unindented join", any(
        "purse, and nothing particular" in b.text for b in paras),
        " || ".join(b.text[:60] for b in paras))
    check("indent starts new paragraph", any(
        b.text.startswith("I thought I would sail") for b in paras),
        " || ".join(b.text[:60] for b in paras))


def test_chapters():
    print("— chapter detection")
    blocks = [
        Block(kind="heading", text="CHAPTER 1. Loomings."),
        Block(kind="paragraph", text="Call me Ishmael. Some years ago, never mind how long "
                                     "precisely, having little or no money in my purse."),
        Block(kind="heading", text="CHAPTER 2. The Carpet-Bag."),
        Block(kind="paragraph", text="I stuffed a shirt or two into my carpet-bag, tucked it "
                                     "under my arm, and started for Cape Horn and the Pacific."),
    ]
    chs = chapterize(blocks)
    check("two chapters detected", len(chs) == 2, f"got {len(chs)}")
    check("chapter titles kept", chs[0].title.startswith("CHAPTER 1") and chs[1].title.startswith("CHAPTER 2"),
          str([c.title for c in chs]))


# ------------------------------------------------------------------ PDF level
def make_fixture_pdf(path: str) -> str:
    """A coherent 4-page book: title-free, two chapters in order, known defects.

    Defects planted: running head every page, page numbers, a drop cap, a
    line-end hyphen, a scene break, and a paragraph crossing a page break.
    """
    doc = pymupdf.open()
    for pno in range(4):
        page = doc.new_page(width=400, height=600)
        page.insert_text((150, 40), "TESTBOOK", fontsize=9)          # running head
        page.insert_text((190, 580), str(pno + 1), fontsize=9)       # page number
        if pno == 0:
            page.insert_text((72, 110), "CHAPTER 1. Loomings.", fontsize=12)
            page.insert_text((72, 136), "C", fontsize=22)            # drop cap (top clearly above the body line)
            page.insert_text((84, 130), "all me Ishmael. Some years ago, never mind how long pre-", fontsize=10)
            for i, t in enumerate([
                "cisely, having little or no money in my purse, and nothing",
                "particular to interest me on shore, I thought I would sail",
                "about a little and see the watery part of the world.",
            ]):
                page.insert_text((72, 156 + i * 16), t, fontsize=10)
        elif pno == 1:
            page.insert_text((72, 100), "It is a way I have of driving off the spleen,", fontsize=10)
            page.insert_text((72, 116), "and regulating the circulation.", fontsize=10)
            page.insert_text((180, 150), "* * *", fontsize=10)       # scene break
            page.insert_text((72, 190), "CHAPTER 2. The Carpet-Bag.", fontsize=12)
            page.insert_text((72, 222), "I stuffed a shirt or two into my carpet-bag, tucked it under", fontsize=10)
            page.insert_text((72, 238), "my arm, and started for Cape Horn and the Pacific.", fontsize=10)
        elif pno == 2:
            page.insert_text((72, 100), "Continued text flows across the page break without a new", fontsize=10)
            page.insert_text((72, 116), "indent, and so must join the paragraph on the page before.", fontsize=10)
        else:
            page.insert_text((72, 100), "And so this small book ends where it began.", fontsize=10)
    doc.save(path)
    doc.close()
    return path


def test_pdf_roundtrip():
    print("— PDF round trip (digital)")
    pdf = make_fixture_pdf(os.path.join(FIX, "synthetic.pdf"))
    out = os.path.join(FIX, "synthetic.epub")
    rep = convert(pdf, out, title="Testbook", author="Tester")
    check("epub written", os.path.exists(out))
    check("report READY", rep["status"] == "READY", str(rep))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        check("nav toc present", any("nav" in n for n in names), str(names[:8]))
        all_text = ""
        for n in names:
            if n.endswith((".xhtml", ".html")):
                all_text += z.read(n).decode("utf-8", "replace")
    check("drop cap rejoined in epub", "Call me Ishmael" in all_text, all_text[:400])
    check("running head stripped", "TESTBOOK" not in all_text)
    check("page numbers stripped", not re.search(r"<p[^>]*>\s*[1-4]\s*</p>", all_text))
    check("dehyphenated across lines", "precisely" in all_text and "pre- cisely" not in all_text)
    check("scene break kept", "scenebreak" in all_text)
    check("chapters in order", rep["chapters"] == ["CHAPTER 1. Loomings.", "CHAPTER 2. The Carpet-Bag."],
          str(rep["chapters"]))
    check("cross-page paragraph joined",
          "page break without a new indent, and so must join" in all_text.replace("\n", " "),
          "cross-page join missing")


def test_italics():
    print("— inline italics survive to markup")
    l1 = Line(spans=[Span(text="Call me ", size=10), Span(text="Ishmael", size=10, flags=FLAG_ITALIC),
                     Span(text=".", size=10)], x0=0, y0=0, x1=100, y1=12)
    l2 = Line(spans=[Span(text="Some years ago.", size=10)], x0=0, y0=12, x1=100, y1=24)
    blk = Block(kind="paragraph", text="", lines=[l1, l2], size=10.0)
    from reflow.layout import _make_block
    blk = _make_block([l1, l2], "paragraph", 10.0)
    book = Book(title="T", chapters=[Chapter(title="C", blocks=[blk])])
    out = os.path.join(FIX, "italics_test.epub")
    build_epub(book, out)
    with zipfile.ZipFile(out) as z:
        xhtml = "".join(z.read(n).decode("utf-8") for n in z.namelist() if n.endswith(".xhtml"))
    check("italic run renders <i>", "<i>Ishmael</i>" in xhtml, xhtml[xhtml.find("<p"):xhtml.find("<p") + 200])
    check("roman stays outside <i>", "Call me <i>Ishmael</i>." in xhtml)
    check("block text coherent", blk.text == "Call me Ishmael. Some years ago.", blk.text)


if __name__ == "__main__":
    test_line_join()
    test_dropcaps()
    test_furniture()
    test_assembly()
    test_chapters()
    test_italics()
    test_pdf_roundtrip()
    print(f"\n{PASS} passed, {FAIL} failed")
    raise SystemExit(1 if FAIL else 0)
