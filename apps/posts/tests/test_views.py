"""Tests for posts views."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.moderation.models import ModerationLog
from apps.posts.models import Post

_PROFANE_TEXT = "you fucking idiot"


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


@pytest.mark.django_db
class TestPostModerationL1:
    """L1 keyword filter on the post-share form. Applies to body AND title."""

    def test_clean_post_publishes(self, authed_client) -> None:
        client, _ = authed_client
        response = client.post(
            "/posts/new/",
            {
                "title": "Trello tips that worked for me",
                "body": "I tried using one column and it actually stuck.",
                "post_type": "strategy",
            },
        )
        assert response.status_code == 302
        assert Post.objects.filter(title="Trello tips that worked for me").exists()
        assert ModerationLog.objects.count() == 0

    def test_profane_body_blocked(self, authed_client) -> None:
        client, user = authed_client
        response = client.post(
            "/posts/new/",
            {
                "title": "Asking for help",
                "body": _PROFANE_TEXT,
                "post_type": "problem",
            },
        )
        assert response.status_code == 200  # form re-renders
        assert not Post.objects.filter(title="Asking for help").exists()

        entry = ModerationLog.objects.get()
        assert entry.layer == ModerationLog.LAYER_L1
        assert entry.surface == ModerationLog.SURFACE_POST_BODY
        assert entry.author_id == user.id
        assert entry.text == _PROFANE_TEXT

    def test_profane_title_blocked(self, authed_client) -> None:
        client, user = authed_client
        response = client.post(
            "/posts/new/",
            {
                "title": _PROFANE_TEXT,
                "body": "clean body content here",
                "post_type": "problem",
            },
        )
        assert response.status_code == 200
        assert not Post.objects.filter(body="clean body content here").exists()

        entry = ModerationLog.objects.get()
        assert entry.layer == ModerationLog.LAYER_L1
        assert entry.surface == ModerationLog.SURFACE_POST_TITLE
        assert entry.author_id == user.id

    def test_adhd_vocabulary_publishes(self, authed_client) -> None:
        """ADHD-context test at the post view layer."""
        client, _ = authed_client
        response = client.post(
            "/posts/new/",
            {
                "title": "Deadlines are destroying me — help",
                "body": "This assignment is killing me. Any tips?",
                "post_type": "problem",
            },
        )
        assert response.status_code == 302
        assert Post.objects.filter(title__startswith="Deadlines are destroying me").exists()
        assert ModerationLog.objects.count() == 0


@pytest.mark.django_db
class TestReportPostView:
    """POST /posts/<pk>/report/ — L3 reporting endpoint for posts."""

    def _post(self) -> Post:
        author = User.objects.create_anonymous(nickname="reportedpost_author")
        return Post.objects.create(author=author, title="t", body="b")

    def test_authed_user_can_report(self, authed_client) -> None:
        client, _ = authed_client
        p = self._post()
        response = client.post(f"/posts/{p.pk}/report/")
        assert response.status_code == 302
        p.refresh_from_db()
        assert p.report_count == 1
        assert p.is_hidden is False

    def test_unauthed_redirected(self) -> None:
        p = self._post()
        response = Client().post(f"/posts/{p.pk}/report/")
        assert response.status_code == 302  # login redirect

    def test_missing_post_404(self, authed_client) -> None:
        client, _ = authed_client
        response = client.post("/posts/9999/report/")
        assert response.status_code == 404

    def test_already_hidden_post_404(self, authed_client) -> None:
        client, _ = authed_client
        p = self._post()
        p.is_hidden = True
        p.save(update_fields=["is_hidden"])
        response = client.post(f"/posts/{p.pk}/report/")
        assert response.status_code == 404

    def test_htmx_returns_confirmation_partial(self, authed_client) -> None:
        client, _ = authed_client
        p = self._post()
        response = client.post(
            f"/posts/{p.pk}/report/",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"recorded your report" in response.content.lower()

    def test_hidden_post_is_404_on_detail(self, authed_client) -> None:
        client, _ = authed_client
        p = self._post()
        p.is_hidden = True
        p.save(update_fields=["is_hidden"])
        response = client.get(f"/posts/{p.pk}/")
        assert response.status_code == 404

    def test_hidden_post_does_not_appear_in_feed(self, authed_client) -> None:
        client, _ = authed_client
        p = self._post()
        p.title = "Should not show on the feed"
        p.is_hidden = True
        p.save(update_fields=["is_hidden", "title"])
        response = client.get("/")
        assert response.status_code == 200
        assert b"Should not show on the feed" not in response.content
