# Samples

Small, committed data samples and the hand-labelled ground truth (`ground_truth.jsonl`, 20 cards). Full downloads go in `data/raw/`, which is git-ignored. See `scripts/download_data.md`.

| File | What | Source |
|---|---|---|
| `sdr_demo.jsonl` | 1,812 JobCards from FAA Service Difficulty Reports, Jan 2024 to Oct 2026, for the 40 B737 / A320-family / CRJ tails with the most repeat system faults. | FAA SDR, US Government work, public |
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

## `sdr_demo.jsonl`
The full three-year set (179,962 cards, ~200 MB) is too big for git. Rebuild it, and this sample, with:
```
cd backend && python -m app.sdr build ../data/raw/sdr/SDR-2024.csv ../data/raw/sdr/SDR-2025.csv ../data/raw/sdr/SDR-2026.csv \
    -o ../data/raw/sdr_cards.jsonl --demo ../data/samples/sdr_demo.jsonl
python -m app.sdr repeats ../data/samples/sdr_demo.jsonl
```
- `id` is `sdr-<OperatorControlNumber>`. The control number is also in `sdr.control_number`; cite it to point back to the FAA record.
- `registration` is the US tail number (`N` + `RegistryNNumber`), so repeats can be grouped per aircraft.
- `ata_chapter` is the first two digits of the FAA JASC code; the full code is in `sdr.jasc_code`.
- `aircraft_type` is the short name (`B737-800`, `A321neo`, `CRJ900`); the FAA make and model codes are in `sdr`.
- `symptom` and `action_taken` are split from the `Discrepancy` text at markers such as `CORRECTIVE ACTION:` or `C/A:`, or at the first sentence that starts the fix. About a quarter of records have no corrective action in the text, so `action_taken` is empty. `raw_text` keeps the text as filed.
- `parts` holds the part and component part numbers when the report gives them (about a third do).
- `failure_mode` comes from the coded `PartCondition` (corroded, cracked, leaking…) and keyword rules in `backend/app/sdr.py` and `vocab.py`. `downtime_hours` is null: SDR does not record it.
