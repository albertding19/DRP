"""Tests for the tag views."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.posts.models import Post
from apps.tags.models import Tag


@pytest.fixture
def authed_client() -> tuple[Client, User]:
    user = User.objects.create_anonymous(nickname="tagviewer")
    client = Client()
    session = client.session
    session["user_id"] = user.id
    session.save()
    return client, user


@pytest.mark.django_db
class TestTagList:
    def test_renders_tag_list(self, authed_client) -> None:
        client, _ = authed_client
        Tag.objects.create(slug="focus", name="focus", post_count=3)
        Tag.objects.create(slug="sleep", name="sleep", post_count=2)
        response = client.get("/tags/")
        assert response.status_code == 200
        assert b"#focus" in response.content
        assert b"#sleep" in response.content

    def test_excludes_empty_tags(self, authed_client) -> None:
        client, _ = authed_client
        Tag.objects.create(slug="empty", name="empty", post_count=0)
        response = client.get("/tags/")
        assert b"#empty" not in response.content


@pytest.mark.django_db
class TestTagDetail:
    def test_shows_posts_with_tag(self, authed_client) -> None:
        client, user = authed_client
        focus = Tag.objects.create(slug="focus", name="focus")
        other = Tag.objects.create(slug="sleep", name="sleep")
        p1 = Post.objects.create(author=user, title="focus-post", body="body1")
        p1.tags.add(focus)
        p2 = Post.objects.create(author=user, title="sleep-post", body="body2")
        p2.tags.add(other)

        response = client.get("/tags/focus/")
        assert response.status_code == 200
        assert b"focus-post" in response.content
        assert b"sleep-post" not in response.content

    def test_unknown_slug_404(self, authed_client) -> None:
        client, _ = authed_client
        response = client.get("/tags/nope/")
        assert response.status_code == 404
