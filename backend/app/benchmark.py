import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS_FILE = ROOT / "data" / "benchmark" / "results.json"


def load_results():
    try:
        with open(RESULTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_results(results):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)