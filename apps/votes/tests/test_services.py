"""Tests for the cast_vote service — the atomic upsert."""

from __future__ import annotations

import pytest

from apps.accounts.models import User
from apps.posts.models import Post
from apps.votes.models import Vote
from apps.votes.services import InvalidVoteValue, cast_vote, user_vote_for


@pytest.fixture
def user() -> User:
    return User.objects.create_anonymous(nickname="voter")


@pytest.fixture
def author() -> User:
    return User.objects.create_anonymous(nickname="author")


@pytest.fixture
def post(author: User) -> Post:
    return Post.objects.create(author=author, title="t", body="b")


@pytest.mark.django_db
class TestCastVote:
    def test_first_upvote_creates_vote_and_increments_score(self, user: User, post: Post) -> None:
        new_score, user_vote = cast_vote(user=user, target=post, value=1)
        assert new_score == 1
        assert user_vote == 1
        assert Vote.objects.filter(user=user).count() == 1

    def test_first_downvote_decrements(self, user: User, post: Post) -> None:
        new_score, user_vote = cast_vote(user=user, target=post, value=-1)
        assert new_score == -1
        assert user_vote == -1

    def test_repeated_upvote_retracts(self, user: User, post: Post) -> None:
        cast_vote(user=user, target=post, value=1)  # +1
        new_score, user_vote = cast_vote(user=user, target=post, value=1)
        # Second identical vote retracts: score back to 0, user_vote = 0
        assert new_score == 0
        assert user_vote == 0
        assert not Vote.objects.filter(user=user, object_id=post.pk).exists()

    def test_change_vote_flips_delta(self, user: User, post: Post) -> None:
        cast_vote(user=user, target=post, value=1)  # +1
        new_score, user_vote = cast_vote(user=user, target=post, value=-1)
        # Delta = -1 - +1 = -2, so score: 1 -> -1
        assert new_score == -1
        assert user_vote == -1
        assert Vote.objects.filter(user=user, object_id=post.pk).count() == 1

    def test_two_users_both_upvote(self, post: Post) -> None:
        u1 = User.objects.create_anonymous(nickname="alice")
        u2 = User.objects.create_anonymous(nickname="bobbie")
        s1, _ = cast_vote(user=u1, target=post, value=1)
        s2, _ = cast_vote(user=u2, target=post, value=1)
        assert s1 == 1
        assert s2 == 2
        assert Vote.objects.filter(object_id=post.pk).count() == 2

    def test_invalid_value_raises(self, user: User, post: Post) -> None:
        with pytest.raises(InvalidVoteValue):
            cast_vote(user=user, target=post, value=2)
        with pytest.raises(InvalidVoteValue):
            cast_vote(user=user, target=post, value=0)


@pytest.mark.django_db
class TestUserVoteFor:
    def test_no_vote_returns_zero(self, user: User, post: Post) -> None:
        assert user_vote_for(user, post) == 0

    def test_after_upvote_returns_plus_one(self, user: User, post: Post) -> None:
        cast_vote(user=user, target=post, value=1)
        assert user_vote_for(user, post) == 1

    def test_after_change_returns_new_value(self, user: User, post: Post) -> None:
        cast_vote(user=user, target=post, value=1)
        cast_vote(user=user, target=post, value=-1)
        assert user_vote_for(user, post) == -1
