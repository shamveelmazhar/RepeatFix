"""Controlled vocabularies: ATA chapters and failure modes.

Failure modes are keyed by ATA chapter. A mode with ``ata=None`` is generic and
can sit under any chapter. The rules here are deterministic keyword matches used
to normalise ASRS records; the LLM extraction step can refine them later but must
only pick codes from ``FAILURE_MODES``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Not a real ATA chapter: used for reports about process or ground handling with
# no aircraft system involved (hazmat shipping, towing, paperwork).
GENERAL_ATA = "00"

# ATA iSpec 2200 chapter names (mirrors frontend/lib/ata.ts, plus 00, rotorcraft and the other
# chapters FAA SDR JASC codes use).
ATA_NAMES: dict[str, str] = {
    "00": "General / Ground Operations",
    "05": "Time Limits / Inspections",
    "11": "Placards & Markings",
    "12": "Servicing",
    "14": "Hardware",
    "21": "Air Conditioning & Pressurization",
    "22": "Auto Flight",
    "23": "Communications",
    "24": "Electrical Power",
    "25": "Equipment / Furnishings",
    "26": "Fire Protection",
    "27": "Flight Controls",
    "28": "Fuel",
    "29": "Hydraulic Power",
    "30": "Ice & Rain Protection",
    "31": "Indicating / Recording",
    "32": "Landing Gear",
    "33": "Lights",
    "34": "Navigation",
    "35": "Oxygen",
    "36": "Pneumatic",
    "37": "Vacuum",
    "38": "Water / Waste",
    "45": "Central Maintenance System",
    "49": "Auxiliary Power Unit",
    "51": "Structures – General",
    "52": "Doors",
    "53": "Fuselage",
    "54": "Nacelles / Pylons",
    "55": "Stabilizers",
    "56": "Windows",
    "57": "Wings",
    "61": "Propellers",
    "62": "Main Rotor",
    "63": "Main Rotor Drive",
    "64": "Tail Rotor",
    "65": "Tail Rotor Drive",
    "67": "Rotors Flight Control",
    "71": "Power Plant",
    "72": "Engine",
    "73": "Engine Fuel & Control",
    "74": "Ignition",
    "75": "Engine Air",
    "76": "Engine Controls",
    "77": "Engine Indicating",
    "78": "Exhaust / Thrust Reverser",
    "79": "Oil",
    "80": "Starting",
    "81": "Turbines",
    "82": "Water Injection",
    "83": "Accessory Gearboxes",
    "85": "Reciprocating Engine",
}


def ata_name(chapter: str | None) -> str:
    return ATA_NAMES.get(chapter or "", "Other")


# ASRS "Aircraft Component" taxonomy -> ATA chapter. Covers the maintenance report set
# plus the common components we expect in larger ASRS exports.
ASRS_COMPONENT_ATA: dict[str, str] = {
    "ac generator/alternator": "24",
    "aircraft furnishing": "25",
    "apu": "49",
    "battery": "24",
    "drinkable/waste water syst": "38",
    "electrical wiring & connectors": "24",
    "engine": "72",
    "engine control": "76",
    "escape rope": "25",
    "exterior pax/crew door": "52",
    "fire extinguishing system": "26",
    "flap control (trailing & leading edge)": "27",
    "fuel booster pump": "28",
    "fuel tank": "28",
    "fuselage nose cone": "53",
    "gear up lock": "32",
    "generator drive": "24",
    "hydraulic system": "29",
    "ils/vor": "34",
    "main gear": "32",
    "nose gear": "32",
    "oxygen system/portable": "35",
    "pitot-static system": "34",
    "powerplant fuel system": "73",
    "pressurization system": "21",
    "reciprocating engine assembly": "72",
    "service/access door": "52",
    "tail rotor drive gearbox": "65",
    "turbine engine": "72",
    "turbine engine thrust reverser": "78",
    "wheel assemblies": "32",
    "wheels/tires/brakes": "32",
    "wing access panel": "57",
}

# Free-text fallbacks when ASRS gives no component: (pattern, ATA, component name).
# Order matters: more specific first.
TEXT_COMPONENT_RULES: list[tuple[str, str, str]] = [
    (r"thrust reverser", "78", "Thrust reverser"),
    (r"bird strike", "72", "Engine inlet"),
    (r"fire (extinguisher|bottle|detection)|extinguisher", "26", "Fire protection"),
    (r"fuel (booster )?pump", "28", "Fuel pump"),
    (r"\bfuel\b", "28", "Fuel system"),
    (r"\bIDG\b|generator", "24", "Generator drive"),
    (r"\bbrake", "32", "Wheels/Tires/Brakes"),
    (r"landing gear|\bgear\b|uplock", "32", "Landing gear"),
    (r"hydraulic", "29", "Hydraulic system"),
    (r"oxygen", "35", "Oxygen system"),
    (r"\bflaps?\b|slat|aileron|elevator|rudder", "27", "Flight controls"),
    (r"\bdoor\b", "52", "Door"),
    (r"radome|nose cone|fuselage", "53", "Fuselage"),
    (r"\bwing\b", "57", "Wing structure"),
    (r"\bAPU\b", "49", "APU"),
    (r"\bengine\b", "72", "Engine"),
]

# Reports about handling, shipping or moving the aircraft rather than a system fault.
GROUND_OPS_RE = re.compile(
    r"hazmat|dangerous goods|\bDG\b|shipping|shipment|parcel|\btow(ing|ed)?\b|marshal|chock"
    r"|ground encounter|service vehicle",
    re.I,
)


def ata_for_component(component: str | None) -> str | None:
    if not component:
        return None
    return ASRS_COMPONENT_ATA.get(component.strip().lower())


def _component_rule(text: str) -> tuple[str, str] | None:
    for pattern, ata, name in TEXT_COMPONENT_RULES:
        if re.search(pattern, text, re.I):
            return ata, name
    return None


def ata_from_text(synopsis_and_narrative: str) -> str:
    """Pick an ATA chapter from free text; synopsis first since narratives wander."""
    synopsis = synopsis_and_narrative.split("\n", 1)[0]
    if GROUND_OPS_RE.search(synopsis):
        return GENERAL_ATA
    hit = _component_rule(synopsis)
    return hit[0] if hit else GENERAL_ATA


def component_from_text(synopsis_and_narrative: str) -> str | None:
    synopsis = synopsis_and_narrative.split("\n", 1)[0]
    if GROUND_OPS_RE.search(synopsis):
        return None
    hit = _component_rule(synopsis)
    return hit[1] if hit else None


@dataclass(frozen=True)
class FailureMode:
    code: str
    label: str
    ata: str | None  # None = generic, valid under any chapter
    pattern: str = ""  # regex matched against synopsis, then narrative


FAILURE_MODES: list[FailureMode] = [
    # System-specific modes (also the ones used by the frontend mock fixtures).
    FailureMode("fuel_leak", "Fuel leak or spill", "28", r"fuel (leak|spill)|\bspill"),
    FailureMode("fuel_qty_indication", "Fuel quantity indication fault", "28", r"fuel (quantity|qty)"),
    FailureMode("fuel_nozzle_leak", "Fuel nozzle leak", "73", r"fuel nozzle"),
    FailureMode("flap_drive_fault", "Flap drive or track fault", "27", r"\bflaps?\b|track \d"),
    FailureMode("brake_overheat", "Brake overheat / dragging brake", "32", r"brake.*(overheat|drag|temp)|fuse plug"),
    FailureMode("brake_component_crack", "Brake component cracked", "32", r"(rotor|drive clip|brake).*crack|crack.*brake"),
    FailureMode("brake_lockup", "Brakes locked up", "32", r"lock(ed)? up"),
    FailureMode("tire_damage", "Tire damage", "32", r"\btire"),
    FailureMode("gear_rigging_error", "Landing gear part installed wrong", "32", r"uplock|upside|safety wire|valve stem"),
    FailureMode("idg_low_oil_pressure", "IDG low oil pressure", "24", r"IDG.*oil pressure"),
    FailureMode("idg_servicing_error", "IDG drain plug or servicing fault", "24", r"IDG|drain plug|generator drive"),
    FailureMode("wiring_connector_fault", "Wiring or connector fault", "24", r"connector|harness|wiring"),
    FailureMode("generator_fault", "Generator fault", "24", r"generator"),
    FailureMode("hyd_pump_leak", "Hydraulic pump leak", "29", r"hydraulic pump|\bEDP\b|hyd.*leak"),
    FailureMode("hyd_system_failure", "Hydraulic system failure", "29", r"hydraulic (system )?failure|gear retraction"),
    FailureMode("thrust_reverser_fault", "Thrust reverser fault", "78", r"reverser"),
    FailureMode("door_actuator_fault", "Door or assist actuator fault", "52", r"actuator|\bdoor\b"),
    FailureMode("panel_missing", "Panel missing or departed", None, r"panels? (departed|missing)|missing panel"),
    FailureMode("fire_bottle_discharge", "Fire bottle discharged", "26", r"discharge"),
    FailureMode("gearbox_cap_missing", "Gearbox cap not installed", "65", r"cap .*not installed|oil cap"),
    FailureMode("water_leak", "Water leak", "38", r"water leak"),
    FailureMode("bird_strike", "Bird strike", "72", r"bird strike"),
    FailureMode("engine_power_loss", "Engine loss of power", "72", r"loss of power|power loss"),
    FailureMode("pressure_controller_fault", "Cabin pressure controller fault", "21", r"pressure controller"),
    FailureMode("bleed_valve_fault", "Bleed valve fault", "36", r"bleed valve"),
    # System-specific modes common in FAA SDR (added with the SDR ingestion).
    FailureMode("emer_light_battery_fault", "Emergency light or battery fault", "33",
                r"(emer(gency)?|exit|escape|path(way)?|floor prox).{0,40}(light|batt|power supply)|batt(ery)? pack"),
    FailureMode("escape_slide_fault", "Escape slide fault", "25", r"\bslides?\b|girt bar"),
    FailureMode("emergency_equipment_fault", "Emergency equipment fault or missing", "25",
                r"flashlight|megaphone|\bPBE\b|\bELT\b|first aid|life ?vest"),
    FailureMode("oxygen_mask_deploy", "Oxygen masks deployed or fault", "35", r"\bmasks?\b"),
    FailureMode("flight_control_sensor_fault", "Flight control sensor or computer fault", "27",
                r"sensor|transmitter|\bRVDT\b|\bLVDT\b|computer|\bFCE\b|\bSEC\b|\bELAC\b"),
    FailureMode("gear_sensor_fault", "Landing gear sensor or indication fault", "32",
                r"proximity|prox sensor|sensor|gear (disagree|unsafe)|indication"),
    # Generic modes, valid under any chapter.
    FailureMode("corrosion", "Corrosion found", None, r"corro"),
    FailureMode("incorrect_installation", "Incorrect installation or missing hardware", None,
                r"incorrect(ly)? install|upside|reversed|not installed|un-?installed|missing (a )?(bolt|step|part)|mistakenly removed|over-?torqu"),
    FailureMode("manual_or_procedure_gap", "Manual, IPC or MEL procedure unclear", None,
                r"\bAMM\b|manual|\bIPC\b|\bMEL\b|\bEA\b|procedure"),
    FailureMode("hazmat_handling", "Hazmat or parts shipping error", None,
                r"hazmat|dangerous goods|\bDG\b|shipping|shipment|parcel|extinguisher bottles"),
    FailureMode("ground_handling", "Towing or ground handling event", None,
                r"\btow(ing|ed)?\b|marshal|chock|ground encounter|service vehicle"),
    FailureMode("structural_damage", "Structural damage", None, r"damage|\bdent|struck"),
    # Generic modes added with the FAA SDR ingestion, where PartCondition codes them.
    FailureMode("crack_found", "Crack found", None, r"\bcrack"),
    FailureMode("wear_or_chafing", "Worn, chafed or loose", None,
                r"\bworn\b|\bwear\b|chaf|excess(ive)? play|\bloose\b"),
    FailureMode("fluid_leak", "Fluid leak", None, r"\bleak"),
    FailureMode("smoke_or_odor", "Smoke, fumes or odor", None, r"smoke|fume|odou?r|smell"),
    FailureMode("false_warning", "False warning or unwanted activation", None,
                r"false (warning|activation|indication|alarm)|nuisance|uncommanded|inadvertent"),
    FailureMode("low_pressure", "Low pressure (bottle, tire or system)", None, r"low (pressure|press\b)"),
    FailureMode("out_of_adjustment", "Out of adjustment, binding or needs lubrication", None,
                r"out of (adjust|rig)|binding|\bstiff\b|lack of lub"),
    # The part that failed, for SDR reports that only say "failed" or "inoperative".
    # No text pattern: sdr.py picks these from the reported part name, so ASRS
    # narratives are not affected. Names follow the FAA AMT Handbooks.
    FailureMode("fire_detection_fault", "Fire or overheat detection fault", None),
    FailureMode("warning_indication_fault", "Warning message or indicator fault", None),
    FailureMode("battery_power_fault", "Battery or power supply fault", None),
    FailureMode("lighting_fault", "Light, bulb or sign fault", None),
    FailureMode("door_latch_fault", "Door, latch or handle fault", None),
    FailureMode("floor_panel_fault", "Floor panel or seat track defect", None),
    FailureMode("skin_frame_fault", "Skin, frame or fitting defect", None),
    FailureMode("window_fault", "Window or windshield fault", None),
    FailureMode("valve_fault", "Valve fault", None),
    FailureMode("sensor_switch_fault", "Sensor, switch or probe fault", None),
    FailureMode("computer_controller_fault", "Computer, controller or radio fault", None),
    FailureMode("actuator_pump_motor_fault", "Actuator, pump or motor fault", None),
    FailureMode("wiring_relay_fault", "Wiring, connector or relay fault", None),
    FailureMode("seal_bearing_fault", "Seal, bearing or hardware failed", None),
    FailureMode("landing_gear_part_fault", "Landing gear, wheel or brake part fault", None),
    FailureMode("engine_apu_fault", "Engine or APU malfunction", None),
    # Last-resort fallbacks driven by the ASRS "Problem" field.
    FailureMode("component_malfunction", "Component malfunction", None),
    FailureMode("other", "Other / not classified", None),
]

FAILURE_MODES_BY_CODE = {m.code: m for m in FAILURE_MODES}

# ASRS component "Problem" values -> generic fallback.
PROBLEM_FALLBACK = {
    "malfunctioning": "component_malfunction",
    "failed": "component_malfunction",
    "improperly operated": "incorrect_installation",
    "design": "manual_or_procedure_gap",
}


def _as_dict(mode: FailureMode, ata: str | None) -> dict:
    return {"code": mode.code, "label": mode.label, "ata_chapter": mode.ata or ata or GENERAL_ATA}


def failure_mode(ata: str | None, synopsis_and_narrative: str, problem: str | None = None) -> dict:
    """Normalise to one code from FAILURE_MODES.

    Tries the synopsis first, then the full narrative. Within each text, modes
    for this ATA chapter win over generic ones.
    """
    synopsis = synopsis_and_narrative.split("\n", 1)[0]
    specific = [m for m in FAILURE_MODES if m.pattern and m.ata is not None and m.ata == ata]
    generic = [m for m in FAILURE_MODES if m.pattern and m.ata is None]

    for text in (synopsis, synopsis_and_narrative):
        for mode in specific + generic:
            if re.search(mode.pattern, text, re.I):
                return _as_dict(mode, ata)

    fallback = PROBLEM_FALLBACK.get((problem or "").strip().lower(), "other")
    return _as_dict(FAILURE_MODES_BY_CODE[fallback], ata)


def failure_mode_list() -> list[dict]:
    """Shape of GET /api/failure-modes."""
    return [{"code": m.code, "label": m.label, "ata_chapter": m.ata or "*"} for m in FAILURE_MODES]
