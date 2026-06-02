"""Tests for posts services."""

from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.posts.models import Post, PostReport
from apps.posts.services import (
    REPORT_AUTO_HIDE_THRESHOLD,
    create_post,
    feed_queryset,
    report_post,
)


@pytest.mark.django_db
class TestCreatePost:
    def test_creates_post_with_defaults(self) -> None:
        user = User.objects.create_anonymous(nickname="author1")
        post = create_post(author=user, title="hello", body="world")
        assert post.pk is not None
        assert post.author == user
        assert post.post_type == Post.STRATEGY
        assert post.score == 0
        assert post.comment_count == 0
        assert post.is_deleted is False

    def test_create_problem_type(self) -> None:
        user = User.objects.create_anonymous(nickname="author2")
        post = create_post(author=user, title="stuck", body="?", post_type=Post.PROBLEM)
        assert post.post_type == Post.PROBLEM


@pytest.mark.django_db
class TestFeedQueryset:
    def _setup(self) -> tuple[User, Post, Post, Post]:
        user = User.objects.create_anonymous(nickname="qsfeed")
        a = create_post(author=user, title="A", body="..")
        b = create_post(author=user, title="B", body="..")
        c = create_post(author=user, title="C", body="..")
        # tweak scores so top != new ordering
        Post.objects.filter(pk=a.pk).update(score=10)
        Post.objects.filter(pk=b.pk).update(score=5)
        Post.objects.filter(pk=c.pk).update(score=20)
        a.refresh_from_db()
        b.refresh_from_db()
        c.refresh_from_db()
        return user, a, b, c

    def test_sort_new_orders_by_created_desc(self) -> None:
        _, a, b, c = self._setup()
        qs = list(feed_queryset(sort="new"))
        assert qs == [c, b, a]  # most-recently-created first

    def test_sort_top_orders_by_score_desc(self) -> None:
        _, a, b, c = self._setup()
        qs = list(feed_queryset(sort="top"))
        assert qs[0] == c  # score 20
        assert qs[1] == a  # score 10
        assert qs[2] == b  # score 5

    def test_unknown_sort_falls_back_to_new(self) -> None:
        _, _, _, c = self._setup()
        qs = list(feed_queryset(sort="bogus"))
        assert qs[0] == c

    def test_excludes_soft_deleted(self) -> None:
        _, a, _, _ = self._setup()
        Post.objects.filter(pk=a.pk).update(is_deleted=True)
        qs = list(feed_queryset())
        assert a not in qs

    def test_excludes_hidden(self) -> None:
        """L3-hidden posts are filtered out of the feed (alongside is_deleted)."""
        _, a, _, _ = self._setup()
        Post.objects.filter(pk=a.pk).update(is_hidden=True)
        qs = list(feed_queryset())
        assert a not in qs


@pytest.mark.django_db
class TestReportPost:
    """L3 reporting service for posts. Threshold is 3 reports → auto-hide."""

    def _post(self) -> Post:
        author = User.objects.create_anonymous(nickname="reportedposted")
        return Post.objects.create(author=author, title="t", body="b")

    def test_single_report_no_hide(self) -> None:
        p = self._post()
        reporter = User.objects.create_anonymous(nickname="postreporter1")
        count, just_hidden = report_post(post=p, reporter=reporter)
        assert count == 1
        assert just_hidden is False
        p.refresh_from_db()
        assert p.report_count == 1
        assert p.is_hidden is False
        assert PostReport.objects.count() == 1

    def test_threshold_hides_post(self) -> None:
        p = self._post()
        reporters = [
            User.objects.create_anonymous(nickname=f"postreporter_{i}")
            for i in range(REPORT_AUTO_HIDE_THRESHOLD)
        ]
        results = [report_post(post=p, reporter=r) for r in reporters]
        assert [hidden for _, hidden in results] == [False, False, True]
        p.refresh_from_db()
        assert p.is_hidden is True

    def test_same_reporter_idempotent(self) -> None:
        p = self._post()
        reporter = User.objects.create_anonymous(nickname="postreporter_dup")
        a = report_post(post=p, reporter=reporter)
        b = report_post(post=p, reporter=reporter)
        assert a == (1, False)
        assert b == (1, False)
        p.refresh_from_db()
        assert p.report_count == 1
