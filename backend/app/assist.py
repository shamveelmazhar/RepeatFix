import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.aircraft import same_aircraft_type
from app.extract import extract_card
from app.hypotheses import make_hypotheses
from app.procedures import ProcedureIndex, check_citations, cite_tag, to_procedure
from app.repeats import GENERIC_MODES, repeat_history
from app.retrieval import similar_cards
from app.workorder import make_work_order

AC_FILE = Path(__file__).resolve().parents[2] / "data" / "procedures" / "ac_43-13-1b.jsonl"

_procedure_index = None


def get_procedure_index():
    """Load AC 43.13-1B plus the three FAA handbooks so assist can cite any of them."""
    global _procedure_index
    if _procedure_index is None:
        _procedure_index = ProcedureIndex.load()
    return _procedure_index


def find_procedures(fault_text, card):
    """Candidate AC 43.13 paragraphs. The work order decides which ones it really uses."""
    query = f"{fault_text} {card.get('component') or ''}".strip()
    hits = get_procedure_index().search(
        f"{query} {card.get('symptom') or ''}", k=3
    )
    return query, hits


def pick_similar(cards, query, card, aircraft_type):
    """Best 5 past cards. Prefer the chosen aircraft type, then the same ATA chapter."""
    candidates = similar_cards(cards, query, k=30)

    if aircraft_type:
        typed = [c for c in candidates if same_aircraft_type(c["card"].get("aircraft_type"), aircraft_type)]
        typed_ids = {c["card"]["id"] for c in typed}
        rest = [c for c in candidates if c["card"]["id"] not in typed_ids]
        candidates = typed if len(typed) >= 3 else typed + rest

    chapter = card.get("ata_chapter")
    same = [c for c in candidates if chapter and c["card"].get("ata_chapter") == chapter]
    same_ids = {c["card"]["id"] for c in same}
    other = [c for c in candidates if c["card"]["id"] not in same_ids]
    return same[:5] if len(same) >= 3 else (same + other)[:5]


def refine_failure_mode(card, similar):
    """Use the failure mode that at least 4 of the 5 most similar cards share.
    This keeps the alert consistent with how the data was labelled."""
    votes = Counter(
        s["card"]["failure_mode"] for s in similar if s["card"].get("failure_mode")
    )
    if votes:
        mode, count = votes.most_common(1)[0]
        if count >= 4 and card["failure_mode"] != mode:
            card["failure_mode"] = mode
            
def run_assist(cards, fault_text, asset=None, aircraft_type=None):
    t0 = time.time()

    # 1. Turn the fault text into a JobCard (one model call)
    card, _ = extract_card(fault_text, source="text")
    if asset:
        card["registration"] = asset
    if aircraft_type:
        card["aircraft_type"] = aircraft_type
    tail = card.get("registration")
    t1 = time.time()

    # 2. Find candidate procedures and similar past cards (no model call)
    query, hits = find_procedures(fault_text, card)
    similar = pick_similar(cards, query, card, aircraft_type)
    refine_failure_mode(card, similar)
    t2 = time.time()

    # 3. Causes and work order at the same time (two model calls)
    with ThreadPoolExecutor(max_workers=2) as pool:
        h_job = pool.submit(make_hypotheses, fault_text, similar)
        w_job = pool.submit(make_work_order, card, fault_text, similar, hits, tail)
        hypotheses, h_stats = h_job.result()
        work_order, w_stats = w_job.result()
    t3 = time.time()

    # 4. Show only the procedures the work order really cites (unknown citations were already removed)
    cited, _ = check_citations(" ".join(work_order["steps"]), hits)
    used = [h for h in hits if cite_tag(h.chunk) in cited]

    # 5. Timing. tokens_per_s is the average speed of the two writing calls,
    # counting thinking tokens, network and waiting. It is a measured end-to-end rate.
    rates = []
    for stats in (h_stats, w_stats):
        if stats["completion_tokens"] and stats["ms"] > 0:
            rates.append(stats["completion_tokens"] / (stats["ms"] / 1000))
    tokens_per_s = round(sum(rates) / len(rates), 1) if rates else None

    print(
        f"assist stages: extract {int((t1 - t0) * 1000)} ms, "
        f"search {int((t2 - t1) * 1000)} ms, writing {int((t3 - t2) * 1000)} ms"
    )

    return {
        "id": f"wo-{uuid.uuid4().hex[:8]}",
        "structured": card,
        "similar": similar,
        "hypotheses": hypotheses,
        "procedures": [to_procedure(h.chunk, query) for h in used],
        "work_order": work_order,
        "repeat_history": repeat_history(
            cards, card["failure_mode"], tail, aircraft_type, card.get("ata_chapter")
        ),
        "timing": {"total_ms": int((t3 - t0) * 1000), "tokens_per_s": tokens_per_s},
    }