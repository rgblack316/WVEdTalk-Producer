# WV Education News Desk — Self-Hosted Edition

A standalone, fully self-hostable build of the WV Education News Desk that runs on an operator's own
server with their own AI and email accounts — no Emergent platform, keys, or services involved.

## Who it's for
- The desk owner/operator who wants to run the News Desk on their own Ubuntu/Debian server (or a VM),
  own all the data and credentials, and update it on their own schedule.
- Non-specialist operators: setup, configuration, and upgrades are designed to be doable without
  editing code — one install command, then everything else from inside the app.

> Context: this is a separate track from the current Emergent-hosted app. The existing app keeps
> running unchanged; this plan is built in a fork so the two versions stay independent. Data moves
> between them via the app's existing backup export/import (see User flow).

## Core features and experience
Everything the current News Desk does — daily statewide briefings, the weekly podcast script
producer, podcast prep, reader submissions, subscribers, digests, source-link verification, archive,
roles, share links, data export/import — carries over unchanged. What's new or different in the
self-hosted edition:

- **Bring-your-own AI model.** The operator chooses the research model and supplies their own key:
  - **Google Gemini (default)** with live Google Search grounding (the grounded-citation behavior the
    desk relies on).
  - **OpenAI** as an alternative, using its web-search capability.
  Switching providers is a setting; no redeploy needed.
- **Bring-your-own email.** Two options, both the operator's own accounts:
  - **Resend (default)** via the operator's Resend API key and a verified sending domain.
  - **SMTP fallback** (any mailbox/host) used when Resend isn't configured or a Resend send fails.
- **In-app Integrations settings.** A new admin-only "Integrations" area on the Settings page holds
  every third-party credential — AI provider + key + model, Resend key/sender, SMTP host/port/
  credentials, and the Turnstile CAPTCHA keys. Keys are entered once in the UI, shown masked
  afterward, and testable in place ("test AI connection", "send test email via Resend / via SMTP").
  Env-file values act as an initial fallback, but day-to-day management lives in the app.
- **First-run setup wizard.** On a brand-new install (empty database) the app opens a setup screen
  instead of a default login. The operator either:
  1. **Creates the first admin account** (name, email, password), or
  2. **Imports an existing backup** — uploads a JSON export from the current app, which restores all
     accounts (with their existing passwords) and data, completing a migration in one step.
  The old built-in `admin`/`admin` default login is removed entirely.
- **Safe defaults for runs.** Scheduled research runs and email digests start **disabled** on a fresh
  install and are switched on in Settings once the operator has entered working AI and email keys —
  so nothing errors out before it's configured.
- **One-command install and upgrade.** An `install.sh` sets up a fresh Ubuntu/Debian host end to end
  (installs Docker, fetches the app, starts it); an `upgrade.sh` safely updates it later, always
  taking a database backup first and never touching stored data.

## User flow
1. **Install.** On a fresh server the operator runs the install command. It installs Docker if
   missing, pulls the app, generates the required security secret, and starts everything. It prints
   the site URL and points the operator at the first-run setup screen (no default password is shown).
2. **First-run setup.** The operator opens the site and either creates the first admin account or
   uploads a backup exported from the current app. If they import, their existing users and data come
   across and they sign in with their current credentials.
3. **Configure integrations.** As an admin, they open Settings → Integrations, enter their AI key +
   model and their email details (Resend and/or SMTP), and use the "test" buttons to confirm each
   works. They optionally add Turnstile keys for the public submission form.
4. **Turn on automation.** With keys verified, they enable the daily briefing schedule and email
   digests in Settings. From here the app behaves exactly like the hosted version.
5. **Operate.** Everyday use — briefings, weekly scripts, prep, submissions, subscribers, exports — is
   identical to today.
6. **Upgrade later.** When a new version is published, the operator runs the upgrade command. It
   refuses to run on unsafe states, backs up the database, updates the code, and restarts — data in
   place.

## UI/UX feel
- Matches the current desk styling throughout; the new surfaces (Integrations panel, setup wizard)
  reuse the existing look — clear headings, plain-language labels, calm and reassuring.
- The Integrations panel groups settings into "AI / Research model", "Email — Resend", "Email — SMTP
  fallback", and "Turnstile", each with an inline test action and a masked display of any saved
  secret (never echoing the real value).
- The setup wizard is a single focused screen with two obvious choices (create admin vs. import a
  backup), a progress/result readout on import, and no jargon.
- Destructive or sensitive actions (importing a backup, replacing data) carry an explicit confirm, as
  they do in the existing export/import tool.

## Implementation phases

### Phase 1 — MVP (built now)
The complete hard cut, delivered in one build:
- Remove all Emergent dependencies (managed LLM key, managed email, the Emergent integration library).
- **Configurable AI provider** — Gemini (default, with Google Search grounding) and OpenAI — with the
  key and model set in-app. Phase 1 begins with a short **grounding-parity check**: confirm that
  direct Gemini still yields source citations so the "Grounded" badge and link verification keep
  working; if a citation can't be matched it falls back to the normal verified/unverified link
  treatment (nothing breaks, the badge just isn't shown for that link).
- **Email** — Resend (default) with SMTP fallback, configured in-app.
- **In-app Integrations settings** — all credentials managed and tested from Settings, with env as
  initial fallback; secrets stored so a database copy alone doesn't expose live keys.
- **First-run setup wizard** — create first admin or import a backup; default `admin`/`admin` removed.
- **Runs/digests default to off** until keys are configured.
- **Docker deployment** with working `install.sh` (auto-installs Docker, clones the repo, starts the
  stack) and `upgrade.sh` (git-safety checks, mandatory pre-upgrade database backup, in-place update).

### Phase 2 — Later
- Scheduled/automatic off-server backups on a cadence, and a short history of recent backups.
- Selective export/import (choose collections or a date range) for partial transfers.
- An in-app "update available" indicator that surfaces when a newer version has been published.

### Phase 3 — Later
- Optional one-click HTTPS/own-domain setup (e.g. automatic certificate issuance) in front of the app.
- Additional AI providers beyond Gemini/OpenAI, and additional email providers, behind the same
  Integrations settings.

## Assumptions
- The self-hosted edition is a separate fork; the current Emergent-hosted app is left running and
  unchanged. Migration between them is one-directional for now: export from the current app, import on
  the self-hosted first run.
- Target OS for the automated install/upgrade is Ubuntu/Debian with Docker; other operating systems
  require installing Docker manually first, after which the same stack runs.
- The operator provides and pays for their own AI and email accounts. Gemini is the default AI
  provider to stay closest to current behavior (Google Search grounding); OpenAI is offered as an
  alternative. Exact default model names are chosen at build time to match current research quality.
- Email requires the operator's own Resend account with a verified sending domain, or their own SMTP
  server/credentials; without at least one configured, digests stay off and no mail is sent.
- `APP_PASSCODE` (the programmatic API header credential) is optional and blank by default; it only
  needs setting if an outside automation will read the API without logging in.
- Integration credentials are managed in-app and stored on the server (encrypted at rest). They are
  treated as configuration, not data: the data export redacts them by default, so moving a backup
  between environments does not carry live keys (the operator re-enters them in Settings).
- Importing a backup during first-run requires an archive produced by this app's own export; the
  import matches the existing tool's behavior (accounts with hashed passwords included).
- Feature behavior otherwise matches the current app exactly; no existing features are dropped or
  redesigned beyond the credential/setup/deployment changes described here.
- The grounding-parity check may show that direct Gemini citations differ enough that some links can't
  be labeled "Grounded"; that is an accepted, non-blocking degradation — links still flow through the
  existing reachability + title-match verification.
- Live production deployment specifics outside the app (DNS, firewall, server sizing, the operator's
  GitHub access to the repo used by the install script) are the operator's responsibility and not
  part of this build.
