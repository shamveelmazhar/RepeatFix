"""Parse FAA Service Difficulty Reports (SDR) into JobCard records.

The FAA SDR system (https://sdrs.faa.gov) exports one CSV per year with 76
columns. Unlike ASRS, SDR keeps the tail number, the part numbers and a JASC
code (the FAA's 4-digit version of the ATA chapter), so it gives real
per-aircraft repeats.

This module only does the deterministic part:
- ``registration`` is ``N`` + ``RegistryNNumber``.
- ``ata_chapter`` is the first two digits of ``JASCCode``.
- ``aircraft_type`` turns FAA model codes into the names technicians use
  (``7378H4`` -> ``B737-800``, ``CL6002C10`` -> ``CRJ700``).
- ``symptom`` and ``action_taken`` are split out of the free-text
  ``Discrepancy`` at markers such as ``CORRECTIVE ACTION:`` or ``C/A:``.
- ``failure_mode`` is picked from ``vocab.FAILURE_MODES`` using the coded
  ``PartCondition`` first, then keyword rules on the text.

An LLM step on the model API can refine symptom, action and failure mode later.

Usage:
    python -m app.sdr build SDR-2024.csv SDR-2025.csv SDR-2026.csv \\
        -o ../data/raw/sdr_cards.jsonl --demo ../data/samples/sdr_demo.jsonl
    python -m app.sdr repeats ../data/raw/sdr_cards.jsonl
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Iterator

from . import vocab

# Some free-text fields run past the default csv field limit.
csv.field_size_limit(10_000_000)

UNKNOWN_VALUES = {"", "UNKNOWN", "UNK", "NONE", "N/A", "NA", "*"}

# ---------------------------------------------------------------------------
# Aircraft type
# ---------------------------------------------------------------------------

# Exact model codes that the general rules below would get wrong.
MODEL_NAMES: dict[str, str] = {
    # 737 MAX is certified as the 737-7/-8/-9, so its code has no customer suffix.
    "7377": "B737 MAX 7",
    "7378": "B737 MAX 8",
    "7379": "B737 MAX 9",
    "BD5001A10": "A220-100",
    "BD5001A11": "A220-300",
    "CL6002B16": "Challenger 604",
    "CL6002B19": "CRJ200",
    "CL6002C10": "CRJ700",
    "CL6002C11": "CRJ550",
    "CL6002D15": "CRJ705",
    "CL6002D24": "CRJ900",
    "BD1001A10": "Challenger 300",
    "DHC8402": "Dash 8-400",
    "EMB505": "Phenom 300",
    "MD11F": "MD-11F",
    "MD11": "MD-11",
}

BOEING_RE = re.compile(r"^7(\d)7(\d)(\w*)$")  # 7377H4 -> 737, -700, customer code H4
AIRBUS_RE = re.compile(r"^A3(\d\d)(\d)\d\d(N|NX)?$")  # A321271NX -> A321, -200, neo
EMB_RE = re.compile(r"^(ERJ|EMB)(\d{3})(\d{3})?")


def aircraft_type(make: str, model: str) -> str:
    """Turn an SDR make/model pair into a short type name, e.g. ``B737-800``."""
    make, model = (make or "").strip().upper(), (model or "").strip().upper()
    if model in UNKNOWN_VALUES and make in UNKNOWN_VALUES:
        return "Unknown"
    if model in MODEL_NAMES:
        return MODEL_NAMES[model]
    if model.startswith("CL6002D"):
        return "CRJ900"
    if model.startswith("BD7001A"):
        return "Global Express"

    m = BOEING_RE.match(model)
    if make == "BOEING" and m:
        family, series, rest = m.groups()
        name = f"B7{family}7-{series}00"
        if rest.endswith("ER"):
            name += "ER"
        elif rest.endswith("F"):
            name += "F"
        return name

    if make == "AIRBUS" and model.startswith("A300"):
        return "A300-600F" if "F4" in model else "A300-600"
    m = AIRBUS_RE.match(model)
    if make == "AIRBUS" and m:
        family, series, neo = m.groups()
        if neo:
            return f"A3{family}neo"
        return f"A3{family}-{series}00"

    m = EMB_RE.match(model)
    if make == "EMB" and m:
        prefix, base, variant = m.groups()
        if prefix == "ERJ" and base in ("170", "190") and variant:
            # ERJ 170-200 is sold as the E175, ERJ 190-200 as the E195.
            return {"170100": "E170", "170200": "E175", "190100": "E190", "190200": "E195"}.get(
                base + variant, f"E{base}"
            )
        return f"ERJ-{base}" if base in ("135", "140", "145") else f"EMB-{base}"

    if model in UNKNOWN_VALUES:
        return make.title()
    return f"{make.title()} {model}".strip()


# ---------------------------------------------------------------------------
# Discrepancy text: symptom vs. corrective action
# ---------------------------------------------------------------------------

# Explicit markers some operators put between the finding and the fix.
ACTION_MARKER_RE = re.compile(
    r"\s*(?:\bCORR(?:ECTIVE)?\.?\s*ACTION\b|\bC/A\b|\bRESOLUTION\b|\bACTION TAKEN\b"
    r"|\*\*SUPPLEMENTAL REPORT FOR \([^)]*\)|<\[01\])\s*[:\-]*\s*",
    re.I,
)
# Without a marker, the fix usually starts at the first sentence with one of these verbs.
ACTION_VERB_RE = re.compile(
    r"\b(REMOVED (?:AND|&) REPLACED|R\s*&\s*R'?D?|R/R|REPLACED|REPAIRED|REINSTALLED|INSTALLED"
    r"|RE-?SECURED|SECURED|COMPLIED WITH|BLENDED|RESEALED|RESET|ADJUSTED|TIGHTENED|TORQUED"
    r"|SERVICED|CLEANED|LUBRICATED|DEFERRED|REWORKED|SPLICED|PERFORMED|ACCOMPLISHED|C/?W|TROUBLESHOT|OPS? CH(?:ECK|EC?KE?)D? GOOD)\b",
    re.I,
)
# Sentence breaks, plus " / " and "-PERFORMED ..." which some operators use between finding and fix.
SENTENCE_RE = re.compile(r"(?<=[.;])\s+|\s+/\s+|\s*-(?=(?:PERFORMED|ACCOMPLISHED|C/?W)\b)")
# Operator boilerplate at the start of the text that says nothing about the fault.
LEAD_NOISE_RE = re.compile(
    r"^(?:SHIP\s*#?\s*\w+\s*|\(\s*LOG\s*[\w-]+\s*\)\s*|\(?AIRCRAFT (?:WAS )?(?:NOT )?GROUNDED\)?:?\s*"
    r"|AIRCRAFT IN BASE MAINTENANCE:\s*"
    r"|DISC(?:REPANCY)?\s*[:\-]\s*)+",
    re.I,
)
TRAIL_NOISE_RE = re.compile(r"\s*(?:\((?:LP:\s*)?\d+\)|\(CLOSED\)|\d{4}-\d{5,})\s*\.?$", re.I)


def _tidy(text: str) -> str:
    text = " ".join(text.split())
    text = LEAD_NOISE_RE.sub("", text)
    for _ in range(2):
        text = TRAIL_NOISE_RE.sub("", text)
    return text.strip(" .;:-*")


def split_discrepancy(text: str) -> tuple[str, str]:
    """Return ``(symptom, action_taken)`` from an SDR ``Discrepancy`` text.

    ``action_taken`` is empty when no corrective action can be found.
    """
    text = " ".join((text or "").split())
    m = ACTION_MARKER_RE.search(text)
    if m and m.start() > 0:
        return _tidy(text[: m.start()]), _tidy(text[m.end():])

    sentences = SENTENCE_RE.split(text)
    for i, sentence in enumerate(sentences[1:], 1):
        if ACTION_VERB_RE.search(sentence):
            return _tidy(" ".join(sentences[:i])), _tidy(" ".join(sentences[i:]))
    return _tidy(text), ""


# ---------------------------------------------------------------------------
# Failure mode
# ---------------------------------------------------------------------------

# Physical findings that SDR codes in PartCondition. They beat text keywords, since a
# corroded door frame is a corrosion finding however the narrative describes the door.
PHYSICAL_CONDITIONS: dict[str, str] = {
    "CORRODED": "corrosion",
    "CRACKED": "crack_found",
    "DENTED": "structural_damage",
    "GOUGED": "structural_damage",
    "DELAMINATED": "structural_damage",
    "DEBONDED": "structural_damage",
    "BUCKLED": "structural_damage",
    "PUNCTURED": "structural_damage",
    "WORN": "wear_or_chafing",
    "CHAFED": "wear_or_chafing",
    "EXCESS PLAY": "wear_or_chafing",
    "LOOSE": "wear_or_chafing",
    "UNSECURE": "wear_or_chafing",
    "LEAKING": "fluid_leak",
    "ODOR": "smoke_or_odor",
    "SMOKE": "smoke_or_odor",
    "FUMES": "smoke_or_odor",
    "MISSING": "panel_missing",
    "DETACHED": "panel_missing",
    "FALSE ACTIVATION": "false_warning",
    "UNWANTED DEPLOY": "false_warning",
    "DISCHARGED": "fire_bottle_discharge",
}
# Functional findings. Text keywords go first, because "inoperative" says less than
# "landing light lamp burnt out".
FUNCTIONAL_CONDITIONS: dict[str, str] = {
    "INOPERATIVE": "component_malfunction",
    "FAILED": "component_malfunction",
    "FAULTED": "component_malfunction",
    "FAULTY": "component_malfunction",
    "MALFUNCTIONED": "component_malfunction",
    "DEFECTIVE": "component_malfunction",
    "NO TEST": "component_malfunction",
    "BROKEN": "component_malfunction",
    "LOW PRESSURE": "low_pressure",
    "OUT OF ADJUST": "out_of_adjustment",
    "OUT OF POSITION": "out_of_adjustment",
    "BINDING": "out_of_adjustment",
    "LACK OF LUBE": "out_of_adjustment",
}
# Mode-specific patterns that are too broad for SDR text (every ATA 52 write-up says "door").
SDR_PATTERN_OVERRIDES = {"door_actuator_fault": r"actuator|\bstrut\b"}
# Generic modes worth matching in SDR text. "manual_or_procedure_gap" is left out on
# purpose: almost every SDR cites the AMM, so it would match nearly everything.
SDR_GENERIC_TEXT_MODES = [
    "corrosion", "crack_found", "smoke_or_odor", "fluid_leak", "panel_missing",
    "false_warning", "wear_or_chafing", "incorrect_installation", "low_pressure",
    "structural_damage",
]


# When a report only says the part "failed", name the fault after the part.
# Matched against the reported part name, in this order (first hit wins), so
# "door warning light" is an indicator fault and "fire detector" is fire detection.
COMPONENT_MODES: list[tuple[str, str]] = [
    ("fire_detection_fault", r"fire (loop|det|warn|sens|alarm)|overheat|smoke det|(?<!hook and )\bloops?\b"
                             r"|(?<!chip )detector|\bfdu\b"),
    ("warning_indication_fault", r"warning|indicat|annunciat|display|gauge|\becam\b|eicas|message"),
    ("battery_power_fault", r"batter|power supply|\bepsu\b|charger|inverter|transformer|\btru\b"),
    ("lighting_fault", r"(?<!f)light|\blamps?\b|bulb|lens|\bsigns?\b|strobe|beacon"),
    ("door_latch_fault", r"door|latch|handle|hinge|\block\b"),
    ("floor_panel_fault", r"floor|seat track"),
    ("window_fault", r"window|windshield|windscreen"),
    ("skin_frame_fault", r"skin|frame|stringer|structure|fuselage|doubler|longeron|bulkhead|\bribs?\b|spar"
                         r"|former|intercostal|\bbeam|fitting|bracket|gusset|\blug\b|access panel|fairing"),
    ("valve_fault", r"valve"),
    ("sensor_switch_fault", r"sensor|switch|probe|pitot|transducer|transmitter|thermostat"),
    ("computer_controller_fault", r"computer|controller|control (unit|panel)|module|\bunit\b|transceiver"
                                  r"|receiver|radio|antenna|\bfmc\b|\bfmgc\b|\badiru\b|\belac\b|\bsec\b"),
    ("actuator_pump_motor_fault", r"actuator|pump|motor|\bjack\b|\bservo"),
    ("wiring_relay_fault", r"wir(e|ing)|connector|harness|relay|circuit breaker|cable"),
    ("seal_bearing_fault", r"seal|bearing|bushing|\bpins?\b|bolt|\bnuts?\b|snubber|roller|spring|washer"
                           r"|fastener|rivet|clamp|hose|duct|tube"),
    ("landing_gear_part_fault", r"landing gear|(?<!turbine )wheel|(?<!speed )brake|\btires?\b|\bstrut"),
    ("engine_apu_fault", r"engine|\bapu\b|\beec\b|fadec|starter|igniter|ignition"),
]


# With no part name, the JASC chapter alone says which part it was in these chapters.
CHAPTER_MODES: dict[str, str] = {
    "31": "warning_indication_fault",
    "33": "lighting_fault",
    "49": "engine_apu_fault",
    "51": "skin_frame_fault",
    "52": "door_latch_fault",
    "53": "skin_frame_fault",
    "56": "window_fault",
    "57": "skin_frame_fault",
    "72": "engine_apu_fault",
}


def component_mode(part_name: str | None, ata: str | None = None) -> str | None:
    """Name a "failed" report after the part, e.g. "Fire loop" -> fire_detection_fault."""
    if not part_name:
        return CHAPTER_MODES.get(ata or "")
    for code, pattern in COMPONENT_MODES:
        if re.search(pattern, part_name, re.I):
            return code
    return None


def _sdr_pattern(mode: vocab.FailureMode) -> str:
    return SDR_PATTERN_OVERRIDES.get(mode.code, mode.pattern)


def _mode(code: str, ata: str) -> str:
    """Return ``code`` if it is valid under this ATA chapter, else its generic fallback."""
    mode = vocab.FAILURE_MODES_BY_CODE[code]
    if mode.ata is None or mode.ata == ata:
        return code
    return "component_malfunction"


def failure_mode(ata: str, text: str, condition: str | None, part_name: str | None = None) -> str:
    """Pick one ``vocab.FAILURE_MODES`` code for an SDR record.

    A plain "failed" report is named after ``part_name`` when we know the part,
    else after its chapter where the chapter names the part (52 Doors, 33 Lights).
    """
    code = _failure_mode(ata, text, condition)
    if code == "component_malfunction":
        return component_mode(part_name, ata) or code
    return code


def _failure_mode(ata: str, text: str, condition: str | None) -> str:
    condition = (condition or "").strip().upper()
    if condition in PHYSICAL_CONDITIONS:
        return _mode(PHYSICAL_CONDITIONS[condition], ata)

    for mode in vocab.FAILURE_MODES:
        if mode.ata == ata and mode.pattern and re.search(_sdr_pattern(mode), text, re.I):
            return mode.code
    for code in SDR_GENERIC_TEXT_MODES:
        mode = vocab.FAILURE_MODES_BY_CODE[code]
        if re.search(mode.pattern, text, re.I):
            return code
    if condition in FUNCTIONAL_CONDITIONS:
        return FUNCTIONAL_CONDITIONS[condition]
    # Every SDR reports a defect, so with nothing better it is a malfunction.
    return "component_malfunction"


# ---------------------------------------------------------------------------
# JobCard
# ---------------------------------------------------------------------------


def _clean(value: str | None) -> str | None:
    value = " ".join((value or "").split())
    return None if value.upper() in UNKNOWN_VALUES else value


def _iso_date(mmddyyyy: str | None) -> str | None:
    try:
        return datetime.strptime((mmddyyyy or "").strip(), "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _registration(nnumber: str | None) -> str | None:
    n = (_clean(nnumber) or "").upper().replace("-", "").replace(" ", "")
    if not n:
        return None
    return n if n.startswith("N") else f"N{n}"


def _parts(row: dict) -> list[str]:
    parts = []
    for key in ("PartNumber", "ComponentPartNumber"):
        pn = _clean(row.get(key))
        if pn and pn not in parts:
            parts.append(pn)
    return parts


def _part_name(row: dict) -> str | None:
    return _clean(row.get("PartName")) or _clean(row.get("ComponentName"))


def _component(row: dict, ata: str) -> str:
    for key in ("PartName", "ComponentName"):
        name = _clean(row.get(key))
        if name:
            return name.capitalize()
    return vocab.ata_name(ata)


def to_job_card(row: dict) -> dict:
    jasc = (row.get("JASCCode") or "").strip()
    ata = jasc[:2] if re.fullmatch(r"\d{4}", jasc) else vocab.GENERAL_ATA
    discrepancy = " ".join((row.get("Discrepancy") or "").split())
    symptom, action = split_discrepancy(discrepancy)
    condition = _clean(row.get("PartCondition"))

    return {
        "id": f"sdr-{row['OperatorControlNumber'].strip()}",
        "source": "sdr",
        "date": _iso_date(row.get("DifficultyDate")),
        "aircraft_type": aircraft_type(row.get("AircraftMake", ""), row.get("AircraftModel", "")),
        "registration": _registration(row.get("RegistryNNumber")),
        "ata_chapter": ata,
        "ata_name": vocab.ata_name(ata),
        "component": _component(row, ata),
        "symptom": symptom or discrepancy,
        "failure_mode": failure_mode(ata, f"{symptom} {_clean(row.get('PartName')) or ''}", condition,
                                     _part_name(row)),
        "action_taken": action,
        "parts": _parts(row),
        "downtime_hours": None,  # SDR does not record downtime
        "raw_text": discrepancy,
        # Extra, SDR-only context kept for citation and the LLM step. Not part of JobCard.
        "sdr": {
            "control_number": row["OperatorControlNumber"].strip(),
            "jasc_code": jasc or None,
            "operator": _clean(row.get("OperatorDesignator")),
            "aircraft_make": _clean(row.get("AircraftMake")),
            "aircraft_model": _clean(row.get("AircraftModel")),
            "part_condition": condition,
            "part_location": _clean(row.get("PartLocation")),
            "stage_of_operation": _clean(row.get("StageOfOperationCode")),
            "aircraft_total_time": _clean(row.get("AircraftTotalTime")),
            "aircraft_total_cycles": _clean(row.get("AircraftTotalCycles")),
        },
    }


def read_rows(path: str | Path) -> Iterator[dict]:
    # The exports are UTF-8 with the odd broken byte; never fail the whole file on one.
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        yield from csv.DictReader(f)


def read_cards(paths: Iterable[str | Path]) -> list[dict]:
    """Parse several yearly files. Later files win when a control number repeats."""
    by_id: dict[str, dict] = {}
    for path in paths:
        for row in read_rows(path):
            if (row.get("OperatorControlNumber") or "").strip():
                card = to_job_card(row)
                by_id[card["id"]] = card
    return sorted(by_id.values(), key=lambda c: (c["date"] or "", c["id"]))


# ---------------------------------------------------------------------------
# Repeats (reporting only; the API's repeat engine computes its own stats)
# ---------------------------------------------------------------------------


def repeat_groups(cards: Iterable[dict], min_count: int = 2, min_gap_days: int = 0) -> list[dict]:
    """Group cards by tail + ATA chapter + failure mode.

    A heavy check can file dozens of corrosion findings on one tail on one day. Those
    are one event, not a repeat, so ``min_gap_days`` > 0 counts only reports at least
    that many days after the previous counted report of the group.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for c in cards:
        if c["registration"] and c["date"]:
            groups[(c["registration"], c["ata_chapter"], c["failure_mode"])].append(c)

    rows = []
    for (tail, ata, mode), members in groups.items():
        members.sort(key=lambda c: c["date"])
        events, last = [], None
        for c in members:
            d = date.fromisoformat(c["date"])
            if last is None or (d - last).days >= min_gap_days:
                events.append(c)
                last = d
        if len(events) >= min_count:
            rows.append({
                "asset": tail,
                "aircraft_type": members[-1]["aircraft_type"],
                "ata_chapter": ata,
                "ata_name": vocab.ata_name(ata),
                "failure_mode": mode,
                "count": len(events),
                "reports": len(members),
                "first_date": members[0]["date"],
                "last_date": members[-1]["date"],
                "years": sorted({c["date"][:4] for c in members}),
                "card_ids": [c["id"] for c in members],
            })
    rows.sort(key=lambda r: (-r["count"], r["asset"]))
    return rows


def repeat_summary(cards: list[dict], min_gap_days: int = 7) -> dict:
    tails = {c["registration"] for c in cards if c["registration"]}
    all_groups = repeat_groups(cards, 2)
    spaced = repeat_groups(cards, 2, min_gap_days)
    return {
        "cards": len(cards),
        "tails": len(tails),
        "repeat_groups": len(all_groups),
        "tails_with_repeats": len({g["asset"] for g in all_groups}),
        f"repeat_groups_{min_gap_days}d_apart": len(spaced),
        f"tails_with_repeats_{min_gap_days}d_apart": len({g["asset"] for g in spaced}),
        "repeat_groups_across_years": sum(len(g["years"]) > 1 for g in spaced),
        "system_repeat_groups": sum(map(is_system_repeat, spaced)),
        "tails_with_system_repeats": len({g["asset"] for g in spaced if is_system_repeat(g)}),
    }


# ---------------------------------------------------------------------------
# Demo subset
# ---------------------------------------------------------------------------

DEMO_TYPES = re.compile(r"^(B737-[789]00|B737 MAX|A319|A320|A321|CRJ)")
# Structure chapters. Their repeats are mostly heavy-check corrosion and crack findings,
# which matter less to a line technician than a system that keeps failing.
STRUCTURE_ATA = {"51", "52", "53", "54", "55", "56", "57"}


def is_system_repeat(group: dict) -> bool:
    return group["ata_chapter"] not in STRUCTURE_ATA and group["failure_mode"] not in (
        "corrosion", "crack_found", "structural_damage")


def demo_subset(cards: list[dict], max_tails: int = 40, min_gap_days: int = 7) -> list[dict]:
    """A small, repeat-rich slice for the committed sample and the demo.

    Takes the B737 / A320-family / CRJ tails with the most spaced-out system repeats
    and keeps every card for those tails, so the Repeat failures screen has real history.
    """
    fleet = [c for c in cards if DEMO_TYPES.match(c["aircraft_type"])]
    score: dict[str, int] = defaultdict(int)
    for g in repeat_groups(fleet, 2, min_gap_days):
        if is_system_repeat(g):
            score[g["asset"]] += g["count"]
    # Spread the pick across types so no single fleet fills the demo.
    by_type: dict[str, list[str]] = defaultdict(list)
    type_of = {c["registration"]: DEMO_TYPES.match(c["aircraft_type"]).group(1) for c in fleet}
    for tail in sorted(score, key=lambda t: (-score[t], t)):
        by_type[type_of[tail]].append(tail)
    picked: list[str] = []
    while len(picked) < max_tails and any(by_type.values()):
        for t in sorted(by_type):
            if by_type[t] and len(picked) < max_tails:
                picked.append(by_type[t].pop(0))
    keep = set(picked)
    return [c for c in fleet if c["registration"] in keep]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _write_jsonl(cards: list[dict], path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def _read_jsonl(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="parse SDR CSV exports into JobCard JSONL")
    b.add_argument("csv", nargs="+", help="SDR yearly CSV exports")
    b.add_argument("-o", "--out", required=True, help="full JSONL (large; keep under data/raw/)")
    b.add_argument("--demo", help="also write the demo subset here")
    b.add_argument("--demo-tails", type=int, default=40)

    r = sub.add_parser("repeats", help="print per-tail repeat stats for a JSONL file")
    r.add_argument("jsonl")
    r.add_argument("--top", type=int, default=15)
    r.add_argument("--gap", type=int, default=7, help="min days between counted reports")

    args = ap.parse_args(argv)
    if args.cmd == "build":
        cards = read_cards(args.csv)
        _write_jsonl(cards, args.out)
        print(f"{len(cards)} cards -> {args.out}", file=sys.stderr)
        if args.demo:
            demo = demo_subset(cards, args.demo_tails)
            _write_jsonl(demo, args.demo)
            print(f"{len(demo)} demo cards -> {args.demo}", file=sys.stderr)
        print(json.dumps(repeat_summary(cards), indent=2))
        return 0

    cards = _read_jsonl(args.jsonl)
    print(json.dumps(repeat_summary(cards, args.gap), indent=2))
    for g in repeat_groups(cards, 2, args.gap)[: args.top]:
        print(f"{g['asset']:8} {g['aircraft_type']:12} ATA {g['ata_chapter']} {g['failure_mode']:24}"
              f" x{g['count']} ({g['first_date']} .. {g['last_date']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
