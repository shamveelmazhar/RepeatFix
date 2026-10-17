import json
import sys
from pathlib import Path

# Let this script find the backend code
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.extract import extract_card  # noqa: E402

sample = ROOT / "data" / "samples" / "asrs_mechanic.jsonl"
with open(sample, encoding="utf-8") as f:
    original = json.loads(f.readline())

card, ms = extract_card(original["raw_text"], source="asrs")

print(json.dumps(card, indent=2)[:1500])
print("Time:", ms, "ms")
print("failure_mode  model:", card["failure_mode"], "| teammate:", original["failure_mode"])
print("ata_chapter   model:", card["ata_chapter"], "| teammate:", original["ata_chapter"])