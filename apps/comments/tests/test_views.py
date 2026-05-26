"""Tests for comment views."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.comments.models import Comment
from apps.posts.models import Post


@pytest.fixture
def authed_client() -> tuple[Client, User]:
    user = User.objects.create_anonymous(nickname="commentviewer")
    client = Client()
    session = client.session
    session["user_id"] = user.id
    session.save()
    return client, user


@pytest.fixture
def post() -> Post:
    author = User.objects.create_anonymous(nickname="postauthor")
    return Post.objects.create(author=author, title="t", body="b")


@pytest.mark.django_db
class TestCreateComment:
    def test_authed_can_post(self, authed_client, post: Post) -> None:
        client, _ = authed_client
        response = client.post(f"/posts/{post.pk}/comments/", {"body": "great strategy"})
        assert response.status_code == 302
        assert Comment.objects.filter(post=post, body="great strategy").exists()

    def test_unauthed_redirected(self, post: Post) -> None:
        response = Client().post(f"/posts/{post.pk}/comments/", {"body": "no auth"})
        assert response.status_code == 302  # to login URL

    def test_post_not_found(self, authed_client) -> None:
        client, _ = authed_client
        response = client.post("/posts/9999/comments/", {"body": "x"})
        assert response.status_code == 404

    def test_empty_body_redirects_back_no_comment_created(self, authed_client, post: Post) -> None:
        client, _ = authed_client
        response = client.post(f"/posts/{post.pk}/comments/", {"body": ""})
        assert response.status_code == 302
        assert not Comment.objects.filter(post=post, body="").exists()


@pytest.mark.django_db
class TestReplyComment:
    def test_creates_reply(self, authed_client, post: Post) -> None:
        client, user = authed_client
        parent = Comment.objects.create(author=user, post=post, body="parent")
        response = client.post(f"/comments/{parent.pk}/reply/", {"body": "reply"})
        assert response.status_code == 302
        assert Comment.objects.filter(parent=parent, body="reply").exists()


@pytest.mark.django_db
class TestDeleteComment:
    def test_author_deletes_own(self, authed_client, post: Post) -> None:
        client, user = authed_client
        c = Comment.objects.create(author=user, post=post, body="mine")
        response = client.post(f"/comments/{c.pk}/delete/")
        assert response.status_code == 302
        c.refresh_from_db()
        assert c.is_deleted

    def test_other_user_cannot_delete(self, authed_client, post: Post) -> None:
        client, _ = authed_client
        not_me = User.objects.create_anonymous(nickname="notmevoter")
        c = Comment.objects.create(author=not_me, post=post, body="not yours")
        response = client.post(f"/comments/{c.pk}/delete/")
        assert response.status_code == 403
        c.refresh_from_db()
        assert not c.is_deleted
