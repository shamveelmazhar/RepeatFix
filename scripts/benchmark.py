import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import app.extract as ex  # noqa: E402
from app.assist import run_assist  # noqa: E402
from app.benchmark import save_results  # noqa: E402
from app.main import CARDS  # noqa: E402

SAMPLE = ROOT / "data" / "samples" / "asrs_mechanic.jsonl"
N_CARDS = 20

FAULTS = [
    {"fault_text": "Number 3 main wheel brake hot after taxi-in, brake temp indication high, crew reports dragging brake", "asset": "N926NK"},
    {"fault_text": "Fuel leak from right wing inboard fuel pump area found during walkaround", "asset": None},
    {"fault_text": "Hydraulic fluid leaking from system B engine driven pump, low quantity indication", "asset": None},
    {"fault_text": "Left generator fault light on, generator drive disconnect on climb", "asset": None},
    {"fault_text": "Flap asymmetry message, trailing edge flaps stopped at position 5", "asset": None},
]


def chapter_of(value):
    """'00' and None both mean 'no specific ATA chapter'."""
    return None if value in (None, "00") else value


# ---------- Part A: how often the model agrees with the parser labels ----------
with open(SAMPLE, encoding="utf-8") as f:
    labelled = [json.loads(line) for line in f if line.strip()]
chosen = random.Random(42).sample(labelled, min(N_CARDS, len(labelled)))

mode_ok = chapter_ok = strict_chapter_ok = done = 0
extract_ms = []
differences = []
for card in chosen:
    try:
        got, ms = ex.extract_card(card["raw_text"], source="asrs")
    except Exception as error:
        print("FAILED", card["id"], str(error)[:100])
        time.sleep(5)
        continue
    done += 1
    extract_ms.append(ms)
    same_mode = got["failure_mode"] == card["failure_mode"]
    same_chapter = chapter_of(got["ata_chapter"]) == chapter_of(card["ata_chapter"])
    mode_ok += same_mode
    chapter_ok += same_chapter
    strict_chapter_ok += got["ata_chapter"] == card["ata_chapter"]
    if not (same_mode and same_chapter):
        differences.append({
            "id": card["id"],
            "model": [got["failure_mode"], got["ata_chapter"]],
            "parser": [card["failure_mode"], card["ata_chapter"]],
        })
        print(f"DIFFERENT {card['id']}: model {got['failure_mode']}/{got['ata_chapter']} | parser {card['failure_mode']}/{card['ata_chapter']}")
    time.sleep(4)  # stay well under 20 requests per minute

# ---------- Part B: how fast /api/assist is, live (no saved answers) ----------
totals, rates = [], []
for fault in FAULTS:
    try:
        result = run_assist(CARDS, fault["fault_text"], fault["asset"], None)
    except Exception as error:
        print("FAILED assist:", str(error)[:100])
        time.sleep(10)
        continue
    totals.append(result["timing"]["total_ms"])
    if result["timing"]["tokens_per_s"]:
        rates.append(result["timing"]["tokens_per_s"])
    print("assist:", result["timing"])
    time.sleep(10)

if not done or not totals:
    print("Not enough successful calls, nothing saved.")
    sys.exit(1)

results = {
    "model": ex.MODEL,
    "measured_at": time.strftime("%Y-%m-%d %H:%M"),
    "labelled_cards": done,
    "extraction_field_accuracy": round((mode_ok + chapter_ok) / (2 * done), 3),
    "failure_mode_agreement": round(mode_ok / done, 3),
    "ata_chapter_agreement": round(chapter_ok / done, 3),
    "ata_chapter_agreement_strict": round(strict_chapter_ok / done, 3),
    "extraction_p50_ms": int(statistics.median(extract_ms)),
    "assist_runs": len(totals),
    "assist_total_ms_all_runs": totals,
    "p50_latency_ms": int(statistics.median(totals)),
    "tokens_per_s": round(statistics.median(rates), 1) if rates else None,
    "differences": differences,
    "note": "Agreement with the ASRS parser labels, not human labels. ATA '00' and null count as the same.",
}
save_results(results)
print(json.dumps(results, indent=2))