import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

import app.cache as cache  # noqa: E402
from app.assist import refine_failure_mode  # noqa: E402
from app.main import CARDS  # noqa: E402
from app.repeats import repeat_history  # noqa: E402

for key, entry in list(cache.load().items()):
    result = entry["result"]
    card = result["structured"]
    before = card["failure_mode"]
    refine_failure_mode(card, result["similar"])
    result["repeat_history"] = repeat_history(
        CARDS, card["failure_mode"], card.get("registration"), card.get("aircraft_type"), card.get("ata_chapter")
    )
    cache.save(key, entry["fault_text"], result)
    history = result["repeat_history"]
    print(entry["fault_text"], "|", before, "->", card["failure_mode"], "| repeats:", history and history["count"])