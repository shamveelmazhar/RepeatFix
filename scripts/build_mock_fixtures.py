"""Build the frontend fixtures in frontend/mocks/ from the real data.

The UI reads these files when no backend is connected (mock / cached demo mode):
  cards.json      every JobCard in data/samples/sdr_demo.jsonl and asrs_mechanic.jsonl
  knowledge.json  failure-mode labels, plus cited procedures (AC 43.13-1B and the AMT
                  Handbooks, via backend/app/procedures.py) for each ATA chapter + failure mode
  metrics.json    counts measured on the data; model numbers stay null until benchmarked

Run from the repo root:
    python scripts/build_mock_fixtures.py
    python scripts/build_mock_fixtures.py --full /mnt/project-files/sdr/sdr_cards_2024_2026.jsonl.gz

With --full, the Results counts come from the full SDR build (all tails, 2024-2026);
without it they come from the committed demo slice.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import vocab  # noqa: E402
from app.procedures import ProcedureIndex, snippet, to_procedure  # noqa: E402
from app.sdr import repeat_groups  # noqa: E402

SAMPLES = ROOT / "data" / "samples"
MOCKS = ROOT / "frontend" / "mocks"

CARD_FIELDS = ["id", "source", "date", "aircraft_type", "registration", "ata_chapter", "ata_name", "component",
               "symptom", "failure_mode", "action_taken", "parts", "downtime_hours", "raw_text"]

# Extra search words where the failure-mode label alone pulls the wrong book section
# (e.g. "slide" matching "slide calipers").
QUERY_HINTS = {
    "smoke_or_odor": "cabin air contamination odor fumes air conditioning pack bleed air",
    "emer_light_battery_fault": "emergency lighting battery exit lights",
    "escape_slide_fault": "emergency evacuation equipment inspection",
    "emergency_equipment_fault": "emergency equipment inspection",
    "oxygen_mask_deploy": "oxygen system masks crew passenger",
    "low_pressure": "pressure check servicing",
    "panel_missing": "access panels fasteners inspection",
    "component_malfunction": "troubleshooting inspection",
    "corrosion": "corrosion removal treatment inspection",
    "crack_found": "crack inspection repair",
    "wear_or_chafing": "chafing wear inspection",
    "fluid_leak": "leak inspection",
}
# Chapter words added to every query for that ATA chapter.
ATA_HINTS = {
    "21": "cabin environmental control",
    "25": "cabin equipment",
    "26": "fire detection protection",
    "28": "fuel system",
    "33": "lights lighting",
    "35": "oxygen system",
    "49": "auxiliary power unit APU",
    "53": "fuselage structure",
    "57": "wing structure",
}
PROCEDURES_PER_GROUP = 2

AC, GEN, AF, PP = "AC 43.13-1B", "FAA-H-8083-30B", "FAA-H-8083-31B", "FAA-H-8083-32B"
STRUCTURE = [(AC, "4"), (AC, "5"), (AC, "6"), (AF, "1"), (AF, "4")]
# Which book chapters a search may cite, by ATA chapter, so a cabin-lighting fault never
# cites the wood-structure chapter just because a word matched.
ATA_SCOPE = {
    "00": [(GEN, "1"), (GEN, "2")],
    "21": [(AF, "16")],
    "22": [(AF, "10"), (AC, "12")],
    "23": [(AF, "11"), (AC, "12")],
    "24": [(AF, "9"), (AC, "11")],
    "25": [(AC, "9"), (AC, "11")],
    "26": [(AF, "17"), (PP, "9")],
    "27": [(AF, "2"), (AC, "7")],
    "28": [(AF, "14"), (AC, "8")],
    "29": [(AF, "12")],
    "30": [(AF, "15")],
    "31": [(AF, "10"), (AC, "12")],
    "32": [(AF, "13"), (AC, "9")],
    "33": [(AF, "9"), (AC, "11")],
    "34": [(AF, "11"), (AC, "12")],
    "35": [(AF, "16"), (AC, "9")],
    "36": [(AF, "12"), (AF, "16")],
    "38": [(GEN, "9")],
    "49": [(PP, "1"), (PP, "5"), (GEN, "1")],
    "51": STRUCTURE, "52": STRUCTURE, "53": STRUCTURE, "54": STRUCTURE, "55": STRUCTURE,
    "56": STRUCTURE + [(AC, "3")], "57": STRUCTURE,
    "61": [(PP, "7")],
    "65": [(PP, "6")],
    "71": [(PP, "1"), (PP, "8"), (PP, "10")],
    "72": [(PP, "1"), (PP, "10")],
    "73": [(PP, "2")],
    "74": [(PP, "4")],
    "75": [(PP, "3"), (PP, "6")],
    "76": [(PP, "10"), (PP, "2")],
    "77": [(PP, "10"), (PP, "2")],
    "78": [(PP, "3")],
    "79": [(PP, "6")],
    "80": [(PP, "5")],
}
# Hand-picked sections for the groups where a keyword search alone picks a weak match.
# Key: "ATA|failure_mode", or "*|failure_mode" for any chapter. Value: (document, section title).
PINNED = {
    "33|emer_light_battery_fault": [(AF, "Maintenance & Inspection of Lighting Systems"), (AC, "Battery Maintenance")],
    "25|escape_slide_fault": [(AC, "Functional Check of Stand-by or Emergency Equipment")],
    "*|corrosion": [(AC, "Corrosion Inspection"), (AC, "General Surface Corrosion")],
    "*|crack_found": [(AC, "Repairing Cracked Members"), (GEN, "Surface Cracks")],
}
# Failure modes that point to their own topic whatever the ATA chapter.
MODE_SCOPE = {
    "corrosion": [(AC, "6"), (GEN, "8")],
    "crack_found": [(AC, "4"), (AC, "5"), (AF, "4"), (GEN, "10")],
    "structural_damage": [(AC, "4"), (AF, "4"), (AF, "1")],
    "hazmat_handling": [(GEN, "2")],
    "ground_handling": [(GEN, "1")],
    "manual_or_procedure_gap": [(GEN, "2")],
}


def read_jsonl(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def slim(card: dict) -> dict:
    return {k: card.get(k) for k in CARD_FIELDS}


def procedure_query(ata: str, mode: str, cards: list[dict]) -> str:
    label = vocab.FAILURE_MODES_BY_CODE[mode].label if mode in vocab.FAILURE_MODES_BY_CODE else mode
    chapter = vocab.ata_name(ata)
    components = [c for c, _ in Counter(x["component"] for x in cards if x["component"] != chapter).most_common(3)]
    return " ".join([label, chapter, ATA_HINTS.get(ata, ""), QUERY_HINTS.get(mode, ""), *components])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--full", type=Path, help="full SDR build (jsonl or jsonl.gz) for the Results counts")
    args = ap.parse_args(argv)

    sdr = read_jsonl(SAMPLES / "sdr_demo.jsonl")
    asrs = read_jsonl(SAMPLES / "asrs_mechanic.jsonl")
    cards = [slim(c) for c in sdr + asrs]

    # Cited procedures for every ATA chapter + failure mode in the cards.
    index = ProcedureIndex.load()
    scoped: dict[tuple, ProcedureIndex] = {}

    def search(query: str, scope: list[tuple[str, str]] | None):
        ix = index
        if scope:
            key = tuple(scope)
            if key not in scoped:
                scoped[key] = ProcedureIndex([c for c in index.chunks if (c.ac_number, c.chapter) in set(scope)])
            ix = scoped[key]
        # The Airframe and Powerplant handbooks repeat some sections word for word; keep one.
        chunks, titles = [], set()
        for h in ix.search(query, k=PROCEDURES_PER_GROUP * 3):
            if h.chunk.title not in titles:
                titles.add(h.chunk.title)
                chunks.append(h.chunk)
        return chunks[:PROCEDURES_PER_GROUP]

    def cite(c, query: str) -> dict:
        proc = to_procedure(c, query)
        # Figure captions make poor excerpts; quote the prose around them.
        proc["snippet"] = snippet(re.sub(r"\s*\(Figure [^)]*\)", "", c.text), query)
        return proc


    by_group: dict[str, list[dict]] = defaultdict(list)
    for c in cards:
        by_group[f"{c['ata_chapter']}|{c['failure_mode']}"].append(c)
    procedures = {}
    for key, members in sorted(by_group.items()):
        ata, mode = key.split("|")
        query = procedure_query(ata, mode, members)
        pins = PINNED.get(key) or PINNED.get(f"*|{mode}")
        if pins:
            chunks = [next(c for c in index.chunks if (c.ac_number, c.title) == pin) for pin in pins]
        else:
            chunks = search(query, MODE_SCOPE.get(mode) or ATA_SCOPE.get(ata))
        procedures[key] = [cite(c, query) for c in chunks]

    general = "aircraft inspection troubleshooting maintenance records"
    default_procedures = [cite(c, general) for c in search(general, [(GEN, "2"), (GEN, "10")])][:1]

    used = {c["failure_mode"] for c in cards}
    knowledge = {
        "_note": "Built by scripts/build_mock_fixtures.py. Procedures are real excerpts from FAA AC 43.13-1B and "
                 "the AMT Handbooks (data/procedures/), retrieved per ATA chapter + failure mode.",
        "failure_modes": [m for m in vocab.failure_mode_list() if m["code"] in used],
        "procedures": procedures,
        "default_procedures": default_procedures,
    }

    # Results counts: measured on the data. Model numbers stay null: no model runs in the saved demo.
    full = read_jsonl(args.full) if args.full else sdr
    metrics = {
        "cards_processed": len(full) + len(asrs),
        "extraction_field_accuracy": None,
        "labelled_cards": 0,
        "repeat_groups_found": len(repeat_groups(full, 2, 7)),
        "p50_latency_ms": None,
        "tokens_per_s": None,
        "cost_per_100_cards_usd": None,
        "gpu": "AMD GPUs via AMD Token Factory",
        "model": None,
    }

    MOCKS.mkdir(exist_ok=True)
    with open(MOCKS / "cards.json", "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(json.dumps(c, ensure_ascii=False) for c in cards) + "\n]\n")
    with open(MOCKS / "knowledge.json", "w", encoding="utf-8") as f:
        json.dump(knowledge, f, ensure_ascii=False, indent=1)
        f.write("\n")
    with open(MOCKS / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
        f.write("\n")

    print(f"{len(cards)} cards, {len(procedures)} procedure groups -> {MOCKS}", file=sys.stderr)
    print(json.dumps(metrics, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
