"""Source packet: the real articles the weekly script is allowed to rely on.

Why this exists: Gemini's Google Search grounding returns real citations in response metadata, but
the model's own JSON output has no access to them, so any URL it types into "sources" is written
from memory and is frequently fabricated (hence "Unverified"). It also only sees search snippets,
which is how details like deadlines get misread.

The fix is to (1) take citations from the grounding metadata, (2) resolve and fetch each article,
(3) hand the writer numbered sources with their published date and actual text, and (4) let the
writer cite sources only by ID, so every link in the output is one we fetched.
"""

import asyncio
import json
import logging
import re
import urllib.parse
from typing import Any, Dict, List, Optional

from lib import desk

logger = logging.getLogger(__name__)

MAX_SOURCES = 30
MAX_TEXT_CHARS = 6000
_URL_RE = re.compile(r"https?://[^\s\"'<>)\]]+")
_BLOCKED_BUT_REAL = {401, 403, 429, 999}


def _clean_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header|form)[^>]*>.*?</\1>", " ", html or "")
    text = re.sub(r"<[^>]+>", " ", html)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
        .replace("&#39;", "'").replace("&rsquo;", "’").replace("&lsquo;", "‘")
    )
    return re.sub(r"\s+", " ", text).strip()


def _meta(html: str, *names: str) -> str:
    for n in names:
        m = re.search(
            rf'(?is)<meta[^>]+(?:property|name|itemprop)=["\']{re.escape(n)}["\'][^>]*content=["\']([^"\']+)["\']',
            html or "",
        ) or re.search(
            rf'(?is)<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name|itemprop)=["\']{re.escape(n)}["\']',
            html or "",
        )
        if m:
            return m.group(1).strip()
    return ""


def _published(html: str) -> str:
    val = _meta(html, "article:published_time", "og:article:published_time", "datePublished", "date", "pubdate")
    if not val:
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html or "")
        val = m.group(1) if m else ""
    return val[:10] if re.match(r"\d{4}-\d{2}-\d{2}", val or "") else val[:40]


def _title(html: str, fallback: str) -> str:
    t = _meta(html, "og:title")
    if not t:
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
        t = _clean_text(m.group(1)) if m else ""
    return (t or fallback)[:200]


def urls_in_text(text: str) -> List[str]:
    return [u.rstrip(".,;") for u in _URL_RE.findall(text or "")]


async def _build_one(client, cache, cite: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw = (cite.get("url") or "").strip()
    if not raw:
        return None
    grounded = bool(cite.get("grounded", True))
    url = await desk._resolve_one(client, raw, {}) if grounded else raw
    if not desk._is_valid_source_url(url):
        return None
    host = urllib.parse.urlparse(url).hostname or ""
    if not host or desk._is_private_host(host):
        return None
    status, final, body = await desk._fetch_page(client, url, cache)
    fetched = 0 < status < 400 and desk._looks_like_article(url, final, body)
    blocked = status in _BLOCKED_BUT_REAL
    if not fetched and not (grounded and blocked) and not (grounded and raw != url):
        # Not reachable and not a trusted grounding citation: do not offer it to the writer.
        return None
    final = final if fetched else url
    text = _clean_text(body)[:MAX_TEXT_CHARS] if fetched else ""
    hint = cite.get("title") or ""
    return {
        "url": final,
        "title": _title(body, hint) if fetched else (hint or desk._domain(final)),
        "outlet": desk._domain(final),
        "published": _published(body) if fetched else "",
        "text": text,
        "fetched": fetched,
        "grounded": grounded,
    }


async def build_packet(
    citations: List[Dict[str, Any]],
    existing: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Resolve + fetch citations into numbered sources. `existing` entries keep their IDs; new
    unique URLs are appended with the next free ID. Returns the merged list."""
    import httpx

    packet = [dict(p) for p in (existing or [])]
    seen = {desk._norm_url(p["url"]) for p in packet}
    todo: List[Dict[str, Any]] = []
    for c in citations or []:
        n = desk._norm_url(c.get("url") or "")
        if n and n not in seen and len(packet) + len(todo) < MAX_SOURCES:
            seen.add(n)  # raw-URL dedupe; resolved duplicates are removed below
            todo.append(c)
    if not todo:
        return packet

    cache: Dict[str, tuple] = {}
    sem = asyncio.Semaphore(6)
    async with httpx.AsyncClient(
        follow_redirects=True,
        max_redirects=5,
        timeout=10.0,
        headers={"User-Agent": "Mozilla/5.0 (WV-Desk)"},
    ) as client:
        async def run(c):
            async with sem:
                try:
                    return await _build_one(client, cache, c)
                except Exception:
                    logger.exception("source packet: failed building %s", c.get("url"))
                    return None

        results = await asyncio.gather(*(run(c) for c in todo))

    have = {desk._norm_url(p["url"]) for p in packet}
    next_id = 1 + max([int(p["id"][1:]) for p in packet if str(p.get("id", "")).startswith("S")] or [0])
    for r in results:
        if not r:
            continue
        n = desk._norm_url(r["url"])
        if n in have:
            continue
        have.add(n)
        r["id"] = f"S{next_id}"
        next_id += 1
        packet.append(r)
    return packet


def render_for_prompt(packet: List[Dict[str, Any]]) -> str:
    """Numbered source blocks for the writer. Text is real article text, not a search snippet."""
    if not packet:
        return "(no source articles are available; make only the edits the feedback requires and do not add new factual claims)"
    blocks = []
    for p in packet:
        head = f"[{p['id']}] {p.get('title','')} — {p.get('outlet','')} — published: {p.get('published') or 'date not found'}"
        body = p.get("text") or "(article text could not be retrieved; do not state specifics from this source)"
        blocks.append(f"{head}\nURL: {p['url']}\n{body}")
    return "\n\n---\n\n".join(blocks)


def to_links(packet: List[Dict[str, Any]], ids: List[str]) -> List[Dict[str, Any]]:
    """SourceLink-shaped dicts for the given source IDs (unknown IDs are dropped)."""
    by_id = {p["id"]: p for p in packet}
    out, seen = [], set()
    for i in ids:
        p = by_id.get(str(i).strip().strip("[]"))
        if not p or p["id"] in seen:
            continue
        seen.add(p["id"])
        out.append(
            {
                "url": p["url"],
                "title": p.get("title", ""),
                "outlet": p.get("outlet", ""),
                "verified": bool(p.get("fetched")) or bool(p.get("grounded")),
                "grounded": bool(p.get("grounded")),
            }
        )
    return out


def parse_ids(value: Any) -> List[str]:
    """Accept ["S1","S2"], [{"id":"S1"}], or "S1, S2" from the model."""
    if isinstance(value, str):
        return re.findall(r"S\d+", value)
    ids: List[str] = []
    for v in value or []:
        if isinstance(v, dict):
            v = v.get("id", "")
        ids.extend(re.findall(r"S\d+", str(v)))
    return ids


def dumps_compact(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)
