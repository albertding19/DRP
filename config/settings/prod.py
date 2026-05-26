"""Production settings — Render free tier."""

from .base import *  # noqa: F401, F403

DEBUG = False

# ALLOWED_HOSTS comes from env via django-environ (see base.py)
# Render injects its own hostname, e.g. drp-web.onrender.com

# Security headers
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# CSRF trusted origins (Render injects its own URL via env)
import os  # noqa: E402

_render_url = os.getenv("RENDER_EXTERNAL_URL", "").strip()
if _render_url:
    CSRF_TRUSTED_ORIGINS = [_render_url]
