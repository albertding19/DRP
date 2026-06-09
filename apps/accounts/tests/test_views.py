"""Tests for the welcome page + HTMX uniqueness checks.

Welcome page (`/accounts/start/`) was rebuilt to take an EMAIL not a
nickname (M2 brand pass: email + Google OAuth replace nickname-only
signup). The form sends a magic link rather than creating a user
immediately; the user materialises when they click the link, which is
covered by `test_signin_services.py` and `test_view_flows.py`.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.test import Client

from apps.accounts.models import SignInToken, User


@pytest.fixture(autouse=True)
def _clear_cache():
    """Rate-limit counters are per-test-isolated."""
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestStartView:
    def test_get_renders_welcome(self) -> None:
        response = Client().get("/accounts/start/")
        assert response.status_code == 200
        # The form's email input is present.
        assert b'type="email"' in response.content

    def test_get_authenticated_user_redirects_home(self) -> None:
        user = User.objects.create_anonymous(nickname="signedin")
        client = Client()
        s = client.session
        s["user_id"] = user.id
        s.save()
        response = client.get("/accounts/start/")
        assert response.status_code == 302
        assert response.url == "/"

    def test_post_with_email_sends_link_and_redirects(self) -> None:
        client = Client()
        response = client.post("/accounts/start/", {"email": "me@example.com"})
        assert response.status_code == 302
        assert response.url.startswith("/accounts/check-email/")
        assert SignInToken.objects.count() == 1
        assert len(mail.outbox) == 1

    def test_post_with_invalid_email_re_renders_form(self) -> None:
        response = Client().post("/accounts/start/", {"email": "not an email"})
        assert response.status_code == 200
        assert SignInToken.objects.count() == 0
        assert len(mail.outbox) == 0

    def test_open_redirector_blocked_on_already_signed_in(self) -> None:
        # If already signed in, GET respects `?next=` — but only if it's
        # safe. External redirect attempts get clamped to "/".
        user = User.objects.create_anonymous(nickname="signedin")
        client = Client()
        s = client.session
        s["user_id"] = user.id
        s.save()
        response = client.get("/accounts/start/?next=https://evil.com")
        assert response.url == "/"


@pytest.mark.django_db
class TestCheckNickname:
    """HTMX uniqueness check. Still in use on the settings page."""

    def test_available(self) -> None:
        response = Client().post("/accounts/check-nickname/", {"nickname": "freshname"})
        assert response.status_code == 200
        assert b"available" in response.content

    def test_taken(self) -> None:
        User.objects.create_anonymous(nickname="alex")
        response = Client().post("/accounts/check-nickname/", {"nickname": "alex"})
        assert response.status_code == 200
        assert b"taken" in response.content
