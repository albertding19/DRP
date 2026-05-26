"""Tests for comment services."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.comments.models import Comment
from apps.comments.services import create_comment, soft_delete_comment
from apps.posts.models import Post


@pytest.fixture
def author() -> User:
    return User.objects.create_anonymous(nickname="commenter")


@pytest.fixture
def post(author: User) -> Post:
    return Post.objects.create(author=author, title="t", body="b")


@pytest.mark.django_db
class TestCreateComment:
    def test_top_level(self, author: User, post: Post) -> None:
        c = create_comment(author=author, post=post, body="hello")
        assert c.pk is not None
        assert c.parent_id is None
        assert c.body == "hello"
        post.refresh_from_db()
        assert post.comment_count == 1

    def test_reply(self, author: User, post: Post) -> None:
        parent = create_comment(author=author, post=post, body="parent")
        reply = create_comment(author=author, post=post, body="reply", parent=parent)
        assert reply.parent_id == parent.id
        post.refresh_from_db()
        assert post.comment_count == 2

    def test_two_levels_of_nesting_rejected(self, author: User, post: Post) -> None:
        parent = create_comment(author=author, post=post, body="parent")
        child = create_comment(author=author, post=post, body="child", parent=parent)
        with pytest.raises(ValidationError):
            create_comment(author=author, post=post, body="grandchild", parent=child)

    def test_parent_on_other_post_rejected(self, author: User, post: Post) -> None:
        other_post = Post.objects.create(author=author, title="x", body="y")
        parent = create_comment(author=author, post=other_post, body="parent on other")
        with pytest.raises(ValidationError):
            create_comment(author=author, post=post, body="reply", parent=parent)

    def test_reply_to_deleted_rejected(self, author: User, post: Post) -> None:
        parent = create_comment(author=author, post=post, body="parent")
        parent.is_deleted = True
        parent.save()
        with pytest.raises(ValidationError):
            create_comment(author=author, post=post, body="reply", parent=parent)


@pytest.mark.django_db
class TestSoftDeleteComment:
    def test_author_can_delete(self, author: User, post: Post) -> None:
        c = create_comment(author=author, post=post, body="mine")
        soft_delete_comment(comment=c, requesting_user=author)
        c.refresh_from_db()
        assert c.is_deleted

    def test_other_user_cannot_delete(self, author: User, post: Post) -> None:
        other = User.objects.create_anonymous(nickname="notauthor")
        c = create_comment(author=author, post=post, body="not yours")
        with pytest.raises(PermissionError):
            soft_delete_comment(comment=c, requesting_user=other)
        c.refresh_from_db()
        assert not c.is_deleted


@pytest.mark.django_db
class TestCommentCountSignal:
    def test_increment_on_create(self, author: User, post: Post) -> None:
        assert post.comment_count == 0
        create_comment(author=author, post=post, body="one")
        create_comment(author=author, post=post, body="two")
        post.refresh_from_db()
        assert post.comment_count == 2

    def test_no_increment_for_already_deleted_comment(self, author: User, post: Post) -> None:
        Comment.objects.create(author=author, post=post, body="ghost", is_deleted=True)
        post.refresh_from_db()
        assert post.comment_count == 0

    def test_no_increment_on_update(self, author: User, post: Post) -> None:
        c = create_comment(author=author, post=post, body="one")
        post.refresh_from_db()
        assert post.comment_count == 1
        c.body = "edited"
        c.save()
        post.refresh_from_db()
        assert post.comment_count == 1
