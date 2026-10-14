# Data sources (all public)

Save full downloads to `data/raw/`, which is git-ignored. Commit only small samples to `data/samples/`.

| # | Source | What | Where | Licence |
|---|---|---|---|---|
| 1 | NASA ASRS | Maintenance (mechanic) report set: de-identified narratives | https://asrs.arc.nasa.gov/search/reportsets.html | US Government work, public |
| 2 | FAA Service Difficulty Reports (SDR) | Yearly CSVs of malfunction/defect reports, with registration, part, ATA → real per-aircraft repeats | https://www.faa.gov/av-info/download_SDR (query tool: https://sdrs.faa.gov) | US Government work, public |
| 3 | FAA AC 43.13-1B | Acceptable methods, techniques and practices for aircraft inspection and repair → cited procedures | https://www.faa.gov/regulations_policies/advisory_circulars/index.cfm/go/document.information/documentID/99861 | US Government work, public |
| 4 | FAA Aviation Maintenance Technician Handbook (FAA-H-8083-30B General, -31B Airframe) | More cited procedures | https://www.faa.gov/regulations_policies/handbooks_manuals/aviation | US Government work, public |
| 5 | MaintNet (UND aviation logbook, 6,169 records) | Very messy abbreviated log lines; good stress test | arXiv:2005.12443 | **Licence unconfirmed: do not use until checked** |

## Notes
- **ASRS** has no tail numbers. Group repeats by `aircraft_type + ata_chapter + failure_mode`.
- **SDR** has an aircraft registration, so it can find true per-tail repeats. Check on day 1 that the download page is live, because AIN reported maintenance downtime in mid-2026. Start with one recent year and filter to 2–3 common types (e.g. B737, A320, CRJ) to keep the demo focused.
- **AC 43.13-1B:** the indexed file is `AC_43.13-1B_CHG_1_Ed_Upd_FAA.pdf` (CHG 1 editorial update, May 2024, 756 pages). Save it to `data/raw/ac/`. The older `AC_43.13-1B_w-chg1.pdf` (2002) has the same content, so it isn't indexed separately.
- Record each file's download date here.
