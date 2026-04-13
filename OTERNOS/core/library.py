"""
library.py - UI-independent library helpers.

Phase 1E starts with pure helpers for saved-track filtering and index remapping.
The legacy Tkinter app still owns imports, dialogs, playback state, and UI
refreshes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def filter_existing_tracks(tracks: Any) -> list[dict[str, Any]]:
    """Return saved track dicts whose `path` still exists on disk."""
    if not isinstance(tracks, list):
        return []
    existing: list[dict[str, Any]] = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        path = track.get("path")
        if path and Path(path).exists():
            existing.append(track)
    return existing


def remap_indices_after_library_removal(
    indices: list[int],
    removed_index: int,
) -> list[int]:
    """Drop a removed library index and shift later indices down by one."""
    return [
        idx if idx < removed_index else idx - 1
        for idx in indices
        if idx != removed_index
    ]


def remap_playlists_after_library_removal(
    playlists: dict[str, list[int]],
    removed_index: int,
) -> dict[str, list[int]]:
    """Return playlists with indices remapped after a library item removal."""
    return {
        name: remap_indices_after_library_removal(list(indices), removed_index)
        for name, indices in playlists.items()
    }


def add_index_to_playlist(
    playlists: dict[str, list[int]],
    playlist_name: str,
    library_index: int,
) -> str:
    """Add a library index to a saved playlist.

    Returns ``"added"``, ``"existing"``, or ``"missing"``.
    """
    if not playlist_name or playlist_name not in playlists:
        return "missing"
    indices = playlists.get(playlist_name)
    if not isinstance(indices, list):
        indices = []
        playlists[playlist_name] = indices
    if library_index in indices:
        return "existing"
    indices.append(library_index)
    return "added"


def adjust_queue_pos_after_library_removal(queue_pos: int, queue_len: int) -> int:
    """Preserve legacy queue-position clamping after queue index remapping."""
    if queue_pos >= queue_len:
        return max(-1, queue_len - 1)
    return queue_pos
