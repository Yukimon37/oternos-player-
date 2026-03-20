"""
controllers/queue.py — OTERNOS PLAYER
QueueController — owns queue state and all queue manipulation logic.

Extracted from VoidPlayer. The two queue lists (auto + manual) and
queue_pos previously lived directly on VoidPlayer as self.queue,
self._manual_queue, self.queue_pos. VoidPlayer now forwards to this
controller via properties so all existing call-sites keep working.
"""

from __future__ import annotations

import sys
from typing import Optional


class QueueController:
    """
    Owns:
        auto     — the current ordered play queue (list of lib_idx ints)
        pos      — index into auto pointing at the currently playing track
        manual   — user-added "up next" tracks drained before auto advances

    All methods that previously lived on VoidPlayer as _queue_*,
    _clear_queue, _add_to_queue, _play_single are re-implemented here
    and delegate back to app for UI updates and playback triggering.
    """

    def __init__(self, app):
        self._app = app
        self.auto: list[int] = []      # replaces self.queue
        self.pos: int = -1             # replaces self.queue_pos
        self.manual: list[int] = []    # replaces self._manual_queue

    # ── Basic operations ─────────────────────────────────────────────────────

    def enqueue(self, lib_idx: int) -> None:
        """
        Add a track to the manual (Up Next) queue.
        If nothing is playing yet, start immediately.
        Replaces VoidPlayer._add_to_queue.
        """
        self.manual.append(lib_idx)
        app = self._app
        if self.pos < 0 and not app.engine.is_playing:
            self.auto = list(self.manual)
            self.pos = 0
            app._play_item(0)
        app._set_status("QUEUED")
        if getattr(app, "view", "") == "queue":
            app._refresh_queue()

    def play_single(self, lib_idx: int) -> None:
        """
        Replace the queue with a single track and play it immediately.
        Replaces VoidPlayer._play_single.
        """
        self.auto = [lib_idx]
        self.pos = 0
        self._app._play_item(0)

    def set_from_display(self, display_indices: list[int], start_pos: int) -> None:
        """
        Set the auto queue from the current library view display order
        and start playing at start_pos.
        Called when the user double-clicks a track in the library.
        """
        self.auto = list(display_indices)
        self.pos = start_pos
        self._app._play_item(self.pos, force=True)

    def clear_all(self) -> None:
        """Clear both auto and manual queues. Replaces VoidPlayer._clear_queue."""
        self.auto = []
        self.manual = []
        self.pos = -1
        self._app._refresh_queue()

    def clear_manual(self) -> None:
        """Replaces VoidPlayer._clear_manual_queue."""
        self.manual = []
        self._app._refresh_queue()

    # ── Item activation (double-click in queue view) ─────────────────────────

    def activate(self, section: str, idx: int) -> None:
        """
        Double-click a queue row to play it.
        Replaces VoidPlayer._queue_item_activate.
        section: "manual" | "auto"
        """
        app = self._app
        if section == "manual":
            if 0 <= idx < len(self.manual):
                li = self.manual.pop(idx)
                insert_at = (self.pos + 1) if self.pos >= 0 else 0
                self.auto.insert(insert_at, li)
                self.pos = insert_at
                app._play_item(self.pos, force=True)
                app._refresh_queue()
        else:
            app._play_item(idx, force=True)
            app._refresh_queue()

    # ── Removal ──────────────────────────────────────────────────────────────

    def remove(self, section: str, idx: int) -> None:
        """
        Right-click remove a track from the queue.
        Replaces VoidPlayer._queue_remove.
        """
        app = self._app
        if section == "manual":
            if 0 <= idx < len(self.manual):
                self.manual.pop(idx)
                app._refresh_queue()
        else:
            if 0 <= idx < len(self.auto):
                if idx < self.pos:
                    self.pos -= 1
                elif idx == self.pos:
                    self.pos = max(0, self.pos - 1)
                self.auto.pop(idx)
                app._refresh_queue()

    # ── Reorder (drag-and-drop in queue view) ────────────────────────────────

    def reorder(self, section: str, from_idx: int, to_idx: int) -> None:
        """
        Move a track within a queue section.
        Replaces VoidPlayer._queue_reorder.
        """
        lst = self.manual if section == "manual" else self.auto
        if from_idx < 0 or from_idx >= len(lst):
            return
        to_idx = max(0, min(to_idx, len(lst) - 1))
        if from_idx == to_idx:
            return

        item = lst.pop(from_idx)
        lst.insert(to_idx, item)

        # Keep pos pointing at the same track after reorder
        if section == "auto":
            p = self.pos
            if from_idx == p:
                self.pos = to_idx
            elif from_idx < p <= to_idx:
                self.pos -= 1
            elif to_idx <= p < from_idx:
                self.pos += 1

        self._app._refresh_queue()

    # ── Navigation helpers (used by PlaybackController / _next / _prev) ──────

    def next_index(self, shuffle: bool, repeat_mode: str) -> Optional[int]:
        """
        Return the next queue position to play, respecting shuffle/repeat.
        Returns None if the queue is exhausted.
        """
        import random
        if not self.auto:
            return None
        if repeat_mode == "one":
            return self.pos
        if shuffle and len(self.auto) > 1:
            choices = [i for i in range(len(self.auto)) if i != self.pos]
            return random.choice(choices)
        next_pos = self.pos + 1
        if next_pos >= len(self.auto):
            if repeat_mode == "all":
                return 0
            return None  # queue exhausted
        return next_pos

    def prev_index(self) -> Optional[int]:
        """Return the previous queue position, or None if at start."""
        if not self.auto:
            return None
        return (self.pos - 1) % len(self.auto)

    def drain_manual(self) -> Optional[int]:
        """
        If the manual queue has items, pop the first one, insert it into
        auto just after the current position, and return the new pos.
        Returns None if manual queue is empty.
        """
        if not self.manual:
            return None
        lib_idx = self.manual.pop(0)
        insert_at = (self.pos + 1) if self.pos >= 0 else 0
        self.auto.insert(insert_at, lib_idx)
        self.pos = insert_at
        return self.pos
