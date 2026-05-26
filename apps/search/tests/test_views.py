"""Tests for the search view."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.posts.models import Post


@pytest.fixture
def authed_client() -> tuple[Client, User]:
    user = User.objects.create_anonymous(nickname="searcher")
    client = Client()
    session = client.session
    session["user_id"] = user.id
    session.save()
    return client, user


@pytest.mark.django_db
class TestSearchView:
    def test_empty_q_renders_blank_search(self, authed_client) -> None:
        client, _ = authed_client
        response = client.get("/search/")
        assert response.status_code == 200
        assert b"Search posts" in response.content

    def test_q_with_match(self, authed_client) -> None:
        client, user = authed_client
        Post.objects.create(author=user, title="focus tools", body="b")
        response = client.get("/search/?q=focus")
        assert response.status_code == 200
        assert b"focus tools" in response.content
        assert b"1 result" in response.content

    def test_q_no_match(self, authed_client) -> None:
        client, _ = authed_client
        response = client.get("/search/?q=zzzzz")
        assert response.status_code == 200
        assert b"No results" in response.content

    def test_q_in_page_title(self, authed_client) -> None:
        client, _ = authed_client
        response = client.get("/search/?q=nightowl")
        assert b"nightowl" in response.content
