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
  per-story importance/podcast scores and **content-verified** source links.
- **Source-link verification** — every model-authored link is fetched and checked that it is
  really the article it claims to be, not just any page that returns HTTP 200. A link is flagged
  **Unverified** (amber badge, never auto-deleted) when it 404s, is unreachable, silently bounces
  to the publisher's homepage, is a soft-404 "page not found" landing, or resolves to a real but
  **wrong** story whose page is missing the claimed headline words. Google-grounded citations show a
  **Grounded** badge and are trusted. Tools: a desk-wide one-pass **re-check all**, an admin
  **purge dead links**, a per-story and a **per-episode "Re-verify links"** button, a per-episode
  **dead-link report** + **Hide/Show unverified** toggle + **Copy verified links**, a global
  hide-unverified setting, and an amber unverified-count badge on the **Archive** nav item.
- **Weekly Podcast Producer** — a 15–20 min recording script with a verbatim host intro,
  `## Chapter` headers, per-story segment timers, and producer notes, generated Fridays.
  Uses a **hybrid** approach: host-flagged Podcast Prep candidates are prioritized
  alongside fresh independent research, with an audit trail of any pick set aside.
  Includes a configurable **Value 4 Value** support read (editable text, per-episode toggle) and a
  **"Links to New Sources for This Week"** show-notes list of clickable source hyperlinks after the
  script (with one-click backfill for older episodes).
- **Podcast Prep** — flag any story as an episode candidate and attach prep notes. The board sorts
  by date (grouped by edition, with per-day clear), podcast potential, or importance (choice
  remembered between visits), shows a live flagged-count badge in the nav, and can clear candidates
  for a single day, a date range, or all at once — each with an **Undo** and prep notes always kept.
- **Public story submissions** — a public `/submit` reader-tip form (and an embeddable
  version for partner sites) protected by a hidden honeypot and optional **Cloudflare
  Turnstile**. Tips are auto-linked when used in a briefing/episode, with a moderation
  dashboard (filter tabs, bulk reject, private notes, thank-you emails, auto-scraped
  article titles, and an **outlet/domain badge** on every tip). **Duplicate handling**:
  same-link tips are flagged, and can be **merged into one** — keeping a credited list of
  every submitter — one group at a time or in a single **"merge all duplicates"** sweep;
  any accidental merge can be **un-merged** back to the inbox.
- **Excluded & rejected review** — a dedicated `/excluded` page listing every briefing story
  ruled out of episode consideration and every rejected reader tip, each with one-click
  **Restore** to bring it back.
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
                   EpisodePage, Settings, Users, Submissions, Excluded, SharedBriefing,
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

## Migrating off Emergent / self-hosting (data export & import)

An admin-only **Data export & import** panel lives on the Settings page for moving the News Desk's
data to your own server (or keeping an off-platform backup).

1. **Capture production data.** Sign in to the **published Emergent site** as an admin, open
   **Settings → Data export & import**, and click **Download a full copy**. Because the app reads and
   writes the live database, the archive reflects production at the moment you take it. It is a single,
   human-readable JSON file (one section per collection — briefings, episodes, submissions,
   subscribers, users, settings/schedule, run history, delivery records — plus a header with the date
   and per-collection counts). User accounts are included with their **hashed** passwords (plaintext is
   never stored or exported), so everyone logs in unchanged after the move.
2. **Stand up the self-hosted app.** Follow *Getting started (local)* above against your own MongoDB,
   and set the secrets in `backend/.env` yourself — `SESSION_SECRET`, `MONGO_URL`/`DB_NAME`,
   `EMERGENT_LLM_KEY`, email/CAPTCHA keys. These are configuration, **not** part of the export (by
   design, for security).
3. **Load the data.** Sign in to the self-hosted app as an admin, open the same panel, choose the
   downloaded file, pick a mode, and load:
   - **Merge** (default) — add/replace records by their id; anything already present that isn't in the
     archive is left untouched.
   - **Replace** — clear each collection first, then load an exact copy. This is destructive and asks
     for an explicit confirmation before it runs.
   A per-collection summary reports how many records loaded (and any that failed).
4. **Sign in fresh.** Login sessions do not transfer (the session signing secret differs per
   environment), which is expected and harmless — everyone signs in again with their existing
   credentials.

### Requesting a raw native database dump from Emergent

The in-app export is portable JSON. If you'd instead prefer a **byte-for-byte native MongoDB dump**
(e.g. a `mongodump` BSON archive), that lives in Emergent's managed database and is provided by the
platform, not by this app. Request it through Emergent support / your account contact, asking for a
`mongodump` of the app's database for the deployed environment. Use it to restore with `mongorestore`
against your own MongoDB. The in-app JSON export and a native dump are complementary — either can
rehydrate a self-hosted instance.

## Notes

- **Source-link verification is a heuristic, non-destructive gate.** The desk fetches each
  model-authored link and marks it `verified=False` (keeps it, badges it amber) unless it returns a
  live page that passes a homepage-bounce check, a soft-404 title/h1 check, and a title-match check
  (at least half of the claimed headline's distinctive words appear on the page). This deliberately
  errs toward flagging rather than hiding — a reworded real headline or an anti-bot 403 can read as
  unverified, so links are never auto-removed; an admin can purge them explicitly.
- Environment secrets and database data are **not** included in the repository.
- Scheduled jobs run in-process against an admin-configured schedule (defaults: daily briefing
  22:00, weekly episode Fridays 16:00, in the configured home timezone; each fires only if that
  edition isn't already produced). Times, weekday, and timezone are editable in Settings.
