"""Community-aware matching with general-pool fallback.

Behaviour (per the plan §"Matching logic at a glance"):

  - Ticket WITH a community: try same-community first. If no match in
    that community, accept any waiting partner whose `created_at` is at
    least `settings.BODY_DOUBLE_FALLBACK_S` seconds in the past.
  - Ticket WITHOUT a community: pure FIFO across all waiting tickets
    (backwards-compatible with the original `FIFOStrategy`).

The strategy runs inside `services.enqueue`'s outer
`@transaction.atomic`, so `select_for_update` is meaningful — it
serialises simultaneous matches on the same partner.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.body_double.models import PoolTicket


class CommunityFallbackStrategy:
    def find_match(self, ticket: PoolTicket) -> PoolTicket | None:
        waiting = (
            PoolTicket.objects.select_for_update()
            .filter(status=PoolTicket.STATUS_WAITING)
            .exclude(user_id=ticket.user_id)
        )

        if ticket.community_id is None:
            # No community preference — pure FIFO. Identical to the
            # original FIFOStrategy.
            return waiting.order_by("created_at").first()

        # Phase 1: same-community match (oldest first).
        same_community = waiting.filter(community_id=ticket.community_id).order_by("created_at")
        partner = same_community.first()
        if partner is not None:
            return partner

        # Phase 2: fallback — pair with the oldest waiting ticket from
        # any community (or none), but only if they've been waiting long
        # enough that the fallback should kick in for them too.
        fallback_seconds = getattr(settings, "BODY_DOUBLE_FALLBACK_S", 60)
        fallback_cutoff = timezone.now() - timedelta(seconds=fallback_seconds)
        return waiting.filter(created_at__lte=fallback_cutoff).order_by("created_at").first()
