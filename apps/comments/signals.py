"""Comment signals — maintain Post.comment_count + broadcast to live viewers."""

from __future__ import annotations

from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.posts.models import Post
from apps.realtime import broadcast

from .models import Comment


@receiver(post_save, sender=Comment)
def on_comment_save(sender, instance: Comment, created: bool, **kwargs):  # noqa: ANN001, ARG001
    """When a new comment lands, bump the post's comment_count and broadcast.

    Skip updates and soft-deletes — only the `created` path increments and
    fires the broadcast. (Soft delete updates the row but `created=False`.)
    """
    if not created or instance.is_deleted:
        return
    Post.objects.filter(pk=instance.post_id).update(comment_count=F("comment_count") + 1)
    broadcast.broadcast_new_comment(instance)
