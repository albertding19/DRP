"""FIFO matching — first-two-in-pool get paired.

Simplest possible strategy: the oldest waiting ticket (excluding the
requester) becomes the partner. Combined with the partial-unique-active
constraint on `PoolTicket`, this gives the "random" feel the MVP wants:
who joins when is the source of randomness, no shuffling needed.

Future variants live in sibling modules — see `base.py` for the Protocol.
"""

from __future__ import annotations

from apps.body_double.models import PoolTicket


class FIFOStrategy:
    """Pair the requester with the oldest other waiting ticket."""

    def find_match(self, ticket: PoolTicket) -> PoolTicket | None:
        # `select_for_update` requires an outer atomic block — the
        # `services.enqueue` caller provides it. Locking ensures two
        # concurrent enqueues can't both claim the same partner row.
        return (
            PoolTicket.objects.select_for_update()
            .filter(status=PoolTicket.STATUS_WAITING)
            .exclude(user_id=ticket.user_id)
            .order_by("created_at")
            .first()
        )
