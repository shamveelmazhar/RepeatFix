# CLAUDE.md — RepeatFix

Guidance for Claude Code (and humans) working in this repo. The full plan and schedule are in [`PLAN.md`](PLAN.md). The API contract is in [`docs/API.md`](docs/API.md).

## What we are building
RepeatFix is an AI tool that finds **repeat failures hidden in messy aviation maintenance logs** and helps technicians fix the next breakdown faster, using past fixes and **cited procedures**. All model inference runs on an **AMD Instinct MI300X** (AMD Developer Cloud, ROCm, vLLM).

The entry is for the AMD Developer Hackathon: ACT III on lablab.ai. It targets the Intelligent Industry track plus the Evolus partner prize. **Submissions close Sun 18 Oct 2026, 15:00 UTC; we submit by 10:00 UTC. Feature freeze is Fri 16 Oct, evening.**

Pitch line: *"No new sensors: your logbooks already know which aircraft will break next."* Call it a reliability-engineering tool, never a "chatbot".

**Demo storyline (about 3 min):**
1. Messy logs.
2. The pain: downtime and wrench-time stats.
3. Ingest into JSON live on the MI300X.
4. The repeat-failure Pareto ("bad actors").
5. A new fault comes in. RepeatFix shows the 3 similar past fixes, likely causes, the cited AC 43.13 section and a draft work order. The supervisor edits and approves it.
6. Measured numbers + architecture.

## Team and ownership
| Area | Owner | Branch |
|---|---|---|
| `backend/`: vLLM, FastAPI, extraction, retrieval, repeat engine, Evolus REST, Docker | Nida Amir (@Nidaamir083) | `nida/backend` |
| `frontend/`: Next.js UI; plus data, docs, Evolus workspace, video, slides, submission | Shamveel Mazhar (@shamveelmazhar) | `shamveel/frontend` |

## Repo layout
```
frontend/       Next.js + Tailwind app (deployed on Vercel)
backend/        FastAPI service + pipelines (Docker, runs next to vLLM on the MI300X droplet)
data/samples/   small committed samples + hand-labelled ground truth
data/raw/       full downloads; git-ignored
docs/           API contract, architecture, metrics write-up
scripts/        data download notes, benchmark scripts
```

## Git workflow
- Work on your own branch. Open PRs into `main`, and merge both branches at the end (or earlier when a piece is stable).
- Keep each commit small with a clear message.
- **Never force-push or rebase someone else's branch.** To pick up others' work, merge `main` into your branch.
- Only `docs/API.md` is shared. Change it through a PR that the other person reviews, because both sides depend on it.

## Data model (summary; source of truth is `docs/API.md`)
`JobCard` fields:
- `id`
- `source` (`asrs | sdr | photo | text`)
- `date`
- `aircraft_type`
- `registration?`
- `ata_chapter`
- `component`
- `symptom`
- `failure_mode`
- `action_taken`
- `parts[]`
- `downtime_hours?`
- `raw_text`

`failure_mode` is normalised to a controlled list keyed by ATA chapter. The LLM only normalises text. All statistics (count, MTBF, downtime, Pareto) are computed deterministically in pandas.

## Running locally
- **Backend** (once scaffolded): `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`. It needs `VLLM_BASE_URL` to point at the MI300X vLLM endpoint.
- **Frontend:** `cd frontend && npm install && npm run dev` (http://localhost:3000). Before pushing, run `npm run lint && npm run build`. Details are in `frontend/README.md`.
- **Mock mode:** `NEXT_PUBLIC_USE_MOCKS=true` makes the UI read JSON fixtures in `frontend/mocks/` instead of the API. Use it to build the UI before the backend is ready, and as the fallback "cached demo mode" during judging.

## Environment variables (never commit values; use `.env`, which is git-ignored)
| Var | Used by | Meaning |
|---|---|---|
| `VLLM_BASE_URL` | backend | OpenAI-compatible URL of vLLM on MI300X, e.g. `http://<droplet>:8000/v1` |
| `VLLM_MODEL` | backend | `Qwen/Qwen2.5-VL-7B-Instruct` |
| `EVOLUS_API_KEY`, `EVOLUS_APP_ID` | backend | Evolus REST (`X-ApiKey`, `X-Application-Id` headers; base `https://api.evolus.ai/api/v1`) |
| `NEXT_PUBLIC_API_URL` | frontend | Public URL of the FastAPI service |
| `NEXT_PUBLIC_USE_MOCKS` | frontend | `true` = use fixtures |

## Hackathon rules we must satisfy
- AMD tech must visibly run the product: vLLM-ROCm on MI300X serves every LLM/VLM call, and embeddings run there too. Say so in the UI and in the video.
- Evolus: the main agent runs on **our** vLLM endpoint, and we use 3 building blocks (knowledge library, document extractor, workflow).
- Submission needs:
  - a title, plus short and long descriptions
  - tags
  - a 16:9 PNG/JPG cover
  - an MP4 video
  - PDF slides
  - a **public** GitHub repo
  - a live app URL
- Show **measured numbers**:
  - extraction field accuracy on the 20 hand-labelled cards
  - repeat failures found
  - latency
  - tokens/s
  - cost per 100 cards at $1.99/h
- Cost discipline: **stop the MI300X droplet when you're not working.**

## UI style rules (users are technicians and engineers)
- Three screens only: **Fix a fault**, **Repeat failures**, **Results**.
- Plain words. No ML jargon, and never the word "chat". Labels read like "Seen before", "Likely causes", "Procedure", "Draft work order", "Approve".
- Show every ATA code with its name (e.g. "ATA 32 – Landing Gear").
- Every AI answer shows its evidence: the past cards it used and the manual section/page it cites. Nothing auto-executes; a human approves the work order.
- Large type, high contrast, a neutral palette with one accent colour. Generous spacing, usable on a tablet.
- No login or auth.
- No marketing-page elements in the app (big glowing heroes, pricing, "trusted by" logos). Keep that style for the cover image, slides and video.

### Colour palette
Light mode is the default; dark mode is optional, and the user's choice is remembered. Tokens live in `frontend/app/globals.css`, so use the Tailwind names and never raw hex values. The single accent is blue. Red, amber and green are **reserved for status** and always come with an icon and a word.

| Token (Tailwind) | Light | Dark | Use |
|---|---|---|---|
| `bg` | `#F8FAFC` | `#0B1220` | page |
| `surface` | `#FFFFFF` | `#111A2E` | cards, tables |
| `line` | `#E2E8F0` | `#1F2A44` | borders |
| `ink` | `#0F172A` | `#E2E8F0` | body text |
| `muted` | `#475569` | `#94A3B8` | labels |
| `accent` | `#2563EB` | `#60A5FA` | buttons, links, chart bars |
| `accent-soft` | `#EFF6FF` | `#172554` | selected / highlight |
| `critical` | `#B91C1C` | `#F87171` | 4+ repeats, errors |
| `warning` | `#B45309` | `#FBBF24` | 3 repeats, sample-data banner |
| `ok` | `#15803D` | `#4ADE80` | approved |

Font: Geist Sans and Geist Mono (the `geist` npm package, served locally). Base size 18px; use tabular numbers in tables.

## Data rules
- Public, licence-clean sources only (NASA ASRS, FAA SDR, FAA AC 43.13-1B, FAA AMT Handbook). Download links are in `scripts/download_data.md`.
- Keep the `source` field on every record. Credit sources in the README.
- Large raw files go in `data/raw/` (git-ignored). Commit only small samples.
- Don't add datasets that have unclear or non-commercial licences (e.g. MaintNet until its licence is confirmed).

## Out of scope (do not build)
Model training or fine-tuning, live sensor streaming, mobile app, voice input, login/auth, multi-site support.
