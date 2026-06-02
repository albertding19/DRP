"""Tests for comment views."""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.comments.models import Comment
from apps.moderation.models import ModerationLog
from apps.posts.models import Post

# Phrase that better-profanity reliably flags. Kept here so only one
# copy lives in the suite.
_PROFANE_TEXT = "you fucking idiot"


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

    def test_empty_body_renders_form_with_error_no_comment_created(
        self, authed_client, post: Post
    ) -> None:
        """Invalid form re-renders the detail page (non-HTMX) with errors;
        no DB row is created. Previously this returned 302; the form-error
        rendering work in the moderation PR replaced the silent redirect."""
        client, _ = authed_client
        response = client.post(f"/posts/{post.pk}/comments/", {"body": ""})
        assert response.status_code == 200
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


@pytest.mark.django_db
class TestPermalink:
    """GET /posts/<p>/comments/<c>/ — single-comment permalink page."""

    def test_top_level_renders_with_replies(self, authed_client, post: Post) -> None:
        client, user = authed_client
        parent = Comment.objects.create(author=user, post=post, body="parent")
        Comment.objects.create(author=user, post=post, parent=parent, body="reply 1")
        response = client.get(f"/posts/{post.pk}/comments/{parent.pk}/")
        assert response.status_code == 200
        body = response.content.decode()
        assert "parent" in body
        assert "reply 1" in body
        # Back-to-thread link should point at the post detail anchor.
        assert f'href="/posts/{post.pk}/#c{parent.pk}"' in body

    def test_reply_shows_parent_context_link(self, authed_client, post: Post) -> None:
        client, user = authed_client
        parent = Comment.objects.create(author=user, post=post, body="parent")
        child = Comment.objects.create(author=user, post=post, parent=parent, body="child")
        response = client.get(f"/posts/{post.pk}/comments/{child.pk}/")
        assert response.status_code == 200
        body = response.content.decode()
        assert "child" in body
        # The "see parent thread" link should resolve to the parent permalink.
        assert f"/posts/{post.pk}/comments/{parent.pk}/" in body

    def test_deleted_comment_404s(self, authed_client, post: Post) -> None:
        client, user = authed_client
        c = Comment.objects.create(author=user, post=post, body="x", is_deleted=True)
        response = client.get(f"/posts/{post.pk}/comments/{c.pk}/")
        assert response.status_code == 404

    def test_mismatched_post_404s(self, authed_client, post: Post) -> None:
        """Comment belongs to a *different* post → 404, not 200."""
        client, user = authed_client
        other = Post.objects.create(author=user, title="other", body="b")
        c = Comment.objects.create(author=user, post=other, body="elsewhere")
        response = client.get(f"/posts/{post.pk}/comments/{c.pk}/")
        assert response.status_code == 404

    def test_post_not_found_404s(self, authed_client) -> None:
        client, _ = authed_client
        response = client.get("/posts/9999/comments/1/")
        assert response.status_code == 404

    def test_post_method_not_allowed(self, authed_client, post: Post) -> None:
        client, user = authed_client
        c = Comment.objects.create(author=user, post=post, body="x")
        response = client.post(f"/posts/{post.pk}/comments/{c.pk}/")
        assert response.status_code == 405


@pytest.mark.django_db
class TestCommentModerationL1:
    """L1 keyword filter on the comment-create path."""

    def test_clean_comment_publishes(self, authed_client, post: Post) -> None:
        client, _ = authed_client
        response = client.post(
            f"/posts/{post.pk}/comments/",
            {"body": "this strategy really helped me focus"},
        )
        assert response.status_code == 302  # redirect to detail#c<id>
        assert Comment.objects.filter(post=post).count() == 1
        assert ModerationLog.objects.count() == 0

    def test_profane_comment_blocked_no_row(self, authed_client, post: Post) -> None:
        client, user = authed_client
        response = client.post(f"/posts/{post.pk}/comments/", {"body": _PROFANE_TEXT})
        assert response.status_code == 200
        assert not Comment.objects.filter(post=post).exists()

        # ModerationLog row records the block.
        entry = ModerationLog.objects.get()
        assert entry.layer == ModerationLog.LAYER_L1
        assert entry.surface == ModerationLog.SURFACE_COMMENT
        assert entry.author_id == user.id
        assert entry.text == _PROFANE_TEXT

    def test_profane_comment_htmx_retargets_form(self, authed_client, post: Post) -> None:
        """HTMX submission of profane comment returns the form partial with
        HX-Retarget/HX-Reswap headers so the form replaces itself instead of
        being prepended to the thread."""
        client, _ = authed_client
        response = client.post(
            f"/posts/{post.pk}/comments/",
            {"body": _PROFANE_TEXT},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert response["HX-Retarget"] == f"#comment-form-{post.pk}"
        assert response["HX-Reswap"] == "outerHTML"
        body = response.content.decode()
        # The form re-renders with the input preserved (input retention).
        assert _PROFANE_TEXT in body

    def test_adhd_frustration_publishes(self, authed_client, post: Post) -> None:
        """The critical assessment-evidence test at the view layer: ADHD
        frustration vocabulary submits cleanly."""
        client, _ = authed_client
        response = client.post(
            f"/posts/{post.pk}/comments/",
            {"body": "this assignment is killing me today"},
        )
        assert response.status_code == 302
        assert Comment.objects.filter(post=post).count() == 1
        assert ModerationLog.objects.count() == 0


@pytest.mark.django_db
class TestReplyModerationL1:
    """L1 keyword filter on the reply path."""

    def test_profane_reply_blocked_no_row(self, authed_client, post: Post) -> None:
        client, user = authed_client
        parent = Comment.objects.create(author=user, post=post, body="parent")
        response = client.post(
            f"/comments/{parent.pk}/reply/",
            {"body": _PROFANE_TEXT},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert response["HX-Retarget"] == f"#reply-form-{parent.pk}"
        assert response["HX-Reswap"] == "outerHTML"
        assert not Comment.objects.filter(parent=parent).exists()
        entry = ModerationLog.objects.get()
        assert entry.layer == ModerationLog.LAYER_L1
        assert entry.surface == ModerationLog.SURFACE_COMMENT


@pytest.mark.django_db
class TestReportCommentView:
    """POST /comments/<pk>/report/ — L3 user-reporting endpoint."""

    def test_authed_user_can_report(self, authed_client, post: Post) -> None:
        client, user = authed_client
        author = User.objects.create_anonymous(nickname="reportedauth")
        c = Comment.objects.create(author=author, post=post, body="x")
        response = client.post(f"/comments/{c.pk}/report/")
        assert response.status_code == 302
        c.refresh_from_db()
        assert c.report_count == 1
        assert c.is_hidden is False

    def test_unauthed_redirected(self, post: Post) -> None:
        c = Comment.objects.create(author=post.author, post=post, body="x")
        response = Client().post(f"/comments/{c.pk}/report/")
        assert response.status_code == 302  # to login URL

    def test_missing_comment_404(self, authed_client) -> None:
        client, _ = authed_client
        response = client.post("/comments/9999/report/")
        assert response.status_code == 404

    def test_already_hidden_comment_404(self, authed_client, post: Post) -> None:
        client, _ = authed_client
        c = Comment.objects.create(author=post.author, post=post, body="x", is_hidden=True)
        response = client.post(f"/comments/{c.pk}/report/")
        assert response.status_code == 404

    def test_htmx_returns_confirmation_partial(self, authed_client, post: Post) -> None:
        client, _ = authed_client
        c = Comment.objects.create(author=post.author, post=post, body="x")
        response = client.post(
            f"/comments/{c.pk}/report/",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        body = response.content.decode()
        assert "recorded your report" in body.lower()

    def test_threshold_hides_comment(self, authed_client, post: Post) -> None:
        client, _ = authed_client
        author = User.objects.create_anonymous(nickname="thresholdauth")
        c = Comment.objects.create(author=author, post=post, body="x")
        # Existing two reports from other users.
        for nick in ["thresh_a", "thresh_b"]:
            r = User.objects.create_anonymous(nickname=nick)
            from apps.comments.models import CommentReport

            CommentReport.objects.create(comment=c, reporter=r)
        c.report_count = 2
        c.save(update_fields=["report_count"])

        # Authed client = third reporter → just_hidden.
        response = client.post(f"/comments/{c.pk}/report/")
        assert response.status_code == 302
        c.refresh_from_db()
        assert c.report_count == 3
        assert c.is_hidden is True

    def test_hidden_comment_disappears_from_thread(self, authed_client, post: Post) -> None:
        """Once is_hidden=True, the comment doesn't render in the detail page."""
        client, _ = authed_client
        Comment.objects.create(
            author=post.author, post=post, body="should not appear", is_hidden=True
        )
        response = client.get(f"/posts/{post.pk}/")
        assert response.status_code == 200
        assert b"should not appear" not in response.content
