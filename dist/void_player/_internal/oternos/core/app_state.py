"""
app_state.py - read-only app snapshot helpers for non-Tk UI shells.

The legacy Tkinter player remains the runtime owner of playback and mutation.
This module only reads the existing `.voidplayer.json` shape and returns a small
snapshot that the Qt prototype can display safely.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .library import filter_existing_tracks
from .settings import merge_settings


DEFAULT_DATA_FILE = Path.home() / ".voidplayer.json"


@dataclass(frozen=True)
class TrackSummary:
    title: str
    artist: str
    album: str
    source: str
    duration: str
    path: str
    art_path: str = ""
    art_url: str = ""


@dataclass(frozen=True)
class SourceSummary:
    name: str
    state: str
    healthy: bool
    detail: str = ""
    action: str = ""
    view_key: str = ""


@dataclass(frozen=True)
class PlaylistSummary:
    name: str
    count: int
    tracks: tuple[TrackSummary, ...]


@dataclass(frozen=True)
class AppSnapshot:
    data_file: str
    data_file_exists: bool
    library_count: int
    playlist_count: int
    history_count: int
    shuffle: bool
    repeat_mode: str
    active_theme: str
    flow_mode: bool
    autoplay: bool
    now_track: TrackSummary | None
    recent_tracks: tuple[TrackSummary, ...]
    library_preview: tuple[TrackSummary, ...]
    queue_preview: tuple[TrackSummary, ...]
    playlist_names: tuple[str, ...]
    playlist_previews: tuple[PlaylistSummary, ...]
    sources: tuple[SourceSummary, ...]
    error: str = ""


def load_app_snapshot(data_file: str | Path | None = None) -> AppSnapshot:
    """Read saved OTERNOS state without importing or constructing the Tk app."""
    path = Path(data_file) if data_file is not None else DEFAULT_DATA_FILE
    empty = _empty_snapshot(path, data_file_exists=path.exists())
    if not path.exists():
        return empty

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _empty_snapshot(path, data_file_exists=True, error=str(exc))

    if not isinstance(raw, dict):
        return _empty_snapshot(path, data_file_exists=True, error="Saved app state is not a JSON object.")

    library = filter_existing_tracks(raw.get("library", []))
    history = _dict_list(raw.get("history", []))
    playlists = raw.get("playlists", {})
    if not isinstance(playlists, dict):
        playlists = {}
    settings = merge_settings(raw.get("settings", {}))

    library_preview = _track_summaries(library, limit=48)
    recent = _history_summaries(list(reversed(history)), library, limit=5)
    now_track = recent[0] if recent else (library_preview[0] if library_preview else None)
    queue_preview = tuple(library_preview[:3])
    playlist_names = tuple(str(name) for name in playlists.keys())
    playlist_previews = _playlist_summaries(playlists, library, limit=12, track_limit=3)

    return AppSnapshot(
        data_file=str(path),
        data_file_exists=True,
        library_count=len(library),
        playlist_count=len(playlists),
        history_count=len(history),
        shuffle=bool(raw.get("shuffle", False)),
        repeat_mode=str(raw.get("repeat_mode", "off") or "off"),
        active_theme=str(settings.get("active_theme", "void") or "void"),
        flow_mode=bool(settings.get("flow_mode", False)),
        autoplay=bool(settings.get("autoplay", True)),
        now_track=now_track,
        recent_tracks=tuple(recent or library_preview),
        library_preview=library_preview,
        queue_preview=queue_preview,
        playlist_names=playlist_names,
        playlist_previews=playlist_previews,
        sources=_source_summaries(library, raw, settings),
    )


def snapshot_file_marker(data_file: str | Path | None = None) -> tuple[bool, int]:
    """Return a cheap marker for detecting saved-state file changes."""
    path = Path(data_file) if data_file is not None else DEFAULT_DATA_FILE
    try:
        stat = path.stat()
    except OSError:
        return (False, 0)
    return (True, stat.st_mtime_ns)


def _empty_snapshot(path: Path, *, data_file_exists: bool, error: str = "") -> AppSnapshot:
    return AppSnapshot(
        data_file=str(path),
        data_file_exists=data_file_exists,
        library_count=0,
        playlist_count=0,
        history_count=0,
        shuffle=False,
        repeat_mode="off",
        active_theme="void",
        flow_mode=False,
        autoplay=True,
        now_track=None,
        recent_tracks=(),
        library_preview=(),
        queue_preview=(),
        playlist_names=(),
        playlist_previews=(),
        sources=(
            SourceSummary("LOCAL", "EMPTY", False, "No saved local tracks found.", "OPEN LIBRARY", "library"),
            SourceSummary("SOUNDCLOUD", "READY", True, "Legacy stream search is available.", "OPEN STREAM", "soundcloud"),
            SourceSummary("YOUTUBE", "CACHE READY", True, "Legacy stream cache is ready.", "OPEN STREAM", "youtube"),
            SourceSummary("ARCHIVE", "READY", True, "Public-domain archive search is ready.", "OPEN STREAM", "archive"),
            SourceSummary("NETSTREAM", "OFFLINE", False, "Local network handoff opens in the legacy player.", "OPEN NET", "netstream"),
        ),
        error=error,
    )


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _track_summaries(tracks: list[dict[str, Any]], *, limit: int) -> tuple[TrackSummary, ...]:
    return tuple(_track_summary(track) for track in tracks[:limit])


def _history_summaries(
    tracks: list[dict[str, Any]],
    library: list[dict[str, Any]],
    *,
    limit: int,
) -> tuple[TrackSummary, ...]:
    summaries: list[TrackSummary] = []
    for track in tracks[:limit]:
        summaries.append(_track_summary(_merge_history_track(track, library)))
    return tuple(summaries)


def _playlist_summaries(
    playlists: dict[str, Any],
    library: list[dict[str, Any]],
    *,
    limit: int,
    track_limit: int,
) -> tuple[PlaylistSummary, ...]:
    summaries: list[PlaylistSummary] = []
    for name, value in list(playlists.items())[:limit]:
        if not isinstance(value, list):
            indices: list[int] = []
        else:
            indices = []
            for item in value:
                try:
                    indices.append(int(item))
                except (TypeError, ValueError):
                    continue
        tracks = []
        for index in indices:
            if 0 <= index < len(library):
                tracks.append(_track_summary(library[index]))
            if len(tracks) >= track_limit:
                break
        summaries.append(
            PlaylistSummary(
                name=str(name),
                count=sum(1 for index in indices if 0 <= index < len(library)),
                tracks=tuple(tracks),
            )
        )
    return tuple(summaries)


def _merge_history_track(track: dict[str, Any], library: list[dict[str, Any]]) -> dict[str, Any]:
    match = _matching_library_track(track, library)
    if match is None:
        return track
    merged = dict(match)
    for key in ("title", "artist", "album", "source", "duration", "length"):
        if track.get(key):
            merged[key] = track[key]
    merged["path"] = match.get("path", "")
    if match.get("art_path"):
        merged["art_path"] = match.get("art_path")
    if match.get("art_url"):
        merged["art_url"] = match.get("art_url")
    return merged


def _matching_library_track(track: dict[str, Any], library: list[dict[str, Any]]) -> dict[str, Any] | None:
    path = _path_key(track.get("path"))
    title = _text_key(track.get("title") or track.get("name"))
    artist = _text_key(track.get("artist") or track.get("username"))
    for candidate in library:
        if path and _path_key(candidate.get("path")) == path:
            return candidate
    if title and artist:
        for candidate in library:
            if _text_key(candidate.get("title") or candidate.get("name")) == title and _text_key(candidate.get("artist") or candidate.get("username")) == artist:
                return candidate
    if title:
        for candidate in library:
            if _text_key(candidate.get("title") or candidate.get("name")) == title:
                return candidate
    return None


def _track_summary(track: dict[str, Any]) -> TrackSummary:
    path = str(track.get("path", "") or "")
    title = str(track.get("title", "") or "").strip()
    if not title and path:
        title = Path(path).stem
    artist = str(track.get("artist", "") or "").strip()
    album = str(track.get("album", "") or "").strip()
    source = str(track.get("source", "") or "").strip() or _source_from_path(path)
    duration = _format_duration(track.get("duration") or track.get("length"))
    return TrackSummary(
        title=title or "Unknown Track",
        artist=artist or "Unknown Artist",
        album=album or "Unknown Album",
        source=source,
        duration=duration,
        path=path,
        art_path=str(track.get("art_path", "") or ""),
        art_url=str(track.get("art_url", "") or ""),
    )


def _path_key(value: Any) -> str:
    return str(value or "").replace("\\", "/").casefold()


def _text_key(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _source_from_path(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return "Stream"
    if path:
        return "Local Library"
    return "Unknown"


def _format_duration(value: Any) -> str:
    if isinstance(value, str) and ":" in value:
        parts = value.split(":")
        if len(parts) == 2 and all(part.isdigit() for part in parts):
            return value
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return "--:--"
    if seconds < 0:
        return "--:--"
    minutes, remainder = divmod(seconds, 60)
    return f"{minutes}:{remainder:02d}"


def _source_summaries(
    library: list[dict[str, Any]],
    raw: dict[str, Any],
    settings: dict[str, Any],
) -> tuple[SourceSummary, ...]:
    soundcloud_count = len(_dict_list(raw.get("sc_favorites", [])))
    local_state = f"{len(library)} {_plural('TRACK', len(library))}" if library else "EMPTY"
    sc_state = f"{soundcloud_count} SAVED" if soundcloud_count else "SEARCH READY"
    yt_has_cookies = bool(settings.get("yt_cookies_path"))
    return (
        SourceSummary(
            "LOCAL",
            local_state,
            bool(library),
            "Saved local audio library.",
            "OPEN LIBRARY",
            "library",
        ),
        SourceSummary(
            "SOUNDCLOUD",
            sc_state,
            True,
            f"{soundcloud_count} saved favorites available." if soundcloud_count else "Legacy stream search is available.",
            "OPEN STREAM",
            "soundcloud",
        ),
        SourceSummary(
            "YOUTUBE",
            "COOKIES SET" if yt_has_cookies else "CACHE READY",
            True,
            "Cookies file configured for restricted videos." if yt_has_cookies else "Legacy YouTube cache/search is ready.",
            "OPEN STREAM",
            "youtube",
        ),
        SourceSummary(
            "ARCHIVE",
            "READY",
            True,
            "Public-domain archive search is ready.",
            "OPEN STREAM",
            "archive",
        ),
        SourceSummary(
            "NETSTREAM",
            "OFFLINE",
            False,
            "Local network handoff opens in the legacy player.",
            "OPEN NET",
            "netstream",
        ),
    )


def _plural(word: str, count: int) -> str:
    return word if count == 1 else f"{word}S"
