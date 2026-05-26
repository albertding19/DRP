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

# CSRF trusted origins (Render injects its own URL via env)
_render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
if _render_url:
    CSRF_TRUSTED_ORIGINS = [_render_url]
