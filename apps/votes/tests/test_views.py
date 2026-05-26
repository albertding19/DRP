"""Tests for the vote-cast view."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.posts.models import Post


@pytest.fixture
def authed_client() -> tuple[Client, User]:
    user = User.objects.create_anonymous(nickname="voter")
    client = Client()
    session = client.session
    session["user_id"] = user.id
    session.save()
    return client, user


@pytest.fixture
def post() -> Post:
    author = User.objects.create_anonymous(nickname="postauthor")
    return Post.objects.create(author=author, title="x", body="y")


@pytest.mark.django_db
class TestCastView:
    def test_upvote_returns_partial_with_new_score(self, authed_client, post: Post) -> None:
        client, _ = authed_client
        response = client.post(f"/vote/post/{post.pk}/", {"value": "1"})
        assert response.status_code == 200
        # rendered partial includes the score
        assert b">1<" in response.content or b"1</span>" in response.content

    def test_unauthed_redirected(self, post: Post) -> None:
        response = Client().post(f"/vote/post/{post.pk}/", {"value": "1"})
        # @login_required redirects to LOGIN_URL
        assert response.status_code == 302

    def test_unknown_target_type_400(self, authed_client, post: Post) -> None:
        client, _ = authed_client
        response = client.post(f"/vote/user/{post.pk}/", {"value": "1"})
        assert response.status_code == 400

    def test_missing_value_400(self, authed_client, post: Post) -> None:
        client, _ = authed_client
        response = client.post(f"/vote/post/{post.pk}/", {})
        assert response.status_code == 400

    def test_invalid_value_400(self, authed_client, post: Post) -> None:
        client, _ = authed_client
        response = client.post(f"/vote/post/{post.pk}/", {"value": "2"})
        assert response.status_code == 400

    def test_post_not_found_404(self, authed_client) -> None:
        client, _ = authed_client
        response = client.post("/vote/post/9999/", {"value": "1"})
        assert response.status_code == 404
