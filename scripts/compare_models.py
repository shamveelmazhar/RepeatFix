import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import app.extract as ex  # noqa: E402

CANDIDATES = ["Qwen3.8-27B", "Gemma-4-31B-IT", "DeepSeek-V4-Flash", "Qwen3.8-Flash-Next"]

sample = ROOT / "data" / "samples" / "asrs_mechanic.jsonl"
with open(sample, encoding="utf-8") as f:
    original = json.loads(f.readline())

print("Teammate's answer:", original["failure_mode"], original["ata_chapter"], "\n")

for name in CANDIDATES:
    ex.MODEL = name
    try:
        card, ms = ex.extract_card(original["raw_text"], source="asrs")
        print(f"{name}: {ms} ms | {card['failure_mode']} | chapter {card['ata_chapter']} | {card['component']}")
    except Exception as error:
        print(f"{name}: FAILED - {str(error)[:150]}")