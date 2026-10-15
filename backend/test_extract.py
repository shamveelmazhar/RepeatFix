import json
from pathlib import Path

from app.extract import extract_card

sample = Path("../data/samples/asrs_mechanic.jsonl")
with open(sample, encoding="utf-8") as f:
    original = json.loads(f.readline())

card, ms = extract_card(original["raw_text"], source="asrs")

print(json.dumps(card, indent=2)[:1500])
print("Time:", ms, "ms")
print("failure_mode  model:", card["failure_mode"], "| teammate:", original["failure_mode"])
print("ata_chapter   model:", card["ata_chapter"], "| teammate:", original["ata_chapter"])