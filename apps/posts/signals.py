"""Signals — broadcast new posts to any connected feed subscribers.

The broadcast is a no-op until Thursday's `FeedConsumer` is wired up,
because nothing is subscribed to the channel layer. But the signal lives
here from day one so the realtime layer slots in without code changes
elsewhere.
"""

from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.realtime import broadcast

from .models import Post


@receiver(post_save, sender=Post)
def broadcast_post_on_create(sender, instance, created, **kwargs):  # noqa: ANN001, ARG001
    if created and not instance.is_deleted:
        broadcast.broadcast_new_post(instance)
