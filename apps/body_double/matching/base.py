"""Matching-strategy Protocol — the pluggable extension point for how
two pool tickets get paired.

The services layer instantiates whatever class
`settings.BODY_DOUBLE_MATCHING_STRATEGY` points to and calls `find_match`.
Future strategies (tag-filtered, blocklist-aware, Pomodoro-length, focus-
mode) implement the same Protocol and are selected by flipping the env
var — no changes to views / services / templates needed.

See `apps/body_double/matching/fifo.py` for the MVP implementation.
"""

from __future__ import annotations

from typing import Protocol

from apps.body_double.models import PoolTicket


class MatchingStrategy(Protocol):
    """Decide who, if anyone, this ticket should be paired with.

    Implementations should use `select_for_update` inside an outer
    transaction so concurrent enqueues don't both claim the same partner.
    """

    def find_match(self, ticket: PoolTicket) -> PoolTicket | None:  # pragma: no cover
        """Return another waiting ticket to pair with `ticket`, or None
        if no suitable partner exists in the pool right now."""
        ...
