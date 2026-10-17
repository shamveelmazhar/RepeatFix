import json
import os
import time
import uuid

from dotenv import load_dotenv
from openai import OpenAI

from app.vocab import FAILURE_MODES_BY_CODE, ata_name, failure_mode_list

load_dotenv()


def get_client():
    """Connect to the model service. The address and password come from .env."""
    return OpenAI(
        base_url=os.getenv("VLLM_BASE_URL"),
        api_key=os.getenv("VLLM_API_KEY", "none"),
        timeout=40,  # give up on a call after 40 seconds instead of waiting for minutes
        max_retries=0,  # our own retry loop handles repeats
    )


MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct")


def build_system_prompt():
    """The instructions we give the model. The allowed failure modes come from vocab.py."""
    codes = "\n".join(f"- {m['code']}: {m['label']}" for m in failure_mode_list())
    return f"""You read aircraft maintenance text and turn it into ONE JSON object.
Return ONLY the JSON object. No extra words and no code fences.

Use exactly these fields:
- aircraft_type: for example "B737-800" (null if not stated)
- registration: the tail number, for example "N12345" (null if not stated)
- ata_chapter: the 2-digit ATA chapter as text, for example "32" (null if unsure)
- component: the part or system involved, short
- symptom: what went wrong, in one short sentence
- failure_mode: ONE code from the list below
- action_taken: what the mechanic did (empty text if not stated)
- parts: list of part numbers mentioned (empty list if none)
- downtime_hours: a number (null if not stated)
- date: "YYYY-MM-DD" (null if not stated)

Rules:
- Use only facts from the text. Never invent anything.
- If something is not in the text, use null (or an empty list or empty text as shown above).
- failure_mode must be exactly one code from this list. If none fits, use "other".

Allowed failure modes:
{codes}
"""


def clean_json(text):
    """Models sometimes add extra words. Cut out just the {...} part and read it."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("The model did not return JSON: " + text[:200])
    return json.loads(text[start : end + 1])


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalise(data, raw_text, source):
    """Fix the model's answer so it always matches the JobCard contract."""
    # failure_mode must be in our list, otherwise "other"
    code = data.get("failure_mode")
    if code not in FAILURE_MODES_BY_CODE:
        code = "other"

    # ata_chapter must be digits like "32", otherwise None
    chapter = data.get("ata_chapter")
    chapter = str(chapter).strip() if chapter is not None else None
    if not chapter or not chapter.isdigit():
        chapter = None
    else:
        chapter = chapter.zfill(2)  # "5" becomes "05"

    parts = data.get("parts")
    if not isinstance(parts, list):
        parts = []

    return {
        "id": f"{source}-{uuid.uuid4().hex[:12]}",
        "source": source,
        "date": data.get("date"),
        "aircraft_type": data.get("aircraft_type"),
        "registration": data.get("registration"),
        "ata_chapter": chapter,
        "ata_name": ata_name(chapter),
        "component": data.get("component"),
        "symptom": data.get("symptom"),
        "failure_mode": code,
        "action_taken": data.get("action_taken") or "",
        "parts": [str(p) for p in parts],
        "downtime_hours": to_float(data.get("downtime_hours")),
        "raw_text": raw_text,
    }


def extract_card(text, source="text", client=None):
    """Text in, JobCard out. Also returns how long the model took (in ms)."""
    client = client or get_client()
    started = time.time()
    reply = None
    for attempt in range(2):  # try up to 3 times if the service is busy
        try:
            reply = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": build_system_prompt()},
                    {"role": "user", "content": text},
                ],
                temperature=0,
                max_tokens=1500,
            )
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)
    model_ms = int((time.time() - started) * 1000)
    data = clean_json(reply.choices[0].message.content)
    return normalise(data, text, source), model_ms