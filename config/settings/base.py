"""Shared Django settings.

Environment-specific overrides live in:
- `dev.py`   (DEBUG, console email, dev middleware)
- `test.py`  (InMemoryChannelLayer, fast hashers)
- `prod.py`  (security headers, WhiteNoise, ALLOWED_HOSTS from env)

Values read from environment via django-environ.
"""

from __future__ import annotations

from pathlib import Path

import environ

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
# Read .env if present (no-op on Render where env is injected)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="insecure-default-only-for-dev")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
# `daphne` MUST come first so Django's runserver delegates to it for WS support.
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "channels",
    "django_htmx",
    # Local apps (order matters for migrations)
    "apps.core",
    "apps.accounts",
    "apps.posts",
    "apps.comments",
    "apps.votes",
    "apps.tags",
    "apps.search",
    "apps.realtime",
    "apps.moderation",
    "apps.body_double",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    # Custom: prevents browsers caching HTML so deploy-window 404s don't persist.
    # Must come BEFORE EnsureNicknameMiddleware so it catches the redirect responses
    # too (otherwise the cache header is skipped when EnsureNickname short-circuits).
    "apps.core.middleware.NoCacheHTMLMiddleware",
    # Custom: redirects to /accounts/start/ when no nickname session
    "apps.core.middleware.EnsureNicknameMiddleware",
]

ROOT_URLCONF = "config.urls"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.build_info",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": env.db_url("DATABASE_URL"),
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.NicknameSessionBackend",
]

# No passwords used in MVP, but Django requires this setting present.
AUTH_PASSWORD_VALIDATORS: list[dict] = []

# Session lasts 30 days; renewed on every request
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_SAVE_EVERY_REQUEST = True

LOGIN_URL = "/accounts/start/"

# ---------------------------------------------------------------------------
# Channels / ASGI
# ---------------------------------------------------------------------------
ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL", default="redis://localhost:6379/0")],
            "capacity": 1500,
            "expiry": 10,
        },
    },
}

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files (WhiteNoise in prod, runserver dev-mode otherwise)
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"  # collectstatic target
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Build info (set in prod by Render)
RENDER_GIT_COMMIT = env("RENDER_GIT_COMMIT", default="dev")

# ---------------------------------------------------------------------------
# Content moderation
# ---------------------------------------------------------------------------
# Anthropic API key for L2 (Claude Haiku) judge in apps.moderation.services.
# When empty, judge_with_claude short-circuits to (False, "") — content
# passes L2 unchecked, L1 still blocks the obvious, L3 catches the rest.
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")

# Model ID. Pinned to the codebase convention from CLAUDE.md.
MODERATION_CLAUDE_MODEL = env("MODERATION_CLAUDE_MODEL", default="claude-haiku-4-5-20251001")

# Hard timeout in seconds for the Claude API call before we give up and
# pass the content through.
MODERATION_CLAUDE_TIMEOUT_S = env.float("MODERATION_CLAUDE_TIMEOUT_S", default=3.0)

# ---------------------------------------------------------------------------
# Body-double matchmaking
# ---------------------------------------------------------------------------
# Pluggable matching strategy. The default is first-in-first-out pairing.
# Future variants (tag-filtered, blocklist-aware, Pomodoro-length) implement
# `apps.body_double.matching.base.MatchingStrategy` and are selected by
# setting this env var to a different dotted path.
BODY_DOUBLE_MATCHING_STRATEGY = env(
    "BODY_DOUBLE_MATCHING_STRATEGY",
    default="apps.body_double.matching.fifo.FIFOStrategy",
)

# Pluggable video provider. Same shape as the matching strategy.
BODY_DOUBLE_VIDEO_PROVIDER = env(
    "BODY_DOUBLE_VIDEO_PROVIDER",
    default="apps.body_double.video.livekit.LiveKitProvider",
)

# How long an unmatched ticket stays in the pool before a periodic cleanup
# (M3 work) expires it. Configurable so M3/M4 iteration can tune without
# redeploys.
BODY_DOUBLE_WAIT_TIMEOUT_S = env.int("BODY_DOUBLE_WAIT_TIMEOUT_S", default=300)

# LiveKit Cloud credentials. The three values are obtained from
# cloud.livekit.io after creating a project. Empty defaults mean local
# dev can run without live video — token issuance will raise on first
# match, surfaced as a service error in the UI.
LIVEKIT_API_KEY = env("LIVEKIT_API_KEY", default="")
LIVEKIT_API_SECRET = env("LIVEKIT_API_SECRET", default="")
LIVEKIT_URL = env("LIVEKIT_URL", default="")
