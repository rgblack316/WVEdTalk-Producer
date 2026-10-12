"""Direct email transport for the self-hosted edition — no Emergent dependency.

Resend (default) with an SMTP fallback. `send()` tries Resend when a Resend key is configured, and
falls back to SMTP when Resend is unset or a Resend send fails and SMTP is configured. Callers
(email_digest.py) keep owning the HTML templates and the G2/G3 safety gate; this module is only the
transport. Returns a provider message id (or a synthetic one) on success, raises on failure.
"""

import logging
from email.message import EmailMessage
from typing import Any, Dict, Optional

import httpx

from lib import config_secrets

logger = logging.getLogger(__name__)


async def _resend(cfg: Dict[str, Any], to: str, subject: str, html: str) -> str:
    sender = f'{cfg["from_name"]} <{cfg["from_email"]}>' if cfg.get("from_name") else cfg["from_email"]
    payload: Dict[str, Any] = {"from": sender, "to": [to], "subject": subject, "html": html}
    if cfg.get("reply_to"):
        payload["reply_to"] = cfg["reply_to"]
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f'Bearer {cfg["resend_api_key"]}', "Content-Type": "application/json"},
            json=payload,
        )
    resp.raise_for_status()
    return (resp.json() or {}).get("id", "resend")


async def _smtp(cfg: Dict[str, Any], to: str, subject: str, html: str) -> str:
    import aiosmtplib

    msg = EmailMessage()
    msg["From"] = f'{cfg["from_name"]} <{cfg["from_email"]}>' if cfg.get("from_name") else cfg["from_email"]
    msg["To"] = to
    msg["Subject"] = subject
    if cfg.get("reply_to"):
        msg["Reply-To"] = cfg["reply_to"]
    msg.set_content("This message requires an HTML-capable email client.")
    msg.add_alternative(html, subtype="html")
    await aiosmtplib.send(
        msg,
        hostname=cfg["smtp_host"],
        port=cfg["smtp_port"],
        username=cfg.get("smtp_username") or None,
        password=cfg.get("smtp_password") or None,
        start_tls=bool(cfg.get("smtp_starttls", True)),
    )
    return "smtp"


async def send(*, to: str, subject: str, html: str) -> str:
    cfg = await config_secrets.get_email_config()
    have_resend = bool(cfg.get("resend_api_key"))
    have_smtp = bool(cfg.get("smtp_host"))
    prefer_smtp = cfg.get("provider") == "smtp"

    if have_resend and not prefer_smtp:
        try:
            return await _resend(cfg, to, subject, html)
        except Exception as exc:
            if not have_smtp:
                raise
            logger.warning("Resend send failed (%s) — falling back to SMTP", str(exc)[:160])
    if have_smtp:
        return await _smtp(cfg, to, subject, html)
    if have_resend:  # prefer_smtp was set but no SMTP configured — use Resend anyway
        return await _resend(cfg, to, subject, html)
    raise RuntimeError("No email transport is configured. Add Resend or SMTP in Settings → Integrations.")


async def test_send(to: str, *, provider: Optional[str] = None) -> Dict[str, Any]:
    """Used by the Settings 'send test email (resend|smtp)' buttons."""
    cfg = await config_secrets.get_email_config()
    subject = "WVEdTalk News Desk — test email"
    html = '<p style="font-family:Arial,sans-serif">This is a WVEdTalk News Desk test email. If you received it, delivery works.</p>'
    try:
        if provider == "smtp":
            if not cfg.get("smtp_host"):
                return {"ok": False, "error": "SMTP is not configured."}
            await _smtp(cfg, to, subject, html)
        elif provider == "resend":
            if not cfg.get("resend_api_key"):
                return {"ok": False, "error": "Resend is not configured."}
            await _resend(cfg, to, subject, html)
        else:
            await send(to=to, subject=subject, html=html)
        return {"ok": True}
    except Exception as exc:
        resp = getattr(exc, "response", None)
        if resp is not None:
            try:
                return {"ok": False, "error": f"HTTP {resp.status_code}: {(resp.text or '').strip()[:200]}"}
            except Exception:
                pass
        return {"ok": False, "error": str(exc)[:300]}
