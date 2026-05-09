"""
discord_bridge.py — OTERNOS PLAYER

DiscordRuntimeBridge: thin read-only bridge between the Discord bot and the
running player process.  The player writes a JSON snapshot to a well-known
file on disk; this class reads it and exposes the data through a lightweight
snapshot() call.

The bot uses two fields from the snapshot:
  • is_live  (bool)  — True when the player is running and the file is fresh
  • volume   (float) — current playback volume in [0.0, 1.0]

When the runtime file is absent, stale, or unreadable the snapshot falls back
to is_live=False / volume=1.0 so the bot continues operating normally.
"""

from __future__ import annotations

from pathlib import Path

try:
    from .core.runtime_state import (
        DEFAULT_RUNTIME_FILE,
        RuntimeSnapshot,
        load_runtime_snapshot,
        runtime_file_marker,
    )
except ImportError:
    from oternos.core.runtime_state import (
        DEFAULT_RUNTIME_FILE,
        RuntimeSnapshot,
        load_runtime_snapshot,
        runtime_file_marker,
    )


class DiscordRuntimeBridge:
    """
    Read-only bridge between the Discord bot and the player runtime.

    Parameters
    ----------
    runtime_file:
        Path to the JSON snapshot written by the player.  Defaults to
        ``~/.voidplayer_runtime.json`` (the same default used by the player).
    command_file:
        Path to the command file used for bot → player IPC.  Stored for
        future use; not read by this class.
    """

    def __init__(
        self,
        runtime_file: str | Path | None = None,
        command_file: str | Path | None = None,
    ) -> None:
        self._runtime_file: Path = (
            Path(runtime_file).expanduser() if runtime_file else DEFAULT_RUNTIME_FILE
        )
        self._command_file: Path | None = (
            Path(command_file).expanduser() if command_file else None
        )
        # Cache the last marker so callers can skip re-reading when nothing changed.
        self._last_marker: tuple[bool, int] = (False, 0)
        self._last_snapshot: RuntimeSnapshot | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def snapshot(self) -> RuntimeSnapshot:
        """
        Return the latest :class:`~oternos.core.runtime_state.RuntimeSnapshot`.

        The snapshot is re-read from disk only when the file has changed
        (detected via mtime).  If the file is missing, stale (older than
        8 seconds), or unreadable the returned snapshot has ``is_live=False``
        and ``volume=1.0``.
        """
        marker = runtime_file_marker(self._runtime_file)
        if marker != self._last_marker or self._last_snapshot is None:
            self._last_marker = marker
            self._last_snapshot = load_runtime_snapshot(self._runtime_file)
        return self._last_snapshot
