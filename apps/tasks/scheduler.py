"""Pure scheduling functions — slot math, no Django imports.

The planner is split into two functions so it's easy to test:

  `free_slots`  — given the work window, "now", and a list of busy
                  intervals, returns the gaps available for placement.
  `place_tasks` — greedy walk: for each task in input order, find the
                  first slot with enough remaining capacity and place
                  it; advance the in-slot cursor by task duration +
                  transition. Tasks that don't fit anywhere come back as
                  leftovers.

No DB access here — callers pass in `BusyInterval` dataclasses and
`TaskInput` dataclasses (the bits of `Task` the scheduler cares about),
and receive `Placement` rows back. Service layer is responsible for
turning those into bulk-updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Slot:
    """A contiguous free interval. `end` is exclusive."""

    start: datetime
    end: datetime

    @property
    def length_minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass(frozen=True)
class BusyInterval:
    """An occupied interval the planner must avoid. `end` is exclusive."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class TaskInput:
    """The bits of a Task the scheduler needs. Decoupled from Django so
    `scheduler.py` is a pure module."""

    id: int
    remaining_minutes: int


@dataclass(frozen=True)
class Placement:
    """One scheduled task: which task, and when it runs."""

    task_id: int
    start: datetime
    end: datetime


def _union_intervals(intervals: list[BusyInterval]) -> list[BusyInterval]:
    """Merge overlapping intervals so the slot computation sees disjoint
    occupied ranges. Input order doesn't matter; output is sorted."""
    if not intervals:
        return []
    sorted_iv = sorted(intervals, key=lambda iv: iv.start)
    merged: list[BusyInterval] = [sorted_iv[0]]
    for iv in sorted_iv[1:]:
        last = merged[-1]
        if iv.start <= last.end:
            # Overlap (or touching) — extend the previous interval.
            if iv.end > last.end:
                merged[-1] = BusyInterval(start=last.start, end=iv.end)
        else:
            merged.append(iv)
    return merged


def free_slots(
    *,
    now: datetime,
    work_start: datetime,
    work_end: datetime,
    busy: list[BusyInterval],
) -> list[Slot]:
    """Return gaps in [max(now, work_start), work_end] not covered by busy.

    Busy intervals outside the window are ignored. Overlapping busy
    intervals are unioned. If `now >= work_end`, returns `[]`.
    """
    window_start = max(now, work_start)
    if window_start >= work_end:
        return []

    # Clip busy intervals to the window and union them.
    clipped: list[BusyInterval] = []
    for iv in busy:
        s = max(iv.start, window_start)
        e = min(iv.end, work_end)
        if s < e:
            clipped.append(BusyInterval(start=s, end=e))
    unioned = _union_intervals(clipped)

    slots: list[Slot] = []
    cursor = window_start
    for iv in unioned:
        if cursor < iv.start:
            slots.append(Slot(start=cursor, end=iv.start))
        cursor = max(cursor, iv.end)
    if cursor < work_end:
        slots.append(Slot(start=cursor, end=work_end))
    return slots


def place_tasks(
    *,
    ordered: list[TaskInput],
    slots: list[Slot],
    transition_minutes: int = 0,
) -> tuple[list[Placement], list[int]]:
    """Greedy placement of `ordered` tasks into `slots`.

    For each task, walk `slots` left-to-right. Inside each slot, maintain
    a cursor; place the task if `cursor + remaining_minutes <= slot.end`.
    After placing, advance cursor by `remaining_minutes + transition_minutes`
    — but NOT past the slot end. If the task doesn't fit, try the next
    slot. Anything that doesn't fit anywhere goes to leftovers.

    Transition time is NOT applied after the last task in a slot — it
    only adds gap between consecutive in-slot tasks.

    Returns `(placements, leftover_task_ids)`.
    """
    # Per-slot cursors track how far we've filled each slot.
    cursors: dict[int, datetime] = {i: s.start for i, s in enumerate(slots)}
    placements: list[Placement] = []
    leftovers: list[int] = []
    for task in ordered:
        if task.remaining_minutes <= 0:
            # Already done — nothing to schedule. Skip silently.
            continue
        placed = False
        for i, slot in enumerate(slots):
            cursor = cursors[i]
            task_end = cursor + timedelta(minutes=task.remaining_minutes)
            if task_end <= slot.end:
                placements.append(Placement(task_id=task.id, start=cursor, end=task_end))
                # Advance the cursor by the task + transition. Clamp to
                # slot.end so the next iteration sees the slot as full
                # rather than overflowing.
                next_cursor = task_end + timedelta(minutes=transition_minutes)
                cursors[i] = min(next_cursor, slot.end)
                placed = True
                break
        if not placed:
            leftovers.append(task.id)
    return placements, leftovers
