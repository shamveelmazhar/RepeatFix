import json
import re
import statistics

from app.llm import chat_json
from app.procedures import CITE_INSTRUCTION, context_block, strip_unknown_citations

SYSTEM = f"""You draft aircraft maintenance work orders for a human to review.
{CITE_INSTRUCTION}

Return ONLY this JSON, with no extra words:
{{"title": "...", "steps": ["..."], "parts": ["..."]}}

Rules:
- 3 to 6 short steps, in the order a mechanic would do them.
- Base the steps on the similar past cards and on the procedure excerpts, and use an excerpt only if it really matches this fault. Ignore an excerpt that is about something else.
- Every step that uses a procedure excerpt must end with its citation in square brackets, like [AC 43.13-1B par. 9-14]. Put each citation in its own brackets and never write a paragraph number outside brackets.
- Mention a manual task number (AMM, TSM, SRM) only if it appears in the similar past cards.
- Do not use the word "torque" or give any number, limit or clearance unless it is written in the excerpts or the past cards.
- If neither the excerpts nor the past cards say how this fault was fixed, write general troubleshooting steps (for example "troubleshoot using the aircraft's fault isolation manual") and do not invent a specific procedure.
- Never invent part numbers. parts: only part numbers that appear in the past cards, else an empty list.
- The last step must say that a certified person must inspect and approve the work.
"""


def short(text, limit):
    return (text or "")[:limit]


def clean(text, hits):
    """Remove made-up citations, then tidy the spaces they leave behind."""
    text = strip_unknown_citations(str(text), hits)
    return re.sub(r"\s+([.,;])", r"\1", text).strip()


def make_work_order(card, fault_text, similar, hits, asset):
    past = [
        {
            "id": s["card"]["id"],
            "action_taken": short(s["card"].get("action_taken"), 200),
            "parts": s["card"].get("parts") or [],
        }
        for s in similar
    ]
    excerpts = context_block(hits) if hits else "No procedure excerpts were found."
    user = (
        f"New fault: {fault_text}\n"
        f"Component: {card.get('component')}\n\n"
        f"Similar past cards:\n{json.dumps(past, indent=1)}\n\n"
        f"Procedure excerpts:\n{excerpts}"
    )
    data, stats = chat_json(SYSTEM, user)

    # Only parts that really appear in the past cards
    allowed_parts = {p for s in similar for p in (s["card"].get("parts") or [])}
    parts = [p for p in (data.get("parts") or []) if p in allowed_parts]

    # Hours come from the past cards (the middle value), not from the model
    hours = [
        s["card"]["downtime_hours"]
        for s in similar
        if isinstance(s["card"].get("downtime_hours"), (int, float))
    ]
    est_hours = round(statistics.median(hours), 1) if hours else None

    steps = [clean(s, hits) for s in (data.get("steps") or []) if s][:6]
    work_order = {
        "title": clean(data.get("title") or "Draft work order", hits),
        "asset": asset,
        "steps": steps,
        "parts": parts,
        "est_hours": est_hours,
        "status": "draft",
    }
    return work_order, stats