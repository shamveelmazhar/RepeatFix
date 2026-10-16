from app.extract import normalise
from app.repeats import repeat_rows


def test_single_digit_chapter_gets_leading_zero():
    card = normalise({"ata_chapter": "5", "failure_mode": "fuel_leak"}, "text", "text")
    assert card["ata_chapter"] == "05"


def test_unknown_failure_mode_becomes_other():
    card = normalise({"failure_mode": "made_up_mode"}, "text", "text")
    assert card["failure_mode"] == "other"


def test_ids_are_unique():
    ids = {normalise({}, "text", "text")["id"] for _ in range(200)}
    assert len(ids) == 200


def make_card(number, date, hours):
    return {
        "id": f"c{number}", "registration": "N1", "aircraft_type": "B737",
        "ata_chapter": "32", "component": "Brake", "failure_mode": "brake_overheat",
        "date": date, "downtime_hours": hours,
    }


def test_repeat_group_numbers():
    cards = [
        make_card(1, "2026-01-01", 2.0),
        make_card(2, "2026-01-11", 3.0),
        make_card(3, "2026-01-21", None),
    ]
    rows = repeat_rows(cards, "aircraft", 2)
    assert len(rows) == 1
    assert rows[0]["count"] == 3
    assert rows[0]["mtbf_days"] == 10.0
    assert rows[0]["downtime_hours"] == 5.0
    assert rows[0]["card_ids"] == ["c1", "c2", "c3"]


def test_single_failure_is_not_a_repeat():
    assert repeat_rows([make_card(1, "2026-01-01", 1.0)], "aircraft", 2) == []