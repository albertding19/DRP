"""Preference-aware matchmaking.

Extends the community-fallback shape with three more dimensions:
chattiness, work mode, and session duration. Phased loosening lets a
user wait for the perfect match first, then gradually accept worse-fit
partners as the queue ages.

Hard rule (NEVER loosened): chattiness compatibility.
    chatty × chatty     → match
    quiet × quiet       → match
    flexible × anything → match
    chatty × quiet      → NEVER match
The matcher will let a chatty-and-quiet user wait forever (until the
5-minute ticket timeout) rather than pair them with their opposite.
Mismatched vibes are worse than waiting longer.

Phase progression — every phase requires chattiness compatibility:

    Phase 1  (0 → BODY_DOUBLE_STRICT_S)
        same community + work_mode-compat + |Δduration| ≤ 15
    Phase 2  (→ BODY_DOUBLE_FALLBACK_S)
        same community + work_mode-compat + |Δduration| ≤ 30
    Phase 3  (→ BODY_DOUBLE_LOOSE_S)
        any community  + work_mode-compat + |Δduration| ≤ 30
    Phase 4  (BODY_DOUBLE_LOOSE_S+)
        any community  + any work_mode    + any duration

The "min_wait_s" of each phase applies to the PARTNER's wait time, not
the requester's. So a fresh requester benefits from a stranded waiter
who's already past the threshold — fairness for whoever has been
waiting longest.

work_mode-compat: matches if same value OR either side picked "any".
"any" pairs with everything; named modes only pair with same or "any".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.body_double.models import PoolTicket


def _chattiness_compatible(qs, my_chattiness: str):
    """Filter `qs` to chattiness-compatible candidates.

    "flexible" matches anyone. Named values (chatty / quiet) only match
    the same value OR flexible. The chatty × quiet pair is excluded by
    omission.
    """
    if my_chattiness == PoolTicket.CHATTINESS_FLEXIBLE:
        return qs
    return qs.filter(chattiness__in=[my_chattiness, PoolTicket.CHATTINESS_FLEXIBLE])


def _friends_compatible(qs, ticket: PoolTicket):
    """Apply the friends-only hard rule in both directions.

    Friendship is mutual, so one friend-ids lookup serves both checks:
    my friends-only ticket may only see my friends; a candidate who set
    friends-only may only be seen by THEIR friends (= my friends, when
    the pair would be friends)."""
    from apps.accounts.models import Friendship  # lazy: avoid app-load cycles

    friends = Friendship.friend_ids(ticket.user)
    if ticket.friends_only:
        return qs.filter(user_id__in=friends)
    return qs.filter(Q(friends_only=False) | Q(user_id__in=friends))


def _work_mode_compatible(qs, my_work_mode: str):
    """Filter to work-mode-compatible candidates.

    "any" matches everything. Named modes match same-named or "any".
    """
    if my_work_mode == PoolTicket.WORK_MODE_ANY:
        return qs
    return qs.filter(Q(work_mode=my_work_mode) | Q(work_mode=PoolTicket.WORK_MODE_ANY))


@dataclass(frozen=True)
class _Phase:
    """One step of the loosening schedule.

    `min_wait_s`: how long the PARTNER must have been waiting before this
        phase will pair with them. Phase 1 = 0 (no wait required).
    `same_community`: only candidates in the requester's community.
    `same_work_mode`: only candidates whose work_mode is compatible.
    `max_duration_delta`: max |Δduration|. None = no limit.
    `require_timetable_fit`: only candidates whose timetable shows enough
        free time (checked per-candidate in Python via `_candidate_ok`,
        not in SQL). Unused by this strategy; `TimetableAwareStrategy`
        sets it on its stricter phases.
    """

    min_wait_s: int
    same_community: bool
    same_work_mode: bool
    max_duration_delta: int | None
    require_timetable_fit: bool = False


class PreferenceMatchingStrategy:
    """Pluggable matching strategy keyed off the requester's stated
    needs. Drops cleanly into the same `MatchingStrategy` Protocol used
    by `FIFOStrategy` and `CommunityFallbackStrategy`.

    Set `settings.BODY_DOUBLE_MATCHING_STRATEGY` to the dotted path of
    this class to enable. To roll back without redeploy, point it back
    at `apps.body_double.matching.community.CommunityFallbackStrategy`.
    """

    def find_match(self, ticket: PoolTicket) -> PoolTicket | None:
        """Walk the phases in order. Return the first compatible partner
        we find, or None if the pool is empty for this requester's
        preferences."""
        base_qs = (
            PoolTicket.objects.select_for_update()
            .filter(status=PoolTicket.STATUS_WAITING)
            .exclude(user_id=ticket.user_id)
        )
        # Filters applied to every phase. Chattiness has a hard
        # compatibility rule — we'd rather strand a user than pair them
        # with someone they explicitly don't want. Friends-only is
        # equally hard: a friends-only ticket pairs only with friends,
        # and a friends-only CANDIDATE is only visible to their friends.
        base_qs = _chattiness_compatible(base_qs, ticket.chattiness)
        base_qs = _friends_compatible(base_qs, ticket)

        now = timezone.now()
        for phase in self._phases():
            qs = base_qs
            if phase.same_community and ticket.community_id is not None:
                qs = qs.filter(community_id=ticket.community_id)
            if phase.same_work_mode:
                qs = _work_mode_compatible(qs, ticket.work_mode)
            if phase.max_duration_delta is not None:
                low = ticket.duration_minutes - phase.max_duration_delta
                high = ticket.duration_minutes + phase.max_duration_delta
                qs = qs.filter(duration_minutes__gte=low, duration_minutes__lte=high)
            if phase.min_wait_s > 0:
                cutoff = now - timedelta(seconds=phase.min_wait_s)
                qs = qs.filter(created_at__lte=cutoff)
            # Oldest-first, but give subclasses a per-candidate veto
            # (`_candidate_ok`) for checks that can't be expressed in SQL.
            # The slice caps how many vetoed candidates we'll step over so
            # a pathological pool can't stall the enqueue transaction.
            cap = getattr(settings, "BODY_DOUBLE_TIMETABLE_CANDIDATE_CAP", 5)
            for candidate in qs.order_by("created_at")[:cap]:
                if self._candidate_ok(ticket, candidate, phase):
                    return candidate
        return None

    def _candidate_ok(self, ticket: PoolTicket, candidate: PoolTicket, phase: _Phase) -> bool:
        """Per-candidate hook for checks SQL can't do. Base strategy
        accepts everyone — behaviour is identical to the pre-hook
        `.first()` implementation."""
        return True

    def _phases(self) -> list[_Phase]:
        """The four-phase loosening schedule. Pulled from settings so
        deploys can tune without code changes."""
        strict_s = getattr(settings, "BODY_DOUBLE_STRICT_S", 30)
        fallback_s = getattr(settings, "BODY_DOUBLE_FALLBACK_S", 60)
        loose_s = getattr(settings, "BODY_DOUBLE_LOOSE_S", 120)
        return [
            # Phase 1 — perfect fit, no wait threshold
            _Phase(
                min_wait_s=0,
                same_community=True,
                same_work_mode=True,
                max_duration_delta=15,
            ),
            # Phase 2 — partner has waited STRICT_S; loosen duration
            _Phase(
                min_wait_s=strict_s,
                same_community=True,
                same_work_mode=True,
                max_duration_delta=30,
            ),
            # Phase 3 — partner has waited FALLBACK_S; drop community req
            _Phase(
                min_wait_s=fallback_s,
                same_community=False,
                same_work_mode=True,
                max_duration_delta=30,
            ),
            # Phase 4 — partner has waited LOOSE_S; anything compatible
            _Phase(
                min_wait_s=loose_s,
                same_community=False,
                same_work_mode=False,
                max_duration_delta=None,
            ),
        ]
