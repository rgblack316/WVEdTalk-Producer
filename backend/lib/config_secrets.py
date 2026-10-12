"""Integration credential store for the self-hosted edition.

All third-party credentials (AI provider + key + model, Resend, SMTP fallback, Turnstile) and the
runs/digests enable flags live in the `desk_config` singleton under the `integrations` key. Secrets
are encrypted at rest with a key derived from SESSION_SECRET, so a database copy alone never exposes
live keys. Resolution precedence at call time: DB value (set in Settings) wins; otherwise the
matching environment variable is used as an initial fallback.
"""

import base64
import hashlib
import os
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from lib.db import db

_KEY = {"key": "singleton"}


def _fernet() -> Fernet:
    secret = os.environ.get("SESSION_SECRET", "")
    digest = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def enc(value: str) -> str:
    return _fernet().encrypt((value or "").encode()).decode() if value else ""


def dec(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        return ""


def mask(value: str) -> str:
    """A safe, non-reversible indicator for the UI: whether a secret is set + its last 4 chars."""
    if not value:
        return ""
    tail = value[-4:] if len(value) >= 4 else value
    return f"••••{tail}"


async def _integrations() -> Dict[str, Any]:
    doc = await db.desk_config.find_one(_KEY, {"_id": 0, "integrations": 1}) or {}
    return doc.get("integrations") or {}


async def save_integrations(patch: Dict[str, Any]) -> None:
    """Merge a partial update into desk_config.integrations (dotted $set on the sub-document)."""
    sets = {f"integrations.{k}": v for k, v in patch.items()}
    await db.desk_config.update_one(_KEY, {"$set": sets}, upsert=True)


def _default_model(provider: str) -> str:
    return "gemini-3.1-pro-preview" if provider == "gemini" else "gpt-4o-search-preview"


async def get_llm_config() -> Dict[str, str]:
    ic = await _integrations()
    provider = (ic.get("llm_provider") or os.environ.get("LLM_PROVIDER") or "gemini").strip()
    model = (ic.get("llm_model") or os.environ.get("LLM_MODEL") or _default_model(provider)).strip()
    if provider == "openai":
        key = dec(ic.get("openai_api_key", "")) or os.environ.get("OPENAI_API_KEY", "")
    else:
        key = dec(ic.get("gemini_api_key", "")) or os.environ.get("GEMINI_API_KEY", "")
    return {"provider": provider, "model": model, "api_key": key}


async def get_email_config() -> Dict[str, Any]:
    ic = await _integrations()
    return {
        "provider": (ic.get("email_provider") or os.environ.get("EMAIL_PROVIDER") or "resend").strip(),
        "from_email": ic.get("email_from") or os.environ.get("EMAIL_FROM", ""),
        "from_name": ic.get("email_from_name") or os.environ.get("EMAIL_FROM_NAME", "WV Education News Desk"),
        "reply_to": ic.get("email_reply_to") or os.environ.get("EMAIL_REPLY_TO", ""),
        "resend_api_key": dec(ic.get("resend_api_key", "")) or os.environ.get("RESEND_API_KEY", ""),
        "smtp_host": ic.get("smtp_host") or os.environ.get("SMTP_HOST", ""),
        "smtp_port": int(ic.get("smtp_port") or os.environ.get("SMTP_PORT") or 587),
        "smtp_username": ic.get("smtp_username") or os.environ.get("SMTP_USERNAME", ""),
        "smtp_password": dec(ic.get("smtp_password", "")) or os.environ.get("SMTP_PASSWORD", ""),
        "smtp_starttls": bool(ic.get("smtp_starttls", str(os.environ.get("SMTP_STARTTLS", "true")).lower() == "true")),
    }


async def get_turnstile_config() -> Dict[str, str]:
    ic = await _integrations()
    return {
        "site_key": ic.get("turnstile_site_key") or os.environ.get("TURNSTILE_SITE_KEY", ""),
        "secret_key": dec(ic.get("turnstile_secret_key", "")) or os.environ.get("TURNSTILE_SECRET_KEY", ""),
    }


async def runs_enabled() -> bool:
    """Scheduled research runs — OFF until an operator turns them on (fresh-install safe default)."""
    ic = await _integrations()
    return bool(ic.get("runs_enabled", False))


async def digests_enabled() -> bool:
    """Email digests after a run — OFF until an operator turns them on."""
    ic = await _integrations()
    return bool(ic.get("digests_enabled", False))


async def public_masked() -> Dict[str, Any]:
    """The Settings → Integrations view model: non-secret values verbatim, secrets masked."""
    ic = await _integrations()
    llm = await get_llm_config()
    email = await get_email_config()
    return {
        "llm_provider": llm["provider"],
        "llm_model": llm["model"],
        "gemini_api_key_set": bool(dec(ic.get("gemini_api_key", "")) or os.environ.get("GEMINI_API_KEY", "")),
        "openai_api_key_set": bool(dec(ic.get("openai_api_key", "")) or os.environ.get("OPENAI_API_KEY", "")),
        "gemini_api_key_mask": mask(dec(ic.get("gemini_api_key", ""))),
        "openai_api_key_mask": mask(dec(ic.get("openai_api_key", ""))),
        "email_provider": email["provider"],
        "email_from": email["from_email"],
        "email_from_name": email["from_name"],
        "email_reply_to": email["reply_to"],
        "resend_api_key_set": bool(email["resend_api_key"]),
        "resend_api_key_mask": mask(dec(ic.get("resend_api_key", ""))),
        "smtp_host": email["smtp_host"],
        "smtp_port": email["smtp_port"],
        "smtp_username": email["smtp_username"],
        "smtp_password_set": bool(email["smtp_password"]),
        "smtp_starttls": email["smtp_starttls"],
        "turnstile_site_key": ic.get("turnstile_site_key") or os.environ.get("TURNSTILE_SITE_KEY", ""),
        "turnstile_secret_key_set": bool(dec(ic.get("turnstile_secret_key", "")) or os.environ.get("TURNSTILE_SECRET_KEY", "")),
        "runs_enabled": bool(ic.get("runs_enabled", False)),
        "digests_enabled": bool(ic.get("digests_enabled", False)),
    }
