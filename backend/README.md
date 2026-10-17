# Backend (owner: Nida, branch `nida/backend`)

A FastAPI service that loads the job cards, finds repeat failures and answers new faults. Every model call goes to an OpenAI-compatible model API. We use DeepSeek-V4-Flash on AMD GPUs via AMD Token Factory. Endpoints are listed in `../docs/API.md`.

## Run it
```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # also installs requirements.txt
uvicorn app.main:app --reload --port 8001
python -m pytest
```
Settings come from a `.env` file in `backend/` or the repo root. It's git-ignored, so never commit it; `../.env.example` lists the names.

| Var | Meaning |
|---|---|
| `VLLM_BASE_URL` | the model API's `/v1` address (AMD Token Factory) |
| `VLLM_API_KEY` | the key for it |
| `VLLM_MODEL` | model id; we run `DeepSeek-V4-Flash`, which is also the code default |
| `GPU_LABEL` | where the model runs, shown in the app, e.g. `AMD GPUs via AMD Token Factory` |
| `ALLOWED_ORIGINS` | extra websites allowed to call the API, comma-separated (e.g. the Vercel URL) |
| `ASSIST_BUDGET_S` | optional, default `45`: the total time limit for `/api/assist` in seconds, after which it falls back to the closest saved answer |

Cards, repeat failures and procedures work without the model. If the model is busy, unreachable or too slow, Fix a fault falls back to the saved answer for the closest saved fault. If no saved fault is close enough, it returns a 502 error, and the app then shows its own saved demo answer.

Layout:
- `app/main.py`: the routes
- `app/extract.py`, `app/llm.py`: model calls (text → JobCard, JSON answers)
- `app/assist.py`: Fix a fault, built from `retrieval.py` (similar past cards, TF-IDF), `hypotheses.py` (likely causes), `procedures.py` + `handbooks.py` (cited procedures) and `workorder.py` (draft work order)
- `app/repeats.py`: repeat-failure stats in pandas
- `app/cache.py`: saved answers
- `app/benchmark.py`: reads and writes the measured numbers shown on Results
- `app/asrs.py`, `app/sdr.py`, `app/vocab.py`, `app/aircraft.py`: ingestion and the ATA / failure-mode vocabularies
- `scripts/`: `benchmark.py` (measures the numbers), `make_demo_cache.py` (builds the saved answers for the demo faults) and `check_key.py` (checks the Token Factory key)

## ASRS ingestion (`app/asrs.py`)
Parses a NASA ASRS report set PDF into JobCards with deterministic rules (no LLM):
```
pip install -r requirements-dev.txt
python -m app.asrs ../data/raw/mechanic.pdf -o ../data/samples/asrs_mechanic.jsonl
python -m pytest
```
The ATA and failure-mode vocabularies live in `app/vocab.py`; `vocab.failure_mode_list()` has the shape of `GET /api/failure-modes`.

## FAA SDR ingestion (`app/sdr.py`)
Parses the yearly FAA Service Difficulty Report CSVs into JobCards with deterministic rules (no LLM). SDR keeps the tail number, part numbers and JASC code, so it gives real per-aircraft repeats:
```
python -m app.sdr build SDR-2024.csv SDR-2025.csv SDR-2026.csv -o ../data/raw/sdr_cards.jsonl --demo ../data/samples/sdr_demo.jsonl
python -m app.sdr repeats ../data/raw/sdr_cards.jsonl --top 20
```
`repeat_groups(cards, min_count, min_gap_days)` groups by tail + ATA chapter + failure mode. Use `min_gap_days=7` so that a heavy check filing 30 corrosion findings on one day counts once. It is there for reporting; the `/api/repeats` engine can reuse it or compute its own.

The full 2024–2026 build (179,962 cards) is in our shared project files as `sdr/sdr_cards_2024_2026.jsonl.gz`; only the 1,812-card demo subset is committed.

## Cited procedures (FAA AC 43.13-1B and AMT Handbooks)

`app/procedures.py` splits AC 43.13-1B CHG 1 into one chunk per paragraph (e.g. `9-14. TIRE INSPECTION AND REPAIR`), keeping the chapter, section, paragraph number and the page each chunk starts on. Long paragraphs are split at their sub-paragraphs (`a.`, `(3)`), and each part keeps the page it starts on. The result is committed as `data/procedures/ac_43-13-1b.jsonl` (661 paragraphs, 970 chunks), so the service doesn't need the PDF at runtime.

Search is BM25 on the CPU, with shop shorthand expanded (`brk` → brake, `hyd` → hydraulic). Token Factory has no embedding model, so search stays on the CPU. `to_procedure()` returns the `procedures[]` item from `docs/API.md`, and `citation()` gives the full reference, e.g. `AC 43.13-1B, Chapter 9, Section 1, par. 9-7 (Landing-gear Components), page 9-6`.

`app/handbooks.py` adds the three FAA Aviation Maintenance Technician Handbooks: General (FAA-H-8083-30B), Airframe (31B) and Powerplant (32B). They have no paragraph numbers, so each chunk is the text under one PDF bookmark heading (e.g. "Bleeding Shock Struts"), with the chapter, parent headings and printed page it starts on. Figure callouts are dropped, and captions are kept at the end of the section. The result is committed as `data/procedures/faa-h-8083-3{0,1,2}b.jsonl` (3,573 sections, 5,091 chunks). Their citation looks like `FAA-H-8083-31B, Chapter 13 (Aircraft Landing Gear Systems), "Bleeding Shock Struts", page 13-14`.

`ProcedureIndex.load()` searches the AC and the handbooks together. Pass `docs=` to limit a search, e.g. `index.search(q, k=1, docs={"AC 43.13-1B"})` for the AC paragraph the demo cites, then `docs={"FAA-H-8083-31B", "FAA-H-8083-32B"}` for handbook background.

For `/api/assist`, put `CITE_INSTRUCTION` and `context_block(hits)` in the prompt. Then run `strip_unknown_citations(answer, hits)` on the model output, which removes any citation that wasn't retrieved. The model cites `[AC 43.13-1B par. 9-14]` for the AC and `[FAA-H-8083-31B p. 13-14]` for a handbook.

```bash
cd backend
pip install -r requirements-dev.txt
python -m app.procedures search "#2 brk dragging, brk temp high after taxi"
python -m pytest
# rebuild the chunks (PDFs in data/raw/, git-ignored; the handbooks take about 6 minutes)
python -m app.procedures build ../data/raw/ac/AC_43.13-1B_CHG_1_Ed_Upd_FAA.pdf
python -m app.handbooks ../data/raw/handbooks/FAA-H-8083-30B.pdf ../data/raw/handbooks/FAA-H-8083-31B.pdf ../data/raw/handbooks/FAA-H-8083-32B.pdf
```
