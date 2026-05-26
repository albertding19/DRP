"""Tests for the nickname picker views."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User


@pytest.mark.django_db
class TestStartView:
    def test_get_renders_picker(self) -> None:
        response = Client().get("/accounts/start/")
        assert response.status_code == 200
        assert b"Pick a nickname" in response.content

    def test_post_creates_user_and_redirects(self) -> None:
        client = Client()
        response = client.post("/accounts/start/", {"nickname": "newcomer"})
        assert response.status_code == 302
        assert response.url == "/"
        assert User.objects.filter(nickname="newcomer").exists()
        # Session was set
        assert client.session.get("user_id") is not None

    def test_post_invalid_nickname_re_renders_form(self) -> None:
        response = Client().post("/accounts/start/", {"nickname": "ab"})
        assert response.status_code == 200
        assert not User.objects.filter(nickname="ab").exists()

    def test_post_taken_nickname_shows_error(self) -> None:
        User.objects.create_anonymous(nickname="alex")
        response = Client().post("/accounts/start/", {"nickname": "alex"})
        assert response.status_code == 200
        assert User.objects.filter(nickname="alex").count() == 1


@pytest.mark.django_db
class TestCheckNickname:
    def test_available(self) -> None:
        response = Client().post("/accounts/check-nickname/", {"nickname": "freshname"})
        assert response.status_code == 200
        assert b"available" in response.content

    def test_taken(self) -> None:
        User.objects.create_anonymous(nickname="alex")
        response = Client().post("/accounts/check-nickname/", {"nickname": "alex"})
        assert response.status_code == 200
        assert b"taken" in response.content
