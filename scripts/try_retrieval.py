import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import CARDS  # noqa: E402
from app.retrieval import similar_cards, similar_procedures  # noqa: E402

fault = " ".join(sys.argv[1:]) or "brake overheating after taxi"
print("Fault:", fault, "\n")

print("--- Similar cards ---")
for r in similar_cards(CARDS, fault, k=5):
    c = r["card"]
    print(r["score"], c["id"], c.get("aircraft_type"), "|", c.get("component"), "|", (c.get("symptom") or "")[:80])

print("\n--- Similar procedure chunks ---")
for r in similar_procedures(fault, k=3):
    print(r["score"], {k: str(v)[:70] for k, v in r["chunk"].items() if k != "text"})