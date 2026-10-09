"""The WV Education News Desk research run: prompt, LLM call, persistence, scheduler."""

import asyncio
import json
import logging
import os
import re
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Any, Dict, List, Optional

from lib.db import db
from models.briefing import Briefing, RunStatus, SourceLink, Story

logger = logging.getLogger(__name__)

EASTERN = ZoneInfo("America/New_York")  # DST-aware ET anchor (handles EST/EDT automatically)
MODEL_PROVIDER = "gemini"
MODEL_NAME = "gemini-3.1-pro-preview"
SCHEDULE_HOUR_ET = 22

_run_status = RunStatus()
_run_lock = asyncio.Lock()

SCHEDULE_DEFAULTS = {
    "daily_hour": 22, "daily_minute": 0,
    "weekly_dow": 4, "weekly_hour": 16, "weekly_minute": 0,
}
DEFAULT_TZ = "America/New_York"


def is_valid_tz(name: str) -> bool:
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


def _safe_zone(name: str) -> ZoneInfo:
    return ZoneInfo(name) if is_valid_tz(name) else ZoneInfo(DEFAULT_TZ)


async def load_schedule() -> Dict[str, Any]:
    """Admin-configured run times + home timezone, falling back to defaults. One source of truth
    shared by both schedulers and the header 'next run' indicator."""
    doc = await db.desk_config.find_one({"key": "singleton"}, {"_id": 0}) or {}
    out: Dict[str, Any] = {}
    for k, v in SCHEDULE_DEFAULTS.items():
        try:
            out[k] = int(doc.get(k, v))
        except (TypeError, ValueError):
            out[k] = v
    tz = doc.get("timezone") or DEFAULT_TZ
    out["timezone"] = tz if is_valid_tz(tz) else DEFAULT_TZ
    return out


def _next_daily(now_et: datetime, hour: int, minute: int) -> datetime:
    cand = now_et.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return cand if cand > now_et else cand + timedelta(days=1)


def _next_weekly(now_et: datetime, dow: int, hour: int, minute: int) -> datetime:
    days = (dow - now_et.weekday()) % 7
    cand = (now_et + timedelta(days=days)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return cand if cand > now_et else cand + timedelta(days=7)


async def next_runs() -> Dict[str, str]:
    """Next daily + weekly run as UTC ISO timestamps (browser converts to local time)."""
    s = await load_schedule()
    now_et = datetime.now(_safe_zone(s["timezone"]))
    d = _next_daily(now_et, s["daily_hour"], s["daily_minute"]).astimezone(timezone.utc)
    w = _next_weekly(now_et, s["weekly_dow"], s["weekly_hour"], s["weekly_minute"]).astimezone(timezone.utc)
    return {"daily_next": d.isoformat(), "weekly_next": w.isoformat()}


async def record_run(*, kind: str, trigger: str, status: str, label: str,
                     detail: str, started_at: datetime) -> None:
    """Append one entry to the run history log, and alert admins if a SCHEDULED run failed.
    Best-effort — never raise into a run."""
    try:
        await db.run_log.insert_one({
            "id": str(uuid.uuid4()), "kind": kind, "trigger": trigger, "status": status,
            "label": label, "detail": (detail or "")[:300],
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        logger.exception("failed to record run history (non-fatal)")
    if status == "failed" and trigger == "scheduled":
        try:
            from lib import email_digest
            await email_digest.send_failure_alert(kind=kind, label=label, detail=detail)
        except Exception:
            logger.exception("failed to send failure alert (non-fatal)")


def _norm_url(u: str) -> str:
    try:
        p = urllib.parse.urlparse((u or "").strip().lower())
        host = p.hostname or ""
        if host.startswith("www."):
            host = host[4:]
        return f"{host}{p.path.rstrip('/')}" if host else ""
    except Exception:
        return ""


async def link_submissions_used(urls: List[str], label: str, ref: str) -> int:
    """Auto-link reader submissions whose URL appears among a run's sources: flip them to 'used'
    and record where they appeared. If auto_thank_on_use is enabled, email the reader a thank-you.
    Only touches submissions still marked 'new'. Best-effort."""
    norms = {n for n in (_norm_url(u) for u in urls) if n}
    if not norms:
        return 0
    cfg = await db.desk_config.find_one({"key": "singleton"}, {"_id": 0, "auto_thank_on_use": 1}) or {}
    auto_thank = bool(cfg.get("auto_thank_on_use"))
    linked = 0
    async for doc in db.submissions.find(
        {"status": "new"}, {"_id": 0, "id": 1, "url": 1, "name": 1, "email": 1, "thanked": 1}
    ):
        if _norm_url(doc.get("url", "")) not in norms:
            continue
        sets = {"status": "used", "used_in": label, "used_ref": ref,
                "updated_at": datetime.now(timezone.utc).isoformat()}
        if auto_thank and not doc.get("thanked"):
            try:
                from lib import email_digest
                if await email_digest.send_submission_thanks(
                    name=doc.get("name", ""), email=doc.get("email", ""), url=doc.get("url", "")
                ):
                    sets["thanked"] = True
            except Exception:
                logger.exception("auto-thank failed (non-fatal)")
        await db.submissions.update_one({"id": doc["id"]}, {"$set": sets})
        linked += 1
    return linked


def today_et() -> str:
    return datetime.now(EASTERN).strftime("%Y-%m-%d")


def get_run_status() -> RunStatus:
    return _run_status


EDITORIAL_BRIEF = """You are the WV EDUCATION NEWS DESK, a statewide research and editorial assistant supporting a West Virginia education-focused podcast.

Cover EDUCATION ACROSS ALL OF WEST VIRGINIA, not primarily WVU or other high-profile institutions. Treat WVU, Marshall, and other major institutions as only part of the coverage, not the default center of gravity.

Identify, verify, prioritize, and contextualize significant developments involving education in West Virginia so the host quickly understands: what is happening, what is new, why it matters, who is affected, what remains unknown, what deserves further research, and which stories may warrant discussion, interviews, or an episode.

You are not merely a news aggregator. Exercise editorial judgment. Prioritize significance, accuracy, local relevance, timeliness, and potential audience value over the number of stories found. Do not manufacture controversy, significance, urgency, or connections unsupported by evidence. Accuracy is more important than completeness; completeness is more important than volume.

RESEARCH WINDOW: use live web search. Prioritize stories published or substantially updated in the previous 24 hours. Also check the preceding several days for important developing stories with meaningful new developments. Never use bare relative dates: always state actual calendar dates.

STATEWIDE COVERAGE RULE: deliberately discover meaningful stories from across the state, including multiple regions and rural/local districts. Search beyond statewide institutions: county board activity, individual districts and schools, teachers, students, parents, families, local disputes, school construction, closures, consolidation, transportation, special education, attendance, discipline, school safety, technology, artificial intelligence, curriculum, testing, funding, local policy, education-related legal proceedings, and workforce development connected to education. Do not let one institution, county, region, or source ecosystem dominate unless the news itself is overwhelmingly concentrated there.

GEOGRAPHIC BALANCE: when sufficient news exists, seek representation from Northern, North-central, Eastern Panhandle, Central, mountain communities, Southern, Southwestern, and Western West Virginia. Consider all 55 counties. Do not manufacture geographic diversity, but actively search for local developments before concluding none exist. A lightly covered local story can be more important than a heavily covered statewide institutional announcement.

COVERAGE MIX: prioritize K-12 as the broadest portion of coverage. Higher education matters but must not routinely dominate the Big Three; it is included on significance, not institutional prominence.

BIG THREE BALANCE: before selecting, compare statewide policy, K-12 and local district developments, higher education, legal and student-safety issues, county-level developments, education funding, and major workforce or technology developments. A WVU story takes a Big Three slot only when its statewide educational importance genuinely exceeds the alternatives. The question is: what would a knowledgeable West Virginia education podcast host genuinely need to know today?

DISCOVERY METHOD: use broad statewide searches plus targeted local and county-level searches, by issue AND by geography. Search statewide news organizations, regional outlets, TV and radio news, county boards of education, district and school websites, state agencies, legislative materials, courts and court documents, government records, universities, colleges, community and technical colleges, and national education sources when relevant. Do not rely primarily on WVU, Marshall, WVDE, MetroNews, or any single outlet or press-release feed. When you find an important story, search again to see whether other sources reported it, whether a primary source exists, whether it is developing, whether accounts compete, and whether context changes its significance.

SOURCE HIERARCHY: Tier 1 primary/official (WVDE, WV Board of Education, Legislature, Governor's office, state agencies, HEPC, CTCS, county boards, districts, schools, public and private WV colleges, court documents, government records, federal agencies including the U.S. Department of Education when WV is affected) carries the greatest weight; prefer the original document, minutes, bill, filing, report or data set over secondary reporting. Tier 2 established WV news organizations (WV Public Broadcasting, Charleston Gazette-Mail, MetroNews, WV News, The Register-Herald, The Intelligencer, Wheeling News-Register, Parkersburg News and Sentinel, Times Record & News Journal, and Huntington, Morgantown, Clarksburg, Fairmont and Beckley outlets, among others). Tier 3 local and regional papers, TV, radio, district publications, community news. Tier 4 education trade and national sources (Education Week, K-12 Dive, EdSurge, Hechinger, Inside Higher Ed, Higher Ed Dive, NEA, AFT, AASA, NSBA) for context, treating advocacy groups as interested parties. Tier 5 social media, aggregators, newsletters, forums and press-release services may surface leads but are not sufficient evidence; verify against a primary source or reputable reporting.

VERIFICATION: identify the most authoritative source, review reputable reporting, compare conflicting accounts, determine whether something is an announcement, proposal, allegation, opinion, decision or confirmed event, and state uncertainty plainly. Never invent facts, quotations, statistics, sources, people, organizations, events, legal conclusions or policy outcomes, and never imply a source says something it does not. Do not confuse proposed with enacted legislation, proposed with adopted policy, a board discussion with a final decision, an allegation with established fact, an organization's position with objective fact, or commentary with reporting. When sources disagree, report the disagreement.

DUPLICATES: consolidate substantially duplicative coverage of the same underlying event into one story, naming the strongest primary source and the strongest independent reporting; explain materially different accounts. Track continuing stories across days as one story classified DEVELOPING, stating when it first appeared, what changed, what is new, what was known, what is unresolved, and what to watch.

STORY EVALUATION: score importance to WV education and podcast potential 1-10 using judgment, not mechanical averaging of sub-factors. A lightly covered local story can score high; a heavily covered institutional story does not automatically score high.

CLASSIFICATION: label each story with one or more of NEWS, OFFICIAL, ANALYSIS, OPINION, DEVELOPING, TREND. Clearly separate reporting from opinion and advocacy.

PODCAST RELEVANCE: for high-value stories assess the larger issue, why West Virginians should care, what questions the public should ask, what is missing, competing perspectives, useful expertise, and whether it supports an episode or a segment. If an important story has little podcast potential, say so. Do not manufacture an angle to fill space.

TRENDS: identify emerging patterns only when multiple developments support them; never declare a trend from one incident. Distinguish evidence from hypothesis.

NO-NEWS RULE: when no significant WV education news exists, say so in the editor_note and return fewer stories. Never pad with routine calendar announcements, ordinary events, routine meetings, minor personnel changes, sports results, generic national stories, promotional announcements, or ceremonial events. A short briefing beats a misleading one.

FINAL EDITORIAL TESTS, applied before you answer: (1) statewide relevance; (2) K-12 balance; (3) source diversity beyond the most prominent institutions; (4) WVU/Marshall independence - would the Big Three still be the Big Three if WVU and Marshall had published nothing today? (5) editorial trust; (6) geographic integrity; (7) factual integrity distinguishing allegations, proposals, opinions, confirmed facts, court findings and final decisions; (8) duplicate integrity; (9) podcast value.

OUTPUT: respond with a single JSON object and nothing else - no prose, no markdown fence. Schema:
{
  "editor_note": "1-3 sentences on the state of the day's news, including an explicit no-news statement when warranted",
  "stories": [
    {
      "section": "big_three | other | developing | state_policy | k12 | higher_ed",
      "rank": 1,
      "headline": "",
      "location": "County/region",
      "classification": ["NEWS"],
      "importance": 8,
      "podcast_potential": 6,
      "what_happened": "",
      "why_it_matters": "",
      "podcast_angle": "empty string when not genuinely warranted",
      "questions": [""],
      "original_date": "YYYY-MM-DD for developing stories, else empty",
      "what_is_new": "developing only",
      "previously_known": "developing only",
      "unresolved": "developing only",
      "watch_next": "developing only",
      "sources": [{"title": "", "url": "https://...", "outlet": ""}]
    }
  ],
  "trends": [{"title": "", "why_it_matters": "", "evidence": [""], "missing_evidence": [""], "watch_next": ""}],
  "podcast_ideas": [{"working_title": "", "central_question": "", "why_worth_exploring": "", "supporting_stories": [""], "research_needed": [""], "potential_guests": [""]}],
  "source_log": [{"title": "", "url": "https://...", "outlet": ""}]
}

Section rules: exactly up to three stories in "big_three" with rank 1-3 (fewer if fewer genuinely significant stories exist); roughly 5-10 in "other"; "developing" for continuing stories with new developments; "state_policy" for Legislature, Governor, WVDE, state board, funding, regulation and election items, explicitly stating whether a policy is proposed, under consideration, adopted, enacted, suspended, challenged, repealed or otherwise finalized; "k12" should receive substantial attention; "higher_ed" only where statewide significance earns it. Every URL must be a real page you actually consulted during this run. The source_log lists the important sources actually reviewed, including local and regional ones."""


def _user_prompt(date_str: str, recent: List[Dict[str, Any]], submissions: List[Dict[str, Any]]) -> str:
    lines = [
        f"Today's calendar date is {date_str} (America/New_York). Produce the daily briefing for this date.",
        "Prioritize developments published or substantially updated in the previous 24 hours, and check the preceding several days for continuing stories.",
    ]
    if recent:
        lines.append(
            "\nStories already reported in this desk's recent briefings — use these to judge what is genuinely NEW and to classify continuing coverage as DEVELOPING rather than re-reporting it as fresh:"
        )
        for b in recent:
            heads = "; ".join(s.get("headline", "") for s in b.get("stories", [])[:14])
            lines.append(f"- {b.get('date')}: {heads}")
    else:
        lines.append("\nThis is the first briefing; there is no prior archive to compare against.")
    if submissions:
        lines.append(
            "\nREADER-SUBMITTED LEADS — members of the public submitted the following links for the desk to consider. "
            "Evaluate each independently with live web search and your normal significance and verification standards; "
            "include one ONLY if it genuinely meets the bar. Do not include a story merely because it was submitted, "
            "and never fabricate around a link you cannot verify:"
        )
        for s in submissions:
            who = f" (submitted by {s.get('name')})" if s.get("name") else ""
            lines.append(f"- {s.get('url')}{who}")
    lines.append("\nReturn only the JSON object described in your instructions.")
    return "\n".join(lines)


def _parse_json(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("model response contained no JSON object")
    return json.loads(text[start : end + 1])


async def _call_model(date_str: str, recent: List[Dict[str, Any]], submissions: List[Dict[str, Any]]) -> Dict[str, Any]:
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not key:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")

    chat = (
        LlmChat(api_key=key, session_id=f"wv-desk-{date_str}", system_message=EDITORIAL_BRIEF)
        .with_model(MODEL_PROVIDER, MODEL_NAME)
        .with_tools([{"googleSearch": {}}])  # live Google Search grounding — real cited sources
    )
    resp = await chat.send_message_with_tools(UserMessage(text=_user_prompt(date_str, recent, submissions)))
    content = resp.content if isinstance(resp.content, str) else str(resp.content or "")
    data = _parse_json(content)

    # Grounding citations carry the authoritative source URLs (Google redirect links + outlet titles).
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


def _domain(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


APP_HOST = (urllib.parse.urlparse(os.environ.get("APP_URL", "")).hostname or "").lower()


def _is_valid_source_url(url: str) -> bool:
    """A source URL is publishable only if it's an absolute http(s) link to an EXTERNAL site.
    Rejects: empty/relative URLs (which render as href="" → a link back to our own briefing),
    unresolved Google grounding redirects, and our own app host — the causes of source links
    pointing at the private news desk instead of the actual news story."""
    try:
        p = urllib.parse.urlparse((url or "").strip())
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    host = p.hostname.lower()
    if "vertexaisearch.cloud.google.com" in host:
        return False
    if APP_HOST and (host == APP_HOST or host.endswith("." + APP_HOST)):
        return False
    return True


def _valid_sources(links: List[SourceLink]) -> List[SourceLink]:
    """Keep only sources that resolve to a real external article (see _is_valid_source_url)."""
    return [l for l in (links or []) if l and _is_valid_source_url(l.url)]


def _is_private_host(host: str) -> bool:
    """Block loopback/link-local/private/metadata targets (SSRF guard)."""
    import ipaddress
    import socket

    host = (host or "").lower().strip("[]")
    if not host or host in ("localhost", "metadata.google.internal"):
        return True
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return True  # unresolvable -> treat as unsafe
    for info in infos:
        ip = info[4][0].split("%")[0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            return True
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
            return True
    return False


async def _resolve_one(client, url: str, cache: Dict[str, str]) -> str:
    """Follow a Google grounding redirect to the publisher's direct URL (SSRF-guarded)."""
    if not url or "vertexaisearch.cloud.google.com" not in url:
        return url
    if url in cache:
        return cache[url]
    final = url
    try:
        r = await client.get(url)
        candidate = str(r.url)
        host = urllib.parse.urlparse(candidate).hostname or ""
        if candidate and "vertexaisearch" not in candidate and not _is_private_host(host):
            final = candidate
    except Exception:
        pass
    cache[url] = final
    return final


async def _check_reachable(client, url: str, cache: Dict[str, bool]) -> bool:
    """Confirm a model-authored URL actually resolves to a live page (status < 400). HEAD first,
    GET fallback for servers that reject HEAD. A failure/403/404 => treat as unverified (we keep the
    link but flag it), since Gemini frequently fabricates plausible-looking but non-existent URLs."""
    if not url:
        return False
    if url in cache:
        return cache[url]
    host = urllib.parse.urlparse(url).hostname or ""
    if not host or _is_private_host(host):
        cache[url] = False
        return False
    ok = False
    try:
        r = await client.head(url)
        if r.status_code >= 400:
            r = await client.get(url)
        ok = r.status_code < 400
    except Exception:
        try:
            r = await client.get(url)
            ok = r.status_code < 400
        except Exception:
            ok = False
    cache[url] = ok
    return ok


async def resolve_links(links: List[SourceLink]) -> None:
    """Resolve Google grounding redirects to publisher URLs, fill missing outlets, and verify
    reachability. Google-grounded citations (redirects we successfully follow to a publisher page)
    are trusted as verified; other (model-authored) URLs are probed and marked verified only if the
    page is reachable. Nothing is dropped here — unreachable links are kept with verified=False."""
    import httpx

    links = [l for l in links if l]
    if not links:
        return
    cache: Dict[str, str] = {}
    reach: Dict[str, bool] = {}
    async with httpx.AsyncClient(
        follow_redirects=True,
        max_redirects=5,
        timeout=8.0,
        headers={"User-Agent": "Mozilla/5.0 (WV-Desk)"},
    ) as client:
        async def fix(link):
            original = link.url or ""
            grounded = "vertexaisearch.cloud.google.com" in original
            resolved = await _resolve_one(client, original, cache)
            link.url = resolved
            if not link.outlet:
                link.outlet = _domain(resolved)
            if grounded and "vertexaisearch" not in resolved and resolved != original:
                # A Google grounding citation we followed to a real publisher page — trusted.
                link.verified = True
            else:
                link.verified = await _check_reachable(client, resolved, reach)

        await asyncio.gather(*(fix(link) for link in links), return_exceptions=True)


async def _resolve_sources(briefing: Briefing) -> None:
    links = list(briefing.source_log)
    for s in briefing.stories:
        links.extend(s.sources)
    await resolve_links(links)
    # Drop any link that didn't resolve to a real external article — an empty/relative URL renders
    # as a link back to our own briefing, and an unresolved grounding redirect isn't the story.
    briefing.source_log = _valid_sources(briefing.source_log)
    for s in briefing.stories:
        s.sources = _valid_sources(s.sources)


def _merge_workspace(new: Briefing, previous: Optional[Dict[str, Any]]) -> None:
    """A re-run replaces the date's edition but keeps candidate flags / notes on surviving stories."""
    if not previous:
        return
    by_head = {
        (s.get("headline") or "").strip().lower(): s for s in previous.get("stories", [])
    }
    for story in new.stories:
        old = by_head.get(story.headline.strip().lower())
        if old:
            story.id = old.get("id", story.id)
            story.is_candidate = bool(old.get("is_candidate", False))
            story.notes = old.get("notes", "") or ""


async def run_briefing(date_str: Optional[str] = None, trigger: str = "manual") -> Briefing:
    """Research + write one edition. Serialized: only one run at a time."""
    date_str = date_str or today_et()
    async with _run_lock:
        _run_status.running = True
        _run_status.date = date_str
        _run_status.started_at = datetime.now(timezone.utc)
        _run_status.finished_at = None
        _run_status.message = "Researching West Virginia education news across the state…"
        _run_status.last_error = ""
        run_ok = False
        started = _run_status.started_at
        try:
            recent = (
                await db.briefings.find({"date": {"$lt": date_str}, "status": "complete"})
                .sort("date", -1)
                .to_list(4)
            )
            submissions = (
                await db.submissions.find({"status": "new"}, {"_id": 0, "url": 1, "name": 1})
                .sort("submitted_at", -1)
                .to_list(50)
            )
            data = await _call_model(date_str, recent, submissions)

            stories: List[Story] = []
            for raw in data.get("stories") or []:
                if not isinstance(raw, dict):
                    continue
                raw.pop("id", None)
                cls = raw.get("classification")
                if isinstance(cls, str):
                    raw["classification"] = [cls]
                try:
                    stories.append(Story(**raw))
                except Exception as exc:
                    logger.warning("skipping malformed story: %s", exc)

            # Fold grounding citations into the source log so every edition has verified links,
            # even when the model's own JSON sources are thin.
            source_log = list(data.get("source_log") or [])
            have = {(s or {}).get("url") for s in source_log if isinstance(s, dict)}
            for c in data.get("_citations") or []:
                if c["url"] not in have:
                    source_log.append(SourceLink(url=c["url"], outlet=c.get("title", "")).model_dump())
                    have.add(c["url"])

            briefing = Briefing(
                date=date_str,
                model=f"{MODEL_PROVIDER}/{MODEL_NAME}",
                editor_note=str(data.get("editor_note") or ""),
                stories=stories,
                trends=data.get("trends") or [],
                podcast_ideas=data.get("podcast_ideas") or [],
                source_log=source_log,
            )
            _run_status.message = "Verifying and resolving source links…"
            await _resolve_sources(briefing)
            previous = await db.briefings.find_one({"date": date_str})
            _merge_workspace(briefing, previous)
            await db.briefings.replace_one(
                {"date": date_str}, briefing.model_dump(), upsert=True
            )
            _run_status.message = f"Briefing for {date_str} published ({len(stories)} stories)."
            run_ok = True
            try:
                await link_submissions_used(
                    [src.url for s in stories for src in (s.sources or [])],
                    label=f"Daily briefing {date_str}",
                    ref=f"/briefings/{date_str}",
                )
            except Exception:
                logger.exception("linking used submissions failed (non-fatal)")
            await _send_digest_safe(briefing)
            return briefing
        except Exception as exc:
            logger.exception("briefing run failed")
            _run_status.last_error = "Run failed — see server logs."
            _run_status.message = "Run failed — see server logs."
            raise
        finally:
            _run_status.running = False
            _run_status.finished_at = datetime.now(timezone.utc)
            await record_run(
                kind="daily", trigger=trigger,
                status="complete" if run_ok else "failed",
                label=date_str,
                detail=_run_status.message if run_ok else _run_status.last_error,
                started_at=started,
            )


async def _send_digest_safe(briefing: Briefing) -> None:
    """Email the digest to configured recipients after a run — never fail the run on this."""
    try:
        from lib import email_digest

        cfg = await db.desk_config.find_one({"key": "singleton"}, {"_id": 0})
        recipients = (cfg or {}).get("recipients") or []
        sub_count = await db.subscribers.count_documents({"active": True})
        if recipients or sub_count:
            _run_status.message = "Emailing the digest to recipients and subscribers…"
            res = await email_digest.send_digest(briefing, recipients)
            logger.info(
                "digest sent — admins %d/%d, subscribers %d/%d",
                res.admin_sent, res.admin_sent + res.admin_failed,
                res.sub_sent, res.sub_sent + res.sub_failed,
            )
    except Exception:
        logger.exception("digest email step failed (non-fatal)")


async def _maybe_run_daily() -> None:
    if _run_status.running:
        return
    s = await load_schedule()
    now = datetime.now(_safe_zone(s["timezone"]))
    date_str = now.strftime("%Y-%m-%d")
    if (now.hour * 60 + now.minute) < (s["daily_hour"] * 60 + s["daily_minute"]):
        return
    if await db.briefings.find_one({"date": date_str, "status": "complete"}):
        return
    logger.info("scheduler: generating briefing for %s", date_str)
    await run_briefing(date_str, trigger="scheduled")


async def scheduler_loop() -> None:
    """Fire the daily edition at 10:00 PM Eastern if that date has no briefing yet."""
    while True:
        try:
            await _maybe_run_daily()
        except Exception:
            logger.exception("scheduler loop error")
            await asyncio.sleep(1800)  # back off after a failure
        await asyncio.sleep(300)
