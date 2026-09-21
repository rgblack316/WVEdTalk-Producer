# WVEdTalk Producer — WV Education News Desk

A statewide research and editorial assistant for a West Virginia education podcast
(**WVEdTalk**). Each run, an LLM with **live web search** researches K–12 and higher-ed
news across all 55 WV counties and produces a structured **Daily Briefing**, and every
Friday it independently reassembles the week into a recording-ready **weekly episode
script** for the host. The desk adds podcast-prep tooling, email digests, watchlist
alerts, region filtering, Markdown exports, multi-user accounts, and public share links.

## Features

- **Daily Briefing** — statewide research (The Big Three, K–12, Higher Ed, State Policy,
  Trends, Podcast Opportunities, Source Log) following a strict editorial ruleset, with
  per-story importance/podcast scores and verified source links.
- **Weekly Podcast Producer** — a 15–20 min recording script with a verbatim host intro
  plus producer notes, generated Fridays at 2:00 PM ET. Uses a **hybrid** approach:
  host-flagged Podcast Prep candidates are prioritized alongside fresh independent research.
- **Podcast Prep** — flag any story as an episode candidate and attach prep notes.
- **Multi-user auth** — email + password accounts with three roles:
  - **Admin** — everything, including user management.
  - **Editor** — everything except user management.
  - **Viewer** — read-only (no runs, tagging, edits, emails, or setting changes).
- **Public share links** — copy a tokenized link to any briefing that opens read-only
  without a login.
- **Integrations** — email digests + episode emails (Emergent-managed Resend), watchlist
  alerts, 8-region filtering & keyword search, Markdown copy/download, script-length dial,
  auto-lock on inactivity.

## Tech stack

- **Backend** — FastAPI (Python 3.11), Motor (async MongoDB), Pydantic v2. All routes under
  `/api`; auth routes and token-validated public routes are open, everything else is guarded.
- **Frontend** — Vite + React 19 + TypeScript (strict), Tailwind v4, shadcn/ui, TanStack Query,
  React Router.
- **LLM** — Gemini 3.1 Pro (`gemini-3.1-pro-preview`) via the Emergent Universal key with
  Google Search grounding (the only reliably grounded live-search path over the proxy).
- **Email** — Emergent-managed Resend integration.

## Project layout

```
backend/           FastAPI app
  lib/             auth, dates, db, desk (daily), producer (weekly), email_digest, share tokens
  models/          Pydantic models (briefing, episode, config, user)
  routers/         auth, public, briefings, episodes, settings, users
  server.py        app + api_router (/api), lifespan (schedulers, seed admin)
frontend/          Vite + React app
  src/pages/       Home, Archive, BriefingPage, StoryDetail, Candidates, Episodes,
                   EpisodePage, Settings, Users, SharedBriefing
  src/components/  DeskLayout, AuthGate, BriefingView, StoryCard, ui/*
  src/lib/         api (typed fetch over /api), types, useAuth, regions, episode, session
memory/            spec.md, test_credentials.md
```

## Getting started (local)

Prerequisites: Python 3.11 (+venv), Node 18+ with Yarn, a running MongoDB.

```bash
# 1) Backend config
cp backend/.env.example backend/.env
# edit backend/.env — set SESSION_SECRET (required), MONGO_URL/DB_NAME, and the
# EMERGENT_LLM_KEY / EMERGENT_EMAIL_KEY if you want research + email to work.

# 2) Backend
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# 3) Frontend (in another terminal)
cd frontend
yarn install
yarn dev        # http://localhost:3000  (proxies /api → http://localhost:8001)
```

### First login

A bootstrap admin is seeded automatically the first time the app starts with an empty
`users` collection:

- **Username:** `admin`
- **Password:** `admin`

**Change this password immediately after signing in** (Settings → My account → Change password),
then invite the rest of your team from the **Users** tab (each gets a one-time temporary password).
The seed only runs on an empty `users` collection, so it never overwrites accounts on an existing
database.

## Environment variables

See [`backend/.env.example`](backend/.env.example). `SESSION_SECRET` is **required** (the
server refuses to boot without it). `EMERGENT_LLM_KEY` powers research; `EMERGENT_EMAIL_KEY`
powers email. `MONGO_URL`/`DB_NAME` point at your database. The real `.env` is never
committed.

## Programmatic / downstream access

Machine clients (e.g. a downstream agent reading briefings) authenticate with the
`X-Desk-Passcode: <APP_PASSCODE>` header instead of a login session, e.g.:

```bash
curl -H "X-Desk-Passcode: $APP_PASSCODE" \
  https://your-app/api/briefings/2026-09-20
```

## Notes

- Environment secrets and database data are **not** included in the repository.
- Scheduled jobs run in-process: the daily briefing at ~6:00 AM ET and the weekly episode
  Fridays at 2:00 PM ET (only if not already produced).
