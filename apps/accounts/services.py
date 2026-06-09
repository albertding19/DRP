"""Service layer for accounts — magic-link, OAuth, claim, settings.

All public functions here are kwarg-only and use `@transaction.atomic`
where DB consistency matters. Mirror the style in
`apps/communities/services.py`.

Imports of `requests` happen via `apps.accounts.oauth_google`; this
module never makes outbound HTTP calls directly so it stays trivially
mockable in tests.

The redemption transactions deliberately:
  1. SELECT FOR UPDATE the token row
  2. Check `is_used`, `is_expired`
  3. Mark `used_at`
  4. Invalidate sibling tokens for the same (email, intent)
  5. Find-or-create the user
  6. (For claim/email-change) attach the email to the user
all inside one atomic block, so a concurrent click sees one of two
clean outcomes: either it's the winner, or it sees `is_used` already.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from . import oauth_google
from .models import SignInToken, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions — one type per failure mode so view callers can branch cleanly
# ---------------------------------------------------------------------------
class NicknameTaken(Exception):
    """Raised when create_user races with another request for the same nickname."""


class SignInTokenInvalidError(Exception):
    """Token doesn't exist, was tampered with, or has already been used."""


class SignInTokenExpiredError(Exception):
    """Token exists but is past its expiry."""


class RateLimitedError(Exception):
    """Too many tokens requested for this email or from this IP in the last hour."""

    def __init__(self, scope: str):
        self.scope = scope  # "email" or "ip"
        super().__init__(f"Rate limit hit for {scope}")


class EmailTakenError(Exception):
    """That email is already attached to a different user account."""


class OAuthError(Exception):
    """Wrap any non-2xx response from Google OR a state-mismatch on callback."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash_token(raw: str) -> str:
    """SHA-256 the raw token. Stored as 64-char hex in `token_hash`."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalise_email(email: str) -> str:
    """Lowercase + strip. Use everywhere we touch the email column so
    `alice@x` and `Alice@X` resolve to the same User."""
    return (email or "").strip().lower()


def validate_next_url(next_url: str | None, *, request) -> str:
    """Return `next_url` if it's safe to redirect to, else `/`.

    "Safe" means: same host as the request, AND scheme matches
    HTTPS if the request was HTTPS. This is the standard open-redirector
    defense — accepting `?next=https://evil.com` from a magic link would
    be the easiest phishing setup imaginable.
    """
    if not next_url:
        return "/"
    allowed = {request.get_host()}
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts=allowed, require_https=request.is_secure()
    ):
        return next_url
    logger.warning(
        "open-redirector blocked",
        extra={"next_url": next_url[:200], "host": request.get_host()},
    )
    return "/"


# ---------------------------------------------------------------------------
# Rate limiting via Django cache
# ---------------------------------------------------------------------------
_RATE_WINDOW_S = 3600  # 1 hour rolling window


def _under_rate_limit(*, key: str, limit: int) -> bool:
    """Atomic-ish increment of a cache counter. Returns True if the call is
    UNDER the limit (i.e. allow it); False if the limit was already hit.

    Cache keys are sha256-hashed to avoid leaking the underlying value
    (email or IP) into the cache backend's storage, just in case.
    Counter is initialised to 0 with TTL=window on first call; subsequent
    calls within the window incr without resetting TTL.
    """
    # First-call atomic init. `add` only sets if the key is absent.
    cache.add(key, 0, timeout=_RATE_WINDOW_S)
    try:
        value = cache.incr(key)
    except ValueError:
        # Key disappeared between add() and incr() — race with eviction.
        # Treat as a fresh window and allow.
        cache.set(key, 1, timeout=_RATE_WINDOW_S)
        value = 1
    return value <= limit


def _check_rate_limits(*, email: str, ip_address: str | None) -> None:
    """Raise RateLimitedError if either email or IP is over its hourly
    quota. Run this at issue time, NOT redemption — we want to stop
    mailbomb attacks before the email goes out."""
    email_key = "signin_rate:email:" + _hash_token(_normalise_email(email))
    if not _under_rate_limit(key=email_key, limit=settings.SIGNIN_RATE_LIMIT_PER_HOUR):
        raise RateLimitedError("email")
    if ip_address:
        ip_key = "signin_rate:ip:" + _hash_token(ip_address)
        if not _under_rate_limit(key=ip_key, limit=settings.SIGNIN_IP_RATE_LIMIT_PER_HOUR):
            raise RateLimitedError("ip")


# ---------------------------------------------------------------------------
# Legacy nickname signup — kept for the test fixture / admin shell
# ---------------------------------------------------------------------------
def create_user_with_nickname(nickname: str) -> User:
    """Create a User; raises NicknameTaken on race-condition collision.

    Kept around so the `client_with_session` test fixture and admin shell
    can still mint nickname-only users. New end-user signups go through
    `find_or_create_user_for_email` instead.
    """
    try:
        return User.objects.create_anonymous(nickname=nickname)
    except IntegrityError as exc:
        raise NicknameTaken(nickname) from exc


# ---------------------------------------------------------------------------
# Sign-in link — issue + email
# ---------------------------------------------------------------------------
@transaction.atomic
def send_signin_link(
    *,
    email: str,
    intent: str = SignInToken.INTENT_LOGIN,
    user: User | None = None,
    ip_address: str | None = None,
    next_url: str = "/",
    request=None,
) -> SignInToken:
    """Generate a token, store its hash, send the magic-link email.

    Returns the SignInToken row (with `token_hash` populated). The raw
    token is NOT on the returned object — it's already gone, embedded
    only in the email body.

    `next_url` is the post-signin redirect. It's validated through
    `validate_next_url` if `request` is provided so an attacker can't
    smuggle an open-redirector via the email link.
    """
    email = _normalise_email(email)
    if not email:
        raise ValueError("email: required")

    _check_rate_limits(email=email, ip_address=ip_address)

    if request is not None:
        next_url = validate_next_url(next_url, request=request)

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = timezone.now() + timedelta(minutes=settings.SIGNIN_TOKEN_TTL_MIN)

    token = SignInToken.objects.create(
        token_hash=token_hash,
        email=email,
        user=user,
        intent=intent,
        expires_at=expires_at,
    )

    # Build the absolute link URL. We use the request's host if available
    # so dev (localhost), prod (drp-web-5xwh.onrender.com), and any
    # preview environment all "just work" without per-env config.
    if request is not None:
        verify_path = reverse("accounts:verify")
        link = request.build_absolute_uri(f"{verify_path}?t={raw_token}&next={next_url}")
    else:
        link = f"/accounts/verify/?t={raw_token}&next={next_url}"

    ctx = {
        "link": link,
        "ttl_min": settings.SIGNIN_TOKEN_TTL_MIN,
        "intent": intent,
        "PROJECT_NAME": "unmasked",
    }
    subject_by_intent = {
        SignInToken.INTENT_LOGIN: "Your sign-in link for unmasked",
        SignInToken.INTENT_CLAIM: "Confirm your email for unmasked",
        SignInToken.INTENT_EMAIL_CHANGE: "Verify your new email for unmasked",
        SignInToken.INTENT_DELETE_CONFIRM: "Confirm account deletion",
    }
    template_by_intent = {
        SignInToken.INTENT_LOGIN: "accounts/email/signin_link",
        SignInToken.INTENT_CLAIM: "accounts/email/claim_link",
        SignInToken.INTENT_EMAIL_CHANGE: "accounts/email/email_change",
        SignInToken.INTENT_DELETE_CONFIRM: "accounts/email/signin_link",
    }
    template = template_by_intent.get(intent, "accounts/email/signin_link")
    body_txt = render_to_string(f"{template}.txt", ctx)
    try:
        body_html: str | None = render_to_string(f"{template}.html", ctx)
    except Exception:  # template may not exist for every intent — txt is enough
        body_html = None

    send_mail(
        subject=subject_by_intent.get(intent, "Your link for unmasked"),
        message=body_txt,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=body_html,
        fail_silently=False,
    )
    logger.info(
        "signin_token issued",
        extra={"intent": intent, "email": email, "ip": ip_address},
    )
    return token


def _invalidate_sibling_tokens(*, email: str, intent: str, except_pk: int) -> int:
    """Mark all OTHER unused tokens with this (email, intent) as used.

    Defends against the "user requested two links and clicked the older
    one too" footgun: the second link going stale a second after the
    first is redeemed is the desired UX (and a small security win).
    """
    now = timezone.now()
    return (
        SignInToken.objects.filter(email=email, intent=intent, used_at__isnull=True)
        .exclude(pk=except_pk)
        .update(used_at=now)
    )


@transaction.atomic
def verify_signin_token(
    raw_token: str, *, ip_address: str | None = None, user_agent: str = ""
) -> tuple[User, str]:
    """Validate the raw token from the email link. Returns (user, intent).

    For `login` intent: finds or creates a User by email.
    For `claim` / `email_change`: attaches `token.email` to `token.user`.
    For `delete_confirm` (v2): callers handle deletion themselves.

    Raises:
      SignInTokenInvalidError — bad/used token, OR email collision on a
                                claim that tries to attach an email now
                                owned by someone else (TOCTOU defense).
      SignInTokenExpiredError — past expires_at.
    """
    if not raw_token:
        raise SignInTokenInvalidError("missing")
    token_hash = _hash_token(raw_token)

    try:
        token = SignInToken.objects.select_for_update().get(token_hash=token_hash)
    except SignInToken.DoesNotExist as exc:
        raise SignInTokenInvalidError("unknown") from exc

    if token.is_expired:
        raise SignInTokenExpiredError()
    if token.is_used:
        raise SignInTokenInvalidError("used")

    # Mark used INSIDE the transaction so a concurrent click loses cleanly.
    token.used_at = timezone.now()
    token.save(update_fields=["used_at"])
    _invalidate_sibling_tokens(email=token.email, intent=token.intent, except_pk=token.pk)

    if token.intent == SignInToken.INTENT_LOGIN:
        user, _created = find_or_create_user_for_email(email=token.email)
    elif token.intent == SignInToken.INTENT_CLAIM:
        # TOCTOU recheck: between issue time and now, another user may have
        # claimed this email. Refuse rather than overwrite.
        clash = User.objects.exclude(pk=token.user_id).filter(email=token.email).exists()
        if clash:
            raise EmailTakenError(token.email)
        user = User.objects.get(pk=token.user_id)
        user.email = token.email
        user.save(update_fields=["email"])
    elif token.intent == SignInToken.INTENT_EMAIL_CHANGE:
        clash = User.objects.exclude(pk=token.user_id).filter(email=token.email).exists()
        if clash:
            raise EmailTakenError(token.email)
        user = User.objects.get(pk=token.user_id)
        user.email = token.email
        user.save(update_fields=["email"])
    else:
        raise SignInTokenInvalidError(f"unsupported intent: {token.intent}")

    logger.info(
        "signin_token redeemed",
        extra={
            "intent": token.intent,
            "email": token.email,
            "user_id": user.pk,
            "ip": ip_address,
            "ua": user_agent[:120],
        },
    )
    return user, token.intent


def find_or_create_user_for_email(*, email: str, source: str = "magic_link") -> tuple[User, bool]:
    """Look up a User by email. If none exists, create one with a
    placeholder nickname (`user-<5char>`) that the user can change later
    from the settings page.

    Returns (user, created). `source` is logged for analytics so we can
    see which paths produce the most signups.
    """
    email = _normalise_email(email)
    existing = User.objects.filter(email=email).first()
    if existing is not None:
        return existing, False

    # Generate a unique placeholder nickname. Tiny retry loop because
    # collisions are vanishingly rare with 5 chars of token_hex.
    for _ in range(8):
        candidate = f"user-{secrets.token_hex(3)}"  # 6 hex chars after "user-"
        try:
            user = User.objects.create_anonymous(nickname=candidate)
        except IntegrityError:
            continue
        user.email = email
        user.save(update_fields=["email"])
        logger.info(
            "user created",
            extra={"source": source, "email": email, "nickname": candidate},
        )
        return user, True
    raise RuntimeError("could not allocate a unique placeholder nickname after 8 tries")


# ---------------------------------------------------------------------------
# Claim flow — existing nickname-only user adds an email
# ---------------------------------------------------------------------------
def claim_account_with_email(
    *, user: User, email: str, ip_address: str | None = None, request=None
) -> SignInToken:
    """Send a claim-verification email to `email`. On click, the email
    will be attached to `user`. Refuses at issue time if the email is
    already in use (defense-in-depth alongside the TOCTOU recheck on
    redemption)."""
    email = _normalise_email(email)
    if not email:
        raise ValueError("email: required")
    if User.objects.exclude(pk=user.pk).filter(email=email).exists():
        raise EmailTakenError(email)
    return send_signin_link(
        email=email,
        intent=SignInToken.INTENT_CLAIM,
        user=user,
        ip_address=ip_address,
        request=request,
    )


# ---------------------------------------------------------------------------
# Settings flow — change email + change nickname + delete account
# ---------------------------------------------------------------------------
def request_email_change(
    *, user: User, new_email: str, ip_address: str | None = None, request=None
) -> SignInToken:
    """Send a verification email to the NEW address. User's email isn't
    changed until they click the link."""
    new_email = _normalise_email(new_email)
    if not new_email:
        raise ValueError("new_email: required")
    if User.objects.exclude(pk=user.pk).filter(email=new_email).exists():
        raise EmailTakenError(new_email)
    return send_signin_link(
        email=new_email,
        intent=SignInToken.INTENT_EMAIL_CHANGE,
        user=user,
        ip_address=ip_address,
        request=request,
    )


@transaction.atomic
def delete_account(*, user: User) -> None:
    """Hard-delete the user row. FKs do the right thing per model:
    - Posts / Comments / Communities (content) → SET_NULL → orphaned
      rows survive and display as "[deleted]"
    - Tasks / BusyBlocks / Votes / Memberships (personal data) →
      CASCADE → wiped
    - Body-double sessions → SET_NULL (the partner's view shows
      "[deleted]" but the session row survives for the other user)
    """
    user_pk = user.pk
    user.delete()
    logger.info("user deleted", extra={"user_id": user_pk})


# ---------------------------------------------------------------------------
# Google OAuth — thin orchestration around oauth_google.py
# ---------------------------------------------------------------------------
def google_oauth_authorize_url(*, state: str) -> str:
    """Re-exported for view callers — keeps all account-flow imports
    coming from `services.py`."""
    return oauth_google.authorize_url(state=state)


def google_oauth_complete(*, code: str, ip_address: str | None = None) -> tuple[User, bool]:
    """Exchange code → fetch userinfo → assert email_verified → find or
    create the User. Returns (user, created).

    Raises OAuthError on:
      - Google token exchange failure
      - Google userinfo fetch failure
      - email_verified == False (rare but a real account-hijack vector)
    """
    try:
        token_data = oauth_google.exchange_code(code=code)
    except oauth_google.OAuthError as exc:
        raise OAuthError(str(exc)) from exc
    access_token = token_data.get("access_token")
    if not access_token:
        raise OAuthError("Google response missing access_token")

    try:
        userinfo = oauth_google.fetch_userinfo(access_token=access_token)
    except oauth_google.OAuthError as exc:
        raise OAuthError(str(exc)) from exc

    if userinfo.get("email_verified") is not True:
        raise OAuthError("Google says this email isn't verified. Verify it with Google first.")

    email = userinfo.get("email")
    if not email:
        raise OAuthError("Google response missing email")

    user, was_created = find_or_create_user_for_email(email=email, source="google_oauth")
    logger.info(
        "oauth signin complete",
        extra={
            "email": email,
            "user_id": user.pk,
            "was_created": was_created,  # "created" is a reserved LogRecord field
            "ip": ip_address,
        },
    )
    return user, was_created


# Re-export of OAuthError so view-layer callers can `from services import ...`.
__all__ = [
    "NicknameTaken",
    "SignInTokenInvalidError",
    "SignInTokenExpiredError",
    "RateLimitedError",
    "EmailTakenError",
    "OAuthError",
    "create_user_with_nickname",
    "send_signin_link",
    "verify_signin_token",
    "find_or_create_user_for_email",
    "claim_account_with_email",
    "request_email_change",
    "delete_account",
    "google_oauth_authorize_url",
    "google_oauth_complete",
    "validate_next_url",
]
