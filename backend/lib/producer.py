"""The WVEdTalk weekly podcast producer: prompt, LLM call, persistence, Friday scheduler."""

import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from lib import desk
from lib.db import db
from models.briefing import SourceLink
from models.config import DEFAULT_SUPPORT_SEGMENT
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
SCHEDULE_HOUR_ET = 16  # 4:00 PM ET

# Reproduced VERBATIM per the producer brief — must open the recording script unchanged.
REQUIRED_INTRO = (
    "I'm your host Randy Black. I'm an educator, technology specialist, and podcaster and "
    "I\u2019ve spent much of my career paying attention to the people, policies, and ideas that "
    "shape education. Thank you for joining me this week for WVEdTalk."
)

# Verbatim "Value 4 Value" support segment default (admin-overridable via desk_config).
SUPPORT_CHAPTER = "Support WVEdTalk"
REQUIRED_SUPPORT = DEFAULT_SUPPORT_SEGMENT
# The episode's final uplifting chapter. The support message is inserted immediately BEFORE it, so
# listeners hear the support read and then the episode ends on this positive story.
POSITIVE_CHAPTER = "On a Positive Note"

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


async def resolve_week_of() -> str:
    """Anchor date (the admin-configured weekly run day) of the current ET week. Used so a
    manual or scheduled production keys the episode to the right week even if the run day changed."""
    s = await desk.load_schedule()
    now = datetime.now(desk._safe_zone(s["timezone"]))
    delta = (now.weekday() - s["weekly_dow"]) % 7
    anchor = now - timedelta(days=delta)
    return anchor.strftime("%Y-%m-%d")


from lib.producer_plan import DEFAULT_PLAN, OUTPUT_CONTRACT


async def load_plan() -> str:
    """The editable editorial plan (Settings), falling back to the built-in default when unset."""
    cfg = await db.desk_config.find_one({"key": "singleton"}, {"_id": 0, "producer_plan": 1}) or {}
    return (cfg.get("producer_plan") or "").strip() or DEFAULT_PLAN


def build_system(plan: str) -> str:
    return plan.strip() + "\n\n" + OUTPUT_CONTRACT.replace("__REQUIRED_INTRO__", REQUIRED_INTRO)


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
    positive: List[Dict[str, Any]],
    submissions: List[Dict[str, Any]],
    *,
    stage: str = "research",
    packet_text: str = "",
    dossier: str = "",
) -> str:
    today = datetime.now(desk.EASTERN).strftime("%A, %B %d, %Y")
    lines = [
        f"TODAY'S DATE: {today} (America/New_York). The episode covers the week of {week_start} through {week_end}.",
        f"Produce the WVEdTalk weekly episode covering West Virginia education news for the week of {week_start} through {week_end} (America/New_York).",
    ]
    if stage == "research":
        lines += [
            "STAGE: RESEARCH. Independently research the full week with live web search — do not merely restate the daily briefings below.",
            "Return a plain-text research dossier (NOT JSON). For each story worth considering give: headline, location, what happened and when, "
            "and every date, deadline, number and name exactly as the article states them, with the full article URL you actually read. "
            "Quote deadlines verbatim from the article (e.g. 'comments accepted through Nov. 20') and say which article said it. "
            "Be explicit when you could not find a date. Also list stories considered but not worth covering.",
        ]
    else:
        lines += [
            "STAGE: WRITE. You can no longer search. Write the episode using ONLY the numbered SOURCES and the research dossier below; "
            "when they disagree, the SOURCE text wins over the dossier.",
        ]
    lines += [
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
    if positive:
        lines.append(
            "\nHOST-FLAGGED POSITIVE / GOOD-NEWS STORIES — the host wants the episode to END ON A POSITIVE NOTE. "
            "Verify and update each of the following uplifting stories with fresh independent research, then feature "
            "the strongest as the episode's closing '## On a Positive Note' chapter (placed right before the sign-off, "
            "after the '## Support WVEdTalk' message the desk inserts). Strongly favor these for that positive close; "
            "honor the host's notes where provided:"
        )
        for c in positive:
            note = f" — host note: {c['notes']}" if c.get("notes") else ""
            loc = f" [{c['location']}]" if c.get("location") else ""
            lines.append(f"- ({c.get('date','')}) {c.get('headline','')}{loc}{note}")
    if submissions:
        lines.append(
            "\nREADER-SUBMITTED LEADS — members of the public submitted these links for consideration. "
            "Evaluate each independently with live web search and your normal significance and verification standards; "
            "cover one only if it genuinely merits inclusion. Do not include a story merely because it was submitted:"
        )
        for s in submissions:
            who = f" (submitted by {s.get('name')})" if s.get("name") else ""
            lines.append(f"- {s.get('url')}{who}")
    if briefings:
        lines.append(
            "\nFor reference only, the WV Education News Desk daily briefings from this week reported these stories. Use them to orient your research and to track what developed, but reassess everything independently:"
        )
        for b in briefings:
            heads = "; ".join(s.get("headline", "") for s in b.get("stories", [])[:16])
            lines.append(f"- {b.get('date')}: {heads}")
    else:
        lines.append("\nThere are no daily briefings on file for this week; research the week entirely from the open web.")
    if stage == "write":
        lines.append("\n=== RESEARCH DOSSIER (from the research stage; verify against the sources) ===\n" + dossier)
        lines.append("\n=== SOURCES (real article text; cite by ID only) ===\n" + packet_text)
        lines.append("\nReturn only the single JSON object described in your instructions.")
    else:
        lines.append("\nReturn the research dossier now (plain text).")
    return "\n".join(lines)


async def _gather_candidates() -> List[Dict[str, Any]]:
    """Flagged Podcast Prep stories the host wants considered for the weekly episode."""
    docs = await db.briefings.find({"stories.is_candidate": True}).sort("date", -1).to_list(200)
    out: List[Dict[str, Any]] = []
    for d in docs:
        for s in d.get("stories", []):
            if s.get("is_candidate") and not s.get("is_excluded"):
                out.append(
                    {
                        "date": d.get("date", ""),
                        "headline": s.get("headline", ""),
                        "location": s.get("location", ""),
                        "notes": s.get("notes", ""),
                    }
                )
    return out


async def _gather_positive() -> List[Dict[str, Any]]:
    """Stories the host flagged as good-news/positive to end the episode on."""
    docs = await db.briefings.find({"stories.is_positive": True}).sort("date", -1).to_list(200)
    out: List[Dict[str, Any]] = []
    for d in docs:
        for s in d.get("stories", []):
            if s.get("is_positive") and not s.get("is_excluded"):
                out.append(
                    {
                        "date": d.get("date", ""),
                        "headline": s.get("headline", ""),
                        "location": s.get("location", ""),
                        "notes": s.get("notes", ""),
                    }
                )
    return out


_RESEARCH_SUFFIX = (
    "\n\nYou are in the RESEARCH stage of a multi-stage workflow. Ignore any instruction about JSON or script "
    "formatting for now; return a plain-text research dossier as requested. A later stage writes the script."
)


def _split_contract():
    mech, _, schema = OUTPUT_CONTRACT.partition("\nOUTPUT:")
    return mech.replace("__REQUIRED_INTRO__", REQUIRED_INTRO), "OUTPUT:" + schema


async def _research(
    plan: str, week_start, week_end, briefings, script_length, candidates, positive, submissions,
    extra: str = "",
):
    """Stage 1 (grounded): live Google Search research. Returns (dossier, citations, model)."""
    from lib import llm, source_packet

    user = _user_prompt(
        week_start, week_end, briefings, script_length, candidates, positive, submissions, stage="research"
    )
    if extra:
        user += "\n\n" + extra
    result = await llm.generate(system=plan + _RESEARCH_SUFFIX, user=user, grounded=True)
    dossier = result["content"] or ""
    cites = [{"url": c["url"], "title": c.get("title", ""), "grounded": True} for c in result["citations"]]
    # URLs the model typed into its dossier are NOT grounded; they only enter the packet if they fetch.
    cites += [{"url": u, "title": "", "grounded": False} for u in source_packet.urls_in_text(dossier)]
    # Reader-submitted links are fetched so the writer reads them instead of guessing.
    cites += [{"url": s.get("url", ""), "title": "", "grounded": False} for s in submissions if s.get("url")]
    return dossier, cites, result["model"]


async def _write(
    plan: str, week_start, week_end, briefings, script_length, candidates, positive, submissions,
    packet: List[Dict[str, Any]], dossier: str,
) -> Dict[str, Any]:
    """Stage 2 (ungrounded): write the episode strictly from the fetched source packet."""
    from lib import llm, source_packet

    result = await llm.generate(
        system=build_system(plan),
        user=_user_prompt(
            week_start, week_end, briefings, script_length, candidates, positive, submissions,
            stage="write", packet_text=source_packet.render_for_prompt(packet), dossier=dossier,
        ),
        grounded=False,
    )
    data = desk._parse_json(result["content"])
    data["_model"] = result["model"]
    return data


_FACT_CHECK_SYSTEM = (
    "You are a meticulous news fact-checker for a podcast. You compare a recording script against the numbered "
    "source articles it was written from and report every claim the sources do not support or contradict. "
    "Pay special attention to DATES, DEADLINES and WINDOWS (is a deadline described as 'this week' / 'closes soon' / "
    "a different date than the source gives?), numbers, names, titles, places, and whether a proposal, discussion "
    "or allegation is stated as a decision or fact. Do not nitpick wording. Return ONLY JSON: "
    '{"issues": [{"claim": "the script sentence", "problem": "what the source actually says", '
    '"source_id": "S3", "suggested_fix": "corrected wording", "severity": "high|medium|low"}]}. '
    'If everything is supported return {"issues": []}.'
)


async def fact_check_script(script: str, packet: List[Dict[str, Any]], week_start: str, week_end: str) -> List[Dict[str, Any]]:
    from lib import llm, source_packet

    today = datetime.now(desk.EASTERN).strftime("%A, %B %d, %Y")
    user = (
        f"TODAY: {today}. Episode week: {week_start} through {week_end}.\n\n=== SCRIPT ===\n{script}\n\n"
        f"=== SOURCES ===\n{source_packet.render_for_prompt(packet)}"
    )
    result = await llm.generate(system=_FACT_CHECK_SYSTEM, user=user, grounded=False)
    data = desk._parse_json(result["content"])
    issues = [i for i in (data.get("issues") or []) if isinstance(i, dict) and i.get("claim")]
    for i in issues:
        i["fixed"] = False
    return issues


_REVISE_SUFFIX = (
    "\n\nYou are REVISING an existing script, not writing a new one. Change only what the feedback requires and keep "
    "every unaffected sentence word-for-word. Keep the chapter header format and the verbatim introduction. Do not "
    "add a support/fundraising chapter. The host is the editor and is authoritative on editorial direction and on "
    "corrections of fact; when the sources contradict a factual claim in the feedback, follow the sources and say "
    "so in change_notes. When feedback asks for something the sources do not cover, say so in change_notes instead "
    "of inventing it. Return ONLY JSON: "
    '{"recording_script": "the full revised script", "chapters": ["ordered chapter titles"], '
    '"editorial_summary": "updated only if the changes affect it, else the original", '
    '"change_notes": "2-5 short sentences: what you changed and anything you could not do"}'
)


async def revise_script(
    *, plan: str, script: str, summary: str, packet: List[Dict[str, Any]], feedback: str,
    week_start: str, week_end: str, dossier: str = "",
) -> Dict[str, Any]:
    from lib import llm, source_packet

    mech, _schema = _split_contract()
    today = datetime.now(desk.EASTERN).strftime("%A, %B %d, %Y")
    user = (
        f"TODAY: {today}. Episode week: {week_start} through {week_end}.\n\n"
        f"=== FEEDBACK TO APPLY ===\n{feedback.strip()}\n\n"
        f"=== CURRENT EDITORIAL SUMMARY ===\n{summary}\n\n=== CURRENT SCRIPT ===\n{script}\n\n"
        + (f"=== NEW RESEARCH FOR THIS REVISION ===\n{dossier}\n\n" if dossier else "")
        + f"=== SOURCES ===\n{source_packet.render_for_prompt(packet)}"
    )
    result = await llm.generate(system=plan + "\n\n" + mech + _REVISE_SUFFIX, user=user, grounded=False)
    data = desk._parse_json(result["content"])
    if not str(data.get("recording_script") or "").strip():
        raise ValueError("The revision came back empty — nothing was changed.")
    return data


def _ensure_intro(script: str) -> str:
    """Guarantee the verbatim Randy Black introduction opens the script."""
    if REQUIRED_INTRO in (script or ""):
        return script
    opener = f"## Introduction\n\nWelcome to WVEdTalk, West Virginia's weekly education-news podcast.\n\n{REQUIRED_INTRO}\n\n"
    return opener + (script or "")


def _ensure_support(script: str, text: Optional[str] = None) -> str:
    """Insert the support segment as its own '## Support WVEdTalk' chapter. It goes immediately
    before the final '## On a Positive Note' chapter when present (so the support read is heard and
    the episode then ends on the uplifting story), otherwise before '## Closing', otherwise appended.
    Idempotent by header (won't duplicate)."""
    script = script or ""
    if re.search(rf"(?im)^[ \t]*##[ \t]+{re.escape(SUPPORT_CHAPTER)}[ \t]*$", script):
        return script
    block = f"## {SUPPORT_CHAPTER}\n\n{(text or REQUIRED_SUPPORT).strip()}"
    # Prefer the positive-note chapter as the anchor; fall back to the closing sign-off.
    anchors = [m.start() for m in re.finditer(rf"(?im)^[ \t]*##[ \t]+{re.escape(POSITIVE_CHAPTER)}[ \t]*$", script)]
    if not anchors:
        anchors = [m.start() for m in re.finditer(r"(?im)^[ \t]*##[ \t]+Closing[ \t]*$", script)]
    if anchors:
        idx = anchors[-1]
        return script[:idx].rstrip() + "\n\n" + block + "\n\n" + script[idx:]
    return script.rstrip() + "\n\n" + block


def _remove_support(script: str) -> str:
    """Strip the '## Support WVEdTalk' chapter block (header through the next '## ' or end)."""
    out = re.sub(
        rf"(?ims)\n*^[ \t]*##[ \t]+{re.escape(SUPPORT_CHAPTER)}[ \t]*$.*?(?=^[ \t]*##[ \t]|\Z)",
        "\n\n",
        script or "",
    )
    return out.strip()


def _extract_chapters(script: str) -> List[str]:
    """Fallback: pull chapter titles from the '## ' header lines in the script."""
    return [m.group(1).strip() for m in re.finditer(r"(?m)^\s*##\s+(.+?)\s*$", script or "") if m.group(1).strip()]


def _collect_links(source_log, stories) -> List[SourceLink]:
    """The de-duplicated set of every source used to build the episode — the source log plus
    each selected story's sources — for the show-notes 'Links to New Sources for This Week' list.
    Order: source log first, then story sources; the first occurrence of a URL wins."""
    seen: set = set()
    out: List[SourceLink] = []

    def _add(items) -> None:
        for s in items or []:
            url = (getattr(s, "url", "") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            out.append(
                SourceLink(
                    url=url,
                    title=getattr(s, "title", "") or "",
                    outlet=getattr(s, "outlet", "") or "",
                    verified=bool(getattr(s, "verified", True)),
                    grounded=bool(getattr(s, "grounded", False)),
                )
            )

    _add(source_log)
    for st in stories or []:
        _add(getattr(st, "sources", None))
    return out


async def _chapterize_call(script: str) -> Dict[str, Any]:
    """Ask the model to insert chapter headers into an EXISTING script without rewriting it."""
    import os

    system = (
        "You format existing podcast scripts by inserting chapter headers. You never change, add, "
        "remove, reword, or reorder any spoken words — you only insert '## Chapter Title' header "
        "lines. Return only a single JSON object."
    )
    prompt = (
        "Insert chapter headers into this WVEdTalk recording script so it can be navigated by "
        "chapter, WITHOUT altering any spoken words.\n"
        "Rules:\n"
        "- Do NOT change, add, remove, reword, or reorder any existing text. Only insert header lines.\n"
        "- Before each distinct story or segment, insert a line formatted EXACTLY as '## Chapter Title' "
        "(a short, descriptive 3-7 word title suitable as a podcast chapter title).\n"
        "- Use '## Introduction' for the opening and '## Closing' for the sign-off.\n"
        "- Each header on its own line, with a blank line before and after it. Keep any header that already exists.\n\n"
        'Return ONLY this JSON: {"recording_script": "the full script with ## headers, \\n\\n between paragraphs", '
        '"chapters": ["ordered chapter titles without the ## prefix"]}\n\n'
        "SCRIPT:\n" + script
    )
    from lib import llm

    result = await llm.generate(system=system, user=prompt, grounded=False)
    return desk._parse_json(result["content"])


async def chapterize_episode(week_of: str) -> Dict[str, Any]:
    """Backfill chapter headers on an already-produced episode. Raises ValueError('not_found'
    / 'empty_script') for the router to translate into HTTP errors."""
    doc = await db.episodes.find_one({"week_of": week_of})
    if not doc:
        raise ValueError("not_found")
    script = str(doc.get("recording_script") or "").strip()
    if not script:
        raise ValueError("empty_script")

    data = await _chapterize_call(script)
    # Backfill must NOT add spoken content — only insert headers. Never prepend the intro here
    # (that belongs to fresh production); use the model's returned script, or the original if empty.
    new_script = str(data.get("recording_script") or "").strip() or script
    chapters = _extract_chapters(new_script)

    await db.episodes.update_one(
        {"week_of": week_of},
        {"$set": {"recording_script": new_script, "chapters": chapters}},
    )
    doc["recording_script"] = new_script
    doc["chapters"] = chapters
    doc.pop("_id", None)
    return doc


async def relink_episode(week_of: str) -> Dict[str, Any]:
    """Backfill the consolidated 'Links to New Sources for This Week' list on an existing episode.
    Re-resolves any redirect URLs to direct publisher links, then rebuilds episode_links from the
    source log + every story's sources. Raises ValueError('not_found')."""
    doc = await db.episodes.find_one({"week_of": week_of})
    if not doc:
        raise ValueError("not_found")
    doc.pop("_id", None)
    ep = WeeklyEpisode(**doc)

    links = list(ep.source_log)
    for s in ep.selected_stories:
        links.extend(s.sources)
    try:
        await desk.resolve_links(links)
    except Exception:
        logger.exception("relink: source resolution failed (using stored URLs)")

    ep.source_log = desk._valid_sources(ep.source_log)
    for s in ep.selected_stories:
        s.sources = desk._valid_sources(s.sources)
    ep.episode_links = _collect_links(ep.source_log, ep.selected_stories)
    await db.episodes.update_one(
        {"week_of": week_of},
        {"$set": {
            "source_log": [s.model_dump() for s in ep.source_log],
            "selected_stories": [s.model_dump() for s in ep.selected_stories],
            "episode_links": [s.model_dump() for s in ep.episode_links],
        }},
    )
    return ep.model_dump()


_revise_lock = asyncio.Lock()


async def _load_packet(doc: Dict[str, Any]):
    """The stored source packet for an episode; episodes made before packets existed get one built
    on demand from their links (only links that actually fetch, or came from Google grounding)."""
    from lib import source_packet

    week_of = doc["week_of"]
    pk = await db.episode_packets.find_one({"week_of": week_of}, {"_id": 0})
    if pk and pk.get("packet"):
        return pk["packet"], pk.get("dossier", "")
    links = list(doc.get("source_log") or []) + list(doc.get("episode_links") or [])
    for st in doc.get("selected_stories") or []:
        links += list(st.get("sources") or [])
    cites = [
        {"url": l.get("url", ""), "title": l.get("title", ""), "grounded": bool(l.get("grounded"))}
        for l in links if isinstance(l, dict)
    ]
    packet = await source_packet.build_packet(cites)
    await db.episode_packets.replace_one(
        {"week_of": week_of}, {"week_of": week_of, "packet": packet, "dossier": ""}, upsert=True
    )
    return packet, ""


async def revise_episode(week_of: str, feedback: str, allow_research: bool = False) -> Dict[str, Any]:
    """Apply host feedback to an existing script (minimal edits, no full regeneration). Snapshots the
    prior version so it can be restored. Raises ValueError('not_found' | 'empty_feedback' | 'busy')."""
    from lib import source_packet

    feedback = (feedback or "").strip()
    if not feedback:
        raise ValueError("empty_feedback")
    if _revise_lock.locked():
        raise ValueError("busy")
    async with _revise_lock:
        doc = await db.episodes.find_one({"week_of": week_of})
        if not doc:
            raise ValueError("not_found")
        doc.pop("_id", None)
        cfg = await db.desk_config.find_one({"key": "singleton"}, {"_id": 0}) or {}
        plan = await load_plan()
        packet, dossier = await _load_packet(doc)
        new_dossier = ""
        added = False
        if allow_research:
            new_dossier, cites, _m = await _research(
                plan, doc.get("week_start", ""), doc.get("week_end", ""), [], cfg.get("script_length", "standard"),
                [], [], [],
                extra="TARGETED RESEARCH REQUEST from the editor, to be applied to an existing script. Research only what "
                      "this feedback needs, with the same date discipline:\n" + feedback,
            )
            before = len(packet)
            packet = await source_packet.build_packet(cites, existing=packet)
            added = len(packet) > before
            await db.episode_packets.replace_one(
                {"week_of": week_of}, {"week_of": week_of, "packet": packet, "dossier": dossier}, upsert=True
            )

        current = str(doc.get("recording_script") or "")
        rev = await revise_script(
            plan=plan, script=_remove_support(current), summary=str(doc.get("editorial_summary") or ""),
            packet=packet, feedback=feedback, week_start=doc.get("week_start", ""), week_end=doc.get("week_end", ""),
            dossier=new_dossier,
        )
        base = _ensure_intro(str(rev["recording_script"]))
        support_on = bool(doc.get("support_included", True))
        new_script = _ensure_support(base, cfg.get("support_segment") or REQUIRED_SUPPORT) if support_on else base
        chapters = _extract_chapters(new_script)

        await db.episode_revisions.insert_one({
            "id": str(uuid.uuid4()), "week_of": week_of, "at": datetime.now(timezone.utc).isoformat(),
            "feedback": feedback, "script_before": current, "summary_before": doc.get("editorial_summary", ""),
            "notes": str(rev.get("change_notes") or ""),
        })

        updates: Dict[str, Any] = {
            "recording_script": new_script,
            "chapters": chapters,
            "editorial_summary": str(rev.get("editorial_summary") or doc.get("editorial_summary") or ""),
            "last_revision_notes": str(rev.get("change_notes") or ""),
            "revision_count": int(doc.get("revision_count", 0)) + 1,
        }
        if added:
            existing = {l.get("url") for l in (doc.get("source_log") or [])}
            new_links = [l for l in source_packet.to_links(packet, [p["id"] for p in packet]) if l["url"] not in existing]
            updates["source_log"] = list(doc.get("source_log") or []) + new_links
            updates["episode_links"] = list(doc.get("episode_links") or []) + [
                l for l in new_links if l["url"] not in {x.get("url") for x in (doc.get("episode_links") or [])}
            ]
        try:
            issues = await fact_check_script(base, packet, doc.get("week_start", ""), doc.get("week_end", ""))
            updates["fact_check"] = issues
        except Exception:
            logger.exception("post-revision fact-check failed (non-fatal)")
        await db.episodes.update_one({"week_of": week_of}, {"$set": updates})
        doc.update(updates)
        return doc


async def list_revisions(week_of: str) -> List[Dict[str, Any]]:
    docs = await db.episode_revisions.find({"week_of": week_of}, {"_id": 0, "script_before": 0, "summary_before": 0}).sort("at", -1).to_list(50)
    return docs


async def restore_revision(week_of: str, revision_id: str) -> Dict[str, Any]:
    """Put back the script as it was BEFORE the given revision (the current script is snapshotted first)."""
    rev = await db.episode_revisions.find_one({"week_of": week_of, "id": revision_id})
    doc = await db.episodes.find_one({"week_of": week_of})
    if not rev or not doc:
        raise ValueError("not_found")
    doc.pop("_id", None)
    await db.episode_revisions.insert_one({
        "id": str(uuid.uuid4()), "week_of": week_of, "at": datetime.now(timezone.utc).isoformat(),
        "feedback": "(restored an earlier version)", "script_before": doc.get("recording_script", ""),
        "summary_before": doc.get("editorial_summary", ""), "notes": "",
    })
    script = rev["script_before"]
    updates = {
        "recording_script": script,
        "chapters": _extract_chapters(script),
        "editorial_summary": rev.get("summary_before", doc.get("editorial_summary", "")),
        "last_revision_notes": "Restored an earlier version.",
    }
    await db.episodes.update_one({"week_of": week_of}, {"$set": updates})
    doc.update(updates)
    return doc


async def produce_episode(week_of: Optional[str] = None, trigger: str = "manual") -> WeeklyEpisode:
    week_of = week_of or await resolve_week_of()
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
        run_ok = False
        started = datetime.now(timezone.utc)
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
            positive = await _gather_positive()
            if candidates:
                _status.message = f"Reviewing the week with {len(candidates)} host-flagged candidate(s) prioritized…"
            submissions = (
                await db.submissions.find({"status": "new"}, {"_id": 0, "url": 1, "name": 1})
                .sort("submitted_at", -1)
                .to_list(50)
            )
            from lib import source_packet

            plan = await load_plan()
            plan_is_custom = plan != DEFAULT_PLAN
            args = (week_start, week_end, briefings, script_length, candidates, positive, submissions)

            _status.message = "Stage 1/4: researching the week with Google Search…"
            dossier, cites, _research_model = await _research(plan, *args)

            _status.message = f"Stage 2/4: reading {len(cites)} candidate source(s)…"
            packet = await source_packet.build_packet(cites)
            if not packet:
                raise RuntimeError("Research found no readable sources — check the AI key and web access.")

            _status.message = f"Stage 3/4: writing the script from {len(packet)} source article(s)…"
            data = await _write(plan, *args, packet, dossier)

            selected: List[EpisodeStory] = []
            used_ids: List[str] = []
            for raw in data.get("selected_stories") or []:
                if not isinstance(raw, dict):
                    continue
                cls = raw.get("classification")
                if isinstance(cls, str):
                    raw["classification"] = [cls]
                ids = source_packet.parse_ids(raw.pop("source_ids", []))
                used_ids += ids
                raw["sources"] = source_packet.to_links(packet, ids)
                try:
                    selected.append(EpisodeStory(**raw))
                except Exception as exc:
                    logger.warning("skipping malformed selected story: %s", exc)

            not_selected = [
                NotSelectedStory(**r) for r in (data.get("not_selected") or []) if isinstance(r, dict)
            ]
            look_ahead = [
                LookAheadItem(**{k: str(v) for k, v in r.items() if k in ("label", "date")})
                if isinstance(r, dict) else LookAheadItem(label=str(r))
                for r in (data.get("look_ahead") or [])
            ]

            used_ids += source_packet.parse_ids(data.get("source_ids_used"))
            log_links = source_packet.to_links(packet, used_ids or [p["id"] for p in packet])
            source_log = [SourceLink(**l) for l in log_links]

            support_on = bool(cfg.get("support_default_on", True))
            base_script = _ensure_intro(str(data.get("recording_script") or ""))

            _status.message = "Stage 4/4: fact-checking the script against the sources…"
            fact_issues: List[Dict[str, Any]] = []
            try:
                fact_issues = await fact_check_script(base_script, packet, week_start, week_end)
                serious = [i for i in fact_issues if str(i.get("severity", "medium")).lower() in ("high", "medium")]
                if serious:
                    _status.message = f"Correcting {len(serious)} fact-check issue(s)…"
                    notes = "\n".join(
                        f"- Script says: {i['claim']}\n  Source {i.get('source_id','')} actually says: {i.get('problem','')}\n  Fix: {i.get('suggested_fix','')}"
                        for i in serious
                    )
                    rev = await revise_script(
                        plan=plan, script=base_script, summary=str(data.get("editorial_summary") or ""),
                        packet=packet, feedback="Fact-checker findings — correct each one:\n" + notes,
                        week_start=week_start, week_end=week_end,
                    )
                    base_script = _ensure_intro(str(rev["recording_script"]))
                    for i in serious:
                        i["fixed"] = True
            except Exception:
                logger.exception("fact-check step failed (non-fatal)")

            final_script = (
                _ensure_support(base_script, cfg.get("support_segment") or REQUIRED_SUPPORT)
                if support_on
                else _remove_support(base_script)
            )
            chapters = _extract_chapters(final_script)

            episode = WeeklyEpisode(
                week_of=week_of,
                week_start=week_start,
                week_end=week_end,
                model=str(data.get("_model") or f"{MODEL_PROVIDER}/{MODEL_NAME}"),
                editorial_summary=str(data.get("editorial_summary") or ""),
                selected_stories=selected,
                not_selected=not_selected,
                look_ahead=look_ahead,
                recording_script=final_script,
                chapters=chapters,
                support_included=support_on,
                source_log=source_log,
                fact_check=fact_issues,
                plan_is_custom=plan_is_custom,
            )
            episode.episode_links = _collect_links(episode.source_log, episode.selected_stories)
            await db.episode_packets.replace_one(
                {"week_of": week_of}, {"week_of": week_of, "packet": packet, "dossier": dossier}, upsert=True
            )

            await db.episodes.replace_one({"week_of": week_of}, episode.model_dump(), upsert=True)
            _status.message = f"WVEdTalk episode for week of {week_of} is ready ({len(selected)} stories)."
            run_ok = True
            try:
                urls = [src.url for st in episode.selected_stories for src in (st.sources or [])]
                urls += [src.url for src in (episode.source_log or [])]
                await desk.link_submissions_used(urls, label=f"Weekly episode {week_of}", ref=f"/episodes/{week_of}")
            except Exception:
                logger.exception("linking used submissions failed (non-fatal)")
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
            await desk.record_run(
                kind="weekly", trigger=trigger,
                status="complete" if run_ok else "failed",
                label=week_of,
                detail=_status.message if run_ok else _status.last_error,
                started_at=started,
            )


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
    if _status.running:
        return
    s = await desk.load_schedule()
    now = datetime.now(desk._safe_zone(s["timezone"]))
    if now.weekday() != s["weekly_dow"]:
        return
    if (now.hour * 60 + now.minute) < (s["weekly_hour"] * 60 + s["weekly_minute"]):
        return
    week_of = await resolve_week_of()
    if await db.episodes.find_one({"week_of": week_of, "status": "complete"}):
        return
    logger.info("weekly scheduler: producing WVEdTalk episode for %s", week_of)
    await produce_episode(week_of, trigger="scheduled")


async def scheduler_loop() -> None:
    """Produce the weekly episode at 4:00 PM ET on Fridays if it doesn't exist yet."""
    while True:
        try:
            from lib import config_secrets
            if await config_secrets.runs_enabled():
                await _maybe_produce_weekly()
        except Exception:
            logger.exception("weekly scheduler loop error")
            await asyncio.sleep(1800)
        await asyncio.sleep(300)
