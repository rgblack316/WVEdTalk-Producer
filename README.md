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
- **LLM** — configurable per deployment in Settings → Integrations: **Google Gemini** (default,
  `google-genai` with Google Search grounding) or **OpenAI** (Responses API web search). No Emergent
  dependency.
- **Email** — Resend (default) with an SMTP fallback, using the operator's own account/keys.
- **CAPTCHA** — Cloudflare Turnstile on the public submission form (optional; honeypot-only
  fallback when keys are absent).

## Project layout

```
backend/           FastAPI app
  lib/             auth, dates, db, desk (daily), producer (weekly), email_digest,
                   turnstile, share tokens, llm (Gemini/OpenAI provider layer),
                   mailer (Resend/SMTP), config_secrets (encrypted in-app keys)
  models/          Pydantic models (briefing, episode, config, user, subscriber, submission)
  routers/         auth, setup (first-run), public, briefings, episodes, settings,
                   users, submissions, data_io (backup export/import)
  server.py        app + api_router (/api), lifespan (schedulers; no default seed)
frontend/          Vite + React app
  src/pages/       Home, Archive, BriefingPage, StoryDetail, Candidates, Episodes,
                   EpisodePage, Settings, Users, Submissions, Excluded, SharedBriefing,
                   Subscribe, Unsubscribe, SubmitStory
  src/components/  DeskLayout, AuthGate, SetupWizard, IntegrationsPanel, BriefingView,
                   ScriptView, StoryCard, TurnstileWidget, ui/*
  src/lib/         api (typed fetch over /api), types, useAuth, regions, episode, session
memory/            spec.md, test_credentials.md
install.sh / upgrade.sh    self-hosted Docker install & upgrade
docker-compose.yml, env.example, plan/plan.md
```

## Install & upgrade (self-hosted, Docker)

The self-hosted edition ships two scripts for a turnkey deployment on a fresh **Ubuntu/Debian**
server. They install Docker if needed, build the stack (MongoDB + backend + frontend/nginx), and
keep your data in a Docker volume across upgrades.

### First install

Download just `install.sh` and run it — the script clones the repo for you:

```bash
# On a fresh Ubuntu/Debian host, as a normal (non-root) user with sudo:
curl -fsSL https://raw.githubusercontent.com/rgblack316/WVEdTalk-Producer/main/install.sh -o install.sh
bash install.sh
```

(Already have a clone? Just run `./install.sh` from inside it and the script uses that checkout in
place instead of cloning.)

`install.sh` will:
1. Install Docker Engine + the Compose plugin if missing (adds Docker's official apt repo), enable
   the daemon, and add you to the `docker` group.
2. Clone the repo into `~/wvedtalk` (override with `REPO_URL=` / `INSTALL_DIR=`), or run in place if
   you're already inside a checkout.
3. Create `.env` from `env.example` and generate a `SESSION_SECRET`. `APP_PASSCODE` is left blank
   (optional — see below).
4. Build and start the stack, then wait until the app answers.

It prints the site URL and points you at the **first-run setup screen** (no default password). Open
the site, create your first admin (or import a backup), then open **Settings → Integrations** to add
your AI + email keys. Config lives in `.env`; the only required value is `SESSION_SECRET`
(auto-generated). `HTTP_PORT` (default 80) sets the published port.

### Upgrading

```bash
cd ~/wvedtalk      # your install directory
./upgrade.sh
```

`upgrade.sh` is safe-by-default: it **refuses** to run on uncommitted local changes, a detached
HEAD, or a diverged branch; it **always takes a MongoDB backup first** (`mongodump` into
`backups/pre-upgrade-<timestamp>/`), then fast-forwards the code, rebuilds, and restarts. Your data
stays in its Docker volume and is never touched. The script prints the exact `mongorestore` command
to roll back.

> **"Update available" banner:** admins see an in-app banner when a newer release is published. The
> app compares its baked-in `backend/VERSION` against the same file on the GitHub default branch
> (`GET /api/version`, cached 1h). **To cut a release, bump `backend/VERSION`** (e.g. `1.0.0` →
> `1.1.0`) and push — running installs will then show the banner until an operator runs `./upgrade.sh`.
> The check is best-effort and fails closed (no banner) if GitHub is unreachable. Override the source
> with `GITHUB_REPO` / `UPDATE_BRANCH` env vars.

> **Health & startup order:** each service defines a Docker `healthcheck` (backend probes the
> auth-free `GET /api/`, not the 401-guarded `/api/schedule/next`); `backend` waits for `mongo`
> healthy and `frontend` waits for `backend` healthy via `depends_on: condition: service_healthy`.

> **Publishing the repo first:** use Emergent's **Save → Save to GitHub** to push this project to
> `github.com/rgblack316/WVEdTalk-Producer` so `install.sh` can clone it. Secrets/`.env` are excluded
> from the push by design — `install.sh` generates `SESSION_SECRET`, and the rest are managed in-app.

## Getting started (local dev)

Prerequisites: Python 3.11 (+venv), Node 18+ with Yarn, a running MongoDB.

```bash
# 1) Backend config
cp backend/.env.example backend/.env
# edit backend/.env — set SESSION_SECRET (required) and MONGO_URL/DB_NAME.
# AI (GEMINI_API_KEY/OPENAI_API_KEY) and email (RESEND_API_KEY/SMTP_*) keys are optional here —
# you'll normally set them in-app via Settings → Integrations. TURNSTILE_* are optional too.

# 2) Backend
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# 3) Frontend (in another terminal)
cd frontend
yarn install
yarn dev        # http://localhost:3000  (proxies /api → http://localhost:8001)
```

## First-run setup

There is **no** default `admin`/`admin` login. On a brand-new install (empty `users` collection) the
app opens a **setup wizard** instead of the login screen, with two choices:

- **Create the first admin** — your email + a password (min 8 characters); you're signed in
  immediately. One-shot — the endpoint refuses once any user exists.
- **Import a backup** — upload a JSON export from another News Desk. Restores every account (with
  their existing hashed passwords) and all data in one step; you then sign in with your existing
  credentials.

Invite the rest of your team from the **Users** tab (each gets a one-time temporary password).

## Integrations (in-app credentials — AI, email, Turnstile)

Everything third-party is managed in **Settings → Integrations** (admin-only), so an operator never
edits code or `.env` after install:

- **AI / Research model** — pick **Gemini** (default, Google Search grounding) or **OpenAI**, paste
  the key, set the model, and use **Test AI connection**.
- **Email — Resend (default)** plus an **SMTP fallback** — enter either (or both), each with a
  **send-test** button.
- **Turnstile** — the public-form CAPTCHA site/secret keys.

Keys are entered once, stored **encrypted at rest** (never echoed back — shown masked), and take
precedence over any `.env` fallback. **Scheduled runs and email digests default to OFF** on a fresh
install — enable them in Integrations once your keys test green, so nothing errors before it's
configured.

## Environment variables

See [`backend/.env.example`](backend/.env.example). The real `.env` is never committed.

| Variable | Required | Purpose |
| --- | --- | --- |
| `SESSION_SECRET` | **Yes** | Signs session cookies + share/unsubscribe tokens. Server refuses to boot without it. |
| `MONGO_URL`, `DB_NAME` | Yes | Database connection. |
| `CORS_ORIGINS` | Yes | Comma-separated allowed frontend origins (no wildcard when using cookies). |
| `APP_URL` | Yes | Public base URL used in outgoing email links + share pages. |
| `APP_PASSCODE` | Optional | Machine credential for `X-Desk-Passcode` access; blank disables programmatic access (human logins unaffected). |
| `LLM_PROVIDER`, `GEMINI_API_KEY` / `OPENAI_API_KEY`, `LLM_MODEL` | For research | AI provider; normally set in Settings → Integrations (env is initial fallback). |
| `EMAIL_PROVIDER`, `RESEND_API_KEY` / `SMTP_*`, `EMAIL_FROM`, `EMAIL_FROM_NAME` | For email | Resend default + SMTP fallback; normally set in Settings → Integrations. |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | Optional | Cloudflare Turnstile on the public submit form; blank = honeypot-only. |

## Email delivery notes

- The daily briefing goes to admin recipients (compact edition + login-protected link) **and**
  active public subscribers (the full briefing inline + a no-login share link). Each address is
  sent individually so addresses stay private.
- Every send returns per-audience counts and a **reason for each failed address**, records the
  outcome to the `digest_deliveries` collection, and **emails admins an alert** if any subscriber
  send fails. Use Settings → Email digest to **send a test copy** or **resend to subscribers who
  missed it**.
- Delivery uses **your own Resend account (or SMTP fallback)** configured in Settings → Integrations.
  Invalid/bouncing recipients surface the provider's own per-address error (Resend, for example,
  rejects `example.com` and undeliverable mailboxes). That — not the safety gate — is the usual
  reason a public subscriber does not receive a briefing while a valid admin inbox does. Resend
  requires a verified sending domain.

## Programmatic / downstream access

Machine clients (e.g. a downstream agent reading briefings) authenticate with the
`X-Desk-Passcode: <APP_PASSCODE>` header instead of a login session, e.g.:

```bash
curl -H "X-Desk-Passcode: $APP_PASSCODE" \
  https://your-app/api/briefings/2026-09-20
```

## Migrating off Emergent / self-hosting (data export & import)

An admin-only **Data export & import** panel lives on the Settings page for moving the News Desk's
data to your own server (or keeping an off-platform backup). On a brand-new self-hosted install you
can also load that same export directly from the **first-run setup wizard** ("Import a backup"),
which restores accounts + data in one step.

1. **Capture production data.** Sign in to the **published Emergent site** as an admin, open
   **Settings → Data export & import**, and click **Download a full copy**. Because the app reads and
   writes the live database, the archive reflects production at the moment you take it. It is a single,
   human-readable JSON file (one section per collection — briefings, episodes, submissions,
   subscribers, users, settings/schedule, run history, delivery records — plus a header with the date
   and per-collection counts). User accounts are included with their **hashed** passwords (plaintext is
   never stored or exported), so everyone logs in unchanged after the move.
2. **Stand up the self-hosted app.** Run `install.sh` (Docker) or follow *Getting started (local dev)*
   against your own MongoDB. The only secret you must set is `SESSION_SECRET` (the install script
   generates it); AI, email, and Turnstile keys are added in-app via **Settings → Integrations** and
   are **not** part of the export (by design, for security).
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
- Scheduled jobs run in-process against an admin-configured schedule **only when scheduled runs are
  enabled in Settings → Integrations** (defaults: daily briefing 22:00, weekly episode Fridays 16:00,
  in the configured home timezone; each fires only if that edition isn't already produced). Times,
  weekday, and timezone are editable in Settings.
