"""Tests for tag services + signal-driven post_count maintenance."""

from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.posts.models import Post
from apps.tags.models import Tag, normalise_tag_name
from apps.tags.services import get_or_create_tags, parse_tags_input


class TestNormaliseTagName:
    @pytest.mark.parametrize(
        "raw,expected_name,expected_slug",
        [
            ("focus", "focus", "focus"),
            ("  focus  ", "focus", "focus"),
            ("Focus Time", "Focus Time", "focus-time"),
            ("multi   space", "multi space", "multi-space"),
            ("", "", ""),
            ("   ", "", ""),
            ("!!!", "", ""),  # all-non-alpha returns ("", "") — empty slug rejects whole tag
        ],
    )
    def test_normalises(self, raw, expected_name, expected_slug) -> None:
        name, slug = normalise_tag_name(raw)
        assert name == expected_name
        assert slug == expected_slug


class TestParseTagsInput:
    def test_empty(self) -> None:
        assert parse_tags_input("") == []
        assert parse_tags_input(None) == []

    def test_comma_split(self) -> None:
        result = parse_tags_input("focus, sleep, anxiety")
        assert [slug for _, slug in result] == ["focus", "sleep", "anxiety"]

    def test_dedupes_by_slug(self) -> None:
        result = parse_tags_input("Focus, focus, FOCUS")
        # All three slugify to "focus"; only the first survives
        assert len(result) == 1
        assert result[0][1] == "focus"

    def test_preserves_order(self) -> None:
        result = parse_tags_input("c, a, b")
        slugs = [slug for _, slug in result]
        assert slugs == ["c", "a", "b"]


@pytest.mark.django_db
class TestGetOrCreateTags:
    def test_creates_new(self) -> None:
        tags = get_or_create_tags(["focus", "sleep"])
        assert len(tags) == 2
        assert {t.slug for t in tags} == {"focus", "sleep"}

    def test_returns_existing(self) -> None:
        Tag.objects.create(slug="focus", name="focus")
        tags = get_or_create_tags(["focus"])
        assert len(tags) == 1
        assert Tag.objects.count() == 1  # didn't create a second

    def test_mixed(self) -> None:
        Tag.objects.create(slug="focus", name="focus")
        tags = get_or_create_tags(["focus", "sleep"])
        assert {t.slug for t in tags} == {"focus", "sleep"}
        assert Tag.objects.count() == 2

    def test_returns_in_input_order(self) -> None:
        tags = get_or_create_tags(["zeta", "alpha", "mu"])
        assert [t.slug for t in tags] == ["zeta", "alpha", "mu"]

    def test_empty(self) -> None:
        assert get_or_create_tags([]) == []


@pytest.mark.django_db
class TestTagPostCount:
    """post_count is maintained by m2m_changed signal."""

    def _author(self) -> User:
        return User.objects.create_anonymous(nickname="tagauthor")

    def test_post_count_increments_on_add(self) -> None:
        author = self._author()
        focus = Tag.objects.create(slug="focus", name="focus")
        post = Post.objects.create(author=author, title="t", body="b")
        post.tags.add(focus)
        focus.refresh_from_db()
        assert focus.post_count == 1

    def test_post_count_decrements_on_remove(self) -> None:
        author = self._author()
        focus = Tag.objects.create(slug="focus", name="focus", post_count=1)
        post = Post.objects.create(author=author, title="t", body="b")
        post.tags.add(focus)
        focus.refresh_from_db()
        assert focus.post_count == 2
        post.tags.remove(focus)
        focus.refresh_from_db()
        assert focus.post_count == 1

    def test_two_posts_share_tag(self) -> None:
        author = self._author()
        focus = Tag.objects.create(slug="focus", name="focus")
        p1 = Post.objects.create(author=author, title="a", body="a")
        p2 = Post.objects.create(author=author, title="b", body="b")
        p1.tags.add(focus)
        p2.tags.add(focus)
        focus.refresh_from_db()
        assert focus.post_count == 2
