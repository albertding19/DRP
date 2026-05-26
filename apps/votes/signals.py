"""Vote signals → realtime broadcast.

`cast_vote` already runs inside a transaction that updates the target's
score via F-expression. We hook into Vote's post_save / post_delete to
broadcast the new score to any connected viewers. Until Thursday's
consumers are wired, these broadcasts go to the channel layer and get
dropped — no harm done.
"""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.realtime import broadcast

from .models import Vote


def _push(vote: Vote) -> None:
    target = vote.target
    if target is None:
        # GenericForeignKey resolved to nothing — target was deleted.
        return
    broadcast.broadcast_vote_change(target, target.score)


@receiver(post_save, sender=Vote)
def on_vote_save(sender, instance: Vote, **kwargs):  # noqa: ANN001, ARG001
    _push(instance)


@receiver(post_delete, sender=Vote)
def on_vote_delete(sender, instance: Vote, **kwargs):  # noqa: ANN001, ARG001
    _push(instance)
