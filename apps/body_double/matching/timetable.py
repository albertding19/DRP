"""Timetable-aware matchmaking.

`PreferenceMatchingStrategy` with one extra dimension: does the
candidate's timetable (their `apps.tasks` day plan) actually show enough
free time for the session? A candidate who queued up "for 60 minutes"
but has a lecture in 10 isn't a good partner.

Like work mode, the timetable check is a SOFT rule — required in phases
1–3, dropped at phase 4 — so a stale timetable can only delay a match,
never strand a user. Chattiness remains the one hard rule.

Two asymmetries, both deliberate:
  - Only the CANDIDATE's timetable is checked. The requester clicked
    "match me now" knowing their own schedule; explicit intent wins.
  - Silence is freedom: an empty timetable, or a request outside the
    planning work window, reads as fully free (see
    `availability.free_minutes_from`). Most users won't maintain a
    timetable and must match exactly as before.

Enable via settings:
    BODY_DOUBLE_MATCHING_STRATEGY = "apps.body_double.matching.timetable.TimetableAwareStrategy"
"""

from __future__ import annotations

from dataclasses import replace

from apps.body_double.models import PoolTicket

from .preferences import PreferenceMatchingStrategy, _Phase


class TimetableAwareStrategy(PreferenceMatchingStrategy):
    """Preference matching + "does the candidate actually have time?"."""

    def _phases(self) -> list[_Phase]:
        phases = super()._phases()
        # Require timetable fit on every phase except the last-resort one.
        return [replace(p, require_timetable_fit=True) for p in phases[:-1]] + phases[-1:]

    def _candidate_ok(self, ticket: PoolTicket, candidate: PoolTicket, phase: _Phase) -> bool:
        if not phase.require_timetable_fit:
            return True
        # Same "both leave when the shorter user is done" rule as the
        # session's agreed duration — the candidate only needs time for
        # the overlap, not for the requester's full ask.
        agreed = min(ticket.duration_minutes, candidate.duration_minutes)
        from apps.body_double.availability import free_minutes_from  # lazy: model imports inside

        return free_minutes_from(candidate.user) >= agreed
