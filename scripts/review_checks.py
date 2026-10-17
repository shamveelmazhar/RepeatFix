import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

import app.cache as cache  # noqa: E402
from app.assist import get_procedure_index  # noqa: E402
from app.main import CARDS  # noqa: E402
from app.repeats import event_dates  # noqa: E402

print("1. MANUAL REFERENCES FROM THE SAVED WORK ORDERS (cards containing each text)")
for text in ("05-50-00", "21-00-00-615-813", "21-21-41", "33-51", "M1675"):
    count = sum(text in ((c.get("raw_text") or "") + (c.get("action_taken") or "")) for c in CARDS)
    print("  ", text, "->", count, "cards")

print("\n2. EVIDENCE CARDS FOR THE FIRST FUME HYPOTHESIS")
by_id = {c["id"]: c for c in CARDS}
for entry in cache.load().values():
    if entry["fault_text"].startswith("FUME"):
        for card_id in entry["result"]["hypotheses"][0]["evidence_card_ids"]:
            c = by_id[card_id]
            print("  ", card_id, "|", (c.get("symptom") or "")[:120], "| ACTION:", (c.get("action_taken") or "")[:200])

print("\n3. N926NK SMOKE_OR_ODOR")
c = [x for x in CARDS if x.get("registration") == "N926NK" and x["failure_mode"] == "smoke_or_odor"]
print("  reports:", len(c), "| by ATA:", dict(Counter(x["ata_chapter"] for x in c)))
dates = [date.fromisoformat(x["date"]) for x in c if x.get("date")]
print("  events 7 days apart:", len(event_dates(dates, 7)))
ata21 = [date.fromisoformat(x["date"]) for x in c if x.get("date") and x["ata_chapter"] == "21"]
print("  ATA 21 only, events 7 days apart:", len(event_dates(ata21, 7)))

print("\n4. PROCEDURE MATCH SCORES")
tests = [(e["fault_text"], e["result"]["structured"]) for e in cache.load().values()]
tests.append((
    "Number 3 main wheel brake hot after taxi-in, brake temp indication high, crew reports dragging brake",
    {"component": "main wheel brake", "symptom": "Brake hot after taxi-in, brake temp indication high, crew reports dragging brake"},
))
for fault, card in tests:
    query = f"{fault} {card.get('component') or ''}".strip()
    hits = get_procedure_index().search(f"{query} {card.get('symptom') or ''}", k=3, docs={"AC 43.13-1B"})
    print("\n  ", fault)
    for h in hits:
        print("     ", h.score, "par.", h.chunk.paragraph, h.chunk.title)