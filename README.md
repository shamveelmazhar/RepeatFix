# RepeatFix

**Repeat-failure hunter for messy maintenance logs, running on AMD GPUs via AMD Token Factory.**

RepeatFix reads messy aviation maintenance records (NASA ASRS mechanic reports and FAA Service Difficulty Reports) and turns them into structured job cards. From those it finds the aircraft and components that keep failing. When a new fault comes in, it gives the technician the most similar past fixes, the likely causes and the matching FAA procedure (AC 43.13-1B), with citations. It also drafts a work order for a supervisor to approve. All model inference runs on AMD GPUs through AMD Token Factory, the model API the hackathon is hosted on.

We're Shamveel Mazhar and Nida Amir, and we're building RepeatFix for the AMD Developer Hackathon: ACT III (lablab.ai). Nida owns the backend (the model calls, FastAPI, the data pipelines) and I own the frontend, the data work and the submission.

- Plan and schedule: [PLAN.md](PLAN.md)
- Contributor guide and team conventions: [CLAUDE.md](CLAUDE.md)
- API contract: [docs/API.md](docs/API.md)
- Data sources: [scripts/download_data.md](scripts/download_data.md)

*Data: public US Government sources (NASA ASRS, FAA SDR, FAA AC 43.13-1B, FAA AMT Handbook).*
