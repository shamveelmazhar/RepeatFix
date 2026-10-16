from types import SimpleNamespace

import app.hypotheses as hy
import app.workorder as wo
from app.procedures import Hit


def fake_hit():
    chunk = SimpleNamespace(
        ac_number="AC 43.13-1B", paragraph="9-14", page_label="9-12",
        title="Tire Inspection", text="Inspect the tire.",
    )
    return Hit(chunk, 1.0)


def test_work_order_removes_made_up_citations_and_parts(monkeypatch):
    fake = {
        "title": "Check brake",
        "steps": ["Inspect tire [AC 43.13-1B par. 9-14].", "Do a thing [AC 43.13-1B par. 1-1]."],
        "parts": ["P-1", "FAKE-9"],
    }
    monkeypatch.setattr(wo, "chat_json", lambda s, u: (fake, {"ms": 10, "completion_tokens": 5}))
    similar = [{"card": {"id": "a", "action_taken": "x", "parts": ["P-1"], "downtime_hours": 2.0}, "score": 0.5}]
    card = {"component": "Brake", "symptom": "hot", "failure_mode": "brake_overheat"}

    order, _ = wo.make_work_order(card, "hot brake", similar, [fake_hit()], "N1")

    assert "9-14" in order["steps"][0]
    assert "1-1" not in order["steps"][1]
    assert order["parts"] == ["P-1"]
    assert order["est_hours"] == 2.0
    assert order["status"] == "draft"


def test_hypotheses_only_cite_real_cards(monkeypatch):
    fake = {"hypotheses": [
        {"cause": "Worn pins", "confidence": "high", "evidence_card_ids": ["a", "zzz"]},
        {"cause": "A guess", "confidence": "high", "evidence_card_ids": ["zzz"]},
    ]}
    monkeypatch.setattr(hy, "chat_json", lambda s, u: (fake, {"ms": 1, "completion_tokens": 1}))
    similar = [{"card": {"id": "a", "component": "x", "symptom": "y", "failure_mode": "z", "action_taken": ""}, "score": 0.5}]

    result, _ = hy.make_hypotheses("fault", similar)

    assert result[0]["evidence_card_ids"] == ["a"]
    assert result[1]["confidence"] == "low"