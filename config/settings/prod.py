"""Production settings — Render free tier."""

import os

from .base import *  # noqa: F401, F403

DEBUG = False

# ALLOWED_HOSTS — Render assigns subdomains we can't predict (e.g. drp-web-5xwh).
# Read RENDER_EXTERNAL_HOSTNAME (auto-injected by Render) and add it to the
# allowed list alongside any values from the env var.
_render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip()
if _render_host and _render_host not in ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = list(ALLOWED_HOSTS) + [_render_host]  # noqa: F405

# Security headers
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
# Render's internal health check hits port 10000 over plain HTTP (it doesn't
# pass through the SSL-terminating edge). Exempt it from the HTTPS redirect
# so the deploy health check actually gets a 200 instead of a 301.
SECURE_REDIRECT_EXEMPT = [r"^healthz$", r"^version$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# CSRF trusted origins: the Render-injected URL plus every env-provided
# host (the custom domain lives in ALLOWED_HOSTS). Without the custom
# domain here, every POST on drp.it.com fails Django's CSRF origin check.
_render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
_csrf_origins = {_render_url} if _render_url else set()
_csrf_origins |= {
    f"https://{h}"
    for h in ALLOWED_HOSTS
    if h not in ("localhost", "127.0.0.1")  # noqa: F405
}
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = sorted(_csrf_origins)

# ---------------------------------------------------------------------------
# Email — Resend HTTP API
# ---------------------------------------------------------------------------
# We originally configured Django's stdlib SMTP backend pointed at
# smtp.resend.com:587 — but Render's free tier consistently times out on
# the TCP handshake to that endpoint (port-587 egress is flaky from their
# network). HTTPS to api.resend.com is universally allowed, so we use a
# small custom backend that POSTs there instead. Same RESEND_API_KEY,
# same deliverability, no SMTP.
EMAIL_BACKEND = "apps.accounts.email_backend.ResendHTTPEmailBackend"
