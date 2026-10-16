import time
import uuid

from app.extract import extract_card
from app.hypotheses import make_hypotheses
from app.procedures import ProcedureIndex, to_procedure
from app.repeats import repeat_history
from app.retrieval import similar_cards
from app.workorder import make_work_order
from app.aircraft import same_aircraft_type

_procedure_index = None


def get_procedure_index():
    """Load the AC 43.13 chunks once. The first request is slower because of this."""
    global _procedure_index
    if _procedure_index is None:
        _procedure_index = ProcedureIndex.load()
    return _procedure_index


def run_assist(cards, fault_text, asset=None, aircraft_type=None):
    started = time.time()

    # 1. Turn the fault text into a JobCard
    card, _ = extract_card(fault_text, source="text")
    if asset:
        card["registration"] = asset
    if aircraft_type:
        card["aircraft_type"] = aircraft_type

        candidates = similar_cards(cards, query, k=30)
    if aircraft_type:
        typed = [c for c in candidates if same_aircraft_type(c["card"].get("aircraft_type"), aircraft_type)]
        candidates = typed if len(typed) >= 3 else typed + [c for c in candidates if c not in typed]
    same = [c for c in candidates if c["card"].get("ata_chapter") == card.get("ata_chapter")]
    other = [c for c in candidates if c not in same]
    similar = same[:5] if len(same) >= 3 else (same + other)[:5]

    # 3. Causes and a draft work order
    hypotheses, h_stats = make_hypotheses(fault_text, similar)
    work_order, w_stats = make_work_order(
        card, fault_text, similar, hits, asset or card.get("registration")
    )

    # 4. Timing, measured. tokens_per_s covers the two writing calls.
    total_ms = int((time.time() - started) * 1000)
    tokens = [h_stats["completion_tokens"], w_stats["completion_tokens"]]
    seconds = (h_stats["ms"] + w_stats["ms"]) / 1000
    tokens_per_s = None
    if all(t is not None for t in tokens) and seconds > 0:
        tokens_per_s = round(sum(tokens) / seconds, 1)

    return {
        "id": f"wo-{uuid.uuid4().hex[:8]}",
        "structured": card,
        "similar": similar,
        "hypotheses": hypotheses,
        "procedures": [to_procedure(h.chunk, query) for h in hits],
        "work_order": work_order,
        "repeat_history": repeat_history(
            cards, card["failure_mode"], asset or card.get("registration"), aircraft_type
        ),
        "timing": {"total_ms": total_ms, "tokens_per_s": tokens_per_s},
    }