from app.retrieval import Index, card_text

CARDS = [
    {"id": "a", "aircraft_type": "B737", "component": "Main gear brake",
     "symptom": "Brake overheating after taxi", "failure_mode": "brake_overheat"},
    {"id": "b", "aircraft_type": "A321", "component": "Fuel booster pump",
     "symptom": "Fuel leak from wing tank", "failure_mode": "fuel_leak"},
    {"id": "c", "aircraft_type": "B737", "component": "Hydraulic pump",
     "symptom": "Hydraulic fluid leaking", "failure_mode": "hyd_pump_leak"},
]


def make_index():
    return Index(CARDS, card_text)


def test_best_match_is_the_right_card():
    found = make_index().search("brake overheating", k=3)
    assert found[0]["item"]["id"] == "a"


def test_can_exclude_the_card_itself():
    found = make_index().search("brake overheating", k=3, exclude_id="a")
    assert all(r["item"]["id"] != "a" for r in found)


def test_filter_by_aircraft_type():
    found = make_index().search("leak", k=3, keep=lambda c: c["aircraft_type"] == "A321")
    assert [r["item"]["id"] for r in found] == ["b"]


def test_no_match_gives_empty_list():
    assert make_index().search("zzzz qqqq", k=3) == []