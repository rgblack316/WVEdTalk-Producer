"""Public-site publishing helpers.

Turns a stored briefing document into the sanitized shape that is published on the public website
(wvedtalk.com/daily). Public content is **stories, sources and trends only**. These are never
published: importance / podcast-potential scores, podcast angles and questions, the Podcast
Opportunities section, and the host's private workspace fields (notes, candidate / excluded /
positive flags). Source links the desk could not verify are left out.

Pure functions (no database access) so they are trivially unit-testable.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


def _text(v: Any) -> str:
    return v if isinstance(v, str) else ("" if v is None else str(v))


def _str_list(v: Any) -> List[str]:
    return [_text(x) for x in v] if isinstance(v, list) else []


def _iso(v: Any) -> str:
    if isinstance(v, datetime):
        return v.isoformat()
    return _text(v)


def public_sources(items: Any) -> List[Dict[str, str]]:
    """Keep only http(s) links that were not flagged unverified; expose title/url/outlet only."""
    out: List[Dict[str, str]] = []
    for s in items or []:
        if not isinstance(s, dict):
            continue
        url = _text(s.get("url")).strip()
        if not url.lower().startswith(("http://", "https://")):
            continue
        if s.get("verified") is False:
            continue
        out.append({"title": _text(s.get("title")), "url": url, "outlet": _text(s.get("outlet"))})
    return out


def public_story(s: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": _text(s.get("id")),
        "section": _text(s.get("section")) or "other",
        "rank": s.get("rank") if isinstance(s.get("rank"), int) else None,
        "headline": _text(s.get("headline")),
        "location": _text(s.get("location")),
        "classification": _str_list(s.get("classification")),
        "what_happened": _text(s.get("what_happened")),
        "why_it_matters": _text(s.get("why_it_matters")),
        "original_date": _text(s.get("original_date")),
        "what_is_new": _text(s.get("what_is_new")),
        "previously_known": _text(s.get("previously_known")),
        "unresolved": _text(s.get("unresolved")),
        "watch_next": _text(s.get("watch_next")),
        "sources": public_sources(s.get("sources")),
    }


def public_trend(t: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": _text(t.get("title")),
        "why_it_matters": _text(t.get("why_it_matters")),
        "evidence": _str_list(t.get("evidence")),
        "missing_evidence": _str_list(t.get("missing_evidence")),
        "watch_next": _text(t.get("watch_next")),
    }


def public_briefing(doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Sanitized public view of one briefing document, or None if it should not be published
    (failed / incomplete runs)."""
    if not isinstance(doc, dict) or doc.get("status", "complete") != "complete":
        return None
    date = _text(doc.get("date"))
    if not date:
        return None
    return {
        "date": date,
        "generated_at": _iso(doc.get("generated_at")),
        "editor_note": _text(doc.get("editor_note")),
        "stories": [public_story(s) for s in (doc.get("stories") or []) if isinstance(s, dict)],
        "trends": [public_trend(t) for t in (doc.get("trends") or []) if isinstance(t, dict)],
        "source_log": public_sources(doc.get("source_log")),
    }
