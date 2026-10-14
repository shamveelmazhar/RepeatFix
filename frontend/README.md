# Frontend (owner: Shamveel, branch `shamveel/frontend`)

Next.js + Tailwind, deployed on Vercel. There are three screens: **Fix a fault**, **Repeat failures** and **Results**. The UI rules are in `../CLAUDE.md`, and the response shapes are in `../docs/API.md`.

Scaffold: `npx create-next-app@latest . --ts --tailwind --app --eslint`. Put fixtures in `mocks/`, and set `NEXT_PUBLIC_USE_MOCKS=true` to use them.
