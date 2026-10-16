import json

from app.llm import chat_json

SYSTEM = """You help aircraft maintenance planners.
You get a new fault and a list of similar past job cards. Suggest up to 3 likely causes.

Return ONLY this JSON, with no extra words:
{"hypotheses": [{"cause": "...", "confidence": "high|medium|low", "evidence_card_ids": ["..."]}]}

Rules:
- Base every cause on the past cards. Never invent facts.
- evidence_card_ids must come only from the ids in the list.
- high = several past cards clearly show this cause. medium = one or two cards. low = a guess.
- If the past cards give no clue, return {"hypotheses": []}.
"""


def short(text, limit):
    return (text or "")[:limit]


def make_hypotheses(fault_text, similar):
    """similar is the list from similar_cards(): [{"card": ..., "score": ...}]"""
    cards = [
        {
            "id": s["card"]["id"],
            "component": s["card"].get("component"),
            "symptom": short(s["card"].get("symptom"), 300),
            "failure_mode": s["card"].get("failure_mode"),
            "action_taken": short(s["card"].get("action_taken"), 200),
        }
        for s in similar
    ]
    user = "New fault:\n" + fault_text + "\n\nSimilar past cards:\n" + json.dumps(cards, indent=1)
    data, stats = chat_json(SYSTEM, user)

    valid_ids = {c["id"] for c in cards}
    result = []
    for item in (data.get("hypotheses") or [])[:3]:
        if not isinstance(item, dict) or not item.get("cause"):
            continue
        confidence = item.get("confidence")
        if confidence not in ("high", "medium", "low"):
            confidence = "low"
        ids = [i for i in (item.get("evidence_card_ids") or []) if i in valid_ids]
        if not ids:
            confidence = "low"  # no evidence means it can only be a guess
        result.append({"cause": item["cause"], "confidence": confidence, "evidence_card_ids": ids})
    return result, stats