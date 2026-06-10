"""View-level tests for the magic-link + OAuth + claim + settings flows.

Each test exercises the full request → view → response cycle, including
the in-memory email outbox (locmem backend) and mocked Google OAuth
endpoints. The complementary service-level tests (`test_signin_services`)
cover the same logic at a lower layer; this file ensures the views wire
that logic up correctly to the URL surface and template rendering.
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.cache import cache
from django.test import Client

from apps.accounts.models import SignInToken, User


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _authed_client(email: str | None = None) -> tuple[Client, User]:
    user = User.objects.create_anonymous(nickname=f"u_{User.objects.count() + 1}")
    if email:
        user.email = email
        user.save(update_fields=["email"])
    client = Client()
    s = client.session
    s["user_id"] = user.id
    s.save()
    return client, user


def _extract_raw_token(body: str) -> str:
    m = re.search(r"\?t=([A-Za-z0-9_\-]+)", body)
    assert m is not None
    return m.group(1)


# ---------------------------------------------------------------------------
# Welcome page (already lightly tested in test_views; this focuses on the
# verify flow it kicks off)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestVerifyFlow:
    def test_happy_path_creates_user_and_signs_in(self) -> None:
        client = Client()
        client.post("/accounts/start/", {"email": "first@example.com"})
        raw = _extract_raw_token(mail.outbox[0].body)
        response = client.get(f"/accounts/verify/?t={raw}")
        assert response.status_code == 302
        assert response.url == "/"
        # Session is set, user exists.
        assert client.session.get("user_id")
        assert User.objects.filter(email="first@example.com").exists()

    def test_verify_with_safe_next_redirects_there(self) -> None:
        client = Client()
        client.post("/accounts/start/", {"email": "next@example.com", "next": "/feed/"})
        raw = _extract_raw_token(mail.outbox[0].body)
        response = client.get(f"/accounts/verify/?t={raw}&next=/feed/")
        assert response.status_code == 302
        assert response.url == "/feed/"

    def test_verify_with_external_next_blocked(self) -> None:
        client = Client()
        client.post("/accounts/start/", {"email": "phish@example.com"})
        raw = _extract_raw_token(mail.outbox[0].body)
        response = client.get(f"/accounts/verify/?t={raw}&next=https://evil.com")
        assert response.status_code == 302
        # Must NOT redirect to evil.com.
        assert response.url == "/"
        assert "evil" not in response.url

    def test_verify_missing_token_returns_400(self) -> None:
        response = Client().get("/accounts/verify/")
        assert response.status_code == 400

    def test_verify_unknown_token_returns_400(self) -> None:
        response = Client().get("/accounts/verify/?t=not-a-real-token")
        assert response.status_code == 400

    def test_verify_twice_second_time_400(self) -> None:
        client = Client()
        client.post("/accounts/start/", {"email": "twice@example.com"})
        raw = _extract_raw_token(mail.outbox[0].body)
        client.get(f"/accounts/verify/?t={raw}")  # first
        # Second click on the SAME link, fresh client (no session)
        response = Client().get(f"/accounts/verify/?t={raw}")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Google OAuth — both pieces
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestOAuthGoogle:
    def test_start_unconfigured_returns_400(self, settings) -> None:
        settings.GOOGLE_OAUTH_CLIENT_ID = ""
        settings.GOOGLE_OAUTH_CLIENT_SECRET = ""
        response = Client().get("/accounts/oauth/google/start/")
        assert response.status_code == 400

    def test_start_configured_redirects_to_google(self, settings) -> None:
        settings.GOOGLE_OAUTH_CLIENT_ID = "fake-cid"
        settings.GOOGLE_OAUTH_CLIENT_SECRET = "fake-secret"
        client = Client()
        response = client.get("/accounts/oauth/google/start/")
        assert response.status_code == 302
        assert response.url.startswith("https://accounts.google.com/")
        # state and next stashed in session
        assert "oauth_state" in client.session

    def test_callback_no_state_returns_400(self) -> None:
        response = Client().get("/accounts/oauth/google/callback/?code=abc")
        assert response.status_code == 400

    def test_callback_mismatched_state_returns_400(self) -> None:
        client = Client()
        s = client.session
        s["oauth_state"] = "expected"
        s.save()
        response = client.get("/accounts/oauth/google/callback/?code=abc&state=wrong")
        assert response.status_code == 400

    def test_callback_happy_path_creates_user_and_signs_in(self) -> None:
        client = Client()
        s = client.session
        s["oauth_state"] = "matching"
        s["oauth_next"] = "/feed/"
        s.save()
        with (
            patch(
                "apps.accounts.oauth_google.exchange_code",
                return_value={"access_token": "x"},
            ),
            patch(
                "apps.accounts.oauth_google.fetch_userinfo",
                return_value={
                    "email": "google@example.com",
                    "email_verified": True,
                },
            ),
        ):
            response = client.get("/accounts/oauth/google/callback/?code=abc&state=matching")
        assert response.status_code == 302
        assert response.url == "/feed/"
        assert User.objects.filter(email="google@example.com").exists()

    def test_callback_unverified_email_rejected(self) -> None:
        client = Client()
        s = client.session
        s["oauth_state"] = "m"
        s.save()
        with (
            patch(
                "apps.accounts.oauth_google.exchange_code",
                return_value={"access_token": "x"},
            ),
            patch(
                "apps.accounts.oauth_google.fetch_userinfo",
                return_value={
                    "email": "g@example.com",
                    "email_verified": False,
                },
            ),
        ):
            response = client.get("/accounts/oauth/google/callback/?code=abc&state=m")
        assert response.status_code == 400
        # User NOT created.
        assert not User.objects.filter(email="g@example.com").exists()


# ---------------------------------------------------------------------------
# Claim flow
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestClaimFlow:
    def test_user_with_email_redirected_to_settings(self) -> None:
        client, _ = _authed_client(email="alreadyset@example.com")
        response = client.get("/accounts/claim/")
        assert response.status_code == 302
        assert response.url == "/accounts/settings/"

    def test_user_without_email_sees_form(self) -> None:
        client, _ = _authed_client()
        response = client.get("/accounts/claim/")
        assert response.status_code == 200
        assert b"Add an email" in response.content

    def test_post_sends_link_redirects_to_check_email(self) -> None:
        client, _ = _authed_client()
        response = client.post("/accounts/claim/", {"email": "claim@example.com"})
        assert response.status_code == 302
        assert response.url.startswith("/accounts/check-email/")
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["claim@example.com"]

    def test_claiming_taken_email_re_renders_form(self) -> None:
        # Pre-existing user owns the email.
        owner = User.objects.create_anonymous(nickname="owner")
        owner.email = "taken@example.com"
        owner.save()
        client, _ = _authed_client()
        response = client.post("/accounts/claim/", {"email": "taken@example.com"})
        assert response.status_code == 200
        assert SignInToken.objects.count() == 0


# ---------------------------------------------------------------------------
# Settings page
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestSettings:
    def test_get_renders_for_authed_user(self) -> None:
        client, user = _authed_client(email="me@example.com")
        response = client.get("/accounts/settings/")
        assert response.status_code == 200
        # Email shown.
        assert b"me@example.com" in response.content
        # Nickname shown.
        assert user.nickname.encode() in response.content

    def test_anon_redirected_by_middleware(self) -> None:
        response = Client().get("/accounts/settings/")
        assert response.status_code == 302
        assert response.url.startswith("/accounts/start/")

    def test_nickname_change_updates_immediately(self) -> None:
        client, user = _authed_client(email="me@example.com")
        response = client.post("/accounts/settings/nickname/", {"nickname": "rebranded"})
        assert response.status_code == 302
        user.refresh_from_db()
        assert user.nickname == "rebranded"

    def test_nickname_change_to_taken_nickname_re_renders(self) -> None:
        User.objects.create_anonymous(nickname="taken")
        client, user = _authed_client(email="me@example.com")
        original = user.nickname
        response = client.post("/accounts/settings/nickname/", {"nickname": "taken"})
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.nickname == original

    def test_email_change_sends_to_new_address(self) -> None:
        client, _ = _authed_client(email="old@example.com")
        response = client.post("/accounts/settings/email/", {"email": "new@example.com"})
        assert response.status_code == 302
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["new@example.com"]
        # User's email NOT yet changed (waits for verify click).
        user = User.objects.get(email="old@example.com")
        assert user.email == "old@example.com"

    def test_delete_account_hard_deletes_and_flushes_session(self) -> None:
        client, user = _authed_client(email="bye@example.com")
        pk = user.pk
        response = client.post("/accounts/settings/delete/")
        assert response.status_code == 302
        assert response.url == "/accounts/start/"
        assert not User.objects.filter(pk=pk).exists()
        # Session cleared.
        assert client.session.get("user_id") is None


# ---------------------------------------------------------------------------
# Legacy nickname-only users (regression — they should NOT get bounced)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestLegacyNicknameUsersSurvive:
    def test_authed_legacy_user_can_visit_authed_pages(self) -> None:
        client, _ = _authed_client()  # no email
        # The dashboard at / shouldn't bounce them.
        response = client.get("/")
        assert response.status_code == 200

    def test_unclaimed_banner_renders_for_them(self) -> None:
        client, _ = _authed_client()  # no email
        response = client.get("/")
        assert b"doesn't have an email" in response.content
        assert b"Add email" in response.content

    def test_unclaimed_banner_hidden_for_users_with_email(self) -> None:
        client, _ = _authed_client(email="haveit@example.com")
        response = client.get("/")
        assert b"doesn't have an email" not in response.content


# ---------------------------------------------------------------------------
# HTMX email availability check
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestEmailAvailabilityCheck:
    def test_available_state(self) -> None:
        response = Client().post("/accounts/check-email/available/", {"email": "fresh@example.com"})
        assert response.status_code == 200
        assert b"available" in response.content

    def test_taken_state(self) -> None:
        u = User.objects.create_anonymous(nickname="taker")
        u.email = "occupied@example.com"
        u.save()
        response = Client().post(
            "/accounts/check-email/available/", {"email": "occupied@example.com"}
        )
        assert response.status_code == 200
        assert b"taken" in response.content


# ---------------------------------------------------------------------------
# Email-send failure must degrade to a form error, never a 500
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestEmailDeliveryFailure:
    """Regression: in prod the Resend backend raises on any non-2xx (the
    sandbox sender refuses recipients other than the account owner). A
    nickname-only user adding an email then got a bare 500. Every view
    that sends a magic link must catch the failure and re-render its form
    with a friendly message — and the aborted transaction must roll the
    token row back so a retry starts clean."""

    _COULDNT_SEND = b"couldn&#x27;t send the"

    def test_claim_send_failure_re_renders_form(self) -> None:
        client, user = _authed_client()
        with patch(
            "apps.accounts.services.send_mail", side_effect=RuntimeError("403 from provider")
        ):
            response = client.post("/accounts/claim/", {"email": "claimfail@example.com"})
        assert response.status_code == 200
        assert self._COULDNT_SEND in response.content
        assert SignInToken.objects.count() == 0  # rolled back with the transaction
        user.refresh_from_db()
        assert user.email is None

    def test_settings_email_send_failure_re_renders_form(self) -> None:
        client, user = _authed_client()  # no email yet — the reported case
        with patch(
            "apps.accounts.services.send_mail", side_effect=RuntimeError("403 from provider")
        ):
            response = client.post("/accounts/settings/email/", {"email": "setfail@example.com"})
        assert response.status_code == 200
        assert self._COULDNT_SEND in response.content
        assert SignInToken.objects.count() == 0
        user.refresh_from_db()
        assert user.email is None

    def test_start_send_failure_re_renders_form(self) -> None:
        with patch(
            "apps.accounts.services.send_mail", side_effect=RuntimeError("403 from provider")
        ):
            response = Client().post("/accounts/start/", {"email": "startfail@example.com"})
        assert response.status_code == 200
        assert self._COULDNT_SEND in response.content
        assert SignInToken.objects.count() == 0


# ---------------------------------------------------------------------------
# Check-email page: verification wait must not bounce signed-in users
# ---------------------------------------------------------------------------
@pytest.mark.django_db
class TestCheckEmailVerificationWait:
    """Regression: the check-email page polls check_email_poll, whose
    first branch answered signed_in=true for ANY session — so users who
    were already signed in (claim / email-change) were redirected to /
    on the first poll, 2 seconds after landing. In verifying mode the
    poll must instead answer "is the email attached yet"."""

    def test_poll_verifying_false_while_unclicked(self) -> None:
        client, _ = _authed_client()  # no email yet
        r = client.get("/accounts/check-email/poll/?verifying=new@example.com")
        assert r.json() == {"verified": False}

    def test_poll_verifying_true_once_email_attached(self) -> None:
        client, user = _authed_client()
        user.email = "new@example.com"
        user.save(update_fields=["email"])
        r = client.get("/accounts/check-email/poll/?verifying=new@example.com")
        assert r.json() == {"verified": True}

    def test_poll_verifying_normalises_case(self) -> None:
        client, user = _authed_client()
        user.email = "new@example.com"
        user.save(update_fields=["email"])
        r = client.get("/accounts/check-email/poll/?verifying=New@Example.COM")
        assert r.json() == {"verified": True}

    def test_poll_verifying_anonymous_is_false(self) -> None:
        r = Client().get("/accounts/check-email/poll/?verifying=x@example.com")
        assert r.json() == {"verified": False}

    def test_poll_without_param_keeps_login_behaviour(self) -> None:
        client, _ = _authed_client()
        r = client.get("/accounts/check-email/poll/")
        assert r.json() == {"signed_in": True}

    def test_page_renders_verifying_copy_for_authed_user(self) -> None:
        client, _ = _authed_client()
        r = client.get("/accounts/check-email/?email=new@example.com")
        assert b"confirmation link" in r.content
        assert b"go back to settings" in r.content
        assert b"sign-in link" not in r.content

    def test_page_renders_login_copy_for_anonymous(self) -> None:
        r = Client().get("/accounts/check-email/?email=new@example.com")
        assert b"sign-in link" in r.content
        assert b"confirmation link" not in r.content

    def test_full_claim_wait_cycle(self) -> None:
        # POST claim → poll false → click link → poll true.
        client, user = _authed_client()
        client.post("/accounts/claim/", {"email": "cycle@example.com"})
        poll = "/accounts/check-email/poll/?verifying=cycle@example.com"
        assert client.get(poll).json() == {"verified": False}
        raw = _extract_raw_token(mail.outbox[-1].body)
        client.get(f"/accounts/verify/?t={raw}")
        assert client.get(poll).json() == {"verified": True}
        user.refresh_from_db()
        assert user.email == "cycle@example.com"
