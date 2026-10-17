import json
from types import SimpleNamespace

import app.extract as extract
import app.retrieval as retrieval
from app.assist import run_assist


class FakeClient:
    """Pretends to be the model. It answers based on which prompt it receives."""

    def __init__(self):
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, model, messages, temperature, max_tokens):
        self.calls += 1
        system = messages[0]["content"]
        if "ONE JSON object" in system:  # extraction
            answer = {
                "aircraft_type": "B737-800", "registration": None, "ata_chapter": "32",
                "component": "Brake", "symptom": "Brake hot after taxi",
                "failure_mode": "brake_overheat", "action_taken": "", "parts": [],
                "downtime_hours": None, "date": None,
            }
        elif "likely causes" in system:  # hypotheses
            answer = {"hypotheses": [
                {"cause": "Worn brake", "confidence": "high", "evidence_card_ids": ["c1", "c2", "c3"]}
            ]}
        else:  # work order
            answer = {"title": "Replace brake", "steps": ["Inspect the brake.", "A certified person must approve."], "parts": []}
        message = SimpleNamespace(content=json.dumps(answer))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=SimpleNamespace(completion_tokens=50))


def make_cards():
    cards = []
    for n in (1, 2, 3):
        cards.append({
            "id": f"c{n}", "source": "sdr", "date": f"2026-0{n}-10", "aircraft_type": "B737-800",
            "registration": "N1", "ata_chapter": "32", "ata_name": "Landing Gear",
            "component": "Brake", "symptom": "Brake hot after taxi, brake temp high",
            "failure_mode": "brake_overheat", "action_taken": "Replaced brake",
            "parts": [], "downtime_hours": 2.0, "raw_text": "brake hot after taxi",
        })
    cards.append({
        "id": "c4", "source": "sdr", "date": "2026-02-01", "aircraft_type": "A320-200",
        "registration": "N2", "ata_chapter": "29", "ata_name": "Hydraulic Power",
        "component": "Pump", "symptom": "Hydraulic pump leak", "failure_mode": "hyd_pump_leak",
        "action_taken": "", "parts": [], "downtime_hours": None, "raw_text": "hyd leak",
    })
    return cards


def run(monkeypatch, **kwargs):
    fake = FakeClient()
    monkeypatch.setattr(extract, "get_client", lambda: fake)
    monkeypatch.setattr(retrieval, "_card_index", None)  # build a fresh index for these cards
    result = run_assist(make_cards(), "brake hot after taxi", **kwargs)
    return result, fake


def test_assist_without_aircraft_type(monkeypatch):
    result, fake = run(monkeypatch)
    assert fake.calls == 3  # extraction, hypotheses, work order
    assert result["structured"]["failure_mode"] == "brake_overheat"
    assert len(result["similar"]) >= 1
    assert result["work_order"]["status"] == "draft"
    assert result["hypotheses"][0]["evidence_card_ids"] == ["c1", "c2", "c3"]
    assert result["repeat_history"]["count"] == 3
    assert result["timing"]["total_ms"] >= 0


def test_assist_with_aircraft_type_and_asset(monkeypatch):
    result, _ = run(monkeypatch, asset="N1", aircraft_type="B737")
    assert result["structured"]["registration"] == "N1"
    assert result["structured"]["aircraft_type"] == "B737"
    assert all(s["card"]["aircraft_type"] == "B737-800" for s in result["similar"][:3])
    assert result["repeat_history"]["count"] == 3

def test_ingest_adds_a_card(monkeypatch):
    monkeypatch.setattr(extract, "get_client", lambda: FakeClient())
    from app.main import CARDS, CARDS_BY_ID, IngestRequest, ingest

    before = len(CARDS)
    result = ingest(IngestRequest(text="Brake hot after taxi"))
    card = result["cards"][0]
    try:
        assert card["failure_mode"] == "brake_overheat"
        assert card["source"] == "text"
        assert len(CARDS) == before + 1
    finally:
        CARDS.pop()
        CARDS_BY_ID.pop(card["id"], None)