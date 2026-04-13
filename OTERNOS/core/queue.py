"""
queue.py - UI-independent queue decision helpers.

Phase 1C keeps this deliberately narrow: the legacy Tkinter player still owns
its queue lists, but next/previous decisions live here so future UIs can reuse
the same playback order rules.
"""

from __future__ import annotations

from collections.abc import Callable, MutableSequence, Sequence
from typing import TypeVar


T = TypeVar("T")


def promote_manual_next(
    queue: MutableSequence[T],
    manual_queue: MutableSequence[T],
    queue_pos: int,
) -> int | None:
    """
    Move the next manual item into the auto queue immediately after current.

    Returns the inserted playback position, or None when there is no manual item.
    This preserves the legacy behavior used by VoidPlayer._next().
    """
    if not manual_queue:
        return None
    next_item = manual_queue.pop(0)
    insert_at = (queue_pos + 1) if queue_pos >= 0 else 0
    queue.insert(insert_at, next_item)
    return insert_at


def choose_next_position(
    queue_len: int,
    queue_pos: int,
    *,
    shuffle: bool = False,
    chooser: Callable[[Sequence[int]], int] | None = None,
) -> int | None:
    """Return the next queue position, or None for an empty queue."""
    if queue_len <= 0:
        return None
    if shuffle:
        if queue_len > 1:
            choices = [i for i in range(queue_len) if i != queue_pos]
            pick = chooser or (lambda items: items[0])
            return pick(choices)
        return 0
    return (queue_pos + 1) % queue_len


def choose_previous_position(queue_len: int, queue_pos: int) -> int | None:
    """Return the previous queue position, or None for an empty queue."""
    if queue_len <= 0:
        return None
    return (queue_pos - 1) % queue_len


def clear_all(queue: MutableSequence[T], manual_queue: MutableSequence[T]) -> int:
    """Clear both queue tiers and return the reset queue position."""
    queue.clear()
    manual_queue.clear()
    return -1


def clear_manual(manual_queue: MutableSequence[T]) -> None:
    """Clear only the manual/up-next queue."""
    manual_queue.clear()


def reorder_items(
    items: MutableSequence[T],
    from_idx: int,
    to_idx: int,
) -> tuple[bool, int]:
    """
    Move one item within a queue-like sequence.

    Returns (changed, final_to_idx). Invalid inputs return (False, to_idx).
    """
    if from_idx < 0 or from_idx >= len(items):
        return False, to_idx
    to_idx = max(0, min(to_idx, len(items) - 1))
    if from_idx == to_idx:
        return False, to_idx
    item = items.pop(from_idx)
    items.insert(to_idx, item)
    return True, to_idx


def adjust_position_after_reorder(queue_pos: int, from_idx: int, to_idx: int) -> int:
    """Adjust current auto-queue position after an auto-queue reorder."""
    if from_idx == queue_pos:
        return to_idx
    if from_idx < queue_pos <= to_idx:
        return queue_pos - 1
    if to_idx <= queue_pos < from_idx:
        return queue_pos + 1
    return queue_pos


def activate_manual_item(
    queue: MutableSequence[T],
    manual_queue: MutableSequence[T],
    idx: int,
    queue_pos: int,
) -> int | None:
    """Move a chosen manual item into the auto queue and return its position."""
    if idx < 0 or idx >= len(manual_queue):
        return None
    item = manual_queue.pop(idx)
    insert_at = (queue_pos + 1) if queue_pos >= 0 else 0
    queue.insert(insert_at, item)
    return insert_at


def remove_manual_item(manual_queue: MutableSequence[T], idx: int) -> bool:
    """Remove a manual queue item by index."""
    if idx < 0 or idx >= len(manual_queue):
        return False
    manual_queue.pop(idx)
    return True


def remove_auto_item(
    queue: MutableSequence[T],
    idx: int,
    queue_pos: int,
) -> tuple[bool, int]:
    """Remove an auto queue item and return (removed, adjusted_queue_pos)."""
    if idx < 0 or idx >= len(queue):
        return False, queue_pos
    if idx < queue_pos:
        queue_pos -= 1
    elif idx == queue_pos:
        queue_pos = max(0, queue_pos - 1)
    queue.pop(idx)
    if not queue:
        queue_pos = -1
    return True, queue_pos


def add_manual_item(
    manual_queue: MutableSequence[T],
    item: T,
    queue_pos: int,
    *,
    is_playing: bool,
) -> bool:
    """
    Append an item to the manual queue.

    Returns True when the legacy player should start playback immediately.
    """
    manual_queue.append(item)
    return queue_pos < 0 and not is_playing
