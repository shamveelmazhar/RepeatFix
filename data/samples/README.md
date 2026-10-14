# Samples

Small, committed data samples and the hand-labelled ground truth (`ground_truth.jsonl`, 20 cards). Full downloads go in `data/raw/`, which is git-ignored. See `scripts/download_data.md`.

| File | What | Source |
|---|---|---|
| `asrs_mechanic.jsonl` | 50 JobCards parsed from the NASA ASRS "Maintenance" report set (`mechanic.pdf`, reports dated 2022-02 to 2024-01). One JSON object per line. | NASA ASRS, US Government work, public |

## `asrs_mechanic.jsonl`
Regenerate it with:
```
cd backend && python -m app.asrs ../data/raw/mechanic.pdf -o ../data/samples/asrs_mechanic.jsonl
```
- `id` is `asrs-<ACN>`. The ACN (ASRS accession number) is also in `asrs.acn`; cite it to point back to the original report.
- `date` is the 1st of the report month: ASRS de-identifies dates to the month.
- `registration` is always null (ASRS is de-identified), so group repeats by `aircraft_type + ata_chapter + failure_mode`.
- `ata_chapter`, `component` and `failure_mode` come from deterministic rules in `backend/app/vocab.py`. ATA `00` ("General / Ground Operations") marks reports with no aircraft system involved, such as hazmat shipping or towing.
- `action_taken`, `parts` and `downtime_hours` are empty: ASRS does not code them. The LLM extraction step fills them from `raw_text`.
- The extra `asrs` object (problem, flight phase, maintenance type, primary problem) is ASRS-only context and is not part of the JobCard contract.
