import json
import os
from pathlib import Path
import statistics
import traceback
import app.extract as extract_module
from dotenv import load_dotenv
from app.aircraft import same_aircraft_type
from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.vocab import failure_mode_list
from typing import Literal
from pydantic import BaseModel, Field
from app.repeats import repeat_rows
from app.assist import run_assist
load_dotenv()

# The project folder (RepeatFix) and where the sample data lives
ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "data" / "samples"


def load_cards():
    """Read all JobCards from the sample files into one list."""
    cards = []
    for name in ["asrs_mechanic.jsonl", "sdr_demo.jsonl"]:
        path = SAMPLES / name
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    cards.append(json.loads(line))
    return cards


CARDS = load_cards()
CARDS_BY_ID = {card["id"]: card for card in CARDS}

app = FastAPI(title="RepeatFix API")

# CORS: which websites may call this server.
# Add the Vercel address in .env as ALLOWED_ORIGINS, separated by commas.
origins = ["http://localhost:3000"]
extra = os.getenv("ALLOWED_ORIGINS", "")
origins += [o.strip() for o in extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# The contract says errors look like {"error": "message"}
@app.exception_handler(StarletteHTTPException)
async def error_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

# A bad value like limit=abc also gets our {"error": "..."} shape
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"] if p != "query")
    return JSONResponse(
        status_code=422,
        content={"error": f"Invalid value for '{field}': {first['msg']}"},
    )


@app.get("/api/health")
def health():
    # vllm and evolus become real checks later
    return {"ok": True, "vllm": False, "evolus": False}


@app.get("/api/cards")
def list_cards(
    limit: int = Query(50, ge=0, le=500),
    offset: int = Query(0, ge=0),
    ata: str | None = None,
    asset: str | None = None,
    aircraft_type: str | None = None,
):
    found = CARDS
    if ata:
        found = [c for c in found if c.get("ata_chapter") == ata]
    if asset:
        found = [c for c in found if c.get("registration") == asset]
    if aircraft_type:
        found = [c for c in found if same_aircraft_type(c.get("aircraft_type"), aircraft_type)]
    return {"total": len(found), "cards": found[offset : offset + limit]}


@app.get("/api/cards/{card_id}")
def get_card(card_id: str):
    card = CARDS_BY_ID.get(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@app.get("/api/failure-modes")
def failure_modes():
    return failure_mode_list()

@app.get("/api/repeats")
def repeats(
    group_by: Literal["aircraft", "component"] = "aircraft",
    min_count: int = Query(2, ge=1),
):
    return repeat_rows(CARDS, group_by, min_count)


# Approved work orders are kept in memory (they reset when the server restarts)
APPROVED = {}


class ApproveRequest(BaseModel):
    work_order: dict
    approved_by: str


@app.post("/api/work-orders/{work_order_id}/approve")
def approve_work_order(work_order_id: str, body: ApproveRequest):
    APPROVED[work_order_id] = {
        "work_order": body.work_order,
        "approved_by": body.approved_by,
    }
    return {"id": work_order_id, "status": "approved"}


ASSIST_TIMINGS = []  # one entry per /api/assist call (resets when the server restarts)


def median_of(values):
    values = [v for v in values if v is not None]
    return round(statistics.median(values), 1) if values else None


@app.get("/api/metrics")
def metrics():
    # Only measured numbers. Everything else stays null until we measure it.
    return {
        "cards_processed": len(CARDS),
        "extraction_field_accuracy": None,
        "labelled_cards": 0,
        "repeat_groups_found": len(repeat_rows(CARDS, "aircraft", 2)),
        "p50_latency_ms": median_of([t["total_ms"] for t in ASSIST_TIMINGS]),
        "tokens_per_s": median_of([t["tokens_per_s"] for t in ASSIST_TIMINGS]),
        "cost_per_100_cards_usd": None,
        "gpu": "AMD GPU via AMD Token Factory",
        "model": extract_module.MODEL,
    }


class AssistRequest(BaseModel):
    fault_text: str = Field(min_length=3, max_length=5000)
    asset: str | None = None
    aircraft_type: str | None = None


@app.post("/api/assist")
def assist(body: AssistRequest):
    try:
        result = run_assist(CARDS, body.fault_text, body.asset, body.aircraft_type)
    except Exception:
        traceback.print_exc()  # the real error shows in your terminal
        raise HTTPException(status_code=502, detail="The model call failed. Please try again.")
    ASSIST_TIMINGS.append(result["timing"])
    return result