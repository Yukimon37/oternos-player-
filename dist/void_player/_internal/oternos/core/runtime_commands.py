"""
runtime_commands.py - tiny command bridge from Qt shell to legacy player.

The Qt shell writes command requests. The legacy Tkinter player is the only
process allowed to execute them.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import time
from typing import Any
from uuid import uuid4


DEFAULT_COMMAND_FILE = Path.home() / ".voidplayer_command.json"
ALLOWED_COMMANDS = frozenset(
    {
        "toggle_play",
        "add_library_path_to_playlist",
        "add_library_path_to_queue",
        "next",
        "open_legacy_view",
        "previous",
        "play_library_path",
        "play_playlist",
        "play_queue_position",
        "play_source_result",
        "remove_queue_position",
        "seek_relative",
        "set_volume",
    }
)


@dataclass(frozen=True)
class RuntimeCommand:
    command_id: str
    action: str
    payload: dict[str, Any]
    created_at: float


def write_runtime_command(
    action: str,
    payload: dict[str, Any] | None = None,
    data_file: str | Path | None = None,
) -> RuntimeCommand:
    """Write a single command request for the running legacy player."""
    if action not in ALLOWED_COMMANDS:
        raise ValueError(f"Unsupported runtime command: {action}")
    command = RuntimeCommand(
        command_id=f"{int(time.time() * 1000)}-{uuid4().hex}",
        action=action,
        payload=dict(payload or {}),
        created_at=time.time(),
    )
    path = Path(data_file) if data_file is not None else DEFAULT_COMMAND_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(
        json.dumps(
            {
                "id": command.command_id,
                "action": command.action,
                "payload": command.payload,
                "created_at": command.created_at,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    tmp.replace(path)
    return command


def load_runtime_command(data_file: str | Path | None = None) -> RuntimeCommand | None:
    """Read the latest command request."""
    path = Path(data_file) if data_file is not None else DEFAULT_COMMAND_FILE
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    action = str(raw.get("action", "") or "")
    command_id = str(raw.get("id", "") or "")
    if not command_id or action not in ALLOWED_COMMANDS:
        return None
    payload = raw.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    return RuntimeCommand(
        command_id=command_id,
        action=action,
        payload=payload,
        created_at=_float(raw.get("created_at"), 0.0),
    )


def runtime_command_file_marker(data_file: str | Path | None = None) -> tuple[bool, int]:
    """Return a cheap marker for detecting command file changes."""
    path = Path(data_file) if data_file is not None else DEFAULT_COMMAND_FILE
    try:
        stat = path.stat()
    except OSError:
        return (False, 0)
    return (True, stat.st_mtime_ns)


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
