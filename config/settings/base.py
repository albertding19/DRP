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

# When set (prod), CanonicalHostMiddleware 301s every other hostname to
# this one — keeps email links on the domain we send from (mail providers
# treat sender/link domain mismatch as a phishing signal). Empty = off.
CANONICAL_HOST = env("CANONICAL_HOST", default="")

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
    "apps.communities",
    "apps.body_double",
    "apps.tasks",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Custom: pins all traffic to CANONICAL_HOST (no-op when unset). Early,
    # so nothing else wastes work on requests that are about to be 301'd.
    "apps.core.middleware.CanonicalHostMiddleware",
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
    # Custom: redirects anonymous requests to /accounts/start/.
    "apps.core.middleware.EnsureAuthMiddleware",
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
# Pluggable matching strategy. Default is the timetable-aware matcher:
# preference matching (chattiness / work_mode / duration) plus a check
# that the candidate's tasks timetable shows enough free time for the
# session (soft — dropped at the last phase; empty timetable = free).
# Alternatives (set the env to one of these dotted paths to swap):
#   apps.body_double.matching.preferences.PreferenceMatchingStrategy
#       — the previous default; preference-aware but timetable-blind.
#   apps.body_double.matching.community.CommunityFallbackStrategy
#       — community-aware but ignores prefs.
#   apps.body_double.matching.fifo.FIFOStrategy
#       — pure first-in-first-out; ignores everything but wait time.
BODY_DOUBLE_MATCHING_STRATEGY = env(
    "BODY_DOUBLE_MATCHING_STRATEGY",
    default="apps.body_double.matching.timetable.TimetableAwareStrategy",
)

# How many oldest-first candidates a phase will test against per-candidate
# Python checks (the timetable fit) before giving up on that phase. Bounds
# the queries a single enqueue can issue inside its transaction.
BODY_DOUBLE_TIMETABLE_CANDIDATE_CAP = env.int("BODY_DOUBLE_TIMETABLE_CANDIDATE_CAP", default=5)

# Phase progression for PreferenceMatchingStrategy. Each is the partner-
# wait threshold at which the matcher will start considering a less-
# good fit. Phase 1 (0s) requires the perfect fit; subsequent phases
# loosen one constraint at a time so a niche-preference user is never
# stranded.
#
#   STRICT_S      (0–N)  — same community + work_mode-compat + ±15min
#   FALLBACK_S    (N–N)  — same community + work_mode-compat + ±30min
#   LOOSE_S       (N–N)  — any community  + work_mode-compat + ±30min
#   (after LOOSE_S)      — any community  + any work_mode    + any duration
# Chattiness compatibility is NEVER loosened — chatty × quiet stays
# blocked at every phase. Vibe mismatch is worse than waiting longer.
BODY_DOUBLE_STRICT_S = env.int("BODY_DOUBLE_STRICT_S", default=30)
BODY_DOUBLE_FALLBACK_S = env.int("BODY_DOUBLE_FALLBACK_S", default=60)
BODY_DOUBLE_LOOSE_S = env.int("BODY_DOUBLE_LOOSE_S", default=120)

# Pluggable video provider. Same shape as the matching strategy.
BODY_DOUBLE_VIDEO_PROVIDER = env(
    "BODY_DOUBLE_VIDEO_PROVIDER",
    default="apps.body_double.video.livekit.LiveKitProvider",
)

# How long an unmatched ticket stays in the pool before a periodic cleanup
# (M3 work) expires it. Configurable so M3/M4 iteration can tune without
# redeploys.
BODY_DOUBLE_WAIT_TIMEOUT_S = env.int("BODY_DOUBLE_WAIT_TIMEOUT_S", default=300)

# --- Scheduled bookings ("match me at 15:00") ---
# Two bookings pair only if their requested windows share at least this
# many minutes (also the smallest duration choice). An open booking whose
# remaining window can't fit this expires lazily.
BODY_DOUBLE_BOOKING_MIN_OVERLAP_MIN = env.int("BODY_DOUBLE_BOOKING_MIN_OVERLAP_MIN", default=15)
# How early before the agreed start the Join button goes live. The first
# joiner creates the room and waits there — the room is the lobby.
BODY_DOUBLE_BOOKING_JOIN_EARLY_S = env.int("BODY_DOUBLE_BOOKING_JOIN_EARLY_S", default=300)
# How far ahead a booking may be placed.
BODY_DOUBLE_BOOKING_HORIZON_DAYS = env.int("BODY_DOUBLE_BOOKING_HORIZON_DAYS", default=14)

# LiveKit Cloud credentials. The three values are obtained from
# cloud.livekit.io after creating a project. Empty defaults mean local
# dev can run without live video — token issuance will raise on first
# match, surfaced as a service error in the UI.
LIVEKIT_API_KEY = env("LIVEKIT_API_KEY", default="")
LIVEKIT_API_SECRET = env("LIVEKIT_API_SECRET", default="")
LIVEKIT_URL = env("LIVEKIT_URL", default="")

# ---------------------------------------------------------------------------
# Tasks → auto-generated daily timetable
# ---------------------------------------------------------------------------
# Working window in local hours. Tasks are only scheduled inside it.
TASKS_WORK_START_HOUR = env.int("TASKS_WORK_START_HOUR", default=9)
TASKS_WORK_END_HOUR = env.int("TASKS_WORK_END_HOUR", default=21)
# Default break length when the user clicks "I need a break".
TASKS_BREAK_MINUTES = env.int("TASKS_BREAK_MINUTES", default=15)
# Gap to insert between back-to-back tasks in the same slot.
TASKS_TRANSITION_MINUTES = env.int("TASKS_TRANSITION_MINUTES", default=5)
# Minimum seconds between two consecutive "I need a break" presses, to
# prevent the user spamming and stacking breaks.
TASKS_BREAK_COOLDOWN_S = env.int("TASKS_BREAK_COOLDOWN_S", default=60)

# ---------------------------------------------------------------------------
# Auth — magic-link email + Google OAuth
# ---------------------------------------------------------------------------
# Resend SMTP credentials. `RESEND_API_KEY` doubles as the SMTP password
# (Resend uses the literal username "resend" + the API key as password).
# When empty, prod sends will fail with SMTPAuthError — the dev/test
# environments use console/locmem backends so the key is only required in
# prod. See config/settings/prod.py for the SMTP backend wiring.
RESEND_API_KEY = env("RESEND_API_KEY", default="")

# The address magic-link emails come from. Must be a domain verified in
# the Resend dashboard: the `onboarding@resend.dev` default is Resend's
# SANDBOX sender, which can ONLY deliver to the Resend account owner's
# own address — sends to anyone else are rejected with a 403 (surfaced to
# the user as "couldn't send the email", logged as EmailDeliveryError).
# That's why login to the owner's mailbox works while claim/email-change
# for other users fails. See README "Email setup" for the domain-
# verification steps.
DEFAULT_FROM_EMAIL = env(
    "DEFAULT_FROM_EMAIL",
    default="unmasked <onboarding@resend.dev>",
)

# Magic-link expiry in minutes. 15 is the industry standard — long enough
# for the user to switch tabs and find the email, short enough that a
# stolen link goes stale before useful exploitation.
SIGNIN_TOKEN_TTL_MIN = env.int("SIGNIN_TOKEN_TTL_MIN", default=15)

# How many magic links a single email address can request per rolling
# hour, and how many a single IP can request. Both are checked at issue
# time, blocking attackers who try to mailbomb someone's inbox AND
# attackers who try many addresses from one machine.
SIGNIN_RATE_LIMIT_PER_HOUR = env.int("SIGNIN_RATE_LIMIT_PER_HOUR", default=5)
SIGNIN_IP_RATE_LIMIT_PER_HOUR = env.int("SIGNIN_IP_RATE_LIMIT_PER_HOUR", default=10)

# Google OAuth — credentials obtained from https://console.cloud.google.com
# (APIs & Services → Credentials → OAuth 2.0 Client ID, Web application).
# Both client ID and secret are empty by default so dev environments can
# run without OAuth wired up; the welcome page hides the Google button
# when the client ID is missing.
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")

# The redirect URI registered with Google. Must match exactly what's
# configured in the Cloud Console "Authorised redirect URIs" list. We
# never compute this from request data — Google rejects mismatches and
# user-controlled redirect URIs are a known OAuth attack surface.
GOOGLE_OAUTH_REDIRECT_URI = env(
    "GOOGLE_OAUTH_REDIRECT_URI",
    default="http://localhost:8000/accounts/oauth/google/callback/",
)
