# Backend (owner: Nida, branch `nida/backend`)

A FastAPI service that runs alongside vLLM (Qwen2.5-VL-7B-Instruct) on the AMD MI300X droplet. Endpoints are listed in `../docs/API.md`.

Suggested layout: `app/main.py` (routes), `app/extract.py` (LLM → JobCard), `app/repeats.py` (pandas stats), `app/retrieve.py` (embeddings + search), `app/assist.py` (hypotheses + work order), `app/evolus.py`. Also add `Dockerfile` and `requirements.txt`.

vLLM on MI300X: `VLLM_ROCM_USE_AITER=1 vllm serve Qwen/Qwen2.5-VL-7B-Instruct --port 8000`

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

The full 2024–2026 build (179,962 cards) is in the project's shared files as `sdr/sdr_cards_2024_2026.jsonl.gz`; only the 1,812-card demo subset is committed.

## Cited procedures (FAA AC 43.13-1B)

`app/procedures.py` splits AC 43.13-1B CHG 1 into one chunk per paragraph (e.g. `9-14. TIRE INSPECTION AND REPAIR`), keeping the chapter, section, paragraph number and the page each chunk starts on. Long paragraphs are split at their sub-paragraphs (`a.`, `(3)`), and each part keeps the page it starts on. The result is committed as `data/procedures/ac_43-13-1b.jsonl` (661 paragraphs, 970 chunks), so the service doesn't need the PDF at runtime.

Search is BM25 on the CPU, with shop shorthand expanded (`brk` → brake, `hyd` → hydraulic). Embedding search on the MI300X can rerank these hits later. `to_procedure()` returns the `procedures[]` item from `docs/API.md`, and `citation()` gives the full reference, e.g. `AC 43.13-1B, Chapter 9, Section 1, par. 9-7 (Landing-gear Components), page 9-6`.

For `/api/assist`, put `CITE_INSTRUCTION` and `context_block(hits)` in the prompt. Then run `strip_unknown_citations(answer, hits)` on the model output, which removes any citation that wasn't retrieved.

```bash
cd backend
pip install -r requirements-dev.txt
python -m app.procedures search "#2 brk dragging, brk temp high after taxi"
python -m pytest
# rebuild the chunks (PDF in data/raw/ac/, git-ignored)
python -m app.procedures build ../data/raw/ac/AC_43.13-1B_CHG_1_Ed_Upd_FAA.pdf
```
