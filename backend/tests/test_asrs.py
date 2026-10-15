import json
from pathlib import Path

import pytest

from app import asrs, vocab

FIXTURE = Path(__file__).parent / "fixtures" / "asrs_excerpt.txt"
SAMPLE = Path(__file__).resolve().parents[2] / "data" / "samples" / "asrs_mechanic.jsonl"

# Every key of JobCard in docs/API.md.
JOBCARD_KEYS = {
    "id", "source", "date", "aircraft_type", "registration", "ata_chapter", "ata_name",
    "component", "symptom", "failure_mode", "action_taken", "parts", "downtime_hours", "raw_text",
}


@pytest.fixture(scope="module")
def reports():
    return asrs.parse_report_set(asrs.read_text(FIXTURE))


@pytest.fixture(scope="module")
def cards(reports):
    return {c["id"]: c for c in map(asrs.to_job_card, reports)}


def test_skips_synopsis_list_and_splits_reports(reports):
    # The synopsis list repeats each ACN; only the narrative blocks become reports.
    assert [r.acn for r in reports] == ["2069879", "2062965", "2061955", "2032484"]


def test_reads_labelled_fields(reports):
    r = reports[0]
    assert r.date == "202401"
    assert asrs._first(r.aircraft[0], "Make Model Name") == "A321"
    assert asrs._first(r.components[0], "Aircraft Component") == "Fuel Booster Pump"
    assert asrs._first(r.components[0], "Problem") == "Design"
    assert r.fields["Primary Problem"] == ["Procedure"]


def test_page_break_does_not_split_sections(reports):
    # The fixture has a form feed before "Assessments" in the first report.
    assert reports[0].fields["Contributing Factors / Situations"][0] == "Aircraft"


def test_multiple_narratives_and_reflowed_text(reports):
    r = reports[1]
    assert len(r.narratives) == 2
    assert r.narratives[0].startswith("On the night of Day 0 going into Day 1")
    assert "\n" not in r.narratives[0]  # PDF line wraps are joined
    assert r.synopsis.startswith("Maintenance technicians reported")


def test_card_matches_api_contract(cards):
    for card in cards.values():
        assert JOBCARD_KEYS <= card.keys()
        assert card["source"] == "asrs"
        assert card["registration"] is None
        assert card["parts"] == []
        assert card["failure_mode"] in vocab.FAILURE_MODES_BY_CODE
        assert card["ata_name"] == vocab.ata_name(card["ata_chapter"])


def test_card_keeps_report_id_for_citation(cards):
    card = cards["asrs-2069879"]
    assert card["asrs"]["acn"] == "2069879"
    assert card["raw_text"].startswith("Synopsis: Aircraft Technician reported")
    assert "Narrative 1: Aircraft X had an open discrepancy" in card["raw_text"]


def test_normalises_equipment_and_failure(cards):
    card = cards["asrs-2069879"]
    assert card["date"] == "2024-01-01"
    assert card["aircraft_type"] == "A321"
    assert (card["ata_chapter"], card["ata_name"]) == ("28", "Fuel")
    assert card["component"] == "Fuel Booster Pump"
    assert card["failure_mode"] == "fuel_leak"
    assert asrs.is_clean(card)


def test_placeholder_aircraft_type_is_unknown(cards):
    card = cards["asrs-2062965"]  # "Commercial Fixed Wing"
    assert card["aircraft_type"] == "Unknown"
    assert card["ata_chapter"] == "27"
    assert card["failure_mode"] == "flap_drive_fault"
    assert not asrs.is_clean(card)


def test_report_without_component_falls_back_to_text(cards):
    card = cards["asrs-2061955"]  # fire bottle shipping, no Component section
    assert card["aircraft_type"] == "CRJ200"
    assert card["ata_chapter"] == vocab.GENERAL_ATA
    assert card["component"] == "Not stated"
    assert card["failure_mode"] == "hazmat_handling"


def test_uses_reporters_aircraft_when_several(cards):
    card = cards["asrs-2032484"]  # towing event: our B777 struck another aircraft
    assert card["aircraft_type"] == "B777-200"
    assert card["failure_mode"] == "ground_handling"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("B737 Undifferentiated or Other Model", "B737"),
        ("B737 MAX Series Undifferentiated", "B737 MAX"),
        ("B787 Dreamliner Undifferentiated or Other Model", "B787"),
        ("Regional Jet 200 ER/LR (CRJ200)", "CRJ200"),
        ("B767-300 and 300 ER", "B767-300"),
        ("No Aircraft", "Unknown"),
        (None, "Unknown"),
    ],
)
def test_clean_aircraft_type(raw, expected):
    assert asrs.clean_aircraft_type(raw) == expected


@pytest.mark.parametrize(
    "ata, text, problem, expected",
    [
        ("32", "Technician reported brake rotor drive clips cracked.", "Failed", "brake_component_crack"),
        ("24", "IDG drain plug found cracked from over-torquing.", None, "idg_servicing_error"),
        ("57", "Heavy corrosion found on fuel tank components.", None, "corrosion"),
        ("25", "Missing insulation in the cargo pit.", "Malfunctioning", "component_malfunction"),
        ("25", "Nothing to match here.", None, "other"),
    ],
)
def test_failure_mode_rules(ata, text, problem, expected):
    assert vocab.failure_mode(ata, text, problem)["code"] == expected


def test_ata_mapping():
    assert vocab.ata_for_component("Wheels/Tires/Brakes") == "32"
    assert vocab.ata_for_component("Unlisted Thing") is None
    assert vocab.ata_from_text("Technician found a hydraulic leak.") == "29"
    assert vocab.ata_from_text("Storekeeper shipped a hazmat parcel.") == vocab.GENERAL_ATA


def test_cli_writes_jsonl(tmp_path, capsys):
    out = tmp_path / "cards.jsonl"
    assert asrs.main([str(FIXTURE), "-o", str(out)]) == 0
    lines = out.read_text().splitlines()
    assert len(lines) == 4
    assert json.loads(lines[0])["id"] == "asrs-2069879"
    assert "4 reports parsed, 1 clean" in capsys.readouterr().err


def test_committed_sample_is_valid():
    cards = [json.loads(line) for line in SAMPLE.read_text(encoding="utf-8").splitlines()]
    assert len(cards) == 50
    assert len({c["id"] for c in cards}) == 50
    for card in cards:
        assert JOBCARD_KEYS <= card.keys()
        assert card["failure_mode"] in vocab.FAILURE_MODES_BY_CODE
