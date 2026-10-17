# RepeatFix API contract (v0)

Frontend and backend share this contract. Change it only through a PR that the other teammate reviews. Base URL: `NEXT_PUBLIC_API_URL` (e.g. `https://<backend>/`). All bodies are JSON unless noted.

## JobCard
```json
{
  "id": "asrs-1234567",
  "source": "asrs",               // asrs | sdr | photo | text
  "date": "2024-03-18",           // ISO date; null if unknown
  "aircraft_type": "B737-800",
  "registration": "N12345",       // null when the source is de-identified (ASRS)
  "ata_chapter": "32",
  "ata_name": "Landing Gear",
  "component": "Main gear brake assembly",
  "symptom": "Brake temp high after taxi",
  "failure_mode": "brake_overheat", // controlled vocabulary, see GET /api/failure-modes
  "action_taken": "Replaced brake assembly, ops check good",
  "parts": ["2-1577-3"],
  "downtime_hours": 6.5,           // null if unknown
  "raw_text": "original narrative / OCR text"
}
```

## Endpoints

### `POST /api/ingest`
Ingests `{ "text": "..." }` (3 to 20,000 characters) and returns it as a job card. CSV and image uploads (multipart) are planned but not built yet; until then they get a 422.
→ `{ "cards": JobCard[], "model_ms": 1234 }`
The new card is kept in memory, so it shows in `/api/cards` and `/api/repeats` until the server restarts. `date` is `null` unless the text gives a full `YYYY-MM-DD` date.

### `GET /api/cards?limit=50&offset=0&ata=32&asset=N12345&aircraft_type=A320`
→ `{ "total": 1234, "cards": JobCard[] }`
`limit` is 0 to 500 and `offset` is 0 or more. `aircraft_type` ignores case, spaces and hyphens and matches by prefix, so `A320` matches `A320-200` but `A320neo` only matches types that start with it.

### `GET /api/cards/{id}`
→ `JobCard`

### `GET /api/repeats?group_by=aircraft|component&min_count=2`
Returns rows with `count >= min_count`, ranked by downtime, then count.
- `group_by=aircraft` uses our repeat rule: same tail + ATA chapter + failure mode, with reports at least 7 days apart. A report filed within 7 days of the last counted one is the same event, so it isn't counted again. `count` is the number of counted failures, `mtbf_days` is the average number of days between them, and `card_ids` lists every report in the group (so it can be longer than `count`). Cards with no tail or no date are left out.
- `group_by=component` groups by component + failure mode across the whole fleet, and `asset` holds the component name. Here `count` is every report; the 7-day rule doesn't apply.
```json
[{ "asset": "N12345", "aircraft_type": "B737-800", "ata_chapter": "32", "ata_name": "Landing Gear",
   "failure_mode": "brake_overheat", "count": 5, "mtbf_days": 41.2, "downtime_hours": 31.0,
   "card_ids": ["sdr-...", "sdr-..."] }]
```

### `POST /api/assist`
Request: `{ "fault_text": "...", "asset": "N12345" | null, "aircraft_type": "B737-800" | null }`
```json
{
  "id": "wo-0001",
  "structured": JobCard,                       // the new fault, as extracted
  "similar": [{ "card": JobCard, "score": 0.83 }],
  "hypotheses": [{ "cause": "Worn brake wear pins", "confidence": "high|medium|low",
                   "evidence_card_ids": ["sdr-..."] }],
  "procedures": [{ "doc": "FAA AC 43.13-1B CHG 1",
                   "section": "Par. 9-7 Landing-gear Components (Ch. 9, Sec. 1: Inspection and Maintenance of Landing Gear)",
                   "page": 495, "page_label": "9-6",            // page_label and citation are optional
                   "snippet": "...", "url": "optional link to the document",
                   "citation": "AC 43.13-1B, Chapter 9, Section 1, par. 9-7 (Landing-gear Components), page 9-6" }],
  "work_order": { "title": "...", "asset": "N12345", "steps": ["..."], "parts": ["..."],
                  "est_hours": 3.0, "status": "draft" },
  "repeat_history": { "count": 4, "first_date": "2026-01-08", "last_date": "2026-05-19",
                      "card_ids": ["sdr-..."] },   // optional/null; drives the repeat alert, see below
  "timing": { "total_ms": 2100, "tokens_per_s": 95.0 },  // tokens_per_s may be null
  "cached": false,                                      // optional; true = a saved answer, not a fresh model call
  "cached_for": "FUME EVENT ON DESCENT IN COCKPIT"      // optional; only on a fallback: the fault this saved answer was written for
}
```
`cached` is optional and defaults to `false`. The backend sets it to `true` when it returns a saved answer instead of calling the model:
- The same fault text, tail and aircraft type were answered before. `cached_for` is absent.
- The live call failed (rate limit, timeout, bad model answer) and the backend fell back to the saved answer for the closest saved fault. `cached_for` holds that fault's text. If no saved fault is close enough, it returns a 502 instead.

On a saved answer, `timing.total_ms` is the time this request took, and `timing.tokens_per_s` is `null`. Saved answers are not counted in `/api/metrics`. The whole request should finish within about 50 s, so the fallback answers before the UI's 60 s limit. The UI labels these answers "Saved answer" and names `cached_for` when present. If the backend is unreachable, answers 429 or 5xx, or takes more than 60 s, the UI shows its own saved demo answer.
`repeat_history` counts earlier failures with the same ATA chapter and `failure_mode` on the tail in `asset`, using the same 7-day rule as `/api/repeats`, so both screens show the same number for a tail. If only `aircraft_type` is given, it uses that type, and with neither it uses the whole fleet. It is `null` when the failure mode is `other` or nothing matches.

`procedures` can be empty when no AC 43.13-1B or handbook section is relevant enough (e.g. fume events or emergency lights); the UI then says no matching procedure was found.

`procedures[].page` may be `null` when only the section is known. Two optional fields may also be present: `page_label`, the page number printed in the document (e.g. `"9-12"`; `page` is the PDF page, for links), and `citation`, the full reference string, e.g. `"AC 43.13-1B, Chapter 9, Section 1, par. 9-14 (Tire Inspection and Repair), page 9-12"`. AC excerpts come from `data/procedures/ac_43-13-1b.jsonl` (see `backend/README.md`). `ata_name` is optional on any JobCard or repeat row; the UI falls back to its own ATA chapter table.

### `POST /api/work-orders/{id}/approve`
Request: `{ "work_order": { ...edited fields... }, "approved_by": "name" }` → `{ "id": "wo-0001", "status": "approved" }`

### `GET /api/failure-modes`
→ `[{ "code": "brake_overheat", "label": "Brake overheat", "ata_chapter": "32" }]`
`ata_chapter` is `"*"` for failure modes that apply to any chapter (e.g. `fluid_leak`).

### `GET /api/metrics`
```json
{ "cards_processed": 1234, "extraction_field_accuracy": 0.91, "labelled_cards": 20,
  "repeat_groups_found": 57, "p50_latency_ms": 1800, "tokens_per_s": 95.0,
  "cost_per_100_cards_usd": null, "gpu": "AMD GPUs via AMD Token Factory", "model": "DeepSeek-V4-Flash" }
```
Every number except `cards_processed` and `repeat_groups_found` may be `null` until it is measured; the UI shows "Not measured yet". `gpu` comes from `GPU_LABEL` in the backend's `.env`, and `model` is the model id actually in use; the UI shows both in the sidebar, under each answer and on Results. `extraction_field_accuracy` is currently agreement with our rule-based parser's labels on `labelled_cards` ASRS cards, not hand-checked labels.

### `GET /api/health`
→ `{ "ok": true, "vllm": true, "evolus": false }`
`vllm` is `true` when the model service answers (checked at most once a minute), whichever OpenAI-compatible service `VLLM_BASE_URL` points to. `evolus` stays `false`: we dropped the Evolus integration.

## Conventions
- Errors return `{ "error": "message" }` with a 4xx/5xx status.
- Bad query or body values (e.g. `group_by=foo`, `limit=0`, a `fault_text` under 3 characters) return 422, e.g. `{ "error": "Invalid value for 'group_by': ..." }`.
- `/api/assist` returns 502 `{ "error": ... }` when the model call fails and no saved answer is close enough. `/api/ingest` returns 502 when the model call fails.
- CORS must allow the Vercel domain and `http://localhost:3000`.
- The frontend fixtures in `frontend/mocks/*.json` mirror these response shapes exactly.
