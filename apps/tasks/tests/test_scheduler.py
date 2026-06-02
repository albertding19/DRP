"""Pure unit tests for the scheduler — no DB, no Django imports.

These run fast (<100ms) because the scheduler doesn't touch the ORM.
"""

from __future__ import annotations

from datetime import datetime

from apps.tasks.scheduler import (
    BusyInterval,
    Slot,
    TaskInput,
    free_slots,
    place_tasks,
)


def _t(hour: int, minute: int = 0) -> datetime:
    """Naive datetime helper — TZ doesn't matter for the pure scheduler."""
    return datetime(2026, 6, 2, hour, minute, 0)


class TestFreeSlots:
    def test_clamps_start_to_now_when_now_after_work_start(self) -> None:
        slots = free_slots(now=_t(10, 30), work_start=_t(9), work_end=_t(21), busy=[])
        assert slots == [Slot(start=_t(10, 30), end=_t(21))]

    def test_clamps_start_to_work_start_when_now_before(self) -> None:
        slots = free_slots(now=_t(7), work_start=_t(9), work_end=_t(21), busy=[])
        assert slots == [Slot(start=_t(9), end=_t(21))]

    def test_empty_when_now_after_work_end(self) -> None:
        assert free_slots(now=_t(22), work_start=_t(9), work_end=_t(21), busy=[]) == []

    def test_subtracts_busy_intervals(self) -> None:
        slots = free_slots(
            now=_t(9),
            work_start=_t(9),
            work_end=_t(17),
            busy=[BusyInterval(start=_t(11), end=_t(12))],
        )
        assert slots == [
            Slot(start=_t(9), end=_t(11)),
            Slot(start=_t(12), end=_t(17)),
        ]

    def test_unions_overlapping_busy_intervals(self) -> None:
        slots = free_slots(
            now=_t(9),
            work_start=_t(9),
            work_end=_t(17),
            busy=[
                BusyInterval(start=_t(11), end=_t(13)),
                BusyInterval(start=_t(12), end=_t(14)),  # overlaps the first
            ],
        )
        assert slots == [
            Slot(start=_t(9), end=_t(11)),
            Slot(start=_t(14), end=_t(17)),
        ]

    def test_ignores_busy_outside_window(self) -> None:
        slots = free_slots(
            now=_t(9),
            work_start=_t(9),
            work_end=_t(17),
            busy=[
                BusyInterval(start=_t(7), end=_t(8)),  # before work
                BusyInterval(start=_t(20), end=_t(22)),  # after work
            ],
        )
        assert slots == [Slot(start=_t(9), end=_t(17))]

    def test_busy_partially_outside_clipped(self) -> None:
        slots = free_slots(
            now=_t(9),
            work_start=_t(9),
            work_end=_t(17),
            busy=[BusyInterval(start=_t(8), end=_t(10))],  # spills into window
        )
        assert slots == [Slot(start=_t(10), end=_t(17))]

    def test_busy_touching_window_end(self) -> None:
        # Busy block ending exactly at work_end — no trailing slot.
        slots = free_slots(
            now=_t(9),
            work_start=_t(9),
            work_end=_t(17),
            busy=[BusyInterval(start=_t(16), end=_t(17))],
        )
        assert slots == [Slot(start=_t(9), end=_t(16))]


class TestPlaceTasks:
    def test_greedy_fills_first_slot(self) -> None:
        placements, leftovers = place_tasks(
            ordered=[
                TaskInput(id=1, remaining_minutes=30),
                TaskInput(id=2, remaining_minutes=45),
            ],
            slots=[Slot(start=_t(9), end=_t(17))],
            transition_minutes=0,
        )
        assert leftovers == []
        assert placements[0].task_id == 1
        assert placements[0].start == _t(9)
        assert placements[0].end == _t(9, 30)
        assert placements[1].task_id == 2
        assert placements[1].start == _t(9, 30)
        assert placements[1].end == _t(10, 15)

    def test_exact_fit_slot(self) -> None:
        placements, leftovers = place_tasks(
            ordered=[TaskInput(id=1, remaining_minutes=60)],
            slots=[Slot(start=_t(9), end=_t(10))],
            transition_minutes=0,
        )
        assert leftovers == []
        assert placements == [type(placements[0])(task_id=1, start=_t(9), end=_t(10))]

    def test_transition_only_between_tasks(self) -> None:
        # 5-min transition between tasks; not added after the LAST task in
        # a slot. Two tasks of 30min in a 65min slot: 30 + 5 + 30 = 65 fits.
        placements, leftovers = place_tasks(
            ordered=[
                TaskInput(id=1, remaining_minutes=30),
                TaskInput(id=2, remaining_minutes=30),
            ],
            slots=[Slot(start=_t(9), end=_t(10, 5))],
            transition_minutes=5,
        )
        assert leftovers == []
        assert placements[0].start == _t(9)
        assert placements[0].end == _t(9, 30)
        # 5-min transition then the second task at 9:35.
        assert placements[1].start == _t(9, 35)
        assert placements[1].end == _t(10, 5)

    def test_skips_to_next_slot_when_too_big(self) -> None:
        # 90-min task; first slot is only 60 min, second is 120 min.
        placements, leftovers = place_tasks(
            ordered=[TaskInput(id=1, remaining_minutes=90)],
            slots=[
                Slot(start=_t(9), end=_t(10)),
                Slot(start=_t(11), end=_t(13)),
            ],
            transition_minutes=0,
        )
        assert leftovers == []
        assert placements[0].task_id == 1
        assert placements[0].start == _t(11)
        assert placements[0].end == _t(12, 30)

    def test_leftover_when_nothing_fits(self) -> None:
        placements, leftovers = place_tasks(
            ordered=[TaskInput(id=1, remaining_minutes=600)],
            slots=[Slot(start=_t(9), end=_t(10))],
            transition_minutes=0,
        )
        assert placements == []
        assert leftovers == [1]

    def test_zero_remaining_skipped_silently(self) -> None:
        # A "task" with 0 minutes remaining (already done) is skipped, not
        # placed, not in leftovers.
        placements, leftovers = place_tasks(
            ordered=[TaskInput(id=1, remaining_minutes=0)],
            slots=[Slot(start=_t(9), end=_t(17))],
            transition_minutes=0,
        )
        assert placements == []
        assert leftovers == []

    def test_no_slots_all_leftover(self) -> None:
        placements, leftovers = place_tasks(
            ordered=[
                TaskInput(id=1, remaining_minutes=30),
                TaskInput(id=2, remaining_minutes=45),
            ],
            slots=[],
            transition_minutes=0,
        )
        assert placements == []
        assert leftovers == [1, 2]

    def test_order_preserved(self) -> None:
        # `place_tasks` does not re-sort — caller's order is the schedule order.
        placements, _ = place_tasks(
            ordered=[
                TaskInput(id=99, remaining_minutes=10),
                TaskInput(id=1, remaining_minutes=10),
                TaskInput(id=50, remaining_minutes=10),
            ],
            slots=[Slot(start=_t(9), end=_t(17))],
            transition_minutes=0,
        )
        assert [p.task_id for p in placements] == [99, 1, 50]


class TestSlotProperties:
    def test_length_minutes(self) -> None:
        assert Slot(start=_t(9), end=_t(10, 30)).length_minutes == 90
        assert Slot(start=_t(9), end=_t(9)).length_minutes == 0
