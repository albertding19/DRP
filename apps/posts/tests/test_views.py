"""Tests for posts views."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.posts.models import Post


@pytest.fixture
def authed_client() -> tuple[Client, User]:
    user = User.objects.create_anonymous(nickname="viewuser")
    client = Client()
    session = client.session
    session["user_id"] = user.id
    session.save()
    return client, user


@pytest.mark.django_db
class TestFeed:
    def test_anon_user_redirected_to_picker(self) -> None:
        response = Client().get("/")
        assert response.status_code == 302
        assert response.url.startswith("/accounts/start/")

    def test_authed_user_sees_feed(self, authed_client) -> None:
        client, _ = authed_client
        response = client.get("/")
        assert response.status_code == 200
        assert b"Strategies" in response.content
        assert b"No posts yet" in response.content

    def test_feed_lists_existing_posts(self, authed_client) -> None:
        client, user = authed_client
        Post.objects.create(author=user, title="My first post", body="body")
        response = client.get("/")
        assert response.status_code == 200
        assert b"My first post" in response.content

    def test_sort_top(self, authed_client) -> None:
        client, _ = authed_client
        response = client.get("/?sort=top")
        assert response.status_code == 200


@pytest.mark.django_db
class TestCreate:
    def test_get_renders_form(self, authed_client) -> None:
        client, _ = authed_client
        response = client.get("/posts/new/")
        assert response.status_code == 200
        assert b"Share" in response.content

    def test_post_creates_and_redirects(self, authed_client) -> None:
        client, _ = authed_client
        response = client.post(
            "/posts/new/",
            {"title": "Test post", "body": "Hello", "post_type": "strategy"},
        )
        assert response.status_code == 302
        assert Post.objects.filter(title="Test post").exists()
        post = Post.objects.get(title="Test post")
        assert response.url == f"/posts/{post.pk}/"

    def test_post_validation_error_re_renders_form(self, authed_client) -> None:
        client, _ = authed_client
        response = client.post(
            "/posts/new/",
            {"title": "", "body": "", "post_type": "strategy"},
        )
        assert response.status_code == 200
        assert not Post.objects.filter(body="").exists()


@pytest.mark.django_db
class TestDetail:
    def test_detail_view(self, authed_client) -> None:
        client, user = authed_client
        post = Post.objects.create(author=user, title="Detailed", body="..body..")
        response = client.get(f"/posts/{post.pk}/")
        assert response.status_code == 200
        assert b"Detailed" in response.content
        assert b"..body.." in response.content

    def test_soft_deleted_returns_404(self, authed_client) -> None:
        client, user = authed_client
        post = Post.objects.create(author=user, title="Gone", body="..", is_deleted=True)
        response = client.get(f"/posts/{post.pk}/")
        assert response.status_code == 404
