"""Work out how often a recorded fix did not stick, from the full SDR build.

A fix "did not stick" when the same problem (same aircraft, ATA chapter and failure
mode) was reported again 7 to 90 days later. Reports under 7 days apart count as one
event, the same rule the Repeat failures screen uses. We only count:
  - system faults (not structure chapters 51-57, not corrosion, cracks or dents),
  - reports with a named problem (not "Component malfunction" or "Other"),
  - reports where a corrective action was written down,
  - reports at least 90 days before the newest report, so each one had a full 90 days
    in which it could come back.

SDR only holds what operators chose to report to the FAA, so this is a lower bound.

Run from the repo root:
    python scripts/build_insights.py /mnt/project-files/sdr/sdr_cards_2024_2026.jsonl.gz

Writes frontend/mocks/insights.json, which the Results screen reads in every mode.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.sdr import STRUCTURE_ATA  # noqa: E402

OUT = ROOT / "frontend" / "mocks" / "insights.json"
WINDOW_DAYS = 90
SAME_EVENT_DAYS = 7
SKIP_MODES = {"corrosion", "crack_found", "structural_damage", "component_malfunction", "other"}


def read_jsonl(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def fixes_that_came_back(cards: list[dict], window: int = WINDOW_DAYS) -> dict:
    newest = max(date.fromisoformat(c["date"]) for c in cards if c["date"])
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for c in cards:
        if (c["registration"] and c["date"] and c["ata_chapter"] not in STRUCTURE_ATA
                and c["failure_mode"] not in SKIP_MODES):
            groups[(c["registration"], c["ata_chapter"], c["failure_mode"])].append(c)

    fixes = came_back = 0
    for members in groups.values():
        members.sort(key=lambda c: c["date"])
        events, last = [], None
        for c in members:
            d = date.fromisoformat(c["date"])
            if last is None or (d - last).days >= SAME_EVENT_DAYS:
                events.append((d, c))
                last = d
        for i, (d, c) in enumerate(events):
            if (newest - d).days < window or not (c.get("action_taken") or "").strip():
                continue
            fixes += 1
            if i + 1 < len(events) and (events[i + 1][0] - d).days <= window:
                came_back += 1

    return {
        "fixes": fixes,
        "came_back": came_back,
        "share": round(came_back / fixes, 4) if fixes else None,
        "window_days": window,
        "newest_report": newest.isoformat(),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("full", type=Path, help="full SDR build (jsonl or jsonl.gz)")
    args = ap.parse_args(argv)

    result = {
        "_note": "Built by scripts/build_insights.py from the full FAA SDR build (2024-2026).",
        "fix_did_not_stick": fixes_that_came_back(read_jsonl(args.full)),
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
