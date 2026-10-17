import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.stdout.reconfigure(encoding="utf-8")

import app.cache as cache  # noqa: E402

for entry in cache.load().values():
    r = entry["result"]
    s = r["structured"]
    print("=" * 70)
    print("FAULT:", entry["fault_text"])
    print("EXTRACTED:", s["failure_mode"], "| ATA", s["ata_chapter"], "|", s["component"])
    history = r["repeat_history"]
    print("REPEAT HISTORY:", history and {k: history[k] for k in ("count", "first_date", "last_date")})

    print("\nSIMILAR CARDS:")
    for x in r["similar"]:
        c = x["card"]
        print(" ", x["score"], c["id"], c["failure_mode"], "|", (c.get("symptom") or "")[:90])

    print("\nHYPOTHESES:")
    for h in r["hypotheses"]:
        print(" ", h["confidence"], "-", h["cause"], h["evidence_card_ids"])

    print("\nPROCEDURES:")
    for p in r["procedures"]:
        print(" ", p["citation"])

    print("\nWORK ORDER:", r["work_order"]["title"])
    for number, step in enumerate(r["work_order"]["steps"], 1):
        print(f"  {number}. {step}")
    print("  parts:", r["work_order"]["parts"], "| est_hours:", r["work_order"]["est_hours"])