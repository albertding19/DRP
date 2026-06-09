"""Service-layer tests for the sign-in flow.

Covers magic-link issuance + redemption, rate limiting, claim, email
change, Google OAuth completion. Email transport uses the in-memory
locmem backend (configured in `config/settings/test.py`); the `mail.outbox`
attribute holds every send. OAuth is tested by monkeypatching the three
helpers in `apps.accounts.oauth_google` so no network call leaves the
process.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory
from django.utils import timezone

from apps.accounts.models import SignInToken, User
from apps.accounts.services import (
    EmailTakenError,
    OAuthError,
    RateLimitedError,
    SignInTokenExpiredError,
    SignInTokenInvalidError,
    claim_account_with_email,
    delete_account,
    find_or_create_user_for_email,
    google_oauth_complete,
    request_email_change,
    send_signin_link,
    validate_next_url,
    verify_signin_token,
)


@pytest.fixture(autouse=True)
def _clear_cache():
    """Each test starts with empty rate-limit counters."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def rf():
    return RequestFactory()


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _extract_raw_token(message_body: str) -> str:
    """The magic link is the only `?t=…` in the email body."""
    import re

    m = re.search(r"\?t=([A-Za-z0-9_\-]+)", message_body)
    assert m is not None, "no token in email body"
    return m.group(1)


# ---------------------------------------------------------------------------
# send_signin_link
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestSendSignInLink:
    def test_creates_token_row_and_sends_email(self):
        send_signin_link(email="me@example.com")
        assert SignInToken.objects.count() == 1
        token = SignInToken.objects.get()
        assert len(token.token_hash) == 64  # sha256 hex
        assert token.email == "me@example.com"
        assert token.intent == SignInToken.INTENT_LOGIN
        assert token.user is None
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["me@example.com"]

    def test_raw_token_never_appears_in_db(self):
        send_signin_link(email="me@example.com")
        body = mail.outbox[0].body
        raw_token = _extract_raw_token(body)
        # The raw token should be NOWHERE in the DB.
        assert not SignInToken.objects.filter(token_hash=raw_token).exists()
        # But the sha256 of it IS in the DB.
        assert SignInToken.objects.filter(token_hash=_sha256(raw_token)).exists()

    def test_normalises_email(self):
        send_signin_link(email="  Me@Example.COM  ")
        assert SignInToken.objects.get().email == "me@example.com"

    def test_rejects_empty_email(self):
        with pytest.raises(ValueError):
            send_signin_link(email="")


# ---------------------------------------------------------------------------
# verify_signin_token
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestVerifySignInToken:
    def _issue(self, **overrides) -> str:
        send_signin_link(email=overrides.get("email", "me@example.com"))
        return _extract_raw_token(mail.outbox[-1].body)

    def test_round_trip_creates_user(self):
        raw = self._issue()
        user, intent = verify_signin_token(raw)
        assert intent == SignInToken.INTENT_LOGIN
        assert user.email == "me@example.com"
        # Token now marked used.
        assert SignInToken.objects.get().is_used

    def test_unknown_token_rejected(self):
        with pytest.raises(SignInTokenInvalidError):
            verify_signin_token("nope-this-isnt-real")

    def test_expired_token_rejected(self):
        raw = self._issue()
        SignInToken.objects.update(expires_at=timezone.now() - timedelta(minutes=1))
        with pytest.raises(SignInTokenExpiredError):
            verify_signin_token(raw)

    def test_used_token_rejected_on_second_redemption(self):
        raw = self._issue()
        verify_signin_token(raw)
        with pytest.raises(SignInTokenInvalidError):
            verify_signin_token(raw)

    def test_sibling_tokens_invalidated_on_redemption(self):
        # Issue two LOGIN tokens for the same email; redeem the first;
        # the second should be marked used (sibling invalidation).
        send_signin_link(email="me@example.com")
        send_signin_link(email="me@example.com")
        raw_first = _extract_raw_token(mail.outbox[0].body)
        raw_second = _extract_raw_token(mail.outbox[1].body)
        verify_signin_token(raw_first)
        # Look up the second by hash and assert it's now used too.
        second = SignInToken.objects.get(token_hash=_sha256(raw_second))
        assert second.is_used


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestRateLimiting:
    def test_email_quota_blocks_after_limit(self, settings):
        settings.SIGNIN_RATE_LIMIT_PER_HOUR = 3
        for _ in range(3):
            send_signin_link(email="me@example.com")
        with pytest.raises(RateLimitedError) as exc:
            send_signin_link(email="me@example.com")
        assert exc.value.scope == "email"

    def test_ip_quota_blocks_after_limit(self, settings):
        settings.SIGNIN_RATE_LIMIT_PER_HOUR = 100  # don't trip email limit
        settings.SIGNIN_IP_RATE_LIMIT_PER_HOUR = 2
        send_signin_link(email="a@example.com", ip_address="1.2.3.4")
        send_signin_link(email="b@example.com", ip_address="1.2.3.4")
        with pytest.raises(RateLimitedError) as exc:
            send_signin_link(email="c@example.com", ip_address="1.2.3.4")
        assert exc.value.scope == "ip"

    def test_different_emails_dont_share_quota(self, settings):
        settings.SIGNIN_RATE_LIMIT_PER_HOUR = 1
        send_signin_link(email="a@example.com")
        send_signin_link(email="b@example.com")  # different email — fine


# ---------------------------------------------------------------------------
# find_or_create_user_for_email
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestFindOrCreateUser:
    def test_creates_new_user_with_placeholder_nickname(self):
        user, created = find_or_create_user_for_email(email="new@example.com")
        assert created is True
        assert user.email == "new@example.com"
        assert user.nickname.startswith("user-")

    def test_returns_existing_on_repeat_call(self):
        a, _ = find_or_create_user_for_email(email="same@example.com")
        b, created = find_or_create_user_for_email(email="same@example.com")
        assert a.pk == b.pk
        assert created is False


# ---------------------------------------------------------------------------
# Claim flow
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestClaim:
    def test_happy_path_attaches_email(self):
        legacy = User.objects.create_anonymous(nickname="legacy")
        assert legacy.email is None
        claim_account_with_email(user=legacy, email="legacy@example.com")
        raw = _extract_raw_token(mail.outbox[0].body)
        user, intent = verify_signin_token(raw)
        assert intent == SignInToken.INTENT_CLAIM
        assert user.pk == legacy.pk
        legacy.refresh_from_db()
        assert legacy.email == "legacy@example.com"

    def test_blocks_at_issue_time_when_email_already_owned(self):
        # Another user has the email; legacy can't claim it.
        User.objects.create_anonymous(nickname="other").email = "taken@example.com"
        other = User.objects.get(nickname="other")
        other.email = "taken@example.com"
        other.save()
        legacy = User.objects.create_anonymous(nickname="legacy")
        with pytest.raises(EmailTakenError):
            claim_account_with_email(user=legacy, email="taken@example.com")
        assert SignInToken.objects.count() == 0
        assert len(mail.outbox) == 0

    def test_blocks_at_redemption_time_too(self):
        # Issue a claim token for legacy → in the meantime another user
        # grabs the email → redemption fails cleanly.
        legacy = User.objects.create_anonymous(nickname="legacy")
        claim_account_with_email(user=legacy, email="contested@example.com")
        raw = _extract_raw_token(mail.outbox[0].body)
        # Simulate the race: another user takes the email.
        other = User.objects.create_anonymous(nickname="other")
        other.email = "contested@example.com"
        other.save()
        with pytest.raises(EmailTakenError):
            verify_signin_token(raw)


# ---------------------------------------------------------------------------
# Email change
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestEmailChange:
    def test_sends_to_new_address_not_old(self):
        user = User.objects.create_anonymous(nickname="alice")
        user.email = "old@example.com"
        user.save()
        request_email_change(user=user, new_email="new@example.com")
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["new@example.com"]

    def test_blocks_when_new_email_owned_by_another(self):
        a = User.objects.create_anonymous(nickname="alice")
        a.email = "alice@example.com"
        a.save()
        b = User.objects.create_anonymous(nickname="bob")
        b.email = "bob@example.com"
        b.save()
        with pytest.raises(EmailTakenError):
            request_email_change(user=a, new_email="bob@example.com")


# ---------------------------------------------------------------------------
# Delete account
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestDeleteAccount:
    def test_hard_deletes_user_row(self):
        user = User.objects.create_anonymous(nickname="goneaway")
        pk = user.pk
        delete_account(user=user)
        assert not User.objects.filter(pk=pk).exists()


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestGoogleOAuth:
    def _mock(self, *, exchange=None, userinfo=None):
        """Return two patches that turn off the two outbound HTTP calls."""
        return (
            patch(
                "apps.accounts.oauth_google.exchange_code",
                return_value=exchange or {"access_token": "fake-token"},
            ),
            patch(
                "apps.accounts.oauth_google.fetch_userinfo",
                return_value=userinfo or {"email": "google@example.com", "email_verified": True},
            ),
        )

    def test_happy_path_creates_new_user(self):
        ex, ui = self._mock()
        with ex, ui:
            user, created = google_oauth_complete(code="abc")
        assert created is True
        assert user.email == "google@example.com"

    def test_happy_path_returns_existing_user(self):
        existing = User.objects.create_anonymous(nickname="returning")
        existing.email = "google@example.com"
        existing.save()
        ex, ui = self._mock()
        with ex, ui:
            user, created = google_oauth_complete(code="abc")
        assert created is False
        assert user.pk == existing.pk

    def test_unverified_email_rejected(self):
        ex, ui = self._mock(userinfo={"email": "g@example.com", "email_verified": False})
        with ex, ui, pytest.raises(OAuthError):
            google_oauth_complete(code="abc")

    def test_missing_email_rejected(self):
        ex, ui = self._mock(userinfo={"email_verified": True})  # no email key
        with ex, ui, pytest.raises(OAuthError):
            google_oauth_complete(code="abc")


# ---------------------------------------------------------------------------
# Open-redirector defense
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestNextUrlValidation:
    def test_relative_path_allowed(self, rf):
        request = rf.get("/")
        assert validate_next_url("/feed/", request=request) == "/feed/"

    def test_external_host_rejected(self, rf):
        request = rf.get("/")
        # Default → "/"
        assert validate_next_url("https://evil.com", request=request) == "/"

    def test_protocol_only_rejected(self, rf):
        request = rf.get("/")
        assert validate_next_url("javascript:alert(1)", request=request) == "/"

    def test_empty_falls_back_to_root(self, rf):
        request = rf.get("/")
        assert validate_next_url(None, request=request) == "/"
        assert validate_next_url("", request=request) == "/"
