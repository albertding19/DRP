"""Custom Django email backend that talks to Resend's HTTP API.

We tried Resend's SMTP endpoint first (smtp.resend.com:587 with the API
key as the password) because Django's stdlib `smtp.EmailBackend` "just
works" — but Render's free tier consistently times out on TCP handshake
to that endpoint. Egress to port 443 (HTTPS) is universally allowed, so
this backend POSTs to https://api.resend.com/emails instead.

The exposed API matches Django's email backend contract: the rest of
the codebase keeps calling `django.core.mail.send_mail(...)` and doesn't
know which transport is underneath.
"""

from __future__ import annotations

import logging

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

_API_URL = "https://api.resend.com/emails"
_TIMEOUT_S = 10


class ResendHTTPEmailBackend(BaseEmailBackend):
    """Send mail by POSTing to https://api.resend.com/emails.

    Honors `fail_silently` like every other Django backend — if it's
    False (the default), network errors propagate so the view can surface
    a "something went wrong" message; if True, we swallow and log.
    """

    def send_messages(self, email_messages) -> int:
        if not email_messages:
            return 0
        api_key = settings.RESEND_API_KEY
        if not api_key:
            if not self.fail_silently:
                raise RuntimeError("RESEND_API_KEY is empty")
            logger.error("Resend API key missing; skipping %d messages", len(email_messages))
            return 0

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        sent = 0
        for msg in email_messages:
            payload = {
                "from": msg.from_email,
                "to": list(msg.to),
                "subject": msg.subject,
                "text": msg.body,
            }
            # Pull the first text/html alternative if Django produced one
            # (send_mail with html_message= attaches it as an alternative).
            for content, mime in getattr(msg, "alternatives", []):
                if mime == "text/html":
                    payload["html"] = content
                    break
            if msg.cc:
                payload["cc"] = list(msg.cc)
            if msg.bcc:
                payload["bcc"] = list(msg.bcc)
            try:
                resp = requests.post(_API_URL, json=payload, headers=headers, timeout=_TIMEOUT_S)
            except Exception as exc:
                if not self.fail_silently:
                    raise
                logger.exception("Resend HTTP send failed: %s", exc)
                continue
            if resp.status_code >= 400:
                # Resend's response body says WHY (sandbox-recipient
                # restriction, unverified domain, bad from address — all
                # arrive as 403). A bare raise_for_status() only carries
                # the status code, which made these undiagnosable from
                # the logs.
                detail = (
                    f"Resend API {resp.status_code} sending from {msg.from_email!r}: "
                    + (resp.text or "")[:500]
                )
                if not self.fail_silently:
                    raise RuntimeError(detail)
                logger.error(detail)
                continue
            sent += 1
        return sent
