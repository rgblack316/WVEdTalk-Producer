# WV Education News Desk — Self-Hosting Migration (Remove All Emergent Dependencies)

This plan turns the News Desk into a **fully self-hostable** application with **no Emergent
runtime dependency**, deployed via **Docker + docker-compose**, installable and upgradable with
two scripts (`install.sh`, `upgrade.sh`). The LLM provider is **configurable** (Gemini default,
OpenAI optional), and email supports **Resend (default) with an SMTP fallback**. Every third-party
credential (LLM keys, Resend, SMTP, Turnstile) is **managed in-app on the Settings page** so an
operator never has to hand-edit env files after first boot.

> Decision record (confirmed with stakeholder):
> - Deliverable **this pass**: this plan + `install.sh` + `upgrade.sh` + Docker scaffolding.
>   The working LLM/email code is left **as-is** for now (code migration is Phase 2–5 below).
> - LLM: **configurable** (Gemini via `google-genai` with Google Search grounding = default;
>   OpenAI with its web-search tool = optional).
> - Email: **Resend default, SMTP fallback.**
> - Emergent: **hard cut** — remove all Emergent code, packages, and `EMERGENT_*` keys.
> - Install target: **Docker + docker-compose.**
> - All provider credentials must be **manageable from the in-app Settings page** (incl. the SMTP
>   fallback settings).

---

## 1. Current Emergent coupling (inventory)

| Area | Where | Emergent dependency | Replacement |
| --- | --- | --- | --- |
| LLM — daily briefing | `backend/lib/desk.py::_call_model` | `emergentintegrations.llm.chat.LlmChat`, `EMERGENT_LLM_KEY`, `.with_tools([{"googleSearch":{}}])` | `backend/lib/llm.py` provider layer |
| LLM — weekly episode | `backend/lib/producer.py` (`_call_model`) | same | same |
| LLM — chapterize | `backend/lib/producer.py::_chapterize_call` | same (no search tool) | same |
| Email | `backend/lib/email_digest.py` | managed Resend proxy `https://integrations.emergentagent.com`, `EMERGENT_EMAIL_KEY` | `backend/lib/mailer.py` (Resend/SMTP) |
| Package | `backend/requirements.txt` | `emergentintegrations==0.2.0` | removed |
| Docs/env | `README.md`, `backend/.env.example` | `EMERGENT_LLM_KEY`, `EMERGENT_EMAIL_KEY` | new vars (see §5) |

Not coupled to Emergent (keep as-is): Mongo/Motor, auth/sessions, Turnstile (already uses the
operator's own keys), the DB export/import tool, the source-link verification pipeline.

---

## 2. Target architecture (Docker compose)

Three containers, defined in `docker-compose.yml` (added this pass):

- **mongo** — `mongo:7`, data persisted in the `mongo_data` named volume, not published to the host.
- **backend** — `backend/Dockerfile` (python:3.11-slim), runs `uvicorn server:app` on `:8001`.
  Reads config from compose env (`env_file: .env` + a few overrides). `MONGO_URL` is forced to
  `mongodb://mongo:27017` so it always targets the compose Mongo.
- **frontend** — `frontend/Dockerfile` (multi-stage: `node` build → `nginx`). Nginx serves the
  built SPA and **reverse-proxies `/api/` to `backend:8001`**, so the browser only ever calls
  relative `/api/...` (same contract as the Vite dev proxy). Publishes `HTTP_PORT` (default 80).

Supporting files added this pass: `backend/Dockerfile`, `frontend/Dockerfile`,
`frontend/nginx.conf`, `backend/.dockerignore`, `frontend/.dockerignore`, root `env.example`
(compose config), `.dockerignore`.

> Interim note: the backend image currently still installs `emergentintegrations` (via an
> `--extra-index-url` line, commented in the Dockerfile) so the **present** code builds and runs in
> Docker today. Phase 5 deletes that package and the extra index, completing the hard cut.

---

## 3. Configuration & in-app Settings management (key requirement)

Every provider credential has **two sources**, resolved in this precedence order at call time:

1. **Database config** (`desk_config.integrations`, set from the Settings page) — wins when present.
2. **Environment variable** (from `.env`/compose) — bootstrap + fallback, used when the DB value is
   blank. Lets a brand-new instance run before anyone opens Settings, and lets an operator pin
   secrets via env only if they prefer.

### 3.1 New "Integrations" Settings panel (admin-only)
A new panel on the existing Settings page, matching current desk styling, grouped into:

- **AI / Research model**
  - Provider select: `Gemini` | `OpenAI`.
  - API key (Gemini or OpenAI, shown per provider).
  - Model name (defaults filled in: `gemini-2.5-pro`/current, or `gpt-5.x`).
  - "Test connection" button → backend does a tiny live call and reports ok/error.
- **Email — primary (Resend)**
  - Resend API key, From address, From name, Reply-To.
  - "Send test email" (reuses the existing test-digest path).
- **Email — fallback (SMTP)**
  - Host, port, username, password, STARTTLS/SSL toggle, From address.
  - Used automatically when Resend is unset or a Resend send fails.
  - "Send test email via SMTP" button.
- **Turnstile** (move the existing site/secret keys here too, for consistency).

### 3.2 First-run setup wizard (replaces the `admin`/`admin` seed)
Shipping a known default login (`admin`/`admin`) is a weak default for a self-host. Replace the
auto-seed with a **first-run onboarding page** shown whenever the `users` collection is empty:

- The backend exposes `GET /api/setup/status` → `{needs_setup: bool}` and, while `needs_setup` is
  true, **every guarded route except the setup + import endpoints returns 409/redirect to setup** so
  the instance can't be used until an owner is established.
- The page offers two mutually exclusive paths:
  1. **Create the first admin** — name, email, password (min length enforced). `POST /api/setup/admin`
     creates the sole admin and signs them in. One-shot: the endpoint refuses once any user exists.
  2. **Import an existing backup** — upload a JSON archive from the Data export/import tool. Because
     the archive already carries user accounts with **hashed** passwords, a successful import restores
     the original admin(s), and everyone signs in with their prior credentials — ideal for a
     migration off Emergent. Reuses the existing import logic (`routers/data_io.py`), gated so it only
     runs during first-run (empty DB) without admin auth, then locks.
- Remove `ensure_seed_admin()` (and the `admin`/`admin` constants) from startup; `install.sh` output
  points the operator at the setup page instead of a default login.

### 3.3 Secret handling rules
- Secrets are **write-only from the UI**: the API accepts a new value but **never returns the
  stored secret**; GET responses return a masked boolean/`"••••set"` indicator + last-4 only.
- Stored **encrypted at rest** using a key derived from `SESSION_SECRET` (Fernet/AES-GCM), so a DB
  dump alone does not leak live keys. (The DB export tool must redact or encrypt these — see §6.)
- All Integrations writes are **admin-only** and audited in the run log.
- Backend reads them through small accessors (`lib/config_secrets.py`) that apply the precedence in
  §3 and decrypt on use.

---

## 4. Migration phases

### Phase 1 — Scaffolding + tooling (THIS PASS, no app-code changes)
- Rewrite this `plan/plan.md` (done).
- Add `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf`,
  `.dockerignore`s, root `env.example`.
- Add `install.sh` (first-time Docker bring-up, secret generation, health wait) and `upgrade.sh`
  (pre-upgrade Mongo backup, rebuild, recreate, prune).
- The current code still uses `EMERGENT_*`; `env.example` documents both the **current** keys
  (to run today) and the **target** self-hosted keys (used after Phase 2–5).

### Phase 2 — LLM provider abstraction (`backend/lib/llm.py`)
- Introduce a `generate_grounded_json(system, user, *, model) -> {content, citations}` interface.
- **Gemini** implementation via `google-genai`: `tools=[{google_search:{}}]`, parse
  `candidates[].grounding_metadata.grounding_chunks[].web.{uri,title}` into the same `_citations`
  shape the pipeline already consumes (`[{"url","title"}]`).
- **OpenAI** implementation via the Responses API web-search tool; map its URL citations to the
  same shape. (If a provider can't ground, links still flow through the existing
  reachability/title-match verifier, so unverified links are simply badged.)
- Swap the three call sites (`desk._call_model`, `producer._call_model`,
  `producer._chapterize_call`) to the new layer. Keep `_parse_json` and citation handling identical
  downstream.
- `requirements.txt`: add `google-genai` and/or `openai`.

### Phase 3 — Email abstraction (`backend/lib/mailer.py`)
- Replace `email_digest._send_email` internals with a `send(to, subject, html)` that:
  - uses **Resend** (`https://api.resend.com/emails`, `Authorization: Bearer <key>`, `from`,
    `reply_to`) when a Resend key is configured;
  - else/on failure uses **SMTP** (`aiosmtplib`) with the configured host/port/TLS/creds.
- Keep the existing `_assert_safe_email` G2/G3 gate and all HTML templates **unchanged** — only the
  transport changes. `_error_detail` keeps surfacing the provider's reason.
- `requirements.txt`: add `aiosmtplib`; `resend` optional (raw httpx is fine).

### Phase 4 — In-app Integrations Settings panel (§3)
- Backend: extend `models/config.py` + `routers/settings.py` with masked read + admin write
  endpoints and `lib/config_secrets.py` (precedence + encryption). Add "test connection" / "send
  test email (resend|smtp)" endpoints.
- Frontend: new Integrations panel in `pages/Settings.tsx` with masked inputs, provider selects,
  and test buttons; add matching TS interfaces in `lib/types.ts`.
- **First-run onboarding (§3.2):** add `GET /api/setup/status`, `POST /api/setup/admin`, and a
  first-run-only import path; add a `SetupWizard` page/guard on the frontend; remove
  `ensure_seed_admin()` and the `admin`/`admin` constants so no default login ever ships.

### Phase 5 — Hard cut cleanup
- Remove `emergentintegrations` from `requirements.txt` and the `--extra-index-url` line from
  `backend/Dockerfile`.
- Delete all `EMERGENT_LLM_KEY` / `EMERGENT_EMAIL_KEY` reads and the
  `integrations.emergentagent.com` constant.
- Remove `EMERGENT_*` from `.env.example` files; update `README.md` and `memory/spec.md`.
- Repo-wide check: `grep -ri emergent backend/ frontend/ src/` returns nothing but historical notes.

---

## 5. Environment variable mapping (old → new)

| Current (Emergent) | New (self-hosted) | Notes |
| --- | --- | --- |
| `EMERGENT_LLM_KEY` | `LLM_PROVIDER` + `GEMINI_API_KEY` / `OPENAI_API_KEY` + `LLM_MODEL` | provider selectable; model optional (sane default) |
| `EMERGENT_EMAIL_KEY` | `EMAIL_PROVIDER` + `RESEND_API_KEY` **or** `SMTP_HOST`/`SMTP_PORT`/`SMTP_USERNAME`/`SMTP_PASSWORD`/`SMTP_STARTTLS` | Resend default, SMTP fallback |
| (n/a) | `EMAIL_FROM`, `EMAIL_FROM_NAME`, `EMAIL_REPLY_TO` | explicit sender identity (no managed sender) |
| `MONGO_URL`, `DB_NAME` | same | compose forces `MONGO_URL=mongodb://mongo:27017` |
| `SESSION_SECRET`, `APP_URL`, `CORS_ORIGINS` | same | unchanged |
| `APP_PASSCODE` | same (**optional**) | machine credential for the `X-Desk-Passcode` header; leave blank to disable programmatic access entirely (`_service_ok` returns False when unset). Not needed for a self-host with no downstream automation — human email/password logins are unaffected. |
| `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` | same (also editable in Settings) | unchanged |

All of the provider values above become **optional in env** once set in the Settings page (§3),
except `SESSION_SECRET` which must always be present for the server to boot and to derive the
secret-encryption key.

---

## 6. Interactions with the DB export/import tool
- The Integrations secrets live in `desk_config`. The existing export (`routers/data_io.py`) must
  **redact** these fields by default (same spirit as "secrets are config, not data"), with an
  optional "include encrypted integration secrets" checkbox for same-operator migrations.
- Because secret encryption is keyed off `SESSION_SECRET`, encrypted secrets only decrypt on a
  target that shares the same `SESSION_SECRET` — otherwise the operator re-enters keys in Settings.

---

## 7. install.sh / upgrade.sh

Both scripts auto-install Docker on a fresh Ubuntu/Debian host (they add Docker's official apt
repo and install Engine + the Compose plugin, enable the service, and add the invoking user to the
`docker` group) — the operator does **not** pre-install Docker. They run as a normal user and use
`sudo` only where required, with a `docker_cmd` helper that falls back to `sudo docker` until the
new group membership takes effect. Non-apt OSes get a clear "install Docker manually, then re-run".

### `install.sh` (first-time bring-up)
1. Resolves the real (non-root) user even under `sudo`; requires `sudo`; gates to Ubuntu/Debian.
2. Installs host packages (`ca-certificates curl git openssl gnupg`) and **Docker Engine + Compose**
   if missing; enables the daemon; adds the user to the `docker` group.
3. **Clones the repo** into `~/wvedtalk` (override via `REPO_URL`/`INSTALL_DIR`) — *or* runs in place
   if invoked from inside an existing checkout (so "clone first, then run" also works).
4. Creates `.env` from `env.example` and generates `SESSION_SECRET` (`openssl rand -hex 32`).
   **`APP_PASSCODE` is left blank** (optional machine credential — see §5), not auto-generated.
5. `docker compose up -d --build`, then polls `http://localhost:${HTTP_PORT}/api/schedule/next`.
6. Prints the URL and directs the operator to the **first-run setup page** (create admin or import a
   backup — §3.2), then Settings → Integrations for AI + email keys. No default login is printed.

### `upgrade.sh` (pull new code + rebuild)
1. Locates the install (`~/wvedtalk` or `APP_DIR`, or the current checkout); requires Docker + `.env`.
2. **Refuses unsafe git states**: aborts on uncommitted local changes, detached HEAD, a branch that
   is *ahead* of the remote, or a *diverged* branch; exits cleanly if already up to date.
3. **Mandatory pre-upgrade backup**: `mongodump --archive --gzip` from the running mongo container
   into `backups/pre-upgrade-<timestamp>/`, plus a copy of `.env`; aborts if the dump is empty or
   mongo isn't running (never upgrades without a safety net).
4. `git pull --ff-only`, then `docker compose up -d --build`, then `docker image prune -f`.
5. Health poll + summary, and prints the exact `mongorestore` one-liner to roll back. The MongoDB
   named volume is never touched, so data persists across upgrades.

Both scripts are idempotent and safe to re-run.

---

## 8. Testing & rollback
- **Phase 1 (this pass):** `bash -n` on both scripts; validate `docker-compose.yml` parses; confirm
  no app-code changed and the live Emergent app is untouched.
- **Phase 2–5:** after each phase, run tier-1 (curl smoke of `/api/run` + `/api/produce` dry paths,
  `yarn typecheck`, one browser pass) and a real provider test (one briefing run, one test email via
  Resend and via SMTP). Escalate to the testing subagent on failure.
- **Rollback:** every change is additive behind a provider switch until Phase 5; `upgrade.sh` keeps a
  Mongo dump and the previous images so an operator can `git checkout` the prior tag and
  `docker compose up -d --build` to revert.

---

## 9. Risks & mitigations
- **Grounding parity:** direct Gemini grounding metadata differs from the Emergent wrapper's
  OpenAI-style `annotations`. Mitigation: the provider layer normalizes to the existing
  `[{"url","title"}]` shape; the reachability + title-match verifier already guards bad links.
- **Email deliverability:** self-hosted Resend needs a verified domain; SMTP needs correct TLS.
  Mitigation: in-app "send test" buttons surface the exact provider error before a real blast.
- **Secret safety:** keys in the DB. Mitigation: encrypt at rest, mask on read, redact from export.
- **Build reproducibility:** pin image tags (`mongo:7`, `python:3.11-slim`, `node:20-alpine`,
  `nginx:1.27-alpine`) and keep `yarn.lock`/`requirements.txt` pinned.
