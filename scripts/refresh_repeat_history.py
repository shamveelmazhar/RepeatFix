import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

import app.cache as cache  # noqa: E402
from app.main import CARDS  # noqa: E402
from app.repeats import repeat_history  # noqa: E402

for key, entry in list(cache.load().items()):
    result = entry["result"]
    card = result["structured"]
    result["repeat_history"] = repeat_history(
        CARDS, card["failure_mode"], card.get("registration"), card.get("aircraft_type")
    )
    cache.save(key, entry["fault_text"], result)
    history = result["repeat_history"]
    print(entry["fault_text"], "->", history and history["count"])