"""
controllers/playback.py — OTERNOS PLAYER
PlaybackController — owns all playback logic:
    _play_item, _do_load_track, _toggle_play, _next, _prev,
    _seek_relative, _toggle_shuffle, _toggle_repeat,
    _start_crossfade, _gapless_preload,
    _cycle_speed, _apply_playback_speed,
    _ab_set_a, _ab_set_b, _ab_clear, _ab_check,
    _poll (main 100 ms loop),
    _fmt (time formatter)

Seek press/drag/end and _draw_prog stay on VoidPlayer because they are
tightly coupled to the canvas widget references built during _build_ui.
They are kept as thin delegating methods on VoidPlayer that call back into
this controller where the logic is centralised.

VoidPlayer retains forwarding stubs for every method so existing call-sites
(key bindings, button commands, etc.) keep working unchanged.
"""

from __future__ import annotations

import os
import random
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import sys

if getattr(sys, "frozen", False):
    from oternos.constants import C, HW_ACCEL
    from oternos.audio import EQProcessor, SCIPY_AVAILABLE, MUTAGEN_AVAILABLE
    from oternos.diagnostics import log_exception
    from oternos.controllers.source import Source
else:
    from ..constants import C, HW_ACCEL
    from ..audio import EQProcessor, SCIPY_AVAILABLE, MUTAGEN_AVAILABLE
    from ..diagnostics import log_exception
    from .source import Source


SPEED_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]


class PlaybackController:
    """
    All playback state and logic previously scattered across VoidPlayer.
    Receives a reference to app (VoidPlayer) for widget access and
    cross-controller calls.
    """

    def __init__(self, app):
        self._app = app

        # Playback speed
        self._playback_speed: float = 1.0
        self._speed_processing: bool = False

        # A-B loop
        self._ab_a: Optional[float] = None
        self._ab_b: Optional[float] = None
        self._ab_active: bool = False

        # Crossfade state
        self._xfade_job = None
        self._xfade_target_vol: float = 1.0
        self._xfade_fading_in: bool = False
        self._xfade_loading: bool = False

    # ─────────────────────────────────────────────────────────────────────────
    #  Core play
    # ─────────────────────────────────────────────────────────────────────────

    def play_item(self, pos: int, force: bool = False) -> None:
        """
        Play the track at queue position pos.
        Replaces VoidPlayer._play_item.
        """
        app = self._app
        if not app.queue or pos < 0 or pos >= len(app.queue):
            return
        app.queue_pos = pos
        lib_idx = app.queue[pos]
        if lib_idx >= len(app.library):
            return
        track = app.library[lib_idx]
        app.current_idx = lib_idx

        xfade = int(app.settings.get("crossfade_sec", 0))
        if xfade > 0 and app.engine.is_playing and not force:
            self.start_crossfade(
                xfade, lambda: self.do_load_track(track, user_initiated=False)
            )
            return

        # Cancel any in-flight crossfade
        if self._xfade_job:
            try:
                app.root.after_cancel(self._xfade_job)
            except Exception:
                pass
            self._xfade_job = None
        self._xfade_fading_in = False
        self._xfade_loading = False
        app.engine._volume = app.engine.volume
        self.do_load_track(track, user_initiated=force)

    def do_load_track(self, track: dict, user_initiated: bool = False) -> None:
        """
        Load and play a track. Handles EQ, art, history, scrobble,
        Discord, waveform, lyrics, FFT.
        Replaces VoidPlayer._do_load_track.
        """
        app = self._app
        play_path = track["path"]
        eq_preset = app.settings.get("eq_preset", "flat")

        # Clean up previous EQ temp file
        prev_tmp = getattr(app, "_eq_tmp_path", None)
        if prev_tmp:
            try:
                os.unlink(prev_tmp)
            except OSError:
                pass
        app._eq_tmp_path = None

        # Stop all sources cleanly
        app._stop_all_sources()

        # Reset visualizer bars to silence (prevents ghost animation between tracks)
        app._viz_last_real_bars = [0.0] * 48
        app._viz_bars = [0.0] * 48
        if hasattr(app, "_stop_fft_file_decoder"):
            app._stop_fft_file_decoder()

        # Set source
        app._active_source = "library"
        app._set_source_badge("library")

        # Reset speed
        self._playback_speed = 1.0
        if hasattr(app, "_speed_lbl"):
            app._speed_lbl.config(text="1.0×")

        # Update track info labels
        t = track["title"]
        app._anim_label_change(app.now_title, (t[:36] + "…") if len(t) > 37 else t)
        app._anim_label_change(app.now_artist, track.get("artist", ""))
        app._anim_label_change(app.now_album, track.get("album", ""))
        if hasattr(app, "viz_track_lbl"):
            app.viz_track_lbl.config(
                text=f"▶  {t[:40]}  —  {track.get('artist', '')[:24]}"
            )
        app.lbl_tot.config(text=app._fmt(track.get("duration", 0)))
        app.btn_play.config(text="⏸")

        # Load + play
        loaded = app.engine.load(play_path)
        if loaded:
            app._current_play_path = play_path
            if track.get("duration", 0) > 0:
                app.engine.duration = float(track["duration"])
        played = loaded and app.engine.play()

        # EQ processing (async)
        if eq_preset not in ("flat", "") and SCIPY_AVAILABLE and loaded and played:
            _raw = play_path

            def _eq_bg(_r=_raw, _ep=eq_preset):
                import tempfile
                fd, tmp = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                if EQProcessor.process(_r, _ep, tmp):
                    app.root.after(0, lambda t=tmp, r=_r: _eq_swap(t, r))
                else:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass

            def _eq_swap(tmp, raw):
                if app._current_play_path != raw:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                    return
                pos = app.engine.get_position()
                app.engine.load(tmp)
                app.engine.play(start_ms=int(pos * 1000))
                app._current_play_path = tmp
                app._eq_tmp_path = tmp

            threading.Thread(target=_eq_bg, daemon=True).start()

        elif eq_preset not in ("flat", "") and not SCIPY_AVAILABLE:
            app._set_status("EQ N/A — pip install scipy soundfile")

        if loaded and played:
            app.wavevis.set_active(True)
            app._set_logo_playing(True)
            app._set_status("PLAYING")

            # Album art (async)
            app._art_url_last = None
            app._draw_art_placeholder()

            def _load_art_bg(tr=track):
                _loaded = False
                art_path = tr.get("art_path", "")
                if art_path:
                    try:
                        data = Path(art_path).read_bytes()
                        app.root.after(0, lambda d=data: app._load_art_bytes(d))
                        _loaded = True
                    except Exception:
                        pass
                if not _loaded:
                    try:
                        from mutagen.id3 import ID3
                        tags = ID3(tr["path"])
                        for tag in tags.values():
                            if hasattr(tag, "data") and tag.data:
                                data = tag.data
                                app.root.after(0, lambda d=data: app._load_art_bytes(d))
                                _loaded = True
                                break
                    except Exception:
                        pass
                if not _loaded:
                    app.root.after(
                        0,
                        lambda: app._fetch_art_musicbrainz(
                            tr.get("artist", ""), tr.get("title", "")
                        ),
                    )

            threading.Thread(target=_load_art_bg, daemon=True).start()

            # History
            app._history_add(track)

            # Last.fm scrobble
            if (
                app._scrobbler
                and app.settings.get("lastfm_enabled")
                and app._scrobbler.ready
            ):
                app._scrobbler.track_started(track)
                app._schedule_scrobble()

            # Discord RPC
            if app._discord_enabled:
                threading.Thread(
                    target=lambda: app._discord.set_activity(
                        track.get("title", ""),
                        track.get("artist", ""),
                        elapsed_s=0,
                        duration_s=track.get("duration", 0),
                    ),
                    daemon=True,
                ).start()

            # Waveform seekbar
            app._load_waveform(play_path)

            # Lyrics + mini player
            app._set_current_track_for_lyrics(track.get("artist", ""), t)
            app._mini_update()

            # Flow mode + smart skip
            if getattr(app, "_flow_mode", False):
                app._flow_enqueue(track)
            if getattr(app, "_smart_skip_on", False):
                if app._skip_counts.get(track["path"], 0) >= 3:
                    app.root.after(200, app._next)
                    return

            app._start_lyric_ticker()
            app._update_context_sidebar(track)
            if not user_initiated:
                app.root.after(300, lambda: app._show_track_notification(track))
            app.root.after(0, app._refresh_tracks)
            app.root.after(50, app._scroll_to_playing)
            threading.Thread(
                target=lambda p=play_path: app._start_fft_file_decoder(p),
                daemon=True,
            ).start()

        else:
            # Load failed
            app._active_source = "none"
            app._set_source_badge("none")
            app._set_status("LOAD FAILED")
            fname = Path(play_path).name
            app.now_title.config(text="⚠  LOAD FAILED")
            app.now_artist.config(text=fname[:50])
            app.now_album.config(text="")
            err = getattr(app.engine, "_last_error", "")
            import tkinter.messagebox as messagebox
            if not getattr(app.engine, "_pygame", None):
                messagebox.showerror(
                    "OTERNOS // AUDIO ERROR",
                    "pygame is not available.\n\nRun: pip install pygame\nThen rebuild the exe.",
                )
            else:
                messagebox.showerror(
                    "OTERNOS // PLAYBACK ERROR",
                    f"Could not play:\n{fname}\n\n"
                    + (f"Error: {err}\n\n" if err else "")
                    + "Supported formats: MP3, WAV, OGG, FLAC",
                )

        app._tl_update_highlight()
        if app.view == "queue":
            app._refresh_queue()

    # ─────────────────────────────────────────────────────────────────────────
    #  Transport
    # ─────────────────────────────────────────────────────────────────────────

    def toggle_play(self) -> None:
        """Replaces VoidPlayer._toggle_play."""
        app = self._app
        app.ui_sounds.play("play")
        if app.source_ctrl.is_spotify:
            app._sp_playpause()
            return
        if app.engine.is_playing:
            app.engine.pause()
            app.btn_play.config(text="▶")
            app.wavevis.set_active(False)
            app._set_logo_playing(False)
            app._set_status("PAUSED")
            app._mini_update()
        elif app.engine.is_paused:
            app.engine.unpause()
            app.btn_play.config(text="⏸")
            app.wavevis.set_active(True)
            app._set_logo_playing(True)
            app._set_status("PLAYING")
            app._mini_update()
        elif app.queue and app._active_source in ("library", "none"):
            self.play_item(max(0, app.queue_pos))

    def next(self, force: bool = False) -> None:
        """Replaces VoidPlayer._next."""
        app = self._app
        if app.source_ctrl.is_spotify:
            threading.Thread(target=app.sp_api.next_track, daemon=True).start()
            return
        if app._active_source in ("youtube", "soundcloud"):
            app._stop_all_sources()
            app._active_source = "none"
            app._set_source_badge("none")
            if not app.queue:
                return
            app.queue_pos = (app.queue_pos + 1) % len(app.queue)
            self.play_item(app.queue_pos)
            return
        if not app.queue and not app._manual_queue:
            return
        # Smart skip tracking
        if getattr(app, "_smart_skip_on", False):
            idx = app.current_idx
            if 0 <= idx < len(app.library):
                pos = app.engine.get_position()
                dur = app.engine.duration
                if dur > 0 and pos / dur < 0.35:
                    path = app.library[idx]["path"]
                    app._skip_counts[path] = app._skip_counts.get(path, 0) + 1
        # Drain manual queue first
        if app._manual_queue:
            next_idx = app._manual_queue.pop(0)
            insert_at = (app.queue_pos + 1) if app.queue_pos >= 0 else 0
            app.queue.insert(insert_at, next_idx)
            app.queue_pos = insert_at
            self.play_item(app.queue_pos)
            if app.view == "queue":
                app._refresh_queue()
            return
        if not app.queue:
            return
        if app.shuffle:
            if len(app.queue) > 1:
                choices = [i for i in range(len(app.queue)) if i != app.queue_pos]
                app.queue_pos = random.choice(choices)
            else:
                app.queue_pos = 0
        else:
            app.queue_pos = (app.queue_pos + 1) % len(app.queue)
        self.play_item(app.queue_pos, force=force)

    def prev(self, force: bool = False) -> None:
        """Replaces VoidPlayer._prev."""
        app = self._app
        if app.source_ctrl.is_spotify:
            threading.Thread(target=app.sp_api.prev_track, daemon=True).start()
            return
        if app._active_source in ("youtube", "soundcloud"):
            app._stop_all_sources()
            app._active_source = "none"
            app._set_source_badge("none")
            if not app.queue:
                return
            app.queue_pos = (app.queue_pos - 1) % len(app.queue)
            self.play_item(app.queue_pos)
            return
        if not app.queue:
            return
        if app.engine.get_position() > 5 and not force:
            app.engine.seek(0)
        else:
            app.queue_pos = (app.queue_pos - 1) % len(app.queue)
            self.play_item(app.queue_pos, force=force)

    def seek_relative(self, delta_s: float) -> None:
        """Replaces VoidPlayer._seek_relative."""
        app = self._app
        target = 0.0
        if app.source_ctrl.is_spotify and app._sp_dur_ms > 0:
            ms = max(0, min(app._sp_dur_ms, app._sp_pos_ms + int(delta_s * 1000)))
            app._sp_pos_ms = ms
            app.lbl_cur.config(text=app._fmt(ms / 1000))
            threading.Thread(
                target=lambda: app.sp_api.seek(ms), daemon=True
            ).start()
            target = ms / 1000
        elif app.engine.duration > 0:
            pos = app.engine.get_position()
            target = max(0, min(app.engine.duration, pos + delta_s))
            r = target / app.engine.duration
            app.lbl_cur.config(text=app._fmt(target))
            app._prog_r_cur = r
            app._draw_prog(r)
            app.seeking = True

            def _do_seek(t=target, rv=r):
                app.engine.seek(t)
                app.root.after(0, lambda: app._seek_done(rv))

            threading.Thread(target=_do_seek, daemon=True).start()
        app._set_status(
            f"{'→' if delta_s > 0 else '←'}  "
            f"{app._fmt(target) if target else f'{int(delta_s):+d}s'}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  Shuffle / Repeat
    # ─────────────────────────────────────────────────────────────────────────

    def toggle_shuffle(self) -> None:
        """Replaces VoidPlayer._toggle_shuffle."""
        app = self._app
        app.shuffle = not app.shuffle
        col = C["glow"] if app.shuffle else C["white3"]
        app.btn_shuf._active_fg = col
        app.btn_shuf.config(fg=col)

    def toggle_repeat(self) -> None:
        """Replaces VoidPlayer._toggle_repeat."""
        app = self._app
        modes = ["off", "all", "one"]
        app.repeat_mode = modes[(modes.index(app.repeat_mode) + 1) % 3]
        icon = {"off": "↺", "all": "↺", "one": "↻"}[app.repeat_mode]
        col = C["white3"] if app.repeat_mode == "off" else C["glow"]
        app.btn_repeat._active_fg = col
        app.btn_repeat.config(text=icon, fg=col)
        mode_label = {
            "off": "repeat off", "all": "repeat all", "one": "repeat one"
        }[app.repeat_mode]
        if hasattr(app, "_repeat_mode_lbl"):
            app._repeat_mode_lbl.config(text=mode_label, fg=col)
            job = getattr(app, "_repeat_mode_job", None)
            if job:
                try:
                    app.root.after_cancel(job)
                except Exception:
                    pass
        app._repeat_mode_job = app.root.after(
            1800,
            lambda: (
                app._repeat_mode_lbl.config(text="")
                if hasattr(app, "_repeat_mode_lbl")
                else None
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  Speed
    # ─────────────────────────────────────────────────────────────────────────

    def cycle_speed(self) -> None:
        """Replaces VoidPlayer._cycle_speed."""
        app = self._app
        steps = SPEED_STEPS
        idx = steps.index(self._playback_speed) if self._playback_speed in steps else 2
        self._playback_speed = steps[(idx + 1) % len(steps)]
        app._speed_lbl.config(text=f"{self._playback_speed}×")

        if app._active_source == "spotify":
            self._playback_speed = 1.0
            app._speed_lbl.config(text="1.0×")
            app._set_status("SPEED: N/A FOR SPOTIFY")
            return
        if not SCIPY_AVAILABLE:
            self._playback_speed = 1.0
            app._speed_lbl.config(text="1.0×")
            app._set_status("SPEED: NEEDS SCIPY+SOUNDFILE")
            return
        if not app.engine._path:
            app._set_status(
                f"SPEED QUEUED: {self._playback_speed}×"
                if self._playback_speed != 1.0
                else "SPEED: NORMAL"
            )
            return

        app._set_status("PROCESSING…")
        self._speed_processing = True
        speed = self._playback_speed

        def _done():
            self._speed_processing = False
            app.root.after(
                0,
                lambda: app._set_status(
                    f"SPEED {speed}×" if speed != 1.0 else "SPEED NORMAL"
                ),
            )

        def _err(msg):
            self._speed_processing = False
            self._playback_speed = 1.0
            app.root.after(0, lambda: app._speed_lbl.config(text="1.0×"))
            app.root.after(0, lambda: app._set_status("SPEED ERROR"))

        app.engine.set_speed(speed, on_done=_done, on_error=_err)

    def apply_playback_speed(self) -> None:
        """Replaces VoidPlayer._apply_playback_speed."""
        app = self._app
        app.engine.set_speed(
            self._playback_speed,
            on_done=lambda: app.root.after(
                0,
                lambda: app._set_status(
                    f"SPEED {self._playback_speed}×"
                    if self._playback_speed != 1.0
                    else "SPEED NORMAL"
                ),
            ),
            on_error=lambda msg: app.root.after(
                0, lambda: app._set_status("SPEED ERROR")
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  A-B Loop
    # ─────────────────────────────────────────────────────────────────────────

    def ab_set_a(self) -> None:
        """Replaces VoidPlayer._ab_set_a."""
        app = self._app
        pos = (
            app.engine.get_position()
            if not app.source_ctrl.is_spotify
            else app._sp_pos_ms / 1000
        )
        self._ab_a = pos
        self._ab_active = bool(self._ab_a is not None and self._ab_b is not None)
        app._ab_lbl.config(text=f"{app._fmt(self._ab_a)}–?")
        app._set_status(f"A: {app._fmt(self._ab_a)}")

    def ab_set_b(self) -> None:
        """Replaces VoidPlayer._ab_set_b."""
        app = self._app
        pos = (
            app.engine.get_position()
            if not app.source_ctrl.is_spotify
            else app._sp_pos_ms / 1000
        )
        if self._ab_a is not None and pos > self._ab_a:
            self._ab_b = pos
            self._ab_active = True
            app._ab_lbl.config(
                text=f"{app._fmt(self._ab_a)}–{app._fmt(self._ab_b)}"
            )
            app._set_status("A-B LOOP ON")
        else:
            app._set_status("SET A FIRST")

    def ab_clear(self) -> None:
        """Replaces VoidPlayer._ab_clear."""
        app = self._app
        self._ab_a = self._ab_b = None
        self._ab_active = False
        app._ab_lbl.config(text="—")
        app._set_status("A-B CLEAR")

    def ab_check(self) -> None:
        """
        Called every poll tick. Loops back to A when position passes B.
        Replaces VoidPlayer._ab_check.
        """
        if not self._ab_active or self._ab_b is None:
            return
        app = self._app
        pos = (
            app._sp_pos_ms / 1000
            if app.source_ctrl.is_spotify
            else app.engine.get_position()
        )
        if pos >= self._ab_b:
            if app.source_ctrl.is_spotify:
                ms = int(self._ab_a * 1000)
                threading.Thread(
                    target=lambda: app.sp_api.seek(ms), daemon=True
                ).start()
            else:
                app.engine.seek(self._ab_a)

    # ─────────────────────────────────────────────────────────────────────────
    #  Crossfade
    # ─────────────────────────────────────────────────────────────────────────

    def start_crossfade(self, seconds: float, on_done) -> None:
        """Replaces VoidPlayer._start_crossfade."""
        app = self._app
        if self._xfade_job:
            app.root.after_cancel(self._xfade_job)
            self._xfade_job = None
        target_vol = app.engine.volume
        self._xfade_target_vol = target_vol
        self._xfade_fading_in = False
        step_ms = 40
        out_steps = max(8, int(seconds * 1000 / step_ms))
        in_steps = out_steps

        def _fade_out(n=0):
            if not app.engine.is_playing and n > 2:
                _do_load()
                return
            app.engine.set_volume(max(0.0, target_vol * (1.0 - n / out_steps)))
            if n < out_steps:
                self._xfade_job = app.root.after(step_ms, lambda: _fade_out(n + 1))
            else:
                _do_load()

        def _do_load():
            app.engine._volume = 0.0
            self._xfade_fading_in = True
            self._xfade_loading = True
            on_done()
            self._xfade_loading = False
            app.root.after(step_ms * 2, _fade_in)

        def _fade_in(n=0):
            if not self._xfade_fading_in:
                return
            app.engine.set_volume(
                min(
                    self._xfade_target_vol,
                    self._xfade_target_vol * (n + 1) / in_steps,
                )
            )
            if n < in_steps - 1:
                self._xfade_job = app.root.after(step_ms, lambda: _fade_in(n + 1))
            else:
                app.engine.set_volume(self._xfade_target_vol)
                self._xfade_fading_in = False
                self._xfade_job = None

        _fade_out()

    # ─────────────────────────────────────────────────────────────────────────
    #  Gapless preload
    # ─────────────────────────────────────────────────────────────────────────

    def gapless_preload(self) -> None:
        """Replaces VoidPlayer._gapless_preload."""
        app = self._app
        if app.source_ctrl.is_spotify or not app.queue:
            return
        next_pos = app.queue_pos + 1
        if app.repeat_mode == "all" and next_pos >= len(app.queue):
            next_pos = 0
        if next_pos < 0 or next_pos >= len(app.queue):
            return
        lib_idx = app.queue[next_pos]
        if lib_idx >= len(app.library):
            return
        path = app.library[lib_idx]["path"]

        def _preload():
            try:
                with open(path, "rb") as f:
                    f.read(65536)
            except Exception:
                pass

        threading.Thread(target=_preload, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    #  Poll loop (100 ms heartbeat)
    # ─────────────────────────────────────────────────────────────────────────

    def poll(self) -> None:
        """
        Main 100 ms loop. Replaces VoidPlayer._poll.
        Called via app.root.after(100, app._poll) — VoidPlayer._poll
        delegates here.
        """
        app = self._app

        if app.source_ctrl.is_spotify:
            if not app.seeking and app._sp_dur_ms > 0:
                r = min(1.0, app._sp_pos_ms / app._sp_dur_ms)
                app._draw_prog(r)
                app.lbl_cur.config(text=app._fmt(app._sp_pos_ms / 1000))
                app.lbl_tot.config(text=app._fmt(app._sp_dur_ms / 1000))
            if app._sp_playing:
                app._sp_pos_ms += 100

        elif (app.engine.is_playing or app.engine.is_paused) and not app.seeking:
            pos = app.engine.get_position()
            dur = app.engine.duration
            app.lbl_cur.config(text=app._fmt(pos))
            if dur > 0:
                cur_tot = app.lbl_tot.cget("text")
                expected = app._fmt(dur)
                if cur_tot != expected:
                    app.lbl_tot.config(text=expected)
                app._draw_prog(min(1.0, pos / dur))
                if app.engine.is_playing and dur - pos < 5.0:
                    self.gapless_preload()
            else:
                try:
                    import pygame as _pg
                    raw = _pg.mixer.music.get_pos() / 1000.0
                    if raw > 0:
                        app._draw_prog(min(1.0, raw / 240.0))
                except Exception:
                    pass

            if (
                not app.engine.is_paused
                and app.engine.is_done()
                and not self._speed_processing
            ):
                app.engine.is_playing = False
                app.wavevis.set_active(False)
                app.btn_play.config(text="▶")
                app.status_lbl.config(text="[ IDLE ]")
                src = app._active_source

                if app.repeat_mode == "one":
                    if src == "soundcloud" and getattr(app, "_sc_current_track", None):
                        t = app._sc_current_track
                        threading.Thread(
                            target=lambda: app._sc_stream(t), daemon=True
                        ).start()
                    elif src == "youtube" and getattr(app, "_yt_current_track", None):
                        t = app._yt_current_track
                        threading.Thread(
                            target=lambda: app._yt_stream(t), daemon=True
                        ).start()
                    elif app.queue_pos >= 0:
                        self.play_item(app.queue_pos)

                elif src in ("soundcloud", "youtube", "deezer", "archive", "bandcamp"):
                    if src == "soundcloud" and app._sc_stream_queue:
                        next_track = app._sc_stream_queue.pop(0)
                        app._sc_update_queue_lbl()
                        threading.Thread(
                            target=lambda t=next_track: app._sc_stream(t),
                            daemon=True,
                        ).start()
                    elif app.repeat_mode == "all":
                        if src == "soundcloud" and getattr(app, "_sc_current_track", None):
                            t = app._sc_current_track
                            threading.Thread(
                                target=lambda: app._sc_stream(t), daemon=True
                            ).start()
                        elif src == "youtube" and getattr(app, "_yt_current_track", None):
                            t = app._yt_current_track
                            threading.Thread(
                                target=lambda: app._yt_stream(t), daemon=True
                            ).start()
                        elif src == "deezer" and getattr(app, "_dz_current_track", None):
                            t = app._dz_current_track
                            threading.Thread(
                                target=lambda: app._dz_stream(t), daemon=True
                            ).start()
                    else:
                        app._active_source = "none"
                        app._set_source_badge("none")

                elif app.repeat_mode == "all" or app.queue_pos < len(app.queue) - 1:
                    self.next()
                else:
                    app._active_source = "none"
                    app._set_source_badge("none")

        # Lyric ticker sync
        app._sync_lyric_ticker()
        # A-B loop check
        self.ab_check()

        app.root.after(100 if HW_ACCEL else 250, app._poll)

    # ─────────────────────────────────────────────────────────────────────────
    #  Utility
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def fmt(s: float) -> str:
        """Format seconds as m:ss. Replaces VoidPlayer._fmt."""
        s = max(0, int(s))
        return f"{s // 60}:{s % 60:02d}"
