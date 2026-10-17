"""Cited procedures: FAA AC 43.13-1B and AMT Handbook chunks, and a lexical search index.

The AC PDF is split by paragraph ("9-14. TIRE INSPECTION AND REPAIR.") so every
chunk carries the AC number, chapter, section, paragraph number and the page it
starts on. Search is BM25 over those chunks; it runs on the CPU in milliseconds
and needs no model, so it works even when the model service is down. Token Factory
has no embedding model, so this search stays on the CPU.

The FAA AMT Handbooks (General, Airframe, Powerplant) are chunked by heading in
handbooks.py into the same `Chunk` record; for them `ac_number` holds the
handbook number ("FAA-H-8083-31B") and `paragraph` a section key ("13.14").
`ProcedureIndex.load()` searches every chunk file in data/procedures/.

Build the chunk file once from the PDF:
    python -m app.procedures build ../data/raw/ac/AC_43.13-1B_CHG_1_Ed_Upd_FAA.pdf
Then search it:
    python -m app.procedures search "brake dragging, temp high after taxi"
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROCEDURES_DIR = REPO_ROOT / "data" / "procedures"
DEFAULT_CHUNKS = PROCEDURES_DIR / "ac_43-13-1b.jsonl"


def chunk_files() -> list[Path]:
    """Every committed chunk file: the AC and the AMT Handbooks."""
    return sorted(PROCEDURES_DIR.glob("*.jsonl"))

# AC 43.13-1B CHG 1 (editorial update, May 2024) on the FAA site.
AC_43_13_1B = {
    "ac_number": "AC 43.13-1B",
    "doc": "FAA AC 43.13-1B CHG 1",
    "title": "Acceptable Methods, Techniques, and Practices: Aircraft Inspection and Repair",
    "url": "https://www.faa.gov/regulations_policies/advisory_circulars/index.cfm/go/document.information/documentID/99861",
}

MAX_CHUNK_CHARS = 2000
SNIPPET_CHARS = 280


@dataclass
class Chunk:
    id: str
    ac_number: str  # document number: "AC 43.13-1B", or a handbook's "FAA-H-8083-31B"
    doc: str
    chapter: str  # "9"
    chapter_title: str  # "Aircraft Systems and Components"
    section: str  # "1" (sections restart in each chapter); "" for handbooks
    section_title: str  # handbooks: the parent headings, "Landing Gear Types > Shock Struts"
    paragraph: str  # "9-14"; handbooks: a section key, "13.14" (not printed in the book)
    title: str  # "Tire Inspection and Repair"; handbooks: the heading
    part: int  # 1.. when a long paragraph is split
    page: int  # 1-based page in the PDF (for links)
    page_label: str  # printed page, e.g. "9-12"
    text: str
    url: str | None = None


# ---------------------------------------------------------------- PDF parsing

_HEADER = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\s+AC\s*43\.13-1B(\s+CHG\s*\d+)?\s*$")
_FOOTER = re.compile(r"^\s*(Pars?\s+[\dA-Z\-–,and ]+?\s+)?Page\s+([\dA-Z]+-[\dA-Z]+)\s*(Pars?\s+[\dA-Z\-–,and ]+)?\s*$")
_CHAPTER = re.compile(r"^\s*CHAPTER\s+(\d{1,2})\.\s+(.+?)\s*$")
_SECTION = re.compile(r"^\s*SECTION\s+(\d{1,2})\.\s+(.+?)\s*$")
# "9-14. TIRE INSPECTION AND REPAIR. Tires should be ..." -> ("9", "14", "TIRE INSPECTION AND REPAIR")
# Titles are upper case, may hold a mixed-case aside in brackets ("(Natural Fabrics)"), and
# usually end with a period; a few run straight into the sentence ("DISASSEMBLE THE WHEEL in ...").
_CAPS_WORD = r"(?:[A-Z0-9][A-Z0-9,:/&'’\"“”\-–—]*|\([^)a-z]{1,40}\)|\([A-Z][^)]{1,40}\))"
_PARA = re.compile(rf"^\s*(\d{{1,2}})-(\d{{1,3}})\.\s+({_CAPS_WORD}(?:\s+{_CAPS_WORD})*?)(?:\.\s|\.$|\s+(?=\(?[a-z])|$)")
_RESERVED = re.compile(r"^\s*\d{1,2}-\d{1,3}\.\s*[–\-]\s*\d{1,2}-\d{1,3}\.\s*\[RESERVED\.?\]", re.I)
_LEADER = re.compile(r"\.{5,}")  # table-of-contents dot leaders

_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with"}


def _title_case(s: str) -> str:
    words = re.sub(r"\s+", " ", s.strip().rstrip(".")).lower().split(" ")
    out = []
    for i, w in enumerate(words):
        if w.strip("()").upper() in {"NDI", "AC", "FAA", "CFR", "ICA", "TSO", "ELT", "VOR", "ILS", "DME", "ADF"}:
            out.append(w.upper())
        elif i and w in _SMALL_WORDS:
            out.append(w)
        elif w.startswith("(") and len(w.strip("()")) <= 5:
            out.append(w.upper())  # (NDI), (X-RAY)
        else:
            i0 = next((j for j, ch in enumerate(w) if ch.isalpha()), 0)
            out.append(w[:i0] + w[i0:i0 + 1].upper() + w[i0 + 1:])
    return " ".join(out)


def read_pdf_pages(pdf_path: str | Path) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return [page.extract_text() or "" for page in reader.pages]


def chunk_pages(pages: list[str], meta: dict = AC_43_13_1B) -> list[Chunk]:
    """Split page texts into one chunk per AC paragraph (long ones into parts).

    Front matter (cover, table of contents) is skipped: parsing starts at the
    first page with a chapter-style "Page N-M" footer.
    """
    chapter = chapter_title = section = section_title = ""
    current: dict | None = None
    paras: list[dict] = []
    last_key = (0, 0)
    started = False
    heading = ""  # set right after a CHAPTER/SECTION line, to catch a wrapped title

    for page_no, raw in enumerate(pages, start=1):
        lines = _merge_split_lines(raw.splitlines())
        page_label = ""
        for line in lines:
            m = _FOOTER.match(line)
            if m:
                page_label = m.group(2)
        if not started:
            if not page_label:  # cover and contents use roman page numbers
                continue
            started = True
        elif not page_label and re.search(r"Appendix\s+\d|Feedback Form", raw):
            break  # the glossary appendix and feedback form follow the last chapter

        for line in lines:
            if _HEADER.match(line) or _FOOTER.match(line) or _LEADER.search(line):
                continue
            if m := _CHAPTER.match(line):
                chapter, chapter_title = m.group(1), _title_case(m.group(2))
                section = section_title = ""
                heading = "chapter"
                continue
            if m := _SECTION.match(line):
                section, section_title = m.group(1), _title_case(m.group(2))
                heading = "section"
                continue
            if heading and _is_caps_line(line):  # a chapter/section title wrapped onto a second line
                if heading == "chapter":
                    chapter_title = _title_case(f"{chapter_title} {line}")
                else:
                    section_title = _title_case(f"{section_title} {line}")
                continue
            heading = ""
            if _RESERVED.match(line):
                continue
            m = _PARA.match(line)
            if m:
                key = (int(m.group(1)), int(m.group(2)))
                # Paragraph numbers only move forward, within the current chapter
                # or into the next one; anything else is a cross-reference.
                same_ch = key[0] == last_key[0] and key[1] > last_key[1]
                next_ch = key[0] == last_key[0] + 1
                if same_ch or next_ch or last_key == (0, 0):
                    last_key = key
                    if key[0] != int(chapter or 0):
                        chapter, chapter_title, section, section_title = str(key[0]), "", "", ""
                    current = {
                        "chapter": chapter,
                        "chapter_title": chapter_title,
                        "section": section,
                        "section_title": section_title,
                        "paragraph": f"{key[0]}-{key[1]}",
                        "title": _title_case(m.group(3)),
                        "page": page_no,
                        "page_label": page_label,
                        "lines": [line.strip()],
                        "pages": [(page_no, page_label)],
                    }
                    paras.append(current)
                    continue
            if current is not None and line.strip():
                if current["pages"][-1][0] != page_no:
                    current["pages"].append((page_no, page_label))
                    current["lines"].append(_page_mark(len(current["pages"]) - 1))
                current["lines"].append(line.strip())

    chunks: list[Chunk] = []
    for p in paras:
        pages_seen = p.pop("pages")
        text = _join_lines(p.pop("lines"))
        page_idx = 0
        for i, part in enumerate(_split(text), start=1):
            # A part is cited at the page it starts on, so take the last page mark before it.
            p["page"], p["page_label"] = pages_seen[page_idx]
            marks = _MARK.findall(part)
            lead = re.match(r"\s*\x01(\d+)\x01", part)
            if lead:
                p["page"], p["page_label"] = pages_seen[int(lead.group(1))]
            if marks:
                page_idx = int(marks[-1])
            part = _MARK.sub(" ", part)
            part = re.sub(r"\s+", " ", part).strip()
            chunks.append(
                Chunk(
                    id=f"{meta['ac_number'].replace(' ', '')}-{p['paragraph']}" + (f"-{i}" if i > 1 else ""),
                    ac_number=meta["ac_number"],
                    doc=meta["doc"],
                    part=i,
                    text=part,
                    url=meta.get("url"),
                    **p,
                )
            )
    return chunks


_MARK = re.compile(r"\x01(\d+)\x01")


def _page_mark(i: int) -> str:
    """Placeholder for a page turn inside a paragraph's text; removed after splitting."""
    return f"\x01{i}\x01"


def _merge_split_lines(lines: list[str]) -> list[str]:
    """Re-join paragraph numbers that the PDF text layer broke across lines ("1-" / "3. TITLE", "6-12." / "TITLE")."""
    out: list[str] = []
    for line in lines:
        if out and (re.fullmatch(r"\s*\d{1,2}-\s*", out[-1]) or re.fullmatch(r"\s*\d{1,2}-\d{1,3}\.\s*", out[-1])):
            sep = "" if out[-1].rstrip().endswith("-") else " "
            out[-1] = out[-1].strip() + sep + line.strip()
        else:
            out.append(line)
    return out


def _is_caps_line(line: str) -> bool:
    s = line.strip()
    return bool(s) and s.upper() == s and any(ch.isalpha() for ch in s) and not _PARA.match(s) and len(s) < 80


def _join_lines(lines: list[str]) -> str:
    text = " ".join(lines)
    text = re.sub(r"([A-Za-z0-9])- ([A-Za-z0-9])", r"\1-\2", text)  # keep "9-14", "MS-20" intact
    return re.sub(r"\s+", " ", text).strip()


def _split(text: str, limit: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split long paragraphs at sub-paragraph markers ("b. ", "(3) ") or sentences."""
    if len(text) <= limit:
        return [text]
    pieces = re.split(r"(?<=[.:;])\s+(?=(?:[a-z]|\(\d{1,2}\))\.?\s+[A-Z])", text)
    if len(pieces) == 1:
        pieces = re.split(r"(?<=\.)\s+", text)
    parts, buf = [], ""
    for piece in pieces:
        if buf and len(buf) + 1 + len(piece) > limit:
            parts.append(buf)
            buf = piece
        else:
            buf = f"{buf} {piece}".strip()
    if buf:
        parts.append(buf)
    # A single sentence longer than the limit stays whole rather than being cut mid-word.
    return parts


def write_chunks(chunks: list[Chunk], path: str | Path = DEFAULT_CHUNKS) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")


def load_chunks(path: str | Path = DEFAULT_CHUNKS) -> list[Chunk]:
    with Path(path).open(encoding="utf-8") as f:
        return [Chunk(**json.loads(line)) for line in f if line.strip()]


def is_handbook(c: Chunk) -> bool:
    return c.ac_number.startswith("FAA-H-")


# ---------------------------------------------------------------- search

# Shop-floor shorthand seen in ASRS/SDR narratives, expanded so it matches AC wording.
ABBREVIATIONS = {
    "brk": "brake", "brks": "brake", "hyd": "hydraulic", "lg": "landing gear", "mlg": "main landing gear",
    "nlg": "nose landing gear", "eng": "engine", "fwd": "forward", "lh": "left", "rh": "right",
    "insp": "inspection", "inspd": "inspection", "repl": "replace", "rplcd": "replace", "r/r": "replace",
    "chk": "check", "ck": "check", "ops": "operational", "press": "pressure", "temp": "temperature",
    "corr": "corrosion", "elec": "electrical", "wx": "weather", "ctrl": "control", "cbl": "cable",
    "assy": "assembly", "ftg": "fitting", "lkg": "leaking", "lk": "leak", "torq": "torque", "pwr": "power",
    "batt": "battery", "fuel": "fuel", "oxy": "oxygen", "acft": "aircraft", "a/c": "aircraft",
}

_STOP = set(
    "a an and are as at be been by can could do does for from had has have if in into is it its may might "
    "must no not of on or other shall should so such than that the their them then there these they this "
    "to used using was were when where which while will with would be after before during found noted per "
    "also any all each again".split()
)
_TOKEN = re.compile(r"[a-z0-9]+(?:[/\-][a-z0-9]+)*")


def _stem(w: str) -> str:
    for suf, min_len in (("ings", 6), ("ing", 5), ("ies", 5), ("ed", 4), ("es", 4), ("s", 3)):
        if w.endswith(suf) and len(w) >= min_len + len(suf) - 2:
            w = w[: -len(suf)] + ("y" if suf == "ies" else "")
            if suf in ("ings", "ing", "ed") and len(w) > 3 and w[-1] == w[-2] and w[-1] not in "ls":
                w = w[:-1]  # dragging -> drag, chafed -> chaf
            break
    return w


def tokenize(text: str) -> list[str]:
    out: list[str] = []
    for tok in _TOKEN.findall(text.lower()):
        expanded = ABBREVIATIONS.get(tok)
        words = expanded.split() if expanded else re.split(r"[/\-]", tok) if not tok[0].isdigit() else [tok]
        for w in words:
            if w and w not in _STOP and len(w) > 1:
                out.append(_stem(w))
    return out


@dataclass
class Hit:
    chunk: Chunk
    score: float


class ProcedureIndex:
    """BM25 over AC chunks. Titles and section names are weighted in."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.4, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.docs: list[Counter] = []
        for c in chunks:
            heading = f"{c.title} {c.title} {c.section_title} {c.chapter_title}"
            self.docs.append(Counter(tokenize(f"{heading} {c.text}")))
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = sum(self.lengths) / max(len(self.lengths), 1)
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    @classmethod
    def load(cls, paths: str | Path | list[str | Path] | None = None) -> "ProcedureIndex":
        """Load one chunk file, a list of them, or (by default) all of data/procedures/."""
        if paths is None:
            paths = chunk_files()
        elif isinstance(paths, (str, Path)):
            paths = [paths]
        return cls([c for p in paths for c in load_chunks(p)])

    def search(self, query: str, k: int = 3, docs: set[str] | None = None) -> list[Hit]:
        """Top k chunks, one per paragraph/section. `docs` limits it to document numbers,
        e.g. {"AC 43.13-1B"} or {"FAA-H-8083-31B", "FAA-H-8083-32B"}."""
        q = Counter(tokenize(query))
        scored = []
        for i, d in enumerate(self.docs):
            if docs and self.chunks[i].ac_number not in docs:
                continue
            s = 0.0
            norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg_len)
            for t, qf in q.items():
                f = d.get(t)
                if f:
                    s += qf * self.idf[t] * f * (self.k1 + 1) / (f + norm)
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        hits, seen = [], set()
        for s, i in scored:
            c = self.chunks[i]
            if (c.ac_number, c.paragraph) in seen:  # one hit per paragraph, best part wins
                continue
            seen.add((c.ac_number, c.paragraph))
            hits.append(Hit(c, round(s, 3)))
            if len(hits) == k:
                break
        return hits


# ---------------------------------------------------------------- citations


def citation(c: Chunk) -> str:
    """'AC 43.13-1B, Chapter 9, Section 1, par. 9-14 (Tire Inspection and Repair), page 9-12', or
    'FAA-H-8083-31B, Chapter 13 (Aircraft Landing Gear Systems), "Bleeding Shock Struts", page 13-14'"""
    if is_handbook(c):
        return f'{c.ac_number}, Chapter {c.chapter} ({c.chapter_title}), "{c.title}", page {c.page_label}'
    parts = [c.ac_number, f"Chapter {c.chapter}"]
    if c.section:
        parts.append(f"Section {c.section}")
    parts.append(f"par. {c.paragraph} ({c.title})")
    if c.page_label:
        parts.append(f"page {c.page_label}")
    return ", ".join(parts)


def snippet(text: str, query: str | None = None, limit: int = SNIPPET_CHARS) -> str:
    """A short excerpt; with a query, start at the sentence that matches it best."""
    text = re.sub(r"^\d{1,2}-\d{1,3}\.\s+[^.]+\.\s*", "", text)  # drop the repeated heading
    if query:
        q = set(tokenize(query))
        sentences = re.split(r"(?<=\.)\s+", text)
        best = max(range(len(sentences)), key=lambda i: (len(q & set(tokenize(sentences[i]))), -i))
        if q & set(tokenize(sentences[best])):
            text = " ".join(sentences[best:])
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def to_procedure(c: Chunk, query: str | None = None) -> dict:
    """Shape a chunk as a `procedures[]` item of POST /api/assist (docs/API.md)."""
    if is_handbook(c):
        section = f"{c.title} (Ch. {c.chapter}: {c.chapter_title})"
    else:
        section = f"Par. {c.paragraph} {c.title}"
    if c.section_title and not is_handbook(c):
        section += f" (Ch. {c.chapter}, Sec. {c.section}: {c.section_title})"
    return {
        "doc": c.doc,
        "section": section,
        "page": c.page,
        "page_label": c.page_label or None,
        "snippet": snippet(c.text, query),
        "url": c.url,
        "citation": citation(c),
    }


def context_block(hits: list[Hit]) -> str:
    """Procedure text for the LLM prompt. Each excerpt is tagged with the label to cite."""
    blocks = []
    for h in hits:
        c = h.chunk
        blocks.append(f"[{cite_tag(c)}] {c.title} (page {c.page_label})\n{c.text}")
    return "\n\n".join(blocks)


def cite_tag(c: Chunk) -> str:
    """The short label the model cites: 'AC 43.13-1B par. 9-14' or 'FAA-H-8083-31B p. 13-14'."""
    return f"{c.ac_number} p. {c.page_label}" if is_handbook(c) else f"{c.ac_number} par. {c.paragraph}"


CITE_INSTRUCTION = (
    "Use only the procedure excerpts below. After each step that relies on one, cite it in square "
    "brackets exactly as tagged, e.g. [AC 43.13-1B par. 9-14] or [FAA-H-8083-31B p. 13-14]. "
    "Do not cite anything else."
)

_CITED = re.compile(
    r"\[\s*(?:(AC\s*43\.13-1B)\s+par\.?\s*(\d{1,2}-\d{1,3})|(FAA-H-8083-3[012]B)\s+p(?:age|\.)?\s*(\d{1,2}-\d{1,3}))\s*\]",
    re.I,
)


def _cited_tag(m: re.Match) -> str:
    if m.group(1):
        return f"AC 43.13-1B par. {m.group(2)}"
    return f"{m.group(3).upper()} p. {m.group(4)}"


def check_citations(answer: str, hits: list[Hit]) -> tuple[list[str], list[str]]:
    """Return (valid, unknown) citation tags in a model answer, e.g. "AC 43.13-1B par. 9-14".

    Unknown citations point at paragraphs or pages that were not retrieved; the
    caller should strip them so the UI never shows a made-up section.
    """
    allowed = {cite_tag(h.chunk) for h in hits}
    cited = list(dict.fromkeys(_cited_tag(m) for m in _CITED.finditer(answer)))
    return [t for t in cited if t in allowed], [t for t in cited if t not in allowed]


def strip_unknown_citations(answer: str, hits: list[Hit]) -> str:
    allowed = {cite_tag(h.chunk) for h in hits}
    return _CITED.sub(lambda m: m.group(0) if _cited_tag(m) in allowed else "", answer).replace("  ", " ")


# ---------------------------------------------------------------- CLI


def _main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "build":
        chunks = chunk_pages(read_pdf_pages(argv[1]))
        out = argv[2] if len(argv) > 2 else DEFAULT_CHUNKS
        write_chunks(chunks, out)
        paras = len({c.paragraph for c in chunks})
        print(f"{len(chunks)} chunks from {paras} paragraphs -> {out}")
        return 0
    if len(argv) >= 2 and argv[0] == "search":
        index = ProcedureIndex.load()
        hits = index.search(" ".join(argv[1:]), k=5)
        print(json.dumps([to_procedure(h.chunk, " ".join(argv[1:])) | {"score": h.score} for h in hits], indent=2, ensure_ascii=False))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
