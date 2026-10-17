import json
import re
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_FILE = ROOT / "data" / "cache" / "assist_cache.json"

_lock = threading.Lock()
_entries = None


def normalise_text(text):
    """'Brake HOT!' and 'brake  hot' become the same text."""
    return " ".join(re.findall(r"[a-z0-9]+", (text or "").lower()))


def make_key(fault_text, asset=None, aircraft_type=None):
    # The answer depends on the tail and aircraft type too, so they are part of the key
    return "|".join([normalise_text(fault_text), normalise_text(asset), normalise_text(aircraft_type)])


def load():
    global _entries
    if _entries is None:
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                _entries = json.load(f)
        except (OSError, ValueError):
            _entries = {}
    return _entries


def get(key):
    return load().get(key)


def save(key, fault_text, result):
    with _lock:
        entries = load()
        entries[key] = {"fault_text": fault_text, "result": result}
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = CACHE_FILE.with_suffix(".tmp")
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False)
        temp.replace(CACHE_FILE)


def closest(fault_text, min_overlap=0.2):
    """The saved fault that shares the most words, or None if nothing is close enough."""
    words = set(normalise_text(fault_text).split())
    best, best_score = None, 0.0
    for entry in load().values():
        other = set(normalise_text(entry["fault_text"]).split())
        if not words or not other:
            continue
        score = len(words & other) / len(words | other)
        if score > best_score:
            best, best_score = entry, score
    return best if best_score >= min_overlap else None


def as_cached(entry, started, fallback=False):
    """A copy of a saved answer, marked as saved, with honest timing."""
    result = json.loads(json.dumps(entry["result"]))  # a separate copy
    result["id"] = f"wo-{uuid.uuid4().hex[:8]}"
    result["cached"] = True
    if fallback:
        result["cached_for"] = entry["fault_text"]  # which saved fault this answer is for
    result["timing"] = {"total_ms": int((time.time() - started) * 1000), "tokens_per_s": None}
    return result