"""Direct LLM provider layer for the self-hosted edition — no Emergent dependency.

Supports two providers, selected in Settings → Integrations:
  * Gemini (default) via the `google-genai` SDK with the Google Search grounding tool.
  * OpenAI via the Responses API with the hosted `web_search` tool.

`generate()` returns {"content": str, "citations": [{"url","title"}], "model": "provider/model"}.
Citations feed the existing "Grounded" badge + source-link verification; if a provider returns
none, links simply fall back to the normal verified/unverified treatment (nothing breaks).
"""

import logging
from typing import Any, Dict, List, Optional

from lib import config_secrets

logger = logging.getLogger(__name__)


async def generate(*, system: str, user: str, grounded: bool = True) -> Dict[str, Any]:
    cfg = await config_secrets.get_llm_config()
    provider, model, api_key = cfg["provider"], cfg["model"], cfg["api_key"]
    if not api_key:
        raise RuntimeError(
            "No AI provider API key is configured. Add it in Settings → Integrations before running research."
        )
    if provider == "openai":
        result = await _openai(system, user, grounded, model, api_key)
    else:
        result = await _gemini(system, user, grounded, model, api_key)
    result["model"] = f"{provider}/{model}"
    return result


async def _gemini(system: str, user: str, grounded: bool, model: str, api_key: str) -> Dict[str, Any]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    tools = [types.Tool(google_search=types.GoogleSearch())] if grounded else None
    config = types.GenerateContentConfig(system_instruction=system, tools=tools)
    resp = await client.aio.models.generate_content(model=model, contents=user, config=config)
    return {"content": resp.text or "", "citations": _gemini_citations(resp)}


def _gemini_citations(resp) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    try:
        for cand in getattr(resp, "candidates", None) or []:
            gm = getattr(cand, "grounding_metadata", None)
            for ch in (getattr(gm, "grounding_chunks", None) or []):
                web = getattr(ch, "web", None)
                uri = getattr(web, "uri", None) if web else None
                if uri:
                    out.append({"url": uri, "title": (getattr(web, "title", "") or "")})
    except Exception:
        logger.exception("gemini citation extraction failed (non-fatal)")
    return out


async def _openai(system: str, user: str, grounded: bool, model: str, api_key: str) -> Dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)
    kwargs: Dict[str, Any] = {"model": model, "instructions": system, "input": user}
    if grounded:
        kwargs["tools"] = [{"type": "web_search"}]
    resp = await client.responses.create(**kwargs)
    content = getattr(resp, "output_text", "") or ""
    return {"content": content, "citations": _openai_citations(resp)}


def _openai_citations(resp) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    try:
        for item in getattr(resp, "output", None) or []:
            for block in getattr(item, "content", None) or []:
                for ann in getattr(block, "annotations", None) or []:
                    if getattr(ann, "type", "") == "url_citation" and getattr(ann, "url", None):
                        out.append({"url": ann.url, "title": (getattr(ann, "title", "") or "")})
    except Exception:
        logger.exception("openai citation extraction failed (non-fatal)")
    return out


async def test_connection() -> Dict[str, Any]:
    """A tiny live call used by the Settings 'test AI connection' button."""
    try:
        r = await generate(system="You are a connectivity probe.", user="Reply with the single word OK.", grounded=False)
        return {"ok": True, "model": r.get("model", ""), "sample": (r.get("content") or "")[:80]}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}
