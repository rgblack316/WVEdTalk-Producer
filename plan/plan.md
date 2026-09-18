# WV Education News Desk — Plan

## What gets built

A web app that runs the WV Education News Desk brief once a day, stores each briefing, and
lets the host read today's edition, browse the archive, and pull stories into a podcast prep
workspace.

The research and writing is done by GPT-5.4 (OpenAI, via the Emergent universal key) with
OpenAI's live web search turned on, so the model searches the open web at run time and returns
real, clickable source links rather than remembered ones. The full editorial instruction set
from the request — statewide coverage rule, geographic balance, coverage mix, Big Three
balance, source hierarchy, verification rules, duplicate handling, classification labels, the
no-news rule and the nine final editorial tests — is handed to the model verbatim as its
standing brief, with the current calendar date injected on every run.

## What the host sees

**Today's Briefing.** The day's edition in the exact required order: Big Three, Other
Significant Stories, Developing Stories, State Policy & Politics, K–12 Education, Higher
Education, Trends Worth Watching, Podcast Opportunities, Source Log. Big Three items carry
Location, Classification, Importance /10, Podcast Potential /10, What Happened, Why It
Matters, Podcast Angle, Questions to Investigate, and source links. If a run genuinely found
little, the briefing shows a short edition and says so rather than padding.

**Archive.** Every past edition listed by date with its headline count and Big Three headlines,
opening into the same full view.

**Story detail.** Any story opens on its own page with the full editorial workup, its sources,
and the controls below.

**Podcast prep workspace.** Each story can be flagged as an episode candidate and given free-text
notes. A dedicated board collects every flagged story across all dates, grouped so the host can
see the running shortlist in one place, with notes editable inline.

**Run now.** A manual trigger alongside the schedule. The schedule alone means nothing to look
at until tomorrow, and a re-run is needed when a story breaks mid-day. Runs show progress and
land in the archive the same way.

**Handoff to the second agent.** Since these results feed a downstream agent that writes weekly
podcast content, each briefing is also retrievable as structured JSON (stories with their
scores, classifications, locations, sources, plus the host's candidate flags and notes) from a
stable per-date address. That is the contract the second agent reads.

## Decisions made — push back if any are wrong

1. **Schedule: 6:00 AM Eastern daily.** Covers the previous 24 hours and is ready before a
   morning prep session. The app runs on a UTC clock and converts.
2. **Model: GPT-5.4 with live web search at high context.** Chosen per the stated preference for
   GPT-5.x; it is the current recommended model in that family and the one whose web search is
   supported through the universal key. Cost is per run, and one scheduled run a day plus
   occasional manual runs is the expected load.
3. **A run takes minutes, not seconds.** Broad statewide research with verification is slow.
   Runs happen in the background and the page shows a live status; nothing blocks on it.
4. **One briefing per date.** A second run on the same date replaces that date's edition, rather
   than creating a second entry. Candidate flags and notes on stories that survive are kept.
5. **Developing-story tracking is fed by the archive.** Each run is shown the previous several
   days' briefings so it can say what is new versus what was already known, instead of
   re-reporting a continuing story as fresh.
6. **No accounts or login.** Single-host tool; anyone with the link sees the desk.
7. **The model's editorial output is not second-guessed by the app.** Scores, rankings and the
   no-news call are the model's. The app stores and presents them; it does not re-rank.
8. **Look: newsroom editorial.** Serif headlines, dense wire-service column layout, restrained
   WV mountain palette, with the clean-dashboard discipline applied to the controls and the
   candidate board so the reading surface stays uncluttered.

## Known limits

- Source links come from live web search. The model is instructed to prefer primary sources and
  to verify, but a link can still go stale or a paywall can block the host. Links are shown with
  their outlet name so the host can judge before clicking.
- Coverage of very small county boards depends on what those bodies publish on the open web. On
  days when a district posts nothing, the briefing will say a region had no significant story
  rather than inventing one.
- Copy/markdown export of a briefing is not included in this build. It can be added later.
