# Running WVEdTalk News Desk on Your Own Server (Self-Hosting Migration)

The WVEdTalk News Desk is a statewide West Virginia education research and podcast-production
app. This plan changes it so it runs entirely on a small private server the operator controls,
with no dependency on Emergent's hosted AI, email, or deployment systems.

## Who it's for

The podcast operator who wants to run the News Desk on their own hardware or VPS — owning their
API keys, their database, and their email delivery — instead of relying on Emergent-managed
infrastructure. Assumes a single low-traffic server and one small editorial team.

## What changes vs. what stays the same

Every application feature stays exactly as it is today: daily briefings, the weekly episode
producer with show-notes links, Podcast Prep (flagging, sorting, clearing), multi-user roles,
public share links, the public story-submission portal, subscriber digests, alerts, scheduling,
Markdown exports. Nothing about the user-facing product is removed or redesigned.

Three things that are currently provided by Emergent get replaced with services the operator
owns:

1. **AI research (LLM).** Today the app uses Emergent's universal key to reach Gemini with live
   Google Search grounding. It will instead use the operator's own Google Gemini API key (from
   Google AI Studio). Google Search grounding — the core of the research quality — is preserved.
2. **Email sending.** Today the app uses Emergent's managed email service. It will instead send
   through the operator's own Resend account — using the operator's Resend API key and a sending
   domain the operator verifies in Resend. All email features (digests, subscriber briefings,
   failure alerts, thank-yous, test/resend) keep working, as do the existing anti-abuse safety
   checks on outgoing mail.
3. **Hosting/deployment.** Today the app is deployed through Emergent's pipeline. It will instead
   run on the operator's server via a single `docker compose up`, including its own database.

Cloudflare Turnstile (the captcha on the public submission form) stays, using the operator's own
Turnstile keys, and remains optional (falls back to spam-honeypot-only when keys are absent).

## What the operator must provide

To say yes to this plan, the operator should be prepared to supply:

- A **Google Gemini API key** (Google AI Studio). Google Search grounding is billed to the
  operator's own Google account per Google's pricing.
- A **Resend account and API key**, plus a **sending domain verified in Resend** (adding the SPF
  and DKIM DNS records Resend provides). Resend's free tier covers modest volume and paid tiers
  are inexpensive as the subscriber list grows. Until a domain is verified, Resend allows test
  sends only, so a verified domain is required for real subscriber delivery.
- A **Linux server** (VPS or physical) able to run Docker and Docker Compose.
- Optionally, a **domain name and HTTPS** if the desk should be reachable on the public internet
  (needed for public share links, the submission portal, and email links to resolve correctly).
- Optionally, **Cloudflare Turnstile keys** to keep the captcha active.

## Operator experience (how running it feels)

- One configuration file holds every secret and setting (Gemini key, Resend API key and verified
  from-address, database name,
  the public URL, Turnstile keys, admin bootstrap). No Emergent-specific values remain.
- `docker compose up -d` starts the whole system — the app and its database — on the server.
- The app is reached in a browser at the server's address (or the operator's domain behind a
  reverse proxy). First login uses the seeded `admin` / `admin` account, which the operator
  changes immediately.
- A setup guide walks through obtaining each key, filling the config, starting the stack, and
  pointing a domain at it.
- If a required setting is missing or malformed, the app reports it clearly at startup instead of
  failing silently mid-run.

## Implementation phases

### Phase 1 — Self-hostable MVP (built now)

- Swap the AI research path to the operator's own Google Gemini API key while preserving Google
  Search grounding and structured/JSON output.
- Swap email sending to the operator's own Resend account (their API key + verified sending
  domain); all existing email flows and the existing outgoing-mail safety checks continue to work.
- Make Turnstile use the operator's own keys, with the existing honeypot-only fallback when keys
  are absent.
- Package the app and a self-hosted database to launch together with a single command, using one
  configuration file for all secrets, with a persistent data volume so data survives restarts.
- Provide a written setup guide covering keys, configuration, startup, and how to put the app
  behind a domain with HTTPS.
- Remove runtime assumptions tied to Emergent so the app has no dependency on Emergent's systems
  once configured.

Result: the operator can stand up a fully working News Desk on their own server, with their own
AI key, their own SMTP, and their own database.

### Phase 2 — Operational hardening (later)

- Scheduled database backups and a documented restore procedure.
- Optional bundled reverse proxy with automatic HTTPS certificates, so a domain works without a
  separate manual proxy setup.
- Health checks and automatic restart of components, log rotation, and sizing guidance for a small
  server.

### Phase 3 — Portability and provider flexibility (later)

- Pluggable email so the operator can choose Resend, another hosted provider, or a plain SMTP
  server without code changes.
- Optional managed database (e.g. a hosted MongoDB connection string) as an alternative to the
  self-hosted one.
- An assisted migration path to move existing briefings/episodes/subscribers from the current
  hosted instance into the self-hosted one.
- A simple update procedure to pull new versions and restart.

## Assumptions

These choices were made without confirmation and are open to change:

- **LLM provider:** the operator's own Google Gemini API key (Google AI Studio), keeping Google
  Search grounding. Not Vertex AI, and not a non-Google model (either of which would change the
  research path — a non-Google model would lose built-in Search grounding).
- **Grounding cost:** Google Search grounding is billed to the operator's Google account; usage
  volume and cost are the operator's to manage.
- **Email:** the operator's own Resend account (their `RESEND_API_KEY`) sending from a
  Resend-verified domain, via Resend's own API (not the Emergent proxy, and not generic SMTP). The
  operator adds Resend's SPF/DKIM DNS records to their domain; a verified domain is required before
  real subscriber sends work. The app's existing outgoing-mail safety checks are retained.
- **Packaging:** Docker Compose, launching the app plus a self-hosted database in one command,
  with a persistent volume for data.
- **Database:** self-hosted, running in a container on the same server; no managed/cloud database
  in the MVP.
- **HTTPS/domain:** the setup guide explains how to run the app behind a reverse proxy with a
  domain and certificates, but the MVP does not force a specific proxy or auto-provision
  certificates (that is Phase 2). Public share links, the submission portal, and email links
  assume the operator sets a correct public URL.
- **Turnstile:** kept, using the operator's own keys, and optional (honeypot-only when unset).
- **Scheduling:** the existing in-process scheduler is kept (daily/weekly runs), so no separate
  system cron is required.
- **Scale:** a single low-traffic server for one editorial team; no multi-server or
  high-availability setup.
- **Starting data:** the self-hosted instance starts fresh with the seeded `admin` / `admin`
  account (to be changed on first login). Migrating existing content from the hosted instance is
  Phase 3, not the MVP.
- **Model:** the same Gemini Pro model used today, selectable via configuration, with a documented
  fallback model ID if the preview model is unavailable to the operator's project.
