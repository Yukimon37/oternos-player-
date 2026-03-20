"""
controllers/library.py — OTERNOS PLAYER
LibraryController — owns library data, persistence, import, history,
playlist mutation, and tag writes.

Extracted from VoidPlayer to keep player.py lean.
VoidPlayer retains forwarding properties (self.library, self.playlists,
self.settings, self._history) so all existing call-sites keep working
unchanged during the incremental migration.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid circular import — only used for type hints
    pass

# ── runtime imports (frozen vs source) ──────────────────────────────────────
import sys

if getattr(sys, "frozen", False):
    from oternos.constants import DATA_FILE
    from oternos.audio import MUTAGEN_AVAILABLE
    from oternos.diagnostics import log_exception
else:
    from ..constants import DATA_FILE
    from ..audio import MUTAGEN_AVAILABLE
    from ..diagnostics import log_exception


# Default settings — single source of truth (was duplicated in _load_data)
_DEFAULT_SETTINGS: dict = {
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
    "boot_fullscreen": True,
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

HISTORY_MAX = 200
AUDIO_EXT = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".wma"}


class LibraryController:
    """
    Owns all persistent app data:
        library      — list of track dicts
        playlists    — dict {name: [lib_idx, ...]}
        settings     — dict of user preferences
        history      — recently played list
        bookmarks    — {lib_idx: [(seconds, label), ...]}
        album_meta   — {album_name: {art_path, art_url, fav}}
        sc_favorites — list of saved SoundCloud track dicts
        shuffle      — bool
        repeat_mode  — "off" | "all" | "one"
    """

    def __init__(self, app):
        self._app = app

        # Public data attributes — VoidPlayer forwards to these via properties
        self.library: list[dict] = []
        self.playlists: dict[str, list[int]] = {}
        self.settings: dict = dict(_DEFAULT_SETTINGS)
        self.history: list[dict] = []
        self.bookmarks: dict[int, list] = {}
        self.album_meta: dict[str, dict] = {}
        self.sc_favorites: list[dict] = []
        self.shuffle: bool = False
        self.repeat_mode: str = "off"

    # ── Persistence ──────────────────────────────────────────────────────────

    def load(self) -> None:
        """Load all data from disk. Replaces VoidPlayer._load_data."""
        self.settings = dict(_DEFAULT_SETTINGS)

        if DATA_FILE.exists():
            try:
                d = json.loads(DATA_FILE.read_text())
                self.library = [
                    t for t in d.get("library", []) if Path(t["path"]).exists()
                ]
                self.playlists = d.get("playlists", {})
                self.settings.update(d.get("settings", {}))
                self.history = d.get("history", [])[-HISTORY_MAX:]
                self.bookmarks = {
                    int(k): v for k, v in d.get("bookmarks", {}).items()
                }
                self.sc_favorites = d.get("sc_favorites", [])
                self.album_meta = d.get("album_meta", {})
                self.shuffle = d.get("shuffle", False)
                self.repeat_mode = d.get("repeat_mode", "off")
            except Exception as exc:
                log_exception("library_load_failed", exc)

        # Initialise UI sounds with loaded settings (same as before)
        app = self._app
        if hasattr(app, "ui_sounds"):
            app.ui_sounds.set_enabled(bool(self.settings.get("ui_sounds_enabled", True)))
            app.ui_sounds.set_volume(float(self.settings.get("ui_sound_volume", 0.18)))

    def save(self) -> None:
        """Persist all data to disk. Replaces VoidPlayer._save."""
        try:
            DATA_FILE.write_text(
                json.dumps(
                    {
                        "library": self.library,
                        "playlists": self.playlists,
                        "settings": self.settings,
                        "history": self.history[-HISTORY_MAX:],
                        "bookmarks": {str(k): v for k, v in self.bookmarks.items()},
                        "sc_favorites": self.sc_favorites,
                        "album_meta": self.album_meta,
                        "shuffle": self.shuffle,
                        "repeat_mode": self.repeat_mode,
                    },
                    indent=2,
                )
            )
        except Exception as exc:
            log_exception("library_save_failed", exc)

    # ── Import ───────────────────────────────────────────────────────────────

    def import_paths(self, paths: list[str]) -> None:
        """
        Add new audio files to the library.
        Replaces VoidPlayer._import  +  _import_batch.
        Small batches run synchronously; large ones run in a thread.
        """
        existing = {t["path"] for t in self.library}
        new_paths = [p for p in paths if p not in existing]
        if not new_paths:
            self._app._set_status("NO NEW FILES")
            return
        total = len(new_paths)
        if total <= 20:
            self._import_batch(new_paths)
        else:
            self._app.status_lbl.config(text=f"[ IMPORTING {total} FILES… ]")
            threading.Thread(
                target=self._import_batch,
                args=(new_paths,),
                kwargs={"progress": True},
                daemon=True,
            ).start()

    def import_folder(self, folder: str) -> None:
        """Scan a folder recursively and import all audio files found."""
        paths = [
            str(p)
            for p in Path(folder).rglob("*")
            if p.suffix.lower() in AUDIO_EXT
        ]
        self.import_paths(paths)

    def _import_batch(self, paths: list[str], progress: bool = False) -> None:
        added = 0
        total = len(paths)
        for i, p in enumerate(paths):
            try:
                m = self._app.engine.get_metadata(p)
                m["path"] = p
                if MUTAGEN_AVAILABLE:
                    try:
                        from mutagen import File as _MF2
                        _f = _MF2(p)
                        m["duration"] = _f.info.length if _f and _f.info else 0.0
                    except Exception:
                        m["duration"] = 0.0
                else:
                    m["duration"] = 0.0
                self.library.append(m)
                added += 1
            except Exception as exc:
                log_exception(f"import_track_{Path(p).name}", exc)

            if progress and (i + 1) % 10 == 0:
                n, t = i + 1, total
                self._app.root.after(
                    0,
                    lambda n=n, t=t: self._app.status_lbl.config(
                        text=f"[ {n}/{t} ]"
                    ),
                )

        self.save()
        self._app.root.after(0, self._app._refresh_tracks)
        self._app.root.after(
            0, lambda: self._app.status_lbl.config(text=f"[+{added} TRACKS]")
        )

    # ── Removal ──────────────────────────────────────────────────────────────

    def remove_track(self, lib_idx: int) -> None:
        """
        Remove a track from the library and remap all indices.
        Replaces VoidPlayer._rm_from_lib.
        """
        if lib_idx >= len(self.library):
            return

        app = self._app
        was_playing = app.current_idx == lib_idx

        self.library.pop(lib_idx)

        # Remap playlist indices
        for name in self.playlists:
            self.playlists[name] = [
                i if i < lib_idx else i - 1
                for i in self.playlists[name]
                if i != lib_idx
            ]

        # Remap queue
        old_pos = app.queue_pos
        app.queue = [
            i if i < lib_idx else i - 1
            for i in app.queue
            if i != lib_idx
        ]
        if old_pos >= len(app.queue):
            app.queue_pos = max(-1, len(app.queue) - 1)

        # Update current track pointer
        if app.current_idx == lib_idx:
            app.current_idx = -1
            if was_playing:
                app.engine.stop()
                app.engine.is_playing = False
                app.btn_play.config(text="▶")
                app.wavevis.set_active(False)
                app._set_logo_playing(False)
                app.now_title.config(text="NO TRACK")
                app.now_artist.config(text="")
                app.now_album.config(text="")
                app.status_lbl.config(text="[ IDLE ]")
                app._draw_prog(0)
        elif app.current_idx > lib_idx:
            app.current_idx -= 1

        self.save()
        app._refresh_tracks()

    def remove_from_playlist(self, name: str, lib_idx: int) -> None:
        """Replaces VoidPlayer._rm_from_pl."""
        pl = self.playlists.get(name)
        if pl and lib_idx in pl:
            pl.remove(lib_idx)
            self.save()
            self._app._refresh_tracks()

    # ── Playlists ────────────────────────────────────────────────────────────

    def create_playlist(self, name: str) -> bool:
        """Create a new empty playlist. Returns False if name already exists."""
        if not name or name in self.playlists:
            return False
        self.playlists[name] = []
        self.save()
        self._app._refresh_pl_sidebar()
        return True

    def delete_playlist(self, name: str) -> None:
        if name in self.playlists:
            del self.playlists[name]
            self.save()
            self._app._refresh_pl_sidebar()

    def add_to_playlist(self, name: str, lib_idx: int) -> None:
        if name in self.playlists and lib_idx not in self.playlists[name]:
            self.playlists[name].append(lib_idx)
            self.save()

    # ── History ──────────────────────────────────────────────────────────────

    def history_add(self, track: dict, source: str = "library") -> None:
        """Replaces VoidPlayer._history_add."""
        entry = {
            "title": track.get("title", ""),
            "artist": track.get("artist", ""),
            "album": track.get("album", ""),
            "source": source,
            "ts": int(time.time()),
        }
        # Skip consecutive duplicate entries
        if (
            self.history
            and self.history[-1].get("title") == entry["title"]
            and self.history[-1].get("source", "library") == entry.get("source", "library")
        ):
            return
        self.history.append(entry)
        if len(self.history) > HISTORY_MAX:
            self.history = self.history[-HISTORY_MAX:]
        self.save()
        app = self._app
        if getattr(app, "view", "") == "history":
            app._refresh_history_view()

    def history_clear(self) -> None:
        """Replaces VoidPlayer._clear_history."""
        self.history = []
        self._app._refresh_history_view()
        self.save()

    # ── Tags ─────────────────────────────────────────────────────────────────

    def update_tags(self, lib_idx: int, tags: dict) -> None:
        """
        Write title/artist/album into both the library dict and the file.
        Replaces the save path inside VoidPlayer._open_tag_editor.
        """
        if lib_idx >= len(self.library):
            return
        track = self.library[lib_idx]
        for key in ("title", "artist", "album"):
            if key in tags:
                track[key] = tags[key]

        if MUTAGEN_AVAILABLE:
            try:
                from mutagen.id3 import ID3, TIT2, TPE1, TALB
                try:
                    id3 = ID3(track["path"])
                except Exception:
                    id3 = ID3()
                id3["TIT2"] = TIT2(encoding=3, text=track["title"])
                id3["TPE1"] = TPE1(encoding=3, text=track["artist"])
                id3["TALB"] = TALB(encoding=3, text=track["album"])
                id3.save(track["path"])
            except Exception as exc:
                log_exception("update_tags_mutagen", exc)

        self.save()
        self._app._refresh_tracks()
