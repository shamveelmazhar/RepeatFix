# RepeatFix API contract (v0)

Frontend and backend share this contract. Change it only through a PR that the other teammate reviews. Base URL: `NEXT_PUBLIC_API_URL` (e.g. `https://<droplet>/`). All bodies are JSON unless noted.

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
Ingests a CSV upload, an image (handwritten/typed log entry), or `{ "text": "..." }`. Use multipart for files.
→ `{ "cards": JobCard[], "model_ms": 1234 }`

### `GET /api/cards?limit=50&offset=0&ata=32&asset=N12345`
→ `{ "total": 1234, "cards": JobCard[] }`

### `GET /api/cards/{id}`
→ `JobCard`

### `GET /api/repeats?group_by=aircraft|component&min_count=2`
Returns rows ranked by downtime, then count.
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
                      "card_ids": ["sdr-..."] },   // optional/null: earlier cards with the same failure_mode
                                                     // on this asset (or fleet if no asset); drives the repeat alert
  "timing": { "total_ms": 2100, "tokens_per_s": 95.0 },  // tokens_per_s may be null
  "cached": false                                       // optional; true = a saved answer, not a fresh model call
}
```
`cached` is optional and defaults to `false`. The backend sets it to `true` when it returns a saved answer instead of calling the model: the same fault text was answered before, or the live call failed (rate limit, timeout, model error) and it fell back to the saved answer for the closest demo fault. The UI labels these answers "Saved answer". If the backend itself is unreachable, or answers 429 or 5xx, the UI falls back to its own saved demo answer.
`procedures[].page` may be `null` when only the section is known. Two optional fields may also be present: `page_label`, the page number printed in the document (e.g. `"9-12"`; `page` is the PDF page, for links), and `citation`, the full reference string, e.g. `"AC 43.13-1B, Chapter 9, Section 1, par. 9-14 (Tire Inspection and Repair), page 9-12"`. AC excerpts come from `data/procedures/ac_43-13-1b.jsonl` (see `backend/README.md`). `ata_name` is optional on any JobCard or repeat row; the UI falls back to its own ATA chapter table.

### `POST /api/work-orders/{id}/approve`
Request: `{ "work_order": { ...edited fields... }, "approved_by": "name" }` → `{ "id": "wo-0001", "status": "approved" }`

### `GET /api/failure-modes`
→ `[{ "code": "brake_overheat", "label": "Brake overheat", "ata_chapter": "32" }]`

### `GET /api/metrics`
```json
{ "cards_processed": 1234, "extraction_field_accuracy": 0.91, "labelled_cards": 20,
  "repeat_groups_found": 57, "p50_latency_ms": 1800, "tokens_per_s": 95.0,
  "cost_per_100_cards_usd": 0.12, "gpu": "AMD Instinct MI300X", "model": "Qwen2.5-VL-7B-Instruct" }
```

### `GET /api/health`
→ `{ "ok": true, "vllm": true, "evolus": true }`

## Conventions
- Errors return `{ "error": "message" }` with a 4xx/5xx status.
- CORS must allow the Vercel domain and `http://localhost:3000`.
- The frontend fixtures in `frontend/mocks/*.json` mirror these response shapes exactly.
