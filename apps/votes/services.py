"""Vote casting — the atomic upsert that keeps Post.score consistent.

This is the only service that should mutate a Vote row. It handles three
cases idempotently:

1. No existing vote, new value -> create.
2. Existing vote with same value -> retract (delete).
3. Existing vote with different value -> change (update).

All three pathways update the target's denormalised `score` field via
F-expression so two concurrent voters don't race.
"""

from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import F

from .models import Vote


class InvalidVoteValue(ValueError):
    pass


@transaction.atomic
def cast_vote(*, user, target, value: int) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """Cast or update a vote.

    Args:
        user: the voting User
        target: a Post or Comment instance
        value: +1 (upvote) or -1 (downvote)

    Returns:
        (new_target_score, user_current_vote)
        user_current_vote is 0 if the action retracted the vote, else +1 or -1.

    Behaviour:
        - First time: creates a Vote, increments target.score by `value`.
        - Same-value re-vote (toggle): deletes the Vote, decrements
          target.score by `value`. Net effect: vote retracted.
        - Different-value re-vote (change): updates the Vote, applies the
          delta to target.score (e.g. -1 -> +1 => +2 to score).
    """
    if value not in (1, -1):
        raise InvalidVoteValue(f"value must be +1 or -1, got {value!r}")

    ct = ContentType.objects.get_for_model(target)

    # Lock the existing vote row (if any) so concurrent voters don't both
    # double-apply.
    existing = (
        Vote.objects.select_for_update()
        .filter(user=user, content_type=ct, object_id=target.pk)
        .first()
    )

    final_user_vote: int
    if existing is None:
        Vote.objects.create(user=user, target=target, value=value)
        delta = value
        final_user_vote = value
    elif existing.value == value:
        # Same value => retract
        existing.delete()
        delta = -value
        final_user_vote = 0
    else:
        # Different value => change. Delta = new - old.
        delta = value - existing.value
        existing.value = value
        existing.save(update_fields=["value", "updated_at"])
        final_user_vote = value

    # Atomic counter update on the target — F() bypasses Python read/write
    # so two concurrent transactions can't lose an update.
    target.__class__.objects.filter(pk=target.pk).update(score=F("score") + delta)
    target.refresh_from_db(fields=["score"])

    return target.score, final_user_vote


def user_vote_for(user, target) -> int:  # type: ignore[no-untyped-def]
    """Return the user's current vote on target: +1, -1, or 0.

    Useful for rendering vote-button state.
    """
    if not getattr(user, "is_authenticated", False):
        return 0
    ct = ContentType.objects.get_for_model(target)
    vote = (
        Vote.objects.filter(user=user, content_type=ct, object_id=target.pk).only("value").first()
    )
    return vote.value if vote else 0
