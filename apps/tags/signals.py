"""Maintain Tag.post_count via Post.tags m2m_changed signal."""

from __future__ import annotations

from django.db.models import F, Q
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from apps.posts.models import Post

from .models import Tag


@receiver(m2m_changed, sender=Post.tags.through)
def on_post_tags_changed(sender, instance, action, pk_set, **kwargs):  # noqa: ANN001, ARG001
    """Increment / decrement Tag.post_count when a Post.tags membership changes.

    Note: we ignore reverse m2m updates (sender side check) and only
    react to forward `Post.tags.add/remove/clear`.
    """
    if not isinstance(instance, Post):
        return

    if action == "post_add" and pk_set:
        Tag.objects.filter(pk__in=pk_set).update(post_count=F("post_count") + 1)
    elif action == "post_remove" and pk_set:
        Tag.objects.filter(pk__in=pk_set, post_count__gt=0).update(post_count=F("post_count") - 1)
    elif action == "pre_clear":
        # Snapshot the soon-to-be-cleared set on the instance so post_clear
        # can decrement; m2m_changed pre_clear knows the model but not pks.
        instance._tags_about_to_clear = list(  # type: ignore[attr-defined]
            instance.tags.values_list("pk", flat=True)
        )
    elif action == "post_clear":
        about_to_clear = getattr(instance, "_tags_about_to_clear", [])
        if about_to_clear:
            Tag.objects.filter(pk__in=about_to_clear).filter(Q(post_count__gt=0)).update(
                post_count=F("post_count") - 1
            )
            instance._tags_about_to_clear = []  # type: ignore[attr-defined]
