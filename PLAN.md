# RepeatFix — Hackathon Build Plan (AMD Developer Hackathon: ACT III)

## Context
We're entering **AMD Developer Hackathon: ACT III** (lablab.ai, online build 12–17 Oct 2026, on-site in Italy 17–18 Oct, **submissions close Sun 18 Oct 15:00 UTC**; aim to submit by 10:00 UTC). Our project is **RepeatFix**, an AI tool that finds repeat failures hidden in messy maintenance logs and helps technicians fix the next breakdown faster, using past fixes and cited procedures, all running on AMD MI300X. My earlier research write-up ("RepeatFix_ Repeat-Failure Hunter…") picked this idea (scored 32/35) and set the stack: Qwen2.5-VL-7B on vLLM-ROCm on MI300X, FastAPI, pandas stats, Evolus for the partner prize.

**Decisions we've made:**
- **Domain is aviation maintenance, using real public data.** This replaces the synthetic plant/bus cards from the research write-up. Real data counts for more with judges and removes the "synthetic data looks fake" risk.
- **Frontend is Next.js + Tailwind on Vercel.** I (Shamveel) own it. The style is minimal and plain-language, built for technicians.
- **Team:** Nida Amir (github.com/Nidaamir083) owns the Python backend (vLLM, FastAPI, pipelines). I own everything else.
- **Repo:** we use the existing `shamveelmazhar/RepeatFix` repo; no new repo is needed.

## Hackathon requirements (re-check against the event page before submitting)
- **Intelligent Industry track:** "a real manufacturing problem and a working product, not just a dashboard or slides". Its idea list includes "helping technicians search manuals and maintenance records". Strong entries "deliver results that operators can understand". This backs the technician-friendly UI requirement.
- **AMD:** AMD tech must be part of the working product (AMD Developer Cloud + ROCm, here vLLM on MI300X).
- **Evolus partner track ("Evolus Business Agents on AMD"):** the main agent must run on an open model served on AMD infrastructure (our vLLM endpoint), and use at least 2 Evolus building blocks (we use 3: library, extractor, workflow).
- **lablab Rule Book submission items:**
  - clear title
  - short and long descriptions (respect the length limits)
  - tags
  - **16:9 PNG/JPG cover**
  - **MP4 video + PDF slides**
  - **public GitHub repo**
  - **live app URL** (Streamlit/Replit/Vercel)
- **Judging (unconfirmed list):** Technology Application, Presentation, Business Value, Originality.

## Data plan (all public, licence-clean)
| Source | Use | Licence |
|---|---|---|
| **NASA ASRS** maintenance report set (the "mechanic" report set I downloaded) | Messy free-text narratives → JobCard JSON; fleet-type repeats (aircraft model + component/ATA) | US Gov public |
| **FAA Service Difficulty Reports (SDR)**, yearly CSVs at faa.gov/av-info/download_SDR | **Best addition:** has aircraft registration + part + ATA, so per-tail repeat failures are *real*, not seeded. Note: a 2026 AIN report said the database was down for maintenance, so we check availability on day 1 and fall back to ASRS only. | US Gov public |
| **FAA AC 43.13-1B** (the two "AC…" files; documentID 99861 looks like AC 43.13-1B, to confirm) | Cited procedures (knowledge library) | US Gov public |
| **FAA Aviation Maintenance Technician Handbook** (FAA-H-8083-30B/31B) | More cited procedures | US Gov public |
| MaintNet aviation logbook (6,169 UND records) | Optional, messy abbreviations; **only if a licence is confirmed** | unclear |
| 15–20 handwritten logbook entries I photograph myself | VLM extraction accuracy ground truth ("beta") | own |

Raw files go in `data/raw/` (git-ignored). Commit only small samples to `data/samples/`. Source links are in `scripts/download_data.md`.

## Architecture
```
Next.js UI (Vercel) ──REST──> FastAPI (Docker, AMD Developer Cloud droplet)
                               ├─ vLLM-ROCm on MI300X: Qwen2.5-VL-7B-Instruct (OpenAI-compatible /v1)
                               │    extraction → JobCard JSON, failure-mode normalisation,
                               │    root-cause hypotheses, work-order drafting
                               ├─ embeddings on MI300X (e.g. bge-small via PyTorch-ROCm) → similarity search
                               ├─ pandas + SQLite: repeat engine (count, MTBF, Pareto) — deterministic
                               └─ Evolus REST (library = AC 43.13/AMT handbook, extractor, workflow)
```
The UI has a **mock mode** (`NEXT_PUBLIC_USE_MOCKS=true`) that reads JSON fixtures. This lets the frontend move forward before the backend is ready, and it doubles as the "cached demo mode" fallback during judging.

### API contract (agreed on day 1 so we can both work in parallel; lives in `docs/API.md`)
- `JobCard`: `id, source(asrs|sdr|photo|text), date, aircraft_type, registration?, ata_chapter, component, symptom, failure_mode, action_taken, parts[], downtime_hours?, raw_text`
- `POST /api/ingest` (CSV / image / text) → `{cards: JobCard[]}`
- `GET /api/repeats?group_by=aircraft|component` → `[{asset, failure_mode, count, mtbf_days, downtime_hours, card_ids}]`
- `POST /api/assist {fault_text, asset?}` → `{similar:[{card, score}], hypotheses:[{cause, confidence, evidence_card_ids}], procedures:[{doc, section, page, snippet}], work_order:{...}}`
- `POST /api/work-orders/{id}/approve {edits}`, `GET /api/cards/{id}`, `GET /api/metrics`

## Frontend: simple screens for technicians
1. **Fix a fault** (home): one large text box ("Describe the problem") plus an optional photo upload and an aircraft/tail picker. The results come back as three plain cards:
   - **"Seen before"**: the 3 most similar past fixes
   - **"Likely causes"**: each cause with links to its evidence cards
   - **"Procedure"**: the cited AC 43.13 section/page, with a snippet

   Below these sits the editable **draft work order** with an **Approve** button. Nothing is auto-executed.
2. **Repeat failures**: a ranked "bad actors" table (asset, problem, times, avg days between, downtime) plus one simple bar chart. Clicking a row shows its cards.
3. **Results** (metrics): extraction accuracy, repeats found, latency, tokens/s, cost per 100 cards on MI300X, plus a short "How it works" section.

**Style rules:**
- plain words, no ML jargon, and no "chat" anywhere
- ATA codes always shown with their names
- large type, high contrast, neutral palette with one accent colour
- works on a tablet in the hangar

## Responsibilities
**Nida (backend):**
- vLLM on the MI300X droplet (`VLLM_ROCM_USE_AITER=1`)
- FastAPI with the endpoints above
- ASRS/SDR parsers
- the extraction prompt and JSON schema
- normalising failure modes to a controlled list (ATA-based)
- embeddings + retrieval over cards and manual chunks
- the pandas repeat engine
- the hypothesis and work-order prompts
- Evolus REST integration
- Dockerfile
- benchmark script (latency, tokens/s)

**Shamveel (me; everything else):**
- data acquisition and licence checks
- 20 hand-labelled ground-truth cards, plus the photographed handwritten set
- the Next.js UI with mock fixtures, then wiring it to the real API; Vercel deploy
- Evolus workspace setup (from the event link) and uploading the manuals to the library
- README, project write-up and metrics write-up
- cover image, slides (PDF), 3-min demo video (MP4)
- lablab submission and final testing while logged out

## Repo setup
1. Add `PLAN.md` (this plan, with the day-by-day schedule), `CLAUDE.md` (our contributor guide), `docs/API.md`, `.gitignore`, and the skeleton folders:
   - `frontend/`: Shamveel
   - `backend/`: Nida
   - `data/samples/`
   - `docs/`
   - `scripts/`
2. Create **`shamveel/frontend`** and **`nida/backend`** from that commit. Both are merged at the end through PRs.
3. I invite `Nidaamir083` as a collaborator under Settings → Collaborators.

**What the contributor guide (`CLAUDE.md`) covers:**
- one-paragraph project summary and the demo storyline
- repo layout and ownership
- branch workflow (own branch, small PRs into `main`, no force-push on others' branches)
- JobCard schema plus a pointer to the API contract
- how to run the backend, frontend and mock mode
- env vars (`VLLM_BASE_URL`, `EVOLUS_API_KEY`, `EVOLUS_APP_ID`, `NEXT_PUBLIC_API_URL`; never commit keys)
- UI style rules
- data licence rules (public only; label the source in each record)
- hackathon constraints: everything runs on MI300X, cost discipline (stop the droplet when idle), feature freeze Fri evening

## Day-by-day (today is Wed 14 Oct)
| Day | Nida | Shamveel | Done when |
|---|---|---|---|
| Wed 14 | Droplet up with vLLM + Qwen2.5-VL; FastAPI skeleton; ASRS parser | Repo, branches and contributor guide; agree on API contract; download ASRS/SDR/AC/AMT; Next.js scaffold with mock fixtures | One ASRS narrative comes back as valid JobCard JSON from the MI300X endpoint |
| Thu 15 | Extraction on ~500 records; normalisation; repeat engine; retrieval | Label 20 ground-truth cards; photograph 15 handwritten entries; build the 3 screens on mocks; Evolus workspace + library | Repeats table from real data; extraction accuracy measured |
| Fri 16 | `/assist` (hypotheses + citations + work order); Evolus workflow; Docker; benchmark | Wire UI to the live API; deploy to Vercel; README; **feature freeze by evening** | End-to-end: new fault → cited draft → approve, at a public URL |
| Sat 17 | Fixes; keep the endpoint stable; cached demo responses | Cover image, slides, 3-min video, 2 dry runs | MP4 + PDF exported |
| Sun 18 | Keep the endpoint up during judging | Submit on lablab by ~10:00 UTC; test links logged out | Submitted |

**Cut list (from the research write-up):** model training, live sensors, mobile app, voice, auth, multi-site, fine-tuning. If Evolus isn't working by Thu night, drop that prize.

## Verification
- The repo has `main`, `shamveel/frontend` and `nida/backend` branches.
- `CLAUDE.md`, `PLAN.md` and `docs/API.md` render on GitHub.
- Later: `npm run build` passes in `frontend/` (mock mode); `curl /api/assist` returns cited results; the measured numbers appear on the Results screen.
