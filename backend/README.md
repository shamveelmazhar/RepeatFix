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
