import re


def normalise_type(value):
    """'A320-200' and 'a320 200' both become 'a320200'."""
    return re.sub(r"[^a-z0-9]", "", (value or "").lower())


def same_aircraft_type(card_type, wanted):
    """True if the card's type matches. 'A320' matches 'A320-200', but 'A320neo' does not."""
    a, b = normalise_type(card_type), normalise_type(wanted)
    return bool(a and b and (a == b or a.startswith(b) or b.startswith(a)))