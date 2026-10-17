import app.cache as cache


def fresh(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "CACHE_FILE", tmp_path / "cache.json")
    monkeypatch.setattr(cache, "_entries", None)


def test_same_fault_in_other_words_is_found(monkeypatch, tmp_path):
    fresh(monkeypatch, tmp_path)
    cache.save(cache.make_key("Brake hot!", "N1", None), "Brake hot!", {"id": "wo-1"})
    assert cache.get(cache.make_key("brake  HOT", "N1", None)) is not None
    assert cache.get(cache.make_key("brake hot", "N2", None)) is None


def test_closest_needs_enough_overlap(monkeypatch, tmp_path):
    fresh(monkeypatch, tmp_path)
    cache.save("k", "number 3 main wheel brake hot after taxi", {"id": "wo-1"})
    assert cache.closest("brake hot after taxi") is not None
    assert cache.closest("cabin pressure controller fault") is None


def test_saved_answer_is_marked_and_untimed(monkeypatch, tmp_path):
    fresh(monkeypatch, tmp_path)
    entry = {"fault_text": "brake hot", "result": {"id": "wo-1", "timing": {"total_ms": 40000, "tokens_per_s": 11}}}
    first = cache.as_cached(entry, 0.0, fallback=True)
    assert first["cached"] is True
    assert first["cached_for"] == "brake hot"
    assert first["id"] != "wo-1"
    assert first["timing"]["tokens_per_s"] is None
    assert entry["result"]["id"] == "wo-1"  # the saved original is untouched