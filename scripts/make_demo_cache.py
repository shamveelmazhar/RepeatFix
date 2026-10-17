import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from openai import OpenAI  # noqa: E402

import app.cache as cache  # noqa: E402
import app.extract as ex  # noqa: E402
from app.assist import run_assist  # noqa: E402
from app.main import CARDS  # noqa: E402


def patient_client():
    """Waits up to 2 minutes, because a saved answer may take as long as it needs."""
    return OpenAI(
        base_url=os.getenv("VLLM_BASE_URL"),
        api_key=os.getenv("VLLM_API_KEY", "none"),
        timeout=120,
        max_retries=0,
    )


ex.get_client = patient_client

DEMO_FAULTS = [
    {"fault_text": "FUME EVENT ON DESCENT IN COCKPIT", "asset": "N926NK", "aircraft_type": "A320neo"},
    {"fault_text": "ENG 2 FIRE LOOP B FAULT", "asset": "N2193J", "aircraft_type": "A321neo"},
    {"fault_text": "FOUND FWD LH EMERG EXIT LIGHTS INOP", "asset": "N3760C", "aircraft_type": "B737-800"},
]

for item in DEMO_FAULTS:
    key = cache.make_key(item["fault_text"], item["asset"], item["aircraft_type"])
    if cache.get(key):
        print("Already saved, skipping:", item["fault_text"])
        continue
    try:
        result = run_assist(CARDS, item["fault_text"], item["asset"], item["aircraft_type"])
    except Exception as error:
        print("FAILED:", item["fault_text"], str(error)[:120])
        continue
    result["cached"] = False
    cache.save(key, item["fault_text"], result)

    print("\nSAVED:", item["fault_text"], "|", item["asset"], "|", item["aircraft_type"])
    print("  failure_mode:", result["structured"]["failure_mode"], "| ATA", result["structured"]["ata_chapter"])
    print("  repeat_history:", result["repeat_history"] and result["repeat_history"]["count"])
    print("  similar cards:", len(result["similar"]), "| procedures:", len(result["procedures"]))
    print("  timing:", result["timing"])
    time.sleep(10)  # stay well under 20 requests per minute