# WV Education News Desk — Spec

## What it does
A single-host research tool for a West Virginia education podcast. Each run, an LLM (Gemini
3.1 Pro with live Google Search grounding) researches WV education news statewide and writes a
structured daily briefing following the full WV Education News Desk editorial ruleset (statewide
coverage, K-12 majority, geographic balance, source hierarchy, verification, no-news rule, nine
editorial tests). Briefings are stored per calendar date, browsable in an archive, and each
story can be flagged as a podcast episode candidate with free-text prep notes.

## Model / integration
- Gemini `gemini-3.1-pro-preview` via emergentintegrations LlmChat + `{"googleSearch": {}}` tool.
- EMERGENT_LLM_KEY in backend/.env. OpenAI web search is rejected by the proxy and Anthropic
  web_search confabulates, so Gemini grounding is the only functional live-search path here.
- Grounding returns Google redirect URLs; `_resolve_sources()` follows each to the publisher's
  direct URL (httpx, 8s timeout) and fills the outlet from the final domain.

## Data model (MongoDB, collection `briefings`, one doc per date)
- Briefing: id, date (YYYY-MM-DD ET), generated_at, status, model, editor_note, stories[],
  trends[], podcast_ideas[], source_log[], error.
- Story: id, section (big_three|other|developing|state_policy|k12|higher_ed), rank, headline,
  location, classification[], importance, podcast_potential, what_happened, why_it_matters,
  podcast_angle, questions[], developing fields (original_date, what_is_new, previously_known,
  unresolved, watch_next), sources[{title,url,outlet}], is_candidate, notes.
- Unique index on date; index on stories.is_candidate.

## Key flows
- Scheduler loop fires at/after 10:00 PM ET if today has no complete briefing.
- POST /api/run starts a background run (409 if one is in progress); a re-run on the same date
  REPLACES that edition but preserves is_candidate/notes on stories whose headline survives.
- GET /api/run-status drives the header progress banner (frontend polls every 5s while running).
- GET /api/briefings (summaries), /api/briefings/latest, /api/briefings/{date} (full),
  PATCH /api/briefings/{date}/stories/{story_id} (toggle candidate / save notes),
  GET /api/candidates (all flagged stories across dates),
  POST /api/candidates/clear (editor: body {date?} — un-flag ALL candidates, or just one
  edition's week when a date is given; keeps prep notes; manual only, candidates never auto-clear
  so a week can be reconsidered/re-produced). The DeskLayout "Podcast Prep" nav tab shows a live
  count badge of flagged stories (shares the ["candidates"] query cache so it stays in sync).
- /api/briefings/{date} is the stable machine-readable contract for the downstream weekly agent.

## Frontend routes
- `/` Today (latest briefing), `/archive`, `/candidates` (podcast prep board),
  `/briefings/:date` (full edition), `/briefings/:date/stories/:storyId` (detail + prep panel).

## Branding
- Logo: `frontend/public/wvedtalk-logo.png` (WVEDTALK WV license-plate art, ~700×700, optimized).
  Shown on the header masthead (links home), login, and public Subscribe/Unsubscribe/SharedBriefing.
  Favicons regenerated from the logo.
- **Brand palette** (index.css): primary = navy `oklch(0.35 0.13 264)` / dark `0.7 0.12 262`;
  accent = gold `oklch(0.62 0.14 74)` / dark `0.78 0.14 80`; accent-foreground navy for gold buttons.
  ring/chart-1 = navy, chart-2 = gold.
- **Email branding**: `email_digest.py` embeds the logo (`{APP_URL}/wvedtalk-logo.png`) atop both the
  daily digest and weekly episode emails; email hexes swapped to navy `#16305e` + gold `#a67c00`/`#c8971b`.
- **Markdown exports**: `regions.briefingToMarkdown` and `episode.episodeToMarkdown` prepend a
  `![logo](origin/wvedtalk-logo.png)` header.
- **Open Graph / Twitter**: `index.html` has og:/twitter: title, description, and image (logo) tags for
  link previews (absolute URL uses the current public host).

## Auth (multi-user)
Email + password accounts with three roles: **admin** (all features + user management),
**editor** (all features except user management), and **viewer** (read-only — can view every
briefing/episode/candidate but cannot run research, produce episodes, tag/flag stories, edit notes,
send emails, or change any shared setting). Replaced the earlier single shared passcode.
- Passwords stored salted PBKDF2-HMAC-SHA256 (stdlib) in the `users` collection
  (`{id,email,role,created_at,password_hash}`, unique index on email). `password_hash` is never
  in the public `User` model.
- Session = stateless HMAC-signed httpOnly cookie (`lib/auth.py`, cookie `wv_desk_session`, 30-day
  expiry, `secure`+`samesite=lax`) bound to the user's id + current password-hash prefix, so a
  password change/reset revokes that user's sessions. `SESSION_SECRET` in backend/.env.
- Bootstrap admin seeded on first startup if `users` is empty (`ensure_seed_admin`):
  username `admin` / password `admin` (fresh DBs only; change immediately — see memory/test_credentials.md).
- Auth routes open (`routers/auth.py`): POST /api/auth/login {email,password}, POST /api/auth/logout,
  GET /api/auth/me → {authenticated, user}. Login throttled 10/5min per IP → 429.
- User management (`routers/users.py`, admin-guarded via `require_admin`): GET /api/users,
  POST /api/users {email,role} → returns one-time temp_password, POST /api/users/{id}/role,
  POST /api/users/{id}/reset-password → new temp_password, DELETE /api/users/{id}. Guards prevent
  deleting yourself and removing/demoting the last admin.
- **Role enforcement**: write endpoints (POST /run, PATCH story, POST /produce, POST /episodes/send,
  all POST/DELETE settings except /settings/password) are guarded by `auth.require_editor` → 403 for
  viewers. GET endpoints allow any authenticated user. Frontend hides write controls for viewers via
  `lib/useAuth.ts` (canEdit): Run-now, produce/email-episode buttons, story flag/notes panel (shown
  read-only instead), and the recipients/watchlist/script-length/auto-lock Settings panels.
- Own password: POST /api/settings/password {current_password,new_password} (min 8).
- Programmatic/downstream service access unchanged in spirit: header `X-Desk-Passcode: <APP_PASSCODE>`
  (backend/.env) resolves as a synthetic admin identity for the weekly agent reading
  /api/briefings/{date} and /api/episodes/{week}.
- Frontend: `components/AuthGate.tsx` (email+password sign-in), `pages/Users.tsx` (admin-only Users
  nav, shown only when role==admin), Settings → "My account" (change own password + auto-lock).
  `lib/session.ts` beginSession/endSession; header Sign-out button.

## Security audit remediations
- Removed the unauthenticated demo `/api/status` GET/POST routes (were public writes). Only
  `GET /api/` (health) and `/api/auth/*` are open; all else requires the passcode.
- `SESSION_SECRET` is now required at startup (no insecure default) — server refuses to boot without it.
- Session cookie token is bound to the current passcode hash (`_session_key`), so rotating the
  passcode invalidates all existing sessions. Old-format cookies are rejected.
- CORS never combines wildcard origin with credentials; credentials only enabled for explicit origins.
- Login (`/api/auth/login`) throttled: 10 attempts / 5 min per IP → 429.
- Redirect resolver (`lib/desk.py`) blocks private/loopback/link-local/metadata hosts (SSRF) and
  caps redirects at 5.
- Run/produce failure messages are generic ("see server logs"); full errors only in logs.
- **Change passcode in-app**: passcode is DB-backed (`desk_config.passcode_hash`, HMAC-SHA256 with
  SESSION_SECRET); until one is set there the env `APP_PASSCODE` is used. POST /api/settings/passcode
  {current,new} verifies the current passcode and requires new length >= 6. `passcode_hash` is stored
  in the singleton config doc but is NOT part of the DeskConfig model, so /api/settings never returns
  it. Changing the passcode does not invalidate existing signed cookies.
- **Auto-lock**: `desk_config.auto_lock_minutes` (0=off | 5 | 15 | 30 | 60), POST /api/settings/auto-lock.
  DeskLayout runs an inactivity timer (resets on mouse/key/scroll/touch) that calls endSession() —
  a hard redirect to the lock screen — when it elapses. Set on the Settings "Security" panel.

## Added features (post-MVP)
- **Public share link** (backend `routers/public.py` + `auth.make_share_token`/`verify_share_token`,
  frontend `pages/SharedBriefing.tsx`): any signed-in user (incl. viewers) copies a link via
  GET /api/briefings/{date}/share → `/share/briefing/{date}?t=<hmac>`. The `/share/*` route is
  OUTSIDE AuthGate (App.tsx uses a `ProtectedLayout` outlet); it fetches the open, token-validated
  GET /api/public/briefings/{date}?token=… (403 on bad token). BriefingView takes an `isPublic` prop
  that skips the authed /settings query, hides the share button + machine-readable link, and renders
  story headlines as plain text (no authed detail links). Rotate SESSION_SECRET to revoke all links.
- **View-only banner**: DeskLayout shows a subtle ribbon for viewers explaining editing is off.
- **Public newsletter subscribers** (backend `models/subscriber.py`, collection `subscribers`
  {email, active, subscribed_at}, unique email index; `routers/public.py`): a public `/subscribe`
  page (POST /api/public/subscribe {email}, idempotent, IP-throttled) lets anyone opt in. Kept
  SEPARATE from admin `recipients`. The **daily briefing** now sends to admin recipients AND active
  subscribers — each sent individually (the managed Resend proxy has no BCC field, so per-recipient
  sends are how addresses stay hidden from each other) with a per-subscriber one-click unsubscribe
  link (`auth.make_unsub_token`, verified at POST /api/public/unsubscribe → `/unsubscribe?email=&t=`).
  The **weekly WVEdTalk episode email is unchanged — admin recipients only, never subscribers.**
  **Subscriber vs admin digest body**: admin recipients get the compact digest (`_digest_html`: Big
  Three summary + a login-protected "Read the full briefing" link to `/briefings/{date}`). Public
  subscribers get `_full_digest_html` — the COMPLETE briefing rendered inline (every section: Big
  Three, Developing, State Policy, K-12, Higher Ed, Other, with sources) PLUS a "View this briefing
  on the web" button to the public share page `/share/briefing/{date}?t=<make_share_token(date)>`
  (no login). `_safe_source_links` pre-filters source anchors to https/non-shortener hosts with the
  host as anchor text, so a bad source URL can never trip `_assert_safe_email` and block the send.
  NOTE: the full-briefing body renders lots of model-generated news prose, so `_assert_safe_email`'s
  credential-request gate (`_CRED_ASK`) matches only imperative phishing phrases ("reply with your
  password", "enter your cvv"), NOT bare topical nouns like "social security number" — a benign news
  mention once tripped the gate and silently dropped ALL subscriber sends while the smaller admin
  digest still went out. Data-entry surfaces stay hard-blocked by the form/input tag check.
  Admins/editors see and manage subscribers on the Settings "Public subscribers" panel
  (GET /api/subscribers any signed-in user; DELETE /api/subscribers/{email} editors only).
- **Embeddable signup widget**: Settings subscribers panel offers a copy-paste HTML snippet (+ live
  preview) that posts to `POST /api/public/embed-subscribe` (accepts form-urlencoded or JSON, returns
  `Access-Control-Allow-Origin: *`; the widget uses a `no-cors` form submit — a simple request with no
  preflight — so it works embedded on any external site). Shared logic via `_persist_subscriber`.
- **Region filter + search** (frontend, `lib/regions.ts`): 8 WV region quick-filters (county->region
  map) plus a county/keyword search box on any briefing. Filtering hides trends/ideas/source-log.
- **Markdown export** (frontend): Copy-to-clipboard and Download `.md` of the full edition.
- **Watchlist** (backend `desk_config` singleton, `routers/settings.py`): case-insensitive terms
  matched anywhere in a story's text; matches surface as a highlighted alert atop the briefing.
- **Email digest** (backend `lib/email_digest.py`, managed Resend via EMERGENT_EMAIL_KEY,
  EMAIL_FROM_NAME="WVEdTalk News Desk", EMAIL_REPLY_TO=no-reply@wvedtalk.com → contact_email/Reply-To.
  NOTE: the managed proxy's From *address* is the platform's fixed verified shared domain and CANNOT
  be changed to no-reply@wvedtalk.com — only the sender display name + Reply-To are settable):
  EMAIL_FROM_NAME="WV Education News Desk"): HTML digest built from a server-side template and sent
  to configured recipients automatically after each run (`_send_digest_safe`, non-fatal) and via
  POST /api/settings/send-digest. Guardrail gate `_assert_safe_email` runs on every send.
- **Delivery alerting + test send + resend** (all editor-guarded, in the Settings "Email digest"
  panel): `send_digest` returns a `DigestSendResult` (per-audience counts + a `failures[]` reason
  per address) and records every subscriber outcome to the `digest_deliveries` collection
  (`{date,email,status,error,at}`). When any subscriber send fails, admins with a real inbox are
  emailed a delivery-failure alert (`send_delivery_alert`). `POST /api/settings/test-digest`
  ({email}) sends one [TEST] subscriber-style copy and returns `{ok,error}` with the exact provider
  reason. `POST /api/settings/resend-digest` re-sends the latest briefing only to active subscribers
  NOT in the delivery log for that date (recover from a partial failure; idempotent). NOTE: the email
  proxy returns HTTP 422 `undeliverable_recipient` for invalid/bouncing addresses (and for
  example.com) — that, not the safety gate, is the usual reason a public subscriber does not receive
  the briefing; the admin recipient still succeeds because it is a valid inbox.
- **Settings page** (`/settings`): manage recipients (EmailStr-validated) and watch terms, plus a
  "Send latest briefing now" button.
- Config endpoints: GET /api/settings, POST/DELETE /api/settings/recipients, POST/DELETE
  /api/settings/watch-terms, POST /api/settings/send-digest.

## Seed data
None seeded. First real briefing generated for 2026-09-18. Demo watch terms ("consolidation",
"special education") were added during testing and left as harmless examples; no recipients configured.

## WVEdTalk Weekly Producer (feature)
- **Purpose**: every Friday 4:00 PM ET, independently reviews the week and writes a recording-ready
  WVEdTalk episode. Adapts the user's full producer brief (`lib/producer.py` PRODUCER_BRIEF).
- **Model**: Gemini 3.1 Pro + googleSearch grounding; fresh research, does not merely restate the
  daily briefings (they are passed as reference context only).
- **Hybrid candidate injection**: flagged Podcast Prep stories (`stories.is_candidate==True`, with
  the host's notes) are gathered by `producer._gather_candidates()` and injected into the producer
  prompt as strong editorial priorities the model must strongly favor covering (verified with fresh
  research and weighed alongside its own findings). If it drops a flagged candidate it MUST record it
  in `not_selected` with a reason, giving the host a visible audit trail of their pick being set aside.
- **Data model** (collection `episodes`, one doc per `week_of` = the Friday date, unique index):
  WeeklyEpisode {week_of, week_start, week_end, editorial_summary, selected_stories[EpisodeStory],
  not_selected[NotSelectedStory], look_ahead[LookAheadItem], recording_script (str), source_log[]}.
- **Verbatim intro**: `REQUIRED_INTRO` (Randy Black) is enforced — `_ensure_intro()` prepends the
  show ID + exact intro if the model omitted it. Sources resolved via `desk.resolve_links()`.
- **Chapter headers**: the producer emits a `## Chapter Title` header line before each story segment
  (plus `## Introduction`/`## Closing`) in `recording_script`, and returns the ordered titles in a
  `chapters: List[str]` field (fallback `_extract_chapters()` parses the `## ` lines if the model
  omits the array). Frontend `components/ScriptView.tsx` renders `## ` lines as styled chapter
  headings + a numbered "Chapters" list (Episodes + EpisodePage); markdown export lists a CHAPTERS
  section. These double as podcast chapter titles.
- **Backfill chapters** (older episodes): `POST /api/episodes/{week_of}/chapterize` (editor-guarded,
  `producer.chapterize_episode`) runs a lightweight no-web-search LLM pass that inserts `## ` headers
  into the EXISTING script without rewriting/adding spoken content (does NOT call `_ensure_intro`, so
  no intro duplication), then stores recording_script + chapters. Frontend shows a one-click
  "Add chapter headers" button on the Recording Script section (Episodes + EpisodePage) only when
  `canEdit` and the episode has no chapters yet.
- **Scheduler**: `lib/producer.scheduler_loop` fires Friday >=16:00 ET if no episode for the week.
- **Endpoints**: GET /api/episodes, /api/episodes/latest, /api/episodes/{week_of},
  GET /api/produce-status, POST /api/produce (background trigger, 409 if running).
- **Frontend**: `/episodes` (Weekly Script — latest episode, producer notes, not-selected audit,
  look-ahead, full recording script, copy/download, past-episode list) and `/episodes/:week`
  (past episode detail). Nav item "Weekly Script".

## Weekly script — Value 4 Value support segment
- `lib/producer.py` inserts a support segment as its own `## Support WVEdTalk` chapter **immediately
  before `## Closing`** via `_ensure_support(script, text)` (idempotent by header; `_remove_support`
  strips it). **Configurable outro**: text lives in `desk_config.support_segment` (canonical default
  `models.config.DEFAULT_SUPPORT_SEGMENT`); `support_default_on` controls whether new episodes include
  it. Edited from the Settings "Weekly support read" panel via `POST /api/settings/support`.
- **Per-episode toggle**: each episode has `support_included`; `POST /api/episodes/{week_of}/support
  {enabled}` adds/removes the segment on that one script and re-derives chapters. EpisodePage shows an
  Add/Remove support read button. `chapterize_episode` no longer forces the segment (preserves the
  episode's current state). The model is still told not to write its own donation segment.

## Public story submissions (reader tips)
- **Submit page** `/submit` (public, `SubmitStory.tsx`): posts `{url, name, email, website(honeypot), turnstile_token}` to `POST /api/public/submit-story`. Validates URL/name (422), stores to `submissions`, auto-subscribes the email. A hidden **honeypot** (`website`) silently drops bots; **Cloudflare Turnstile** is verified server-side (`lib/turnstile.py`) when `TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET_KEY` are set in backend/.env — else it degrades to no-captcha. Site key served (public) via `GET /api/public/config`; the browser widget is `components/TurnstileWidget.tsx` (explicit render).
- **Embeddable form** for partner sites: `POST /api/public/embed-subscribe` (existing) + `POST /api/public/embed-submit-story` (form-encoded, no-CORS, honeypot-guarded; Turnstile can't run cross-origin so honeypot only). Copyable snippets on the Settings page.
- **Run injection**: `desk.run_briefing` (daily) and `producer.produce_episode` (weekly) inject up to 50 `status:"new"` submission URLs into the model prompt as "reader-submitted leads — verify independently".
- **Used-in auto-link**: after each run, `desk.link_submissions_used()` normalizes the run's source URLs (host+path, strips www/query/trailing slash) and flips any matching `new` submission to `used` with `used_in`/`used_ref` (links to the briefing/episode in the dashboard).
- **Dashboard** `/submissions` (`Submissions.tsx`; actions gated to `canEdit`): status **filter tabs** (all/new/used/rejected/archived with counts), per-tip checkbox **selection** + a **bulk-reject** bar (`POST /api/submissions/bulk-reject {ids}` — rejects + emails each reader), per-tip private **note** (save), status new/used/archived, single **Reject** (`/reject`), **Send thanks** (`/thank`), Delete. An **auto-thank toggle** (`POST /api/settings/auto-thank`, `desk_config.auto_thank_on_use`) auto-emails a reader when their tip is auto-linked as used. Backend routers: `GET /api/submissions`, `PATCH /api/submissions/{id}` (status+note), the POST actions, `DELETE`.

## Configurable schedule + run history (admin)
- **Schedule** lives in the `desk_config` singleton. Run times are interpreted in an admin-chosen
  home timezone (`timezone`, IANA name, default `America/New_York`, DST-aware via `ZoneInfo` +
  `desk._safe_zone`/`is_valid_tz`). `POST /api/settings/schedule` (admin) now also takes `timezone`
  and 422s on an unknown zone. Both schedulers and `next_runs` resolve "now" in that zone.
- **Failure alerts**: `desk.record_run()` calls `email_digest.send_failure_alert()` whenever a
  **scheduled** (not manual) run finishes with status `failed`; it emails every admin user with a
  real email address (best-effort, never raises into the run).
- **Timezone label**: the header next-run indicator (`DeskLayout`) formats with
  `timeZoneName:"short"` and carries the browser's detected IANA zone in its tooltip.
- **Mechanics**: fields `daily_hour/daily_minute` (default 22:00) and
  `weekly_dow`/`weekly_hour`/`weekly_minute` (default Fri 16:00, dow 0=Mon..6=Sun). Both schedulers
  read config through `desk.load_schedule()` (single source of truth): `desk._maybe_run_daily` fires
  when now (in home tz) >= daily time; `producer._maybe_produce_weekly` fires on the configured
  weekday at/after its time. `producer.resolve_week_of()` anchors the episode `week_of` to the
  configured run day.
- **Next-run indicator**: `GET /api/schedule/next` → `{daily_next, weekly_next}` as UTC ISO
  (tz-aware); the header (`DeskLayout`) renders them in the browser's LOCAL timezone via
  `new Date(iso).toLocaleString()`. Settings "Automatic run schedule" panel (admin only) edits times
  with `<input type=time>` + a weekday `<select>`.
- **Run history**: every daily/weekly run (scheduled OR manual) is appended to the `run_log`
  collection by `desk.record_run()` in the run's `finally` (status complete|failed, trigger, label,
  detail, started/finished as UTC-ISO strings). `GET /api/run-log` returns the last 20 (any signed-in
  user); the Settings "Recent runs" panel lists them with local-timezone timestamps so the team can
  confirm the schedule is firing.
- **Script Length Dial** (`desk_config.script_length`: concise | standard | full, default standard):
  set via POST /api/settings/script-length; injected into the producer prompt as a soft target
  (never pads a quiet week / never cuts an important story). Chosen on the Settings page.
- **Segment Timers**: each EpisodeStory carries `estimated_minutes` (model-provided); the frontend
  shows a per-story `~X min` badge and a total episode runtime computed from the script word count
  (~150 wpm). Older episodes produced before this field show only the total runtime.
- **Email The Script**: `email_digest.send_episode()` builds a weekly-episode email (server-side
  template, passes the `_assert_safe_email` guardrail) and is auto-sent to recipients right after
  each production run (`_email_episode_safe`, non-fatal). Manual send via POST /api/episodes/send
  and the "Email episode" button on the weekly page.
- **Links to New Sources for This Week** (show notes): `WeeklyEpisode.episode_links` is the
  de-duplicated set of every source used to build the episode (source_log + each selected story's
  sources; first URL wins), computed via `producer._collect_links()` after link resolution at
  production time. `ScriptView` renders it as a clickable bullet-hyperlink section titled
  "Links to New Sources for This Week:" immediately after the recording script (Episodes +
  EpisodePage); `episode.episodeToMarkdown` emits the same section (replacing the old SOURCE LOG
  block) after the script. Backfill for older episodes: `POST /api/episodes/{week_of}/relink`
  (editor-guarded, `producer.relink_episode`) re-resolves redirect URLs and rebuilds episode_links;
  an "Update source links" button appears on both episode pages.
