import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

from app.assist import get_procedure_index  # noqa: E402
from app.procedures import tokenize  # noqa: E402

QUERIES = [
    "FUME EVENT ON DESCENT IN COCKPIT cockpit",
    "ENG 2 FIRE LOOP B FAULT Engine 2 fire detection loop B",
    "FOUND FWD LH EMERG EXIT LIGHTS INOP forward left emergency exit lights",
    "Number 3 main wheel brake hot after taxi-in, brake temp indication high, crew reports dragging brake main wheel brake",
    "main wheel brake overheat",
    "brake dragging hot after landing",
    "hydraulic leak at wheel well",
    "tire damage found on inspection",
    "corrosion found on landing gear fitting",
    "loose wire connector chafing",
]

index = get_procedure_index()
for query in QUERIES:
    tokens = Counter(tokenize(query))
    ceiling = sum(count * index.idf.get(t, 0) * (index.k1 + 1) for t, count in tokens.items())
    print("\n", query[:80])
    for hit in index.search(query, k=3, docs={"AC 43.13-1B"}):
        print(f"   raw {hit.score:7.2f}   share {hit.score / ceiling:.2f}   par. {hit.chunk.paragraph} {hit.chunk.title}")