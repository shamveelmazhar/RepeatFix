"""FAA Aviation Maintenance Technician Handbooks split into cited section chunks.

The three AMT Handbooks (General FAA-H-8083-30B, Airframe 31B, Powerplant 32B)
have no paragraph numbers like AC 43.13-1B, but their PDF bookmarks list every
heading with the page it is on, and every page prints a chapter-relative number
("13-14"). So a chunk here is the text under one bookmarked heading, cited by
handbook, chapter, heading and printed page, e.g.
    FAA-H-8083-31B, Chapter 13 (Aircraft Landing Gear Systems), "Bleeding Shock Struts", page 13-14

Chunks use the same `Chunk` record as the AC (see procedures.py), so one index
searches both. Build them once from the PDFs:
    python -m app.handbooks ../data/raw/handbooks/FAA-H-8083-30B.pdf ../data/raw/handbooks/FAA-H-8083-31B.pdf ...
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from app.procedures import _MARK, PROCEDURES_DIR, Chunk, _page_mark, _split, read_pdf_pages, write_chunks

HANDBOOK_URLS = {
    "FAA-H-8083-30B": "https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/amt_general_handbook",
    "FAA-H-8083-31B": "https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/amt_airframe_handbook",
    "FAA-H-8083-32B": "https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/amt_powerplant_handbook",
}
HANDBOOKS = {
    "FAA-H-8083-30B": "FAA-H-8083-30B AMT Handbook – General",
    "FAA-H-8083-31B": "FAA-H-8083-31B AMT Handbook – Airframe",
    "FAA-H-8083-32B": "FAA-H-8083-32B AMT Handbook – Powerplant",
}


@dataclass
class Heading:
    level: int  # bookmark depth; 0 when the PDF has a flat outline
    title: str
    page: int  # 0-based PDF page


def read_outline(pdf_path: str | Path) -> list[Heading]:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    out: list[Heading] = []

    def walk(items, depth=0):
        for item in items:
            if isinstance(item, list):
                walk(item, depth + 1)
            else:
                out.append(Heading(depth, _clean(item.title), reader.get_destination_page_number(item)))

    walk(reader.outline)
    return out


def handbook_id(pdf_path: str | Path, pages: list[str]) -> str:
    """'FAA-H-8083-31B', from the file name or else the cover pages."""
    for text in [Path(pdf_path).name, *pages[:4]]:
        m = re.search(r"8083-3([012])B", text) or re.search(r"\b3([012])B\b", text)
        if m:
            return f"FAA-H-8083-3{m.group(1)}B"
    raise ValueError(f"can't tell which AMT handbook {pdf_path} is")


# ---------------------------------------------------------------- page cleanup

_LABEL = re.compile(r"\d{1,2}-\d{1,3}")
_CAPTION = re.compile(r"^Figure\s+\d{1,2}-\d{1,3}[A-Z]?\.\s")
_CHAPTER = re.compile(r"Chapter\s+(\d{1,2})")


def _clean(s: str) -> str:
    s = s.replace(" ", " ").replace(" ", " ")
    return re.sub(r"\s+", " ", s).strip()


def _is_label(line: str) -> bool:
    """A short line that doesn't end a sentence: figure callouts, table cells, page furniture."""
    s = line.strip()
    return len(s) < 42 and not re.search(r"[.:;!?,)\]]$", s) and not re.match(r"^\d{1,2}\.\s", s)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower().replace("’", "'")).strip()


def clean_page(text: str, headings: set[str] = frozenset()) -> tuple[list[str], list[str]]:
    """Return (body lines, figure captions) for one page.

    Figure captions are pulled out of the running text (they sit in the middle of
    sentences in the text layer) and kept separately; runs of two or more short
    callout lines, the printed page number and the "Chapter N" tab are dropped.
    `headings` (normalised bookmark titles for this page) are never dropped, even
    when several short headings follow each other.
    """
    lines = [_clean(l) for l in text.splitlines()]
    lines = [l for l in lines if l and not _LABEL.fullmatch(l) and not _CHAPTER.fullmatch(l)]
    keep = set()
    for i, line in enumerate(lines):
        if _norm(line) in headings:
            keep.add(i)
        elif i + 1 < len(lines) and _norm(f"{line} {lines[i + 1]}") in headings:
            keep.update((i, i + 1))  # a heading wrapped onto two lines
    body: list[str] = []
    captions: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if i in keep:
            body.append(line)
            i += 1
            continue
        if _CAPTION.match(line):
            cap = [line]
            while not re.search(r"[.)]$", cap[-1]) and i + 1 < len(lines) and len(cap) < 5:
                i += 1
                cap.append(lines[i])
            captions.append(" ".join(cap))
            i += 1
            continue
        if _is_label(line):
            j = i
            while j < len(lines) and _is_label(lines[j]) and j not in keep:
                j += 1
            nxt = lines[j] if j < len(lines) else ""
            if j - i >= 2 or _CAPTION.match(nxt) or not line.strip(" 0123456789.-–")[:1].isalpha():
                i = j  # a callout block, or a lone callout right above a caption
                continue
        body.append(line)
        i += 1
    return body, captions


# ---------------------------------------------------------------- sections


def _title_regex(title: str) -> str:
    """A heading as a regex: any whitespace (incl. line wraps), curly/straight quotes, dashes."""
    words = re.split(r"\s+", title.strip())
    alt = {"'": "['’]", "’": "['’]", "-": "[-–—]?\\s*", "–": "[-–—]", "—": "[-–—]"}
    return r"\s+".join("".join(alt.get(ch, re.escape(ch)) for ch in w) for w in words)


def _title_pattern(title: str) -> re.Pattern:
    """Match a heading on a line (or lines) of its own in page text."""
    return re.compile(r"(?:^|\n)\s*" + _title_regex(title) + r"\s*(?=\n|$)")


def chunk_handbook(pages: list[str], outline: list[Heading], doc_id: str) -> list[Chunk]:
    """One chunk per bookmarked heading (long ones split into parts).

    Chapter N starts at the "Chapter N" bookmark; the next bookmark is the chapter
    title, and its text is the chapter introduction. Everything from the
    Glossary bookmark on is skipped.
    """
    chapters = [(int(m.group(1)), h.page) for h in outline if (m := _CHAPTER.fullmatch(h.title))]
    if not chapters:
        raise ValueError("no 'Chapter N' bookmarks")

    def page_label(page: int) -> str:
        ch = [(n, start) for n, start in chapters if start <= page]
        return f"{ch[-1][0]}-{page - ch[-1][1] + 1}" if ch else ""

    # Clean every page once; keep captions to append to the section that holds them.
    near: dict[int, set[str]] = {}
    for h in outline:
        for p in (h.page, h.page + 1):
            near.setdefault(p, set()).add(_norm(h.title))
    cleaned = [clean_page(p, near.get(i, set())) for i, p in enumerate(pages)]
    page_text = ["\n".join(body) for body, _ in cleaned]

    # Walk the outline into (chapter, chapter title, path of parent headings, heading, start page, offset).
    sections = []
    chapter, chapter_title, stack = "", "", []  # stack: [(level, title)]
    expect_title = False
    last_pos = (-1, 0)
    for h in outline:
        if h.title.lower() in ("glossary", "index"):
            break
        if m := _CHAPTER.fullmatch(h.title):
            chapter, chapter_title, stack = m.group(1), "", []
            expect_title = True
            continue
        if not chapter:
            continue  # front matter
        if expect_title:
            chapter_title, expect_title = h.title, False
            title = "Introduction"
        else:
            title = h.title
            while stack and stack[-1][0] >= h.level:
                stack.pop()
        parents = [t for _, t in stack]
        if title != "Introduction":  # a flat outline (30B) is all level 0, so it has no parents
            stack.append((h.level, title))
        pos = _locate(page_text, h.title, h.page, last_pos)
        last_pos = pos
        sections.append(
            {"chapter": chapter, "chapter_title": chapter_title, "parents": parents, "title": title, "pos": pos}
        )

    end = (next((h.page for h in outline if h.title.lower() == "glossary"), len(pages)), 0)
    spans = []
    for n, sec in enumerate(sections):
        stop = sections[n + 1]["pos"] if n + 1 < len(sections) else end
        if n + 1 < len(sections) and sections[n + 1]["chapter"] != sec["chapter"]:
            stop = (_chapter_start(chapters, sections[n + 1]["chapter"]), 0)
        spans.append(_slice(page_text, sec["pos"], stop))

    # Each page's figure captions go to the section with the most text on that page.
    owner: dict[int, tuple[int, int]] = {}
    for n, parts in enumerate(spans):
        for p, t in parts:
            size = len(t.strip())
            if size > owner.get(p, (-1, -1))[1]:
                owner[p] = (n, size)
    figures: dict[int, list[str]] = {}
    for p, (n, _) in owner.items():
        figures.setdefault(n, []).extend(cleaned[p][1])

    chunks: list[Chunk] = []
    counters: dict[str, int] = {}
    for n, (sec, parts) in enumerate(zip(sections, spans)):
        if not parts:
            continue
        pages_seen = [p for p, _ in parts]
        text = " ".join(t if i == 0 else f"{_page_mark(i)} {t}" for i, (_, t) in enumerate(parts))
        text = re.sub(r"(\w)- *\n(\w)", r"\1-\2", text)
        text = re.sub(r"\s+", " ", text).strip()
        heading = sec["chapter_title"] if sec["title"] == "Introduction" else sec["title"]
        text = re.sub(r"^" + _title_regex(heading) + r"\s*", "", text)
        if sec["title"] == "Introduction":
            text = re.sub(r"^Introduction\s+", "", text)
        figs = [re.sub(r"^Figure (\S+?)\.\s+", r"(Figure \1: ", f).rstrip(".") + ")" for f in figures.get(n, [])]
        text = " ".join([text, *figs]).strip()
        if len(_MARK.sub("", text).strip()) < 40:
            continue  # a heading with nothing under it before the next one
        counters[sec["chapter"]] = counters.get(sec["chapter"], 0) + 1
        key = f"{sec['chapter']}.{counters[sec['chapter']]}"
        page_idx = 0
        for i, part in enumerate(_split(text), start=1):
            # A part is cited at the page it starts on (same scheme as the AC chunks).
            page = pages_seen[page_idx]
            lead = re.match(r"\s*\x01(\d+)\x01", part)
            if lead:
                page = pages_seen[int(lead.group(1))]
            marks = _MARK.findall(part)
            if marks:
                page_idx = int(marks[-1])
            part = re.sub(r"\s+", " ", _MARK.sub(" ", part)).strip()
            chunks.append(
                Chunk(
                    id=f"{doc_id}-{key}" + (f"-{i}" if i > 1 else ""),
                    ac_number=doc_id,
                    doc=HANDBOOKS[doc_id],
                    chapter=sec["chapter"],
                    chapter_title=sec["chapter_title"],
                    section="",
                    section_title=" > ".join(sec["parents"]),
                    paragraph=key,
                    title=sec["title"],
                    part=i,
                    page=page + 1,
                    page_label=page_label(page),
                    text=part,
                    url=HANDBOOK_URLS[doc_id],
                )
            )
    return chunks


def _chapter_start(chapters: list[tuple[int, int]], chapter: str) -> int:
    return next(start for n, start in chapters if str(n) == chapter)


def _locate(page_text: list[str], title: str, page: int, last: tuple[int, int]) -> tuple[int, int]:
    """(page, char offset) of a heading: on its bookmarked page or the next, after the previous heading."""
    pat = _title_pattern(title)
    for p in (page, page + 1):
        if p >= len(page_text) or p < last[0]:
            continue
        from_ = last[1] if p == last[0] else 0
        m = pat.search(page_text[p], from_)
        if m:
            return (p, m.start())
    # Not found (e.g. the heading text is split by a figure): start at the bookmark.
    return (page, last[1]) if page == last[0] else (max(page, last[0]), 0)


def _slice(page_text: list[str], start: tuple[int, int], stop: tuple[int, int]) -> list[tuple[int, str]]:
    """Text between two (page, offset) positions, as [(page, text)]."""
    parts = []
    for p in range(start[0], min(stop[0], len(page_text) - 1) + 1):
        a = start[1] if p == start[0] else 0
        b = stop[1] if p == stop[0] else len(page_text[p])
        if b > a:
            parts.append((p, page_text[p][a:b]))
    return parts


def build(pdf_paths: list[str]) -> dict[str, list[Chunk]]:
    out = {}
    for path in pdf_paths:
        pages = read_pdf_pages(path)
        doc_id = handbook_id(path, pages)
        out[doc_id] = chunk_handbook(pages, read_outline(path), doc_id)
    return out


def _main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    for doc_id, chunks in build(argv).items():
        path = PROCEDURES_DIR / f"{doc_id.lower()}.jsonl"
        write_chunks(chunks, path)
        print(f"{doc_id}: {len(chunks)} chunks from {len({c.paragraph for c in chunks})} sections -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
