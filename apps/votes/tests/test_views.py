"""Tests for the vote-cast view."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.comments.models import Comment
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

    def test_upvote_comment(self, authed_client, post: Post) -> None:
        """Voting on a comment hits the same endpoint with target_type='comment'."""
        client, _ = authed_client
        author = User.objects.create_anonymous(nickname="commentauth")
        c = Comment.objects.create(author=author, post=post, body="reply-worthy")
        response = client.post(f"/vote/comment/{c.pk}/", {"value": "1"})
        assert response.status_code == 200
        c.refresh_from_db()
        assert c.score == 1
        # The returned partial is the compact horizontal variant.
        assert b"vote-buttons-inline" in response.content
        assert b"data-score-comment-" in response.content

    def test_retract_comment_vote(self, authed_client, post: Post) -> None:
        """Same value twice retracts (score back to 0)."""
        client, _ = authed_client
        author = User.objects.create_anonymous(nickname="commentauth2")
        c = Comment.objects.create(author=author, post=post, body="x")
        client.post(f"/vote/comment/{c.pk}/", {"value": "1"})
        client.post(f"/vote/comment/{c.pk}/", {"value": "1"})
        c.refresh_from_db()
        assert c.score == 0

    def test_comment_not_found_404(self, authed_client) -> None:
        client, _ = authed_client
        response = client.post("/vote/comment/9999/", {"value": "1"})
        assert response.status_code == 404
