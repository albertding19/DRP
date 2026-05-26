"""Tests for the search service."""

from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.posts.models import Post
from apps.search.services import search_posts


@pytest.fixture
def author() -> User:
    return User.objects.create_anonymous(nickname="searchauthor")


@pytest.mark.django_db
class TestSearchPosts:
    def test_empty_query_returns_none(self) -> None:
        assert search_posts("").count() == 0
        assert search_posts("   ").count() == 0
        assert search_posts(None).count() == 0  # type: ignore[arg-type]

    def test_matches_title(self, author: User) -> None:
        Post.objects.create(author=author, title="focus tools", body="not relevant")
        Post.objects.create(author=author, title="unrelated", body="body")
        results = list(search_posts("focus"))
        assert len(results) == 1
        assert results[0].title == "focus tools"

    def test_matches_body(self, author: User) -> None:
        Post.objects.create(author=author, title="x", body="I use timers for focus")
        results = list(search_posts("timers"))
        assert len(results) == 1

    def test_case_insensitive(self, author: User) -> None:
        Post.objects.create(author=author, title="Focus Tools", body="b")
        assert search_posts("FOCUS").count() == 1
        assert search_posts("focus").count() == 1
        assert search_posts("FoCuS").count() == 1

    def test_excludes_deleted(self, author: User) -> None:
        Post.objects.create(author=author, title="focus", body="b", is_deleted=True)
        assert search_posts("focus").count() == 0
