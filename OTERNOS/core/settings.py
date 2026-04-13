"""
settings.py - UI-independent settings defaults and merge helpers.

This module is intentionally small for Phase 1B. It preserves the existing
`.voidplayer.json` shape while moving settings defaults out of the legacy
Tkinter shell.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_SETTINGS: dict[str, Any] = {
    "crossfade_sec": 0,
    "eq_preset": "flat",
    "normalize": False,
    "viz_sensitivity": 1.0,
    "viz_smoothing": 0.18,
    "output_device": "default",
    "spotify_quality": "high",
    "spotify_crossfade": False,
    "spotify_normalize": True,
    "autoplay": True,
    "show_notifications": True,
    "theme_accent": "white",
    "borderless_fullscreen": False,
    "boot_enabled": True,
    "boot_fullscreen": False,
    "edex_enabled": True,
    "lastfm_api_key": "",
    "lastfm_api_secret": "",
    "lastfm_session_key": "",
    "lastfm_enabled": False,
    "discord_enabled": False,
    "watch_dirs": [],
    "hotkeys": {},
    "playback_speed": 1.0,
    "active_theme": "void",
    "viz_fps": 60,
    "yt_cookies_path": "",
    "ui_sounds_enabled": True,
    "ui_sound_volume": 0.18,
    "show_claude_tab": False,
    "flow_mode": False,
    "smart_skip": False,
    "voice_ctrl": False,
    "ambient_mode": False,
    "cursor_trail": True,
    "debug": False,
}


def build_default_settings() -> dict[str, Any]:
    """Return a mutable copy of the default app settings."""
    return deepcopy(DEFAULT_SETTINGS)


def merge_settings(saved: dict[str, Any] | None) -> dict[str, Any]:
    """Merge saved settings onto defaults without mutating either input."""
    settings = build_default_settings()
    if isinstance(saved, dict):
        settings.update(saved)
    return settings

