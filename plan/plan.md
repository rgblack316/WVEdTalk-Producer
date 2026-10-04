# Database Export & Import — Migrate the News Desk to Self-Hosting

A one-click admin tool to download a complete, portable copy of the News Desk's data and load it
back into a self-hosted (or any other) instance. It exports whatever database the running app is
connected to, so running it on the published Emergent site captures the live production data.

## Who it's for
- The desk owner/admin who wants to move off Emergent hosting to their own server, keep a periodic
  off-platform backup, or clone the app's data into a second environment — without needing shell
  access to the managed database or any MongoDB command-line tools.

## Core features and experience
- **Full export (one file).** A single downloadable archive containing every collection the app
  uses: daily briefings, weekly episodes, reader submissions, newsletter subscribers, user accounts,
  settings/schedule, run history, and email-delivery records. Nothing is left behind.
- **Accounts included.** User accounts are exported with their emails, roles, and hashed passwords,
  so everyone can log in unchanged after the move. (Passwords stay hashed — the plaintext is never
  stored or exported.) Login sessions are not carried over by design; everyone signs in fresh on the
  new server, which is expected and harmless.
- **Portable JSON format.** The archive is human-readable JSON — one section per collection plus a
  small header noting when it was taken and how many records each collection holds. It can be opened,
  inspected, and loaded anywhere, with no dependency on specific MongoDB tooling or versions.
- **Import / restore.** A matching import accepts an archive produced by the export and loads it into
  the target instance's database. Two safety modes:
  - *Merge* (default): add/replace records by their id, leaving anything already present that isn't
    in the archive untouched.
  - *Replace*: clear each collection first, then load the archive, producing an exact copy of the
    source. Guarded behind an explicit confirmation because it deletes existing data.
- **Admin-only.** Both export and import are restricted to admin accounts. The export is a sensitive
  full-data download; the import can overwrite live data.
- **Guidance note for a raw platform dump.** The delivered work includes written guidance on how to
  request a direct, native database dump from Emergent hosting as an alternative/complement to the
  in-app export (useful if a byte-for-byte copy is preferred). See Assumptions for how this is
  provided.

## User flow
1. Admin opens Settings and finds a new "Data export & import" area.
2. **Export:** clicks "Download a full copy." The archive downloads immediately with a dated filename
   (e.g. the app name plus the export date). A short line states what was included and the record
   counts.
3. **Move the data:** the admin stands up the self-hosted app pointed at their own MongoDB, signs in
   there as an admin, and opens the same Settings area.
4. **Import:** chooses the downloaded archive, picks Merge or Replace (Replace asks for confirmation),
   and loads it. A result summary reports how many records were loaded per collection and flags any
   that were skipped or failed, so the admin can confirm the migration succeeded.
5. Everyone logs in on the new server with their existing credentials.

## UI/UX feel
- Lives as a self-contained panel on the existing Settings page, matching the current desk styling:
  a clear heading, a one-paragraph explanation of what the copy contains and that it includes
  accounts, and two grouped actions (download, then an upload-and-load control).
- Calm and reassuring for a data-moving task: plain-language labels, an obvious primary "Download a
  full copy" button, and the destructive Replace option visually set apart with a confirmation step
  and a warning that it erases existing data first.
- Progress and results are shown inline (counts per collection on both export and import), not hidden
  behind a raw file or console output.

## Implementation phases

### Phase 1 — MVP (built now)
- Admin-only full export of every collection into one portable, dated JSON archive, downloadable from
  a new Settings panel, with accounts (hashed passwords) included.
- Admin-only import of that archive with Merge and Replace modes, Replace gated by confirmation, and a
  per-collection result summary on both export and import.
- A written migration note covering: how to run the export on the published site to capture production
  data, how to load it into a self-hosted instance, and how to request a raw native database dump
  directly from Emergent hosting as an alternative.

### Phase 2 — Later
- Scheduled/automatic backups (e.g. a periodic export emailed or retained on a cadence) and a short
  history of recent exports.
- Selective export/import (choose specific collections, or a date range of briefings/episodes) for
  partial transfers.

### Phase 3 — Later
- Direct server-to-server transfer (push a copy straight to another running instance without a manual
  file download/upload), and integrity verification that compares source and destination counts after
  a move.

## Assumptions
- "Export the published version's database" is satisfied by running the in-app export while signed in
  to the live Emergent-hosted site; the app reads/writes the production database, so the export
  reflects production at the moment it is taken. No separate access to Emergent's managed database
  internals is assumed.
- The export is a point-in-time snapshot, not a live continuous replica; data created after the export
  is not included.
- All application collections are included: briefings, episodes, submissions, subscribers, users,
  settings/schedule, run history, and email-delivery records. Internal database bookkeeping and
  anything derived automatically at runtime (e.g. rebuilt indexes) are not part of the archive — the
  app recreates those on first run.
- Secrets that live outside the database (API keys, the session signing secret, email/CAPTCHA keys)
  are configuration, not data, and are NOT part of the export; they are set up separately on the
  self-hosted server. This is intentional for security.
- Because the session signing secret differs between environments, existing login sessions do not
  transfer; users sign in again on the new server. Accounts and passwords themselves do carry over.
- Import matches records by their existing id. Merge replaces matching records and keeps the rest;
  Replace clears each collection before loading. Replace is the only destructive action and always
  requires explicit confirmation.
- The import expects an archive produced by this tool's export (same JSON structure); arbitrary
  external files are not a supported input in the MVP.
- The archive can be large if there is a long history of briefings/episodes; the MVP handles the
  current data volume as a single file and does not add streaming/chunked downloads (deferred to a
  later phase if needed).
- The migration note is delivered as part of the project documentation (the existing README/notes),
  not as a separate product surface.
- The raw-platform-dump guidance describes the request path to Emergent hosting; whether a raw dump is
  actually provided is controlled by the platform, not by this app.
