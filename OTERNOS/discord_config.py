from __future__ import annotations

import os
from pathlib import Path
import socket
import sys


COMMAND_PREFIX = os.environ.get("HIN_TECH_DISCORD_PREFIX", "!")
DISCORD_TOKEN_ENV = "HIN_TECH_DISCORD_BOT_TOKEN"
DISCORD_TOKEN_FILE_ENV = "HIN_TECH_DISCORD_TOKEN_FILE"
DISCORD_TOKEN_FILE_NAME = "discord_bot_token.txt"
DISCORD_LOCK_PORT_ENV = "HIN_TECH_DISCORD_LOCK_PORT"
DISCORD_LOCK_PORT = 51473
DISCORD_STATUS_FILE_ENV = "HIN_TECH_DISCORD_STATUS_FILE"
DISCORD_STATUS_FILE_NAME = ".voidplayer_discord_status.json"
DISCORD_SHARE_QT_NOW_PLAYING_ENV = "HIN_TECH_DISCORD_SHARE_QT_NOW_PLAYING"
DISCORD_CLOUD_MODE_ENV = "HIN_TECH_DISCORD_CLOUD"
DISCORD_DISABLE_LOCAL_LOCK_ENV = "HIN_TECH_DISCORD_DISABLE_LOCAL_LOCK"
DISCORD_PANEL_STATE_FILE_NAME = ".voidplayer_discord_panel.json"


def local_token_paths() -> list[Path]:
    paths: list[Path] = []
    token_file = os.environ.get(DISCORD_TOKEN_FILE_ENV, "").strip()
    if token_file:
        paths.append(Path(token_file).expanduser())
    paths.append(Path.cwd() / DISCORD_TOKEN_FILE_NAME)
    try:
        paths.append(Path(__file__).resolve().parents[1] / DISCORD_TOKEN_FILE_NAME)
    except Exception:
        pass
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def local_token() -> str:
    for path in local_token_paths():
        try:
            if path.exists() and path.is_file():
                return path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
    return ""


def env_truthy(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on", "public", "cloud"}


def cloud_mode(argv: list[str] | None = None) -> bool:
    args = sys.argv if argv is None else argv
    return env_truthy(DISCORD_CLOUD_MODE_ENV) or "--cloud" in args


def token_for_mode(*, is_cloud: bool) -> str:
    env_token = os.environ.get(DISCORD_TOKEN_ENV, "").strip()
    if env_token:
        return env_token
    if is_cloud:
        return ""
    return local_token()


def single_instance_lock() -> socket.socket:
    port = DISCORD_LOCK_PORT
    try:
        port = int(os.environ.get(DISCORD_LOCK_PORT_ENV, DISCORD_LOCK_PORT))
    except Exception:
        port = DISCORD_LOCK_PORT
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        lock.bind(("127.0.0.1", port))
        lock.listen(1)
    except OSError as exc:
        lock.close()
        raise SystemExit("Discord bot is already running.") from exc
    return lock
