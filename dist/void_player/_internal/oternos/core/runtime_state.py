"""
runtime_state.py - live read-only status bridge for external UI shells.

The legacy Tkinter player writes this snapshot while it is running. New shells
can read it, but must not use it as a command channel.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any


DEFAULT_RUNTIME_FILE = Path.home() / ".voidplayer_runtime.json"


@dataclass(frozen=True)
class RuntimeTrack:
    title: str
    artist: str
    album: str
    source: str
    path: str
    art_path: str = ""
    art_url: str = ""


@dataclass(frozen=True)
class RuntimeQueueItem:
    position: int
    is_current: bool
    track: RuntimeTrack


@dataclass(frozen=True)
class RuntimeCommandAck:
    command_id: str
    action: str
    ok: bool
    message: str
    handled_at: float


@dataclass(frozen=True)
class RuntimeSourceStatus:
    source: str
    query: str
    result_count: int
    status: str


@dataclass(frozen=True)
class RuntimeSourceResult:
    title: str
    artist: str
    source: str
    duration: str
    art_url: str = ""


@dataclass(frozen=True)
class RuntimeSnapshot:
    data_file: str
    data_file_exists: bool
    is_live: bool
    updated_at: float
    source: str
    status: str
    is_playing: bool
    is_paused: bool
    position: float
    duration: float
    volume: float
    track: RuntimeTrack | None
    queue_count: int = 0
    manual_queue_count: int = 0
    queue_position: int = -1
    queue_preview: tuple[RuntimeQueueItem, ...] = ()
    queue_paths: tuple[str, ...] = ()
    visualizer_bars: tuple[float, ...] = ()
    source_status: RuntimeSourceStatus | None = None
    source_results: tuple[RuntimeSourceResult, ...] = ()
    last_command: RuntimeCommandAck | None = None
    error: str = ""


def write_runtime_snapshot(payload: dict[str, Any], data_file: str | Path | None = None) -> None:
    """Atomically write the latest runtime state for read-only consumers."""
    path = Path(data_file) if data_file is not None else DEFAULT_RUNTIME_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dict(payload)
    data["updated_at"] = float(data.get("updated_at") or time.time())
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_runtime_snapshot(
    data_file: str | Path | None = None,
    *,
    max_age_s: float = 8.0,
) -> RuntimeSnapshot:
    """Read the latest runtime state and mark it stale when it is too old."""
    path = Path(data_file) if data_file is not None else DEFAULT_RUNTIME_FILE
    if not path.exists():
        return _empty_snapshot(path, data_file_exists=False)

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _empty_snapshot(path, data_file_exists=True, error=str(exc))

    if not isinstance(raw, dict):
        return _empty_snapshot(path, data_file_exists=True, error="Runtime state is not a JSON object.")

    updated_at = _float(raw.get("updated_at"), 0.0)
    is_live = updated_at > 0 and (time.time() - updated_at) <= max_age_s
    track_raw = raw.get("track")
    track = _track(track_raw) if isinstance(track_raw, dict) else None
    queue_preview = _queue_items(raw.get("queue_preview"))
    command_raw = raw.get("last_command")
    last_command = _command_ack(command_raw) if isinstance(command_raw, dict) else None
    source_raw = raw.get("source_status")
    source_status = _source_status(source_raw) if isinstance(source_raw, dict) else None
    source_results = _source_results(raw.get("source_results"))

    return RuntimeSnapshot(
        data_file=str(path),
        data_file_exists=True,
        is_live=is_live,
        updated_at=updated_at,
        source=str(raw.get("source", "none") or "none"),
        status=str(raw.get("status", "") or ""),
        is_playing=bool(raw.get("is_playing", False)),
        is_paused=bool(raw.get("is_paused", False)),
        position=max(0.0, _float(raw.get("position"), 0.0)),
        duration=max(0.0, _float(raw.get("duration"), 0.0)),
        volume=min(1.0, max(0.0, _float(raw.get("volume"), 0.0))),
        track=track,
        queue_count=max(0, _int(raw.get("queue_count"), 0)),
        manual_queue_count=max(0, _int(raw.get("manual_queue_count"), 0)),
        queue_position=_int(raw.get("queue_position"), -1),
        queue_preview=queue_preview,
        queue_paths=_string_tuple(raw.get("queue_paths")),
        visualizer_bars=_float_tuple(raw.get("visualizer_bars")),
        source_status=source_status,
        source_results=source_results,
        last_command=last_command,
    )


def runtime_file_marker(data_file: str | Path | None = None) -> tuple[bool, int]:
    """Return a cheap marker for detecting runtime-state file changes."""
    path = Path(data_file) if data_file is not None else DEFAULT_RUNTIME_FILE
    try:
        stat = path.stat()
    except OSError:
        return (False, 0)
    return (True, stat.st_mtime_ns)


def _empty_snapshot(path: Path, *, data_file_exists: bool, error: str = "") -> RuntimeSnapshot:
    return RuntimeSnapshot(
        data_file=str(path),
        data_file_exists=data_file_exists,
        is_live=False,
        updated_at=0.0,
        source="none",
        status="OFFLINE",
        is_playing=False,
        is_paused=False,
        position=0.0,
        duration=0.0,
        volume=0.0,
        track=None,
        queue_count=0,
        manual_queue_count=0,
        queue_position=-1,
        queue_preview=(),
        queue_paths=(),
        visualizer_bars=(),
        source_status=None,
        source_results=(),
        last_command=None,
        error=error,
    )


def _track(raw: dict[str, Any]) -> RuntimeTrack:
    source = str(raw.get("source", "") or "").strip() or "Unknown"
    return RuntimeTrack(
        title=str(raw.get("title", "") or "Unknown Track"),
        artist=str(raw.get("artist", "") or "Unknown Artist"),
        album=str(raw.get("album", "") or "Unknown Album"),
        source=source,
        path=str(raw.get("path", "") or ""),
        art_path=str(raw.get("art_path", "") or ""),
        art_url=str(raw.get("art_url", "") or ""),
    )


def _queue_items(value: Any) -> tuple[RuntimeQueueItem, ...]:
    if not isinstance(value, list):
        return ()
    items: list[RuntimeQueueItem] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        items.append(
            RuntimeQueueItem(
                position=_int(raw.get("position"), len(items)),
                is_current=bool(raw.get("is_current", False)),
                track=_track(raw),
            )
        )
    return tuple(items)


def _string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if item)


def _float_tuple(value: Any) -> tuple[float, ...]:
    if not isinstance(value, list):
        return ()
    items: list[float] = []
    for item in value:
        try:
            number = float(item)
        except (TypeError, ValueError):
            continue
        items.append(min(1.0, max(0.0, number)))
    return tuple(items)


def _command_ack(raw: dict[str, Any]) -> RuntimeCommandAck | None:
    command_id = str(raw.get("id", "") or "")
    action = str(raw.get("action", "") or "")
    if not command_id or not action:
        return None
    return RuntimeCommandAck(
        command_id=command_id,
        action=action,
        ok=bool(raw.get("ok", False)),
        message=str(raw.get("message", "") or ""),
        handled_at=_float(raw.get("handled_at"), 0.0),
    )


def _source_status(raw: dict[str, Any]) -> RuntimeSourceStatus:
    return RuntimeSourceStatus(
        source=str(raw.get("source", "") or ""),
        query=str(raw.get("query", "") or ""),
        result_count=max(0, _int(raw.get("result_count"), 0)),
        status=str(raw.get("status", "") or ""),
    )


def _source_results(value: Any) -> tuple[RuntimeSourceResult, ...]:
    if not isinstance(value, list):
        return ()
    results: list[RuntimeSourceResult] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        results.append(
            RuntimeSourceResult(
                title=str(raw.get("title", "") or "Unknown Result"),
                artist=str(raw.get("artist", "") or "Unknown Artist"),
                source=str(raw.get("source", "") or "Unknown Source"),
                duration=str(raw.get("duration", "") or "--:--"),
                art_url=str(raw.get("art_url", "") or ""),
            )
        )
    return tuple(results)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
