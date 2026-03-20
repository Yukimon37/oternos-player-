"""
controllers/source.py — OTERNOS PLAYER
SourceController — single source of truth for which audio source is active.

Replaces the scattered triple of:
    self._active_source  (string)
    self._sp_mode        (bool)
    self._set_source_badge(str)

All three are now handled here. VoidPlayer keeps forwarding properties for
_active_source and _sp_mode so existing call-sites keep working unchanged.
"""

from __future__ import annotations

import sys
import threading
from enum import Enum, auto
from typing import TYPE_CHECKING


class Source(Enum):
    NONE       = "none"
    LIBRARY    = "library"
    SPOTIFY    = "spotify"
    YOUTUBE    = "youtube"
    SOUNDCLOUD = "soundcloud"
    DEEZER     = "deezer"
    ARCHIVE    = "archive"
    BANDCAMP   = "bandcamp"

    # Convenience: build from the legacy string used throughout the codebase
    @classmethod
    def from_str(cls, s: str) -> "Source":
        try:
            return cls(s.lower())
        except ValueError:
            return cls.NONE

    @property
    def is_local_engine(self) -> bool:
        """True if playback goes through AudioEngine (not Spotify Connect)."""
        return self in (
            Source.LIBRARY,
            Source.YOUTUBE,
            Source.SOUNDCLOUD,
            Source.DEEZER,
            Source.ARCHIVE,
            Source.BANDCAMP,
        )

    @property
    def is_spotify(self) -> bool:
        return self is Source.SPOTIFY


# Badge labels shown in the player bar
_BADGE_LABELS: dict[Source, str] = {
    Source.NONE:       "",
    Source.LIBRARY:    "",
    Source.SPOTIFY:    "[ SPOTIFY ]",
    Source.YOUTUBE:    "[ YOUTUBE ]",
    Source.SOUNDCLOUD: "[ SOUNDCLOUD ]",
    Source.DEEZER:     "[ DEEZER ]",
    Source.ARCHIVE:    "[ ARCHIVE ]",
    Source.BANDCAMP:   "[ BANDCAMP ]",
}


class SourceController:
    """
    Owns:
        active   — the currently playing Source enum value
    Exposes:
        switch_to(source)    — stop current, set new, update badge
        stop_all()           — stop everything, set NONE
        is_spotify property  — replaces _sp_mode bool checks
        active_str property  — replaces _active_source string checks
    """

    def __init__(self, app):
        self._app = app
        self._active: Source = Source.NONE

    # ── Public interface ─────────────────────────────────────────────────────

    @property
    def active(self) -> Source:
        return self._active

    @property
    def active_str(self) -> str:
        """Legacy string value — used by forwarding property _active_source."""
        return self._active.value

    @property
    def is_spotify(self) -> bool:
        """Drop-in replacement for the old self._sp_mode bool."""
        return self._active is Source.SPOTIFY

    def switch_to(self, source: Source) -> None:
        """
        Set the active source without stopping anything.
        Use after you have already called stop_all() or when you know
        the engine transition is being handled externally.
        Updates the player bar badge.
        """
        self._active = source
        self._update_badge()

    def stop_all(self) -> None:
        """
        Stop every audio source cleanly and reset to NONE.
        Replaces VoidPlayer._stop_all_sources.
        """
        app = self._app

        # Cancel any in-flight crossfade
        if not getattr(app, "_xfade_loading", False):
            app._xfade_fading_in = False
            if getattr(app, "_xfade_job", None):
                try:
                    app.root.after_cancel(app._xfade_job)
                except tk_TclError:
                    pass
                app._xfade_job = None

        # Stop Spotify (fire-and-forget — don't block UI thread)
        try:
            threading.Thread(target=app.sp_api.pause, daemon=True).start()
        except Exception:
            pass

        # Stop local engine
        app.engine.stop()

        # Reset shared state
        app._sp_playing = False
        app._art_url_last = None

        self._active = Source.NONE
        self._update_badge()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _update_badge(self) -> None:
        """Push the badge text to the player bar label."""
        app = self._app
        try:
            app.source_badge.config(text=_BADGE_LABELS.get(self._active, ""))
        except Exception:
            pass


# Import TclError for the except clause above without importing all of tkinter
try:
    import tkinter as _tk
    tk_TclError = _tk.TclError
except Exception:
    tk_TclError = Exception
