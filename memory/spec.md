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
- Scheduler loop fires at/after 6:00 AM ET if today has no complete briefing.
- POST /api/run starts a background run (409 if one is in progress); a re-run on the same date
  REPLACES that edition but preserves is_candidate/notes on stories whose headline survives.
- GET /api/run-status drives the header progress banner (frontend polls every 5s while running).
- GET /api/briefings (summaries), /api/briefings/latest, /api/briefings/{date} (full),
  PATCH /api/briefings/{date}/stories/{story_id} (toggle candidate / save notes),
  GET /api/candidates (all flagged stories across dates).
- /api/briefings/{date} is the stable machine-readable contract for the downstream weekly agent.

## Frontend routes
- `/` Today (latest briefing), `/archive`, `/candidates` (podcast prep board),
  `/briefings/:date` (full edition), `/briefings/:date/stories/:storyId` (detail + prep panel).

## Auth
None — single-host tool, no login.

## Added features (post-MVP)
- **Region filter + search** (frontend, `lib/regions.ts`): 8 WV region quick-filters (county->region
  map) plus a county/keyword search box on any briefing. Filtering hides trends/ideas/source-log.
- **Markdown export** (frontend): Copy-to-clipboard and Download `.md` of the full edition.
- **Watchlist** (backend `desk_config` singleton, `routers/settings.py`): case-insensitive terms
  matched anywhere in a story's text; matches surface as a highlighted alert atop the briefing.
- **Email digest** (backend `lib/email_digest.py`, managed Resend via EMERGENT_EMAIL_KEY,
  EMAIL_FROM_NAME="WV Education News Desk"): HTML digest built from a server-side template and sent
  to configured recipients automatically after each run (`_send_digest_safe`, non-fatal) and via
  POST /api/settings/send-digest. Guardrail gate `_assert_safe_email` runs on every send.
- **Settings page** (`/settings`): manage recipients (EmailStr-validated) and watch terms, plus a
  "Send latest briefing now" button.
- Config endpoints: GET /api/settings, POST/DELETE /api/settings/recipients, POST/DELETE
  /api/settings/watch-terms, POST /api/settings/send-digest.

## Seed data
None seeded. First real briefing generated for 2026-09-18. Demo watch terms ("consolidation",
"special education") were added during testing and left as harmless examples; no recipients configured.
