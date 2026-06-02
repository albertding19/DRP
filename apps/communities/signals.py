"""Denormalised `Community.member_count` maintenance.

Triggered by `post_save` and `post_delete` on `CommunityMembership`. Uses
`F('member_count') + 1` / `- 1` so concurrent joins/leaves don't lose an
update.

The signals are registered in `apps.communities.apps.CommunitiesConfig.ready`
"""

from __future__ import annotations

from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Community, CommunityMembership


@receiver(post_save, sender=CommunityMembership)
def _increment_member_count(sender, instance, created, **kwargs):  # type: ignore[no-untyped-def]
    """Bump member_count once when a new membership is created. Updates to
    existing memberships (which shouldn't happen with the current schema)
    are no-ops."""
    if not created:
        return
    Community.objects.filter(pk=instance.community_id).update(member_count=F("member_count") + 1)


@receiver(post_delete, sender=CommunityMembership)
def _decrement_member_count(sender, instance, **kwargs):  # type: ignore[no-untyped-def]
    """Decrement when a membership is deleted. `Community` may have been
    cascade-deleted; the filter+update silently no-ops in that case."""
    Community.objects.filter(pk=instance.community_id).update(member_count=F("member_count") - 1)
