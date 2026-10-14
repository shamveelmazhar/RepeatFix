"""Parse NASA ASRS report sets into JobCard records.

ASRS report sets (https://asrs.arc.nasa.gov/search/reportsets.html) come as a PDF:
a cover memo, a list of synopses, then one block per report. Each block starts
with ``ACN: <number> (i of n)`` and holds labelled sections (Time / Day, Place,
Aircraft, Component, Person, Events, Assessments), one or more free-text
``Narrative: n`` / ``Callback: n`` sections, and a ``Synopsis``.

This module only does the deterministic part: it splits the report set,
reads the labelled fields, and fills a JobCard with what ASRS already
coded (date, aircraft type, component, problem) plus a rule-based ATA chapter
and failure mode (see ``vocab.py``). Fields ASRS does not code, such as
``action_taken`` and ``parts``, are left empty for the LLM extraction step.

Usage:
    python -m app.asrs path/to/mechanic.pdf -o ../data/samples/asrs_mechanic.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import vocab

ACN_RE = re.compile(r"^ACN:\s*(\d+)\s*\((\d+)\s+of\s+(\d+)\)\s*$")
# Section headers inside a report. Numbered ones look like "Aircraft : 2" or "Narrative: 1".
SECTION_RE = re.compile(
    r"^(Time / Day|Place|Environment|Aircraft|Component|Person|Events|Assessments"
    r"|Narrative|Callback|Synopsis)(?:\s*:\s*(\d+))?$"
)
FIELD_RE = re.compile(r"^(.+?)\s:\s(.*)$")
FREE_TEXT = {"Narrative", "Callback", "Synopsis"}

# ASRS placeholders that mean "no specific aircraft type".
UNKNOWN_TYPES = {
    "no aircraft",
    "commercial fixed wing",
    "any unknown or unlisted aircraft manufacturer",
}


@dataclass
class AsrsReport:
    acn: str
    date: str | None = None  # "YYYYMM" as ASRS gives it
    aircraft: list[dict[str, list[str]]] = field(default_factory=list)
    components: list[dict[str, list[str]]] = field(default_factory=list)
    fields: dict[str, list[str]] = field(default_factory=dict)  # every other "Key : Value"
    narratives: list[str] = field(default_factory=list)
    callbacks: list[str] = field(default_factory=list)
    synopsis: str = ""


def read_text(path: str | Path) -> str:
    """Return the text of a report set. Accepts the PDF or an already-extracted .txt."""
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        return path.read_text(encoding="utf-8")
    from pypdf import PdfReader  # imported lazily so text-only use needs no PDF library

    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def _clean_lines(text: str) -> list[str]:
    return [line.replace("\f", "").strip() for line in text.splitlines()]


def split_reports(text: str) -> list[list[str]]:
    """Split a report set into one list of lines per report.

    The synopsis list at the top also has ``ACN:`` lines, so we start after the
    "Report Narratives" heading when it is present.
    """
    lines = _clean_lines(text)
    try:
        start = lines.index("Report Narratives") + 1
    except ValueError:
        start = 0

    reports: list[list[str]] = []
    for line in lines[start:]:
        if ACN_RE.match(line):
            reports.append([line])
        elif reports:
            reports[-1].append(line)
    return reports


def _join_paragraph(lines: list[str]) -> str:
    """Re-flow PDF-wrapped lines into a paragraph; keep blank-line breaks."""
    paragraphs, current = [], []
    for line in lines:
        if line and current and current[-1].endswith("-"):
            current[-1] += line  # word broken across lines: "non-" + "accomplishment"
        elif line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs).strip()


def parse_report(lines: list[str]) -> AsrsReport:
    acn = ACN_RE.match(lines[0]).group(1)
    report = AsrsReport(acn=acn)

    section, block, text_buf = None, None, []

    def flush_text():
        if section in FREE_TEXT and text_buf:
            body = _join_paragraph(text_buf)
            if section == "Narrative":
                report.narratives.append(body)
            elif section == "Callback":
                report.callbacks.append(body)
            else:
                report.synopsis = body

    for line in lines[1:]:
        m = SECTION_RE.match(line)
        if m:
            flush_text()
            section, text_buf = m.group(1), []
            if section == "Aircraft":
                block = {}
                report.aircraft.append(block)
            elif section == "Component":
                block = {}
                report.components.append(block)
            else:
                block = None
            continue

        if section in FREE_TEXT:
            text_buf.append(line)
            continue

        fm = FIELD_RE.match(line)
        if not fm:
            continue  # e.g. "When Detected.Other" carries no value
        key, value = fm.group(1).strip(), fm.group(2).strip()
        target = block if block is not None else report.fields
        target.setdefault(key, []).append(value)
        if key == "Date" and report.date is None:
            report.date = value

    flush_text()
    return report


def parse_report_set(text: str) -> list[AsrsReport]:
    return [parse_report(lines) for lines in split_reports(text)]


def _first(block: dict[str, list[str]] | None, key: str) -> str | None:
    if not block:
        return None
    values = block.get(key) or []
    return values[0] if values else None


def _iso_month(yyyymm: str | None) -> str | None:
    """ASRS de-identifies dates to the month. We use the 1st as the day."""
    if not yyyymm or not re.fullmatch(r"\d{6}", yyyymm):
        return None
    return f"{yyyymm[:4]}-{yyyymm[4:]}-01"


def primary_aircraft(report: AsrsReport) -> dict[str, list[str]] | None:
    """The aircraft the component belongs to, else the reporter's aircraft (Reference X)."""
    ref = _first(report.components[0], "Aircraft Reference") if report.components else None
    for ref_wanted in (ref, "X"):
        for ac in report.aircraft:
            if ref_wanted and _first(ac, "Reference") == ref_wanted:
                return ac
    return report.aircraft[0] if report.aircraft else None


def clean_aircraft_type(raw: str | None) -> str:
    """Tidy ASRS make/model names, e.g. 'B737 Undifferentiated or Other Model' -> 'B737'."""
    if not raw or raw.strip().lower() in UNKNOWN_TYPES:
        return "Unknown"
    t = re.sub(r"\s+(Undifferentiated or Other Model|Series Undifferentiated)$", "", raw.strip())
    t = re.sub(r"^(B787) Dreamliner$", r"\1", t)
    t = re.sub(r"^(B767-300) and 300 ER$", r"\1", t)
    t = re.sub(r"^Regional Jet .*\((CRJ\d+)\)$", r"\1", t)
    return t


def to_job_card(report: AsrsReport) -> dict:
    aircraft = primary_aircraft(report)
    component_block = report.components[0] if report.components else None
    asrs_component = _first(component_block, "Aircraft Component")
    problem = _first(component_block, "Problem")

    narrative = "\n\n".join(report.narratives + report.callbacks)
    # vocab reads the first line as the synopsis, so keep it on one line.
    search_text = f"{' '.join(report.synopsis.split())}\n{narrative}"

    ata = vocab.ata_for_component(asrs_component) or vocab.ata_from_text(search_text)
    mode = vocab.failure_mode(ata, search_text, problem)
    ata_chapter = ata or mode["ata_chapter"]

    raw_parts = [f"Synopsis: {report.synopsis}"] if report.synopsis else []
    raw_parts += [f"Narrative {i}: {n}" for i, n in enumerate(report.narratives, 1)]
    raw_parts += [f"Callback {i}: {c}" for i, c in enumerate(report.callbacks, 1)]

    return {
        "id": f"asrs-{report.acn}",
        "source": "asrs",
        "date": _iso_month(report.date),
        "aircraft_type": clean_aircraft_type(_first(aircraft, "Make Model Name")),
        "registration": None,  # ASRS is de-identified
        "ata_chapter": ata_chapter,
        "ata_name": vocab.ata_name(ata_chapter),
        "component": asrs_component or vocab.component_from_text(search_text) or "Not stated",
        "symptom": report.synopsis,
        "failure_mode": mode["code"],
        "action_taken": "",  # not coded by ASRS; filled by the LLM extraction step
        "parts": [],
        "downtime_hours": None,
        "raw_text": "\n\n".join(raw_parts),
        # Extra, ASRS-only context kept for citation and the LLM step. Not part of JobCard.
        "asrs": {
            "acn": report.acn,
            "problem": problem,
            "flight_phase": _first(aircraft, "Flight Phase"),
            "maintenance_type": _first(aircraft, "Maintenance Status.Maintenance Type"),
            "primary_problem": (report.fields.get("Primary Problem") or [None])[0],
        },
    }


def is_clean(card: dict) -> bool:
    """A card parsed cleanly when every field ASRS can give us is present and mapped."""
    return bool(
        card["date"]
        and card["aircraft_type"] != "Unknown"
        and card["ata_chapter"] != vocab.GENERAL_ATA
        and card["component"] != "Not stated"
        and card["symptom"]
        and "Narrative 1:" in card["raw_text"]
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path", help="ASRS report set PDF (or extracted .txt)")
    ap.add_argument("-o", "--out", help="write JSONL here (default: stdout)")
    ap.add_argument("--limit", type=int, help="keep only the first N reports")
    args = ap.parse_args(argv)

    cards = [to_job_card(r) for r in parse_report_set(read_text(args.path))]
    if args.limit:
        cards = cards[: args.limit]
    body = "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cards)
    if args.out:
        Path(args.out).write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)

    clean = sum(is_clean(c) for c in cards)
    print(f"{len(cards)} reports parsed, {clean} clean", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
