# WVEdTalk Producer — WV Education News Desk

A statewide research and editorial assistant for a West Virginia education podcast
(**WVEdTalk**). Each run, an LLM with **live web search** researches K–12 and higher-ed
news across all 55 WV counties and produces a structured **Daily Briefing**, and every
Friday it independently reassembles the week into a recording-ready **weekly episode
script** for the host. The desk adds podcast-prep tooling, email digests with delivery
tracking, a public reader-tip inbox, public newsletter subscribers, watchlist alerts,
region filtering, Markdown exports, a configurable run schedule, multi-user accounts, and
public share links.

## Features

- **Daily Briefing** — statewide research (The Big Three, K–12, Higher Ed, State Policy,
  Trends, Podcast Opportunities, Source Log) following a strict editorial ruleset, with
  per-story importance/podcast scores and verified source links.
- **Weekly Podcast Producer** — a 15–20 min recording script with a verbatim host intro,
  `## Chapter` headers, per-story segment timers, and producer notes, generated Fridays.
  Uses a **hybrid** approach: host-flagged Podcast Prep candidates are prioritized
  alongside fresh independent research, with an audit trail of any pick set aside.
  Includes a configurable **Value 4 Value** support read (editable text, per-episode toggle).
- **Podcast Prep** — flag any story as an episode candidate and attach prep notes.
- **Public story submissions** — a public `/submit` reader-tip form (and an embeddable
  version for partner sites) protected by a hidden honeypot and optional **Cloudflare
  Turnstile**. Tips are auto-linked when used in a briefing/episode, with a moderation
  dashboard (filter tabs, bulk reject, private notes, thank-you emails).
- **Email digests + delivery tooling** — the full briefing is emailed to admin recipients
  and public subscribers. Sends record per-address outcomes, **alert admins on any
  failure**, support a **test send** (shows the exact provider error), and a **resend to
  subscribers who missed it**. The weekly episode email is admin-recipients-only.
- **Public subscribers** — a public `/subscribe` page and copy-paste embeddable signup
  widget; each digest is sent individually with a one-click unsubscribe link.
- **Configurable schedule + run history** — admins set the daily/weekly run times and a
  home timezone (DST-aware); every run (scheduled or manual) is logged, and scheduled-run
  failures alert admins by email.
- **Multi-user auth** — email + password accounts with three roles:
  - **Admin** — everything, including user management and schedule/settings.
  - **Editor** — everything except user management.
  - **Viewer** — read-only (no runs, tagging, edits, emails, or setting changes).
- **Public share links** — copy a tokenized link to any briefing that opens read-only
  without a login.
- **More integrations** — watchlist alerts, 8-region filtering & keyword search, Markdown
  copy/download, script-length dial, auto-lock on inactivity.

## Tech stack

- **Backend** — FastAPI (Python 3.11), Motor (async MongoDB), Pydantic v2. All routes under
  `/api`; auth routes and token-validated public routes are open, everything else is guarded.
- **Frontend** — Vite + React 19 + TypeScript (strict), Tailwind v4, shadcn/ui, TanStack Query,
  React Router.
- **LLM** — Gemini 3.1 Pro (`gemini-3.1-pro-preview`) via the Emergent Universal key with
  Google Search grounding (the only reliably grounded live-search path over the proxy).
- **Email** — Emergent-managed Resend integration.
- **CAPTCHA** — Cloudflare Turnstile on the public submission form (optional; honeypot-only
  fallback when keys are absent).

## Project layout

```
backend/           FastAPI app
  lib/             auth, dates, db, desk (daily), producer (weekly),
                   email_digest, turnstile, share tokens
  models/          Pydantic models (briefing, episode, config, user, subscriber, submission)
  routers/         auth, public, briefings, episodes, settings, users, submissions
  server.py        app + api_router (/api), lifespan (schedulers, seed admin)
frontend/          Vite + React app
  src/pages/       Home, Archive, BriefingPage, StoryDetail, Candidates, Episodes,
                   EpisodePage, Settings, Users, Submissions, SharedBriefing,
                   Subscribe, Unsubscribe, SubmitStory
  src/components/  DeskLayout, AuthGate, BriefingView, ScriptView, StoryCard,
                   TurnstileWidget, ui/*
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
# TURNSTILE_* are optional (leave blank to disable the CAPTCHA).

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

See [`backend/.env.example`](backend/.env.example). The real `.env` is never committed.

| Variable | Required | Purpose |
| --- | --- | --- |
| `SESSION_SECRET` | **Yes** | Signs session cookies + share/unsubscribe tokens. Server refuses to boot without it. |
| `MONGO_URL`, `DB_NAME` | Yes | Database connection. |
| `CORS_ORIGINS` | Yes | Comma-separated allowed frontend origins (no wildcard when using cookies). |
| `APP_URL` | Yes | Public base URL used in outgoing email links + share pages. |
| `APP_PASSCODE` | Yes | Machine credential for downstream `X-Desk-Passcode` access. |
| `EMERGENT_LLM_KEY` | For research | Gemini 3.1 Pro + Google Search grounding. |
| `EMERGENT_EMAIL_KEY`, `EMAIL_FROM_NAME` | For email | Managed Resend sender. |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | Optional | Cloudflare Turnstile on the public submit form; blank = honeypot-only. |

## Email delivery notes

- The daily briefing goes to admin recipients (compact edition + login-protected link) **and**
  active public subscribers (the full briefing inline + a no-login share link). Each address is
  sent individually so addresses stay private.
- Every send returns per-audience counts and a **reason for each failed address**, records the
  outcome to the `digest_deliveries` collection, and **emails admins an alert** if any subscriber
  send fails. Use Settings → Email digest to **send a test copy** or **resend to subscribers who
  missed it**.
- The managed email proxy returns `HTTP 422 undeliverable_recipient` for invalid/bouncing
  addresses (and for any `example.com` address). That — not the safety gate — is the usual reason
  a public subscriber does not receive a briefing while the admin recipient (a valid inbox) does.

## Programmatic / downstream access

Machine clients (e.g. a downstream agent reading briefings) authenticate with the
`X-Desk-Passcode: <APP_PASSCODE>` header instead of a login session, e.g.:

```bash
curl -H "X-Desk-Passcode: $APP_PASSCODE" \
  https://your-app/api/briefings/2026-09-20
```

## Notes

- Environment secrets and database data are **not** included in the repository.
- Scheduled jobs run in-process against an admin-configured schedule (defaults: daily briefing
  22:00, weekly episode Fridays 16:00, in the configured home timezone; each fires only if that
  edition isn't already produced). Times, weekday, and timezone are editable in Settings.
