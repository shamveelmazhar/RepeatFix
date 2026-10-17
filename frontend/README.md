# RepeatFix frontend

I (Shamveel) own the frontend, on branch `shamveel/frontend`. Next.js 15 + Tailwind CSS 4. Deployed on Vercel.

## Screens
| Route | Screen | What it does |
|---|---|---|
| `/` | **Fix a fault** | Describe a fault (or read a photo of a log entry, beta). Shows a repeat-failure alert, plus **Seen before** (3 closest past fixes), **Likely causes** (each linked to its evidence cards) and **Procedure** (cited FAA document and section). Below that is an editable **Draft work order** that a supervisor must approve. |
| `/repeats` | **Repeat failures** | Ranked "bad actors" by aircraft or component: times, average days between failures, downtime, status. Has a downtime bar chart, and you can click any card to see the original record. |
| `/results` | **Results** | Measured numbers (agreement with our parser, latency, tokens/s, cost per 100 cards), how it works, where it runs (GPU and model as the backend reports them), and data sources. |

## Run
```bash
npm install
cp .env.example .env.local   # mock mode by default
npm run dev                  # http://localhost:3000
npm run build && npm run lint
```

## Mock mode vs real backend
- `lib/api.ts` is the only place that fetches data. It calls the FastAPI backend (`docs/API.md`) when `NEXT_PUBLIC_API_URL` is set and `NEXT_PUBLIC_USE_MOCKS` is not `true`.
- In mock mode, `lib/mock.ts` answers from `mocks/cards.json`, `mocks/knowledge.json` and `mocks/metrics.json`, using the same response shapes. A yellow "saved demo data" banner shows on every screen, so the saved demo is never passed off as live model output.
- The fixtures hold **real records**: the 1,812 FAA SDR job cards for 40 tails in `data/samples/sdr_demo.jsonl`, the 50 NASA ASRS reports, and cited sections of AC 43.13-1B and the AMT Handbooks for each ATA chapter + failure mode. Repeats use the backend's rule (same tail + ATA chapter + failure mode, at least 7 days apart). Likely causes are the parts named most often in past reports of the same problem. No model runs in mock mode, and the Results screen shows only counts measured on the data; model numbers read "Not measured yet".
- Rebuild the fixtures with `python scripts/build_mock_fixtures.py --full /path/to/sdr_cards_2024_2026.jsonl.gz` from the repo root (without `--full`, Results counts come from the demo slice).

## Deploy (Vercel)
1. Import the GitHub repo in Vercel and set **Root Directory** to `frontend`.
2. Set the environment variables `NEXT_PUBLIC_API_URL=https://<backend>` and `NEXT_PUBLIC_USE_MOCKS=false`. Leaving the backend unset gives the cached demo (mock) mode. The backend must be on HTTPS, because the Vercel page can't call a plain `http://` address.
3. Add the Vercel URL to the backend's `ALLOWED_ORIGINS` so it allows the calls.

## Design rules
See the contributor guide, `../CLAUDE.md` → "UI style rules" and "Colour palette". Colours are CSS variables in `app/globals.css`; use the Tailwind names (`glass`, `bg-surface`, `text-muted`, `bg-accent-gradient`, `text-critical`, …), never raw hex values.
