"""The WVEdTalk weekly podcast producer: prompt, LLM call, persistence, Friday scheduler."""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from lib import desk
from lib.db import db
from models.briefing import SourceLink
from models.episode import (
    EpisodeStory,
    LookAheadItem,
    NotSelectedStory,
    ProduceStatus,
    WeeklyEpisode,
)

logger = logging.getLogger(__name__)

MODEL_PROVIDER = "gemini"
MODEL_NAME = "gemini-3.1-pro-preview"
SCHEDULE_DOW_ET = 4  # Friday (Mon=0)
SCHEDULE_HOUR_ET = 14  # 2:00 PM ET

# Reproduced VERBATIM per the producer brief — must open the recording script unchanged.
REQUIRED_INTRO = (
    "I'm your host Randy Black. I'm an educator, technology specialist, and podcaster and "
    "I\u2019ve spent much of my career paying attention to the people, policies, and ideas that "
    "shape education. Thank you for joining me this week for WVEdTalk."
)

_status = ProduceStatus()
_lock = asyncio.Lock()


def get_status() -> ProduceStatus:
    return _status


def current_week_of() -> str:
    """The Friday of the current ET week (or today if it is Friday)."""
    now = datetime.now(desk.EASTERN)
    delta = (now.weekday() - SCHEDULE_DOW_ET) % 7
    friday = now - timedelta(days=delta)
    return friday.strftime("%Y-%m-%d")


PRODUCER_BRIEF = """WVEdTalk WEEKLY PODCAST PRODUCER
Act as the weekly podcast producer for WVEdTalk, a West Virginia education-focused podcast.
Your job is to review the preceding week's West Virginia education news, independently reassess the week's developments, identify the stories that genuinely deserve attention, and produce a polished podcast episode script suitable for recording.
Do not simply combine or summarize the daily WV Education News Desk briefings. Conduct an independent editorial review of the entire week's news using live web search.
The podcast must cover EDUCATION ACROSS ALL OF WEST VIRGINIA, not primarily WVU, Marshall, or other high-profile institutions. Treat major universities, statewide agencies, and prominent institutions as important sources within the broader education beat, not as the default focus. The goal is a useful, accurate, engaging and trustworthy weekly West Virginia education-news podcast.

WEEKLY RESEARCH WINDOW: review the entire preceding week and continue through the most recent available information. Do not simply use stories that appeared in the daily briefings. Conduct fresh research to identify new developments, stories that changed during the week, stories that grew or shrank in importance, related developments across counties/regions, and emerging statewide trends. Reassess importance based on the complete week: a Monday minor story may be Friday's biggest; a story prominent early may fade.

NO FIXED STORY COUNT: do not target a predetermined number. Include as many or as few stories as are genuinely justified. Never pad to a target; never omit an important story because enough are selected. If the week is quiet, produce a shorter episode. If one story dominates, let it get proportionally more attention. The objective is usefulness, not quantity.

STATEWIDE COVERAGE across all 55 counties and every education topic (K-12, special education, curriculum, testing, accountability, attendance, discipline, school safety, construction, closures, consolidation, transportation, funding, technology, AI, teacher recruitment/retention, workforce, CTE, charter schools, school choice, homeschooling when relevant, court cases, state policy and legislation, higher ed, community and technical colleges, education politics). Consider Northern, North-central, Eastern Panhandle, Central, mountain, Southern, Southwestern and Western WV. Do not manufacture geographic diversity, but actively search local/regional developments before concluding none exist.

K-12 PRIORITY: K-12 should generally be the broadest portion. Higher ed matters but must not routinely dominate; WVU/Marshall get attention on substantial significance, not because they publish more. Default question: what mattered most to West Virginia's students, families, educators, schools and communities this week?

EDITORIAL SELECTION weighs importance, statewide and local significance, people affected, policy significance, timeliness, audience interest, discussion potential, podcast potential, whether it will keep developing, whether it reveals a trend, and whether it gives useful context. Do not auto-pick the most-covered, the government-sourced, or the WVU/Marshall stories. A lightly covered local story may deserve more time than a widely covered institutional announcement.

DISCOVERY: fresh, broad web research across state agencies (WVDE, WV Board of Education, Legislature, Governor, HEPC, CTCS), county boards, districts, individual schools, universities and colleges, courts, government records, statewide and local/regional news, TV, radio, education publications and reputable national organizations. Search by topic AND geography. Do not rely solely on the daily briefing or primarily on WVU, Marshall, WVDE, MetroNews, one newspaper, or press releases.

SOURCE HIERARCHY: Tier 1 primary/official (prefer original document, report, legislation, filing, minutes, data set); Tier 2 established WV news orgs (WV Public Broadcasting, Charleston Gazette-Mail, MetroNews, WV News, Register-Herald, The Intelligencer, Wheeling News-Register, Parkersburg News and Sentinel, Times Record & News Journal, and Huntington/Morgantown/Clarksburg/Fairmont/Beckley outlets); Tier 3 local/regional papers, TV, radio, district and school publications; Tier 4 education trade/national orgs (Education Week, K-12 Dive, EdSurge, Hechinger, Inside Higher Ed, Higher Ed Dive, NEA, AFT, AASA, NSBA) treated as interested parties; Tier 5 social/newsletters/forums/aggregators for leads only, verified before use.

VERIFICATION: identify the strongest source, review reputable reporting, compare conflicting accounts, and classify each claim as confirmed, proposed, alleged, under investigation, under litigation, adopted, enacted, opinion or advocacy, stating uncertainty. Never invent facts, quotes, statistics, sources, people, organizations, events, legal or policy outcomes. Do not infer motives without evidence, present allegations as fact, proposed legislation as law, a board discussion as a decision, or advocacy as objective fact. When sources disagree, explain the disagreement.

DUPLICATES: multiple articles on one event are one story; consolidate; use the strongest primary source and strongest independent reporting; explain materially different accounts. DEVELOPING stories: state when it emerged, what changed this week, what was known, what is new, what is unresolved, what to watch. Do not treat the same event as brand-new repeatedly.

EDITORIAL THEMES: find legitimate, evidence-supported connections among the week's stories (student safety, teacher workforce, funding, enrollment, closures, rural education, school choice, technology, AI, workforce development, mental health, special education, economic development, access, higher ed, state policy). Do not manufacture connections.

RECORDING SCRIPT: write a polished, conversational script for a 15-20 minute episode, roughly 2,200-3,000 spoken words, but do not force a word count; substance and natural pacing matter more. It should sound like an experienced host speaking, not reading an article. Use natural transitions, conversational language, clear explanations, context, logical progression, moderate sentence lengths and spoken rhythm. Avoid sensationalism, repetition, loaded language, jargon, artificial transitions and repetitive briefing summaries. Write for audio: shorter paragraphs, explanations that make sense heard once. Do not include long URLs in the script; use brief spoken references like "According to the West Virginia Department of Education" or "West Virginia Public Broadcasting reported". Full links belong in the producer notes. CHAPTER HEADERS: divide the script into clearly titled chapters that can be used as podcast chapter markers. Begin the opening with a line "## Introduction"; begin each distinct story or segment with its own header line formatted EXACTLY as "## Chapter Title" (a short, descriptive 3-7 word title suitable as a podcast chapter title); and begin the sign-off with "## Closing". Put every header on its own line with a blank line before and after it, and never use "##" anywhere except for these chapter headers.

The recording script MUST begin with the opening show identification, then IMMEDIATELY reproduce this host introduction VERBATIM (do not paraphrase, shorten, reorder, rewrite, substitute or omit any part):
"__REQUIRED_INTRO__"
Then transition naturally into the week's news. Structure: (1) Opening = show identification, then the exact required introduction, then a brief note of what the episode covers; (2) Major story coverage — for each story: what happened, what changed this week, background, why it matters, who is affected, competing perspectives when appropriate, unanswered questions, what to watch next, with more important stories getting more time; (3) legitimate thematic connections, not manufactured; (4) a brief look ahead at genuinely relevant upcoming legislative/board/court/policy events; (5) a concise conversational closing that identifies the program as WVEdTalk. No filler.

LEGAL/ETHICAL: identify allegations as allegations, do not imply guilt before adjudication, distinguish allegations from findings, note unresolved cases, avoid sensational descriptions; state proposed legislation as proposed and where it is in the process; distinguish board discussion from action and note when no final decision was made.

OUTPUT: respond with a SINGLE valid JSON object and nothing else (no markdown fence, no prose outside it). Use these keys:
{
  "editorial_summary": "concise editorial summary of the week (the WEEKLY RESEARCH PRODUCER NOTES lead-in)",
  "selected_stories": [
    {
      "story": "headline",
      "location": "county/region/statewide",
      "classification": ["NEWS"],
      "importance": 8,
      "podcast_potential": 7,
      "estimated_minutes": 3.5,
      "why_it_made_the_cut": "",
      "what_happened_during_week": "",
      "what_remains_unresolved": "",
      "why_it_matters": "",
      "sources": [{"title": "", "url": "https://...", "outlet": ""}]
    }
  ],
  "not_selected": [
    {"story": "", "location": "", "why_considered": "", "why_not_selected": ""}
  ],
  "look_ahead": [{"label": "upcoming event genuinely relevant to WV education", "date": "YYYY-MM-DD or descriptive"}],
  "recording_script": "the full spoken script as one string, beginning with the show identification and the verbatim Randy Black introduction, with a \\"## Chapter Title\\" header line before each story segment (and \\"## Introduction\\"/\\"## Closing\\" for the open and close), using \\n\\n between paragraphs",
  "chapters": ["the ordered chapter titles, matching the ## headers in recording_script exactly but WITHOUT the ## prefix"],
  "source_log": [{"title": "", "url": "https://...", "outlet": ""}]
}
The "not_selected" array (STORIES CONSIDERED BUT NOT SELECTED) is REQUIRED and must include notable alternatives seriously considered but excluded, and stories that were prominent early but faded, forming an editorial audit trail. Every URL must be a real page you actually consulted this run. Apply the quality-control tests before answering, especially: would these still be the top stories if WVU and Marshall had published nothing this week; did K-12 and local education get appropriate weight; did you independently reassess the full week rather than lifting from daily briefings; and does the script open with Randy Black's exact required introduction.""".replace(
    "__REQUIRED_INTRO__", REQUIRED_INTRO
)


LENGTH_GUIDANCE = {
    "concise": "LENGTH PREFERENCE: keep it tight this week — aim for roughly 1,400-1,900 spoken words (about 10-13 minutes), covering only the strongest stories.",
    "standard": "LENGTH PREFERENCE: aim for roughly 2,200-3,000 spoken words (about 15-20 minutes).",
    "full": "LENGTH PREFERENCE: the host wants a fuller episode this week — aim for roughly 3,000-3,800 spoken words (about 20-26 minutes), giving the major stories room to breathe with more context and discussion.",
}


def _user_prompt(
    week_start: str,
    week_end: str,
    briefings: List[Dict[str, Any]],
    script_length: str,
    candidates: List[Dict[str, Any]],
) -> str:
    lines = [
        f"Produce the WVEdTalk weekly episode covering West Virginia education news for the week of {week_start} through {week_end} (America/New_York).",
        "Independently research the full week with live web search — do not merely restate the daily briefings below.",
        LENGTH_GUIDANCE.get(script_length, LENGTH_GUIDANCE["standard"]),
        "The length preference is a target, not a mandate: never pad a quiet week to reach it, and never omit a genuinely important story to stay under it.",
    ]
    if candidates:
        lines.append(
            "\nHOST-FLAGGED PODCAST PREP CANDIDATES — the host has personally tagged the following stories for this podcast. "
            "Treat these as strong editorial priorities: give them meaningful weight and strongly favor covering them in the episode, "
            "verifying and updating each with fresh independent research (they may have developed since being flagged). "
            "Weigh them alongside your own independent findings for the week. "
            "If you judge that a flagged candidate genuinely does not merit inclusion this week (e.g. it faded, was resolved, or a stronger story crowds it out), "
            "you MAY set it aside — but you MUST then list it in \"not_selected\" with a clear, specific reason so the host sees why their pick was dropped. "
            "Honor the host's notes where provided:"
        )
        for c in candidates:
            note = f" — host note: {c['notes']}" if c.get("notes") else ""
            loc = f" [{c['location']}]" if c.get("location") else ""
            lines.append(f"- ({c.get('date','')}) {c.get('headline','')}{loc}{note}")
    if briefings:
        lines.append(
            "\nFor reference only, the WV Education News Desk daily briefings from this week reported these stories. Use them to orient your research and to track what developed, but reassess everything independently:"
        )
        for b in briefings:
            heads = "; ".join(s.get("headline", "") for s in b.get("stories", [])[:16])
            lines.append(f"- {b.get('date')}: {heads}")
    else:
        lines.append("\nThere are no daily briefings on file for this week; research the week entirely from the open web.")
    lines.append("\nReturn only the single JSON object described in your instructions.")
    return "\n".join(lines)


async def _gather_candidates() -> List[Dict[str, Any]]:
    """Flagged Podcast Prep stories the host wants considered for the weekly episode."""
    docs = await db.briefings.find({"stories.is_candidate": True}).sort("date", -1).to_list(200)
    out: List[Dict[str, Any]] = []
    for d in docs:
        for s in d.get("stories", []):
            if s.get("is_candidate"):
                out.append(
                    {
                        "date": d.get("date", ""),
                        "headline": s.get("headline", ""),
                        "location": s.get("location", ""),
                        "notes": s.get("notes", ""),
                    }
                )
    return out


async def _call_model(
    week_start: str,
    week_end: str,
    briefings: List[Dict[str, Any]],
    script_length: str,
    candidates: List[Dict[str, Any]],
) -> Dict[str, Any]:
    import os

    from emergentintegrations.llm.chat import LlmChat, UserMessage

    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")

    chat = (
        LlmChat(api_key=key, session_id=f"wvedtalk-{week_end}", system_message=PRODUCER_BRIEF)
        .with_model(MODEL_PROVIDER, MODEL_NAME)
        .with_tools([{"googleSearch": {}}])
    )
    resp = await chat.send_message_with_tools(
        UserMessage(text=_user_prompt(week_start, week_end, briefings, script_length, candidates))
    )
    content = resp.content if isinstance(resp.content, str) else str(resp.content or "")
    data = desk._parse_json(content)

    citations: List[Dict[str, str]] = []
    try:
        annotations = getattr(resp.raw.choices[0].message, "annotations", None) or []
        for a in annotations:
            uc = a.get("url_citation") if isinstance(a, dict) else None
            if uc and uc.get("url"):
                citations.append({"url": uc["url"], "title": uc.get("title", "")})
    except Exception:
        pass
    data["_citations"] = citations
    return data


def _ensure_intro(script: str) -> str:
    """Guarantee the verbatim Randy Black introduction opens the script."""
    if REQUIRED_INTRO in (script or ""):
        return script
    opener = f"## Introduction\n\nWelcome to WVEdTalk, West Virginia's weekly education-news podcast.\n\n{REQUIRED_INTRO}\n\n"
    return opener + (script or "")


def _extract_chapters(script: str) -> List[str]:
    """Fallback: pull chapter titles from the '## ' header lines in the script."""
    return [m.group(1).strip() for m in re.finditer(r"(?m)^\s*##\s+(.+?)\s*$", script or "") if m.group(1).strip()]


async def produce_episode(week_of: Optional[str] = None) -> WeeklyEpisode:
    week_of = week_of or current_week_of()
    week_end_dt = datetime.strptime(week_of, "%Y-%m-%d")
    week_start = (week_end_dt - timedelta(days=6)).strftime("%Y-%m-%d")
    week_end = week_of

    async with _lock:
        _status.running = True
        _status.week_of = week_of
        _status.started_at = datetime.utcnow()
        _status.finished_at = None
        _status.message = "Reviewing the week and researching WV education news for WVEdTalk…"
        _status.last_error = ""
        try:
            briefings = (
                await db.briefings.find(
                    {"date": {"$gte": week_start, "$lte": week_end}, "status": "complete"}
                )
                .sort("date", 1)
                .to_list(14)
            )
            cfg = await db.desk_config.find_one({"key": "singleton"}, {"_id": 0}) or {}
            script_length = cfg.get("script_length", "standard")
            candidates = await _gather_candidates()
            if candidates:
                _status.message = f"Reviewing the week with {len(candidates)} host-flagged candidate(s) prioritized…"
            data = await _call_model(week_start, week_end, briefings, script_length, candidates)

            selected: List[EpisodeStory] = []
            for raw in data.get("selected_stories") or []:
                if not isinstance(raw, dict):
                    continue
                cls = raw.get("classification")
                if isinstance(cls, str):
                    raw["classification"] = [cls]
                try:
                    selected.append(EpisodeStory(**raw))
                except Exception as exc:
                    logger.warning("skipping malformed selected story: %s", exc)

            not_selected = [
                NotSelectedStory(**r) for r in (data.get("not_selected") or []) if isinstance(r, dict)
            ]
            look_ahead = [
                LookAheadItem(**r) if isinstance(r, dict) else LookAheadItem(label=str(r))
                for r in (data.get("look_ahead") or [])
            ]

            source_log = list(data.get("source_log") or [])
            have = {(s or {}).get("url") for s in source_log if isinstance(s, dict)}
            for c in data.get("_citations") or []:
                if c["url"] not in have:
                    source_log.append(SourceLink(url=c["url"], outlet=c.get("title", "")).model_dump())
                    have.add(c["url"])

            final_script = _ensure_intro(str(data.get("recording_script") or ""))
            chapters = [c.strip() for c in (data.get("chapters") or []) if isinstance(c, str) and c.strip()]
            if not chapters:
                chapters = _extract_chapters(final_script)

            episode = WeeklyEpisode(
                week_of=week_of,
                week_start=week_start,
                week_end=week_end,
                model=f"{MODEL_PROVIDER}/{MODEL_NAME}",
                editorial_summary=str(data.get("editorial_summary") or ""),
                selected_stories=selected,
                not_selected=not_selected,
                look_ahead=look_ahead,
                recording_script=final_script,
                chapters=chapters,
                source_log=source_log,
            )

            _status.message = "Resolving source links…"
            links = list(episode.source_log)
            for s in episode.selected_stories:
                links.extend(s.sources)
            await desk.resolve_links(links)

            await db.episodes.replace_one({"week_of": week_of}, episode.model_dump(), upsert=True)
            _status.message = f"WVEdTalk episode for week of {week_of} is ready ({len(selected)} stories)."
            await _email_episode_safe(episode)
            return episode
        except Exception as exc:
            logger.exception("weekly episode production failed")
            _status.last_error = "Production failed — see server logs."
            _status.message = "Production failed — see server logs."
            raise
        finally:
            _status.running = False
            _status.finished_at = datetime.utcnow()


async def _email_episode_safe(episode: WeeklyEpisode) -> None:
    """Email the finished episode to digest recipients — never fail production on this."""
    try:
        from lib import email_digest

        cfg = await db.desk_config.find_one({"key": "singleton"}, {"_id": 0})
        recipients = (cfg or {}).get("recipients") or []
        if recipients:
            _status.message = "Emailing the episode script to recipients…"
            sent = await email_digest.send_episode(episode, recipients)
            logger.info("episode emailed to %d/%d recipients", sent, len(recipients))
    except Exception:
        logger.exception("episode email step failed (non-fatal)")


async def _maybe_produce_weekly() -> None:
    now = datetime.now(desk.EASTERN)
    if now.weekday() != SCHEDULE_DOW_ET or now.hour < SCHEDULE_HOUR_ET or _status.running:
        return
    week_of = current_week_of()
    if await db.episodes.find_one({"week_of": week_of, "status": "complete"}):
        return
    logger.info("weekly scheduler: producing WVEdTalk episode for %s", week_of)
    await produce_episode(week_of)


async def scheduler_loop() -> None:
    """Produce the weekly episode at 2:00 PM ET on Fridays if it doesn't exist yet."""
    while True:
        try:
            await _maybe_produce_weekly()
        except Exception:
            logger.exception("weekly scheduler loop error")
            await asyncio.sleep(1800)
        await asyncio.sleep(300)
