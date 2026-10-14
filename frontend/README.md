# RepeatFix frontend

Owner: Shamveel (branch `shamveel/frontend`). Next.js 15 + Tailwind CSS 4. Deployed on Vercel.

## Screens
| Route | Screen | What it does |
|---|---|---|
| `/` | **Fix a fault** | Describe a fault (or read a photo of a log entry, beta). Shows a repeat-failure alert, plus **Seen before** (3 closest past fixes), **Likely causes** (each linked to its evidence cards) and **Procedure** (cited FAA document and section). Below that is an editable **Draft work order** that a supervisor must approve. |
| `/repeats` | **Repeat failures** | Ranked "bad actors" by aircraft or component: times, average days between failures, downtime, status. Has a downtime bar chart, and you can click any card to see the original record. |
| `/results` | **Results** | Measured numbers (reading accuracy, latency, tokens/s, cost per 100 cards), how it works, where it runs, and data sources. |

## Run
```bash
npm install
cp .env.example .env.local   # mock mode by default
npm run dev                  # http://localhost:3000
npm run build && npm run lint
```

## Mock mode vs real backend
- `lib/api.ts` is the only place that fetches data. It calls the FastAPI backend (`docs/API.md`) when `NEXT_PUBLIC_API_URL` is set and `NEXT_PUBLIC_USE_MOCKS` is not `true`.
- In mock mode, `lib/mock.ts` answers from `mocks/cards.json`, `mocks/knowledge.json` and `mocks/metrics.json`, using the same response shapes. A yellow "sample data" banner shows on every screen, so mock data is never passed off as real.
- Mock fixtures are **illustrative sample records**: tail numbers and part numbers are made up. Procedure citations are chapter-level only. The backend supplies the exact section and page.

## Deploy (Vercel)
1. Import the GitHub repo in Vercel and set **Root Directory** to `frontend`.
2. Set the environment variables `NEXT_PUBLIC_API_URL=https://<backend>` and `NEXT_PUBLIC_USE_MOCKS=false`. Leaving the backend unset gives the cached demo (mock) mode.
3. The backend must allow CORS from the Vercel domain.

## Design rules
See `../CLAUDE.md` → "UI style rules" and "Colour palette". Colours are CSS variables in `app/globals.css`; use the Tailwind names (`glass`, `bg-surface`, `text-muted`, `bg-accent-gradient`, `text-critical`, …), never raw hex values.
