import json
import re
from pathlib import Path

import pytest

from app import sdr, vocab

FIXTURE = Path(__file__).parent / "fixtures" / "sdr_excerpt.csv"
SAMPLE = Path(__file__).resolve().parents[2] / "data" / "samples" / "sdr_demo.jsonl"

# Every key of JobCard in docs/API.md.
JOBCARD_KEYS = {
    "id", "source", "date", "aircraft_type", "registration", "ata_chapter", "ata_name",
    "component", "symptom", "failure_mode", "action_taken", "parts", "downtime_hours", "raw_text",
}


@pytest.fixture(scope="module")
def cards():
    return {c["id"]: c for c in sdr.read_cards([FIXTURE])}


def test_card_has_jobcard_fields(cards):
    assert len(cards) == 7
    for card in cards.values():
        assert JOBCARD_KEYS <= card.keys()
        assert card["source"] == "sdr"
        assert card["failure_mode"] in vocab.FAILURE_MODES_BY_CODE
        assert card["ata_chapter"] in vocab.ATA_NAMES
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", card["date"])


def test_maps_tail_ata_date_and_record_id(cards):
    card = cards["sdr-DALA2024010200007"]
    assert card["registration"] == "N329NW"
    assert card["date"] == "2024-01-01"
    assert card["aircraft_type"] == "A320-200"
    assert card["ata_chapter"] == "33"
    assert card["ata_name"] == "Lights"
    assert card["sdr"]["control_number"] == "DALA2024010200007"
    assert card["sdr"]["jasc_code"] == "3350"


def test_splits_symptom_and_corrective_action(cards):
    card = cards["sdr-DALA2024010200007"]
    assert card["symptom"].startswith("FOUND BROKEN GROUND WIRE")  # "SHIP 3229 DISC:" stripped
    assert card["action_taken"].startswith("REPAIRED WIRE")
    assert "(LP:" not in card["action_taken"]
    assert card["raw_text"].startswith("SHIP 3229 DISC:")  # raw text is kept as filed


def test_keeps_part_numbers(cards):
    card = cards["sdr-VNAA202407120002"]
    assert card["parts"] == ["601R31707111"]
    assert card["aircraft_type"] == "CRJ700"
    assert card["failure_mode"] == "crack_found"  # PartCondition CRACKED


def test_part_condition_beats_text(cards):
    # Coded CORRODED wins even though the text also talks about a floor beam.
    assert cards["sdr-SWAA2024012637541"]["failure_mode"] == "corrosion"


def test_same_tail_fume_events_are_a_repeat(cards):
    fumes = [c for c in cards.values() if c["registration"] == "N926NK"]
    assert len(fumes) == 3
    assert {c["failure_mode"] for c in fumes} == {"smoke_or_odor"}
    groups = sdr.repeat_groups(cards.values(), min_count=2, min_gap_days=7)
    assert [(g["asset"], g["ata_chapter"], g["failure_mode"], g["count"]) for g in groups] == [
        ("N926NK", "21", "smoke_or_odor", 3)
    ]


@pytest.mark.parametrize("make,model,expected", [
    ("BOEING", "7378H4", "B737-800"),
    ("BOEING", "7377H4", "B737-700"),
    ("BOEING", "737932ER", "B737-900ER"),
    ("BOEING", "7378", "B737 MAX 8"),
    ("BOEING", "717200", "B717-200"),
    ("BOEING", "75724APF", "B757-200F"),
    ("BOEING", "7879", "B787-900"),
    ("AIRBUS", "A321231", "A321-200"),
    ("AIRBUS", "A319114", "A319-100"),
    ("AIRBUS", "A321271NX", "A321neo"),
    ("AIRBUS", "A300F4622R", "A300-600F"),
    ("AIRBUS", "BD5001A11", "A220-300"),
    ("CNDAIR", "CL6002C10", "CRJ700"),
    ("CNDAIR", "CL6002D24", "CRJ900"),
    ("CNDAIR", "CL6002B19", "CRJ200"),
    ("EMB", "ERJ170200LR", "E175"),
    ("EMB", "EMB145LR", "ERJ-145"),
    ("CESSNA", "680A", "Cessna 680A"),
    ("", "", "Unknown"),
])
def test_aircraft_type(make, model, expected):
    assert sdr.aircraft_type(make, model) == expected


@pytest.mark.parametrize("text,symptom,action", [
    ("SHIP 5653 R1 DOOR WILL NOT ARM. CORRECTIVE ACTION: REMOVED DEBRIS DOOR CK GOOD. (4396330)",
     "R1 DOOR WILL NOT ARM", "REMOVED DEBRIS DOOR CK GOOD"),
    ("STEERING INOP CAUTION MSG ON T/O / REMOVED AND REPLACED SELECTOR VALVE. OPS CHECK GOOD",
     "STEERING INOP CAUTION MSG ON T/O", "REMOVED AND REPLACED SELECTOR VALVE. OPS CHECK GOOD"),
    ("ONE CRACK FOUND AT LUG FITTING. FITTING REPLACED REFER EO 4453C024.",
     "ONE CRACK FOUND AT LUG FITTING", "FITTING REPLACED REFER EO 4453C024"),
    ("FUME EVENT ON DESCENT-PERFORMED TSM 05-50-00", "FUME EVENT ON DESCENT", "PERFORMED TSM 05-50-00"),
    ("CRACK GUSSET BS 500D 2024-123931<[01] REPLACED GUSSET IAW SRM 51-10-02",
     "CRACK GUSSET BS 500D", "REPLACED GUSSET IAW SRM 51-10-02"),  # log ref dropped
    ("T/O CONFIG / FLAP DISAGREE", "T/O CONFIG / FLAP DISAGREE", ""),
])
def test_split_discrepancy(text, symptom, action):
    assert sdr.split_discrepancy(text) == (symptom, action)


def test_failure_mode_rules():
    # Physical condition wins.
    assert sdr.failure_mode("52", "AFT CARGO DOOR FRAME", "CORRODED") == "corrosion"
    # A plain door write-up is not a door actuator fault in SDR.
    assert sdr.failure_mode("52", "R1 DOOR WILL NOT ARM", "INOPERATIVE") == "component_malfunction"
    assert sdr.failure_mode("52", "DOOR ASSIST ACTUATOR LEAKING", None) == "door_actuator_fault"
    # Functional condition: the text is more specific, so it goes first.
    assert sdr.failure_mode("33", "EMER LIGHT BATTERY PACK FAILED TEST", "NO TEST") == "emer_light_battery_fault"
    # The AMM reference must not make it a procedure gap.
    assert sdr.failure_mode("29", "PUMP NOISY. REPLACED IAW AMM 29-11", None) == "component_malfunction"
    # A system-specific code is never given under another chapter.
    assert sdr.failure_mode("53", "SKIN", "DISCHARGED") == "component_malfunction"


def test_condition_maps_point_at_real_modes():
    for code in [*sdr.PHYSICAL_CONDITIONS.values(), *sdr.FUNCTIONAL_CONDITIONS.values(),
                 *sdr.SDR_GENERIC_TEXT_MODES, *sdr.SDR_PATTERN_OVERRIDES]:
        assert code in vocab.FAILURE_MODES_BY_CODE, code


def test_min_gap_merges_same_visit_findings():
    def card(i, day, mode="corrosion"):
        return {"id": f"c{i}", "registration": "N1", "date": day, "ata_chapter": "53",
                "failure_mode": mode, "aircraft_type": "B737-800"}

    heavy_check = [card(i, "2025-03-01") for i in range(5)] + [card(9, "2025-03-04")]
    assert sdr.repeat_groups(heavy_check, 2)[0]["count"] == 6
    assert sdr.repeat_groups(heavy_check, 2, min_gap_days=7) == []

    later = heavy_check + [card(10, "2026-01-10")]
    (group,) = sdr.repeat_groups(later, 2, min_gap_days=7)
    assert group["count"] == 2 and group["reports"] == 7
    assert group["years"] == ["2025", "2026"]


def test_demo_sample_is_valid():
    lines = SAMPLE.read_text(encoding="utf-8").splitlines()
    cards = [json.loads(line) for line in lines]
    assert 500 < len(cards) < 5000
    assert len({c["id"] for c in cards}) == len(cards)
    for c in cards:
        assert JOBCARD_KEYS <= c.keys()
        assert c["registration"] and c["date"]
        assert sdr.DEMO_TYPES.match(c["aircraft_type"])
        assert c["failure_mode"] in vocab.FAILURE_MODES_BY_CODE
    summary = sdr.repeat_summary(cards)
    assert summary["tails_with_system_repeats"] == summary["tails"]
    assert summary["repeat_groups_across_years"] > 0
