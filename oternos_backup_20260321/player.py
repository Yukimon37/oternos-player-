""""
player.py — OTERNOS PLAYER
VoidPlayer — the main application class.
"""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import os
import re
import sys
import json
import time
import math
import random
import threading
import tempfile
import urllib.request
import urllib.parse
import urllib.error
import webbrowser
from pathlib import Path

if getattr(sys, "frozen", False):
    from oternos.constants import (
        C,
        FM,
        FMS,
        FML,
        FMX,
        DATA_FILE,
        YT_CACHE,
        HW_ACCEL,
        _ICON_B64,
    )
    from oternos.animation import ColorAnim, FadeOverlay
    from oternos.audio import (
        AudioEngine,
        EQProcessor,
        UISounds,
        MUTAGEN_AVAILABLE,
        SCIPY_AVAILABLE,
    )
    from oternos.services import (
        GlobalHotkeys,
        LastFmScrobbler,
        DiscordRPC,
        FolderWatcher,
    )
    from oternos.streaming import (
        SpotifyAuth,
        SpotifyAPI,
        SoundCloudAPI,
        YouTubeAPI,
        DeezerAPI,
        InternetArchiveAPI,
        BandcampAPI,
        SPOTIFY_CLIENT_ID,
    )
    from oternos.widgets import (
        WaveVisualizer,
        OternosLogo,
        MikuLogo,
        MikuCornerDeco,
        MikuTicker,
        CornerBrackets,
        DataTicker,
        TrackRecommender,
        NormMeter,
        NierLogo,
        AngelTicker,
        BaroqueFrame,
    )
    from oternos.diagnostics import get_logger, log_exception, set_debug
    from oternos.aidj import AIDJEngine, AIDJView
    from oternos.netstream import NetStreamView
    from oternos.audiofx import AudioFXView
    from oternos.cyberui import (
        GlitchText, CircuitLines, RadarSweep,
        FrequencyRing, StatusMatrix, BinaryRain,
        NodeGraph, TerminalCursor,
        WaveformScope, BeatPulse, GlyphWall,
        SpectrumBars, HoloFrame, SignalMeter,
        PlasmaRing, DataBurst,
    )

else:
    from .constants import (
        C,
        FM,
        FMS,
        FML,
        FMX,
        DATA_FILE,
        YT_CACHE,
        HW_ACCEL,
        _ICON_B64,
    )
    from .animation import ColorAnim, FadeOverlay
    from .audio import AudioEngine, EQProcessor, UISounds, MUTAGEN_AVAILABLE, SCIPY_AVAILABLE
    from .services import GlobalHotkeys, LastFmScrobbler, DiscordRPC, FolderWatcher
    from .streaming import (
        SpotifyAuth,
        SpotifyAPI,
        SoundCloudAPI,
        YouTubeAPI,
        DeezerAPI,
        InternetArchiveAPI,
        BandcampAPI,
        SPOTIFY_CLIENT_ID,
    )
    from .widgets import (
        WaveVisualizer,
        OternosLogo,
        MikuLogo,
        MikuCornerDeco,
        MikuTicker,
        CornerBrackets,
        DataTicker,
        TrackRecommender,
        NormMeter,
        NierLogo,
        AngelTicker,
        BaroqueFrame,
    )
    from .diagnostics import get_logger, log_exception, set_debug
    from .aidj import AIDJEngine, AIDJView
    from .netstream import NetStreamView
    from .audiofx import AudioFXView
    from .cyberui import (
        GlitchText, CircuitLines, RadarSweep,
        FrequencyRing, StatusMatrix, BinaryRain,
        NodeGraph, TerminalCursor,
        WaveformScope, BeatPulse, GlyphWall,
        SpectrumBars, HoloFrame, SignalMeter,
        PlasmaRing, DataBurst,
    )


try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB
except ImportError:
    pass



class SmoothScroller:
    """Momentum smooth scrolling."""
    DECAY=0.78; MIN_VEL=0.004; INTERVAL=20; BOOST=0.006

    def __init__(self, root):
        self._root=root; self._vel={}; self._jobs={}

    def scroll(self, widget, delta):
        wid=id(widget); direction=-1 if delta>0 else 1
        self._vel[wid]=max(-0.12,min(0.12,self._vel.get(wid,0.0)+direction*self.BOOST))
        if not self._jobs.get(wid): self._animate(widget,wid)

    def stop(self, widget):
        wid=id(widget)
        if self._jobs.get(wid):
            try: self._root.after_cancel(self._jobs[wid])
            except Exception: pass
        self._jobs[wid]=None; self._vel[wid]=0.0

    def _animate(self, widget, wid):
        vel=self._vel.get(wid,0.0)
        if abs(vel)<self.MIN_VEL:
            self._vel[wid]=0.0; self._jobs[wid]=None; return
        try: widget.yview_moveto(widget.yview()[0]+vel)
        except Exception:
            self._vel[wid]=0.0; self._jobs[wid]=None; return
        self._vel[wid]=vel*self.DECAY
        self._jobs[wid]=self._root.after(self.INTERVAL,lambda:self._animate(widget,wid))

class VoidPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("OTERNOS PLAYER  //  v1.1")
        self._tracks_dirty = True
        self._scroller = SmoothScroller(root)  # full redraw needed flag
        self.root.configure(bg=C["bg"])
        self.root.geometry("1100x700")
        self.root.minsize(900, 600)
        self._is_maximized = False
        self._restore_geo = "1100x700"
        self._hwnd = None
        self._session_start = time.time()
        # Set taskbar / window icon
        try:
            import base64
            import tempfile

            _ico_data = base64.b64decode(_ICON_B64)
            _ico_tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            _ico_tmp.write(_ico_data)
            _ico_tmp.close()
            _ico_img = tk.PhotoImage(file=_ico_tmp.name)
            self.root.iconphoto(True, _ico_img)
            self._icon_img = _ico_img  # prevent GC
        except Exception:
            pass

        self.engine = AudioEngine()
        self._logger = get_logger()
        self.library = []
        self._album_meta = {}  # {album_name: {"art_path":…,"art_url":…,"fav":bool}}
        self.playlists = {}
        self.queue = []  # auto-context (current library/playlist view)
        self.queue_pos = -1
        self._manual_queue = []  # explicit user-added tracks (drain first)
        self.current_idx = -1
        self._skip_counts = {}
        self._flow_mode = False
        self._smart_skip_on = False
        self._voice_on = False
        self._ambient_win = None
        self._lyric_ticker_job = None
        self.shuffle = False
        self.repeat_mode = "off"
        self.seeking = False
        self.active_playlist = None
        self.view = "library"
        self._display_indices = []
        self._dx = self._dy = 0

        # Spotify
        self.sp_auth = SpotifyAuth()
        self.sp_api = SpotifyAPI(self.sp_auth)
        self._sp_tracks = []  # current spotify track list shown
        self._sp_view = "home"  # home | liked | playlist | search

        self._sp_mode = False  # True when Spotify is the active audio source
        self._active_source = (
            "none"  # "spotify" | "youtube" | "soundcloud" | "library" | "none"
        )
        self._sp_pos_ms = 0
        self._sp_dur_ms = 0
        self._sp_playing = False

        # SoundCloud
        self.sc_api = SoundCloudAPI()
        self._sc_tracks = []           # points to whichever view's list is active
        self._sc_search_tracks = []    # search results
        self._sc_likes_tracks = []     # likes results
        self._sc_search_label = ""     # content label for search view
        self._sc_likes_label = ""      # content label for likes view
        self._sc_view = "search"  # search | likes | favorites
        self._sc_favorites = []  # list of saved track dicts
        self._sc_current_track = None  # track dict of currently playing SC track
        self._sc_stream_queue = []  # ordered list of SC track dicts queued for playback
        self._sc_last_query = ""       # last search query for pagination
        self._sc_search_offset = 0    # current pagination offset
        self._sc_can_load_more = False # whether a "Load More" row is shown

        # YouTube
        self.yt_api = YouTubeAPI()
        self._yt_tracks = []
        self._yt_view = "search"  # search only
        self._yt_current_track = None  # track dict of currently playing YT track

        # Deezer
        self.dz_api = DeezerAPI()
        self._dz_tracks = []
        self._dz_view = "search"   # search | chart
        self._dz_current_track = None

        # Internet Archive
        self.ia_api = InternetArchiveAPI()
        self._ia_items = []        # search result items (identifier level)
        self._ia_files = []        # expanded file list for selected item
        self._ia_current = None    # currently playing {identifier, file, title}

        # Bandcamp
        self.bc_api = BandcampAPI()
        self._bc_tracks = []
        self._bc_current_track = None

        # Sleep timer
        self._sleep_minutes = 0
        self._sleep_end_time = None
        self._sleep_job = None

        # Mini player
        self._mini_win = None

        # Lyrics
        self._lyrics_cache = {}  # key -> plain text string
        self._synced_cache = {}  # key -> [(ms, line), ...]
        self._source_cache = {}  # key -> source string (lrclib.net / musixmatch / etc)
        self._current_lyrics_key = (
            None  # (artist_lower, title_lower) for current track — full untruncated
        )
        self._notif_win = None
        self._notif_dismiss_job = None
        self._lyrics_job = None
        self._lyrics_sync_job = None
        self._lyrics_lines = []  # current list of (ms, line_label_widget)
        self._lyrics_active_line = -1

        # Recently played history  (loaded from disk below)
        self._history = []
        self._history_max = 200

        # Last.fm scrobbler (credentials loaded after _load_data)
        self._scrobbler = None
        self._scrobble_job = None

        # Discord RPC
        self._discord = DiscordRPC()
        self._discord_enabled = False

        # Folder watcher
        self._watcher = FolderWatcher(self._on_watcher_new_file)

        # AI DJ
        self.aidj = AIDJEngine(self)
        self._aidj_view = AIDJView(self)

        # Local Network Streaming
        self._netstream_view = NetStreamView(self)

        # Playback Manipulation FX
        self._audiofx_view = AudioFXView(self)

        # Crossfade
        self._xfade_job = None
        self._xfade_active = False
        self._xfade_target_vol = 1.0
        self._xfade_fading_in = False
        self._xfade_loading = False

        # Playback speed
        self._playback_speed = 1.0
        self._current_play_path = None  # path of whatever is loaded into engine

        # A-B loop
        self._ab_a = None  # seconds
        self._ab_b = None
        self._ab_active = False

        # Bookmarks  {lib_idx: [(seconds, label), ...]}
        self._bookmarks = {}

        # BPM / mood analysis caches
        self._bpm_cache = {}  # path -> bpm float
        self._mood_cache = {}  # path -> mood string

        # Album art dedup
        self._art_url_last = None

        # Normalization meter state
        self._norm_rms = 0.0
        self._norm_peak = 0.0

        # Command palette
        self._palette_win = None

        # Theme editor
        self._theme_presets = {
            "VOID": {
                "bg": "#050505",
                "panel": "#0c0c0c",
                "border": "#1f1f1f",
                "border2": "#2e2e2e",
                "white": "#e8e8e8",
                "white2": "#9a9a9a",
                "white3": "#424242",
                "glow": "#ffffff",
                "select": "#1e1e1e",
                "select2": "#242424",
                "red": "#cc2222",
            },
            "CRIMSON": {
                "bg": "#0d0508",
                "panel": "#160a0c",
                "border": "#3a1520",
                "border2": "#502030",
                "white": "#f0d0d8",
                "white2": "#b07080",
                "white3": "#603040",
                "glow": "#e05070",
                "select": "#1a0810",
                "select2": "#220c14",
                "red": "#e05070",
            },
            "EMERALD": {
                "bg": "#050d08",
                "panel": "#0a1610",
                "border": "#153025",
                "border2": "#1e4030",
                "white": "#d0f0e0",
                "white2": "#70b090",
                "white3": "#305040",
                "glow": "#40c070",
                "select": "#081408",
                "select2": "#0c1c10",
                "red": "#c04040",
            },
            "COBALT": {
                "bg": "#05080d",
                "panel": "#0a1020",
                "border": "#152540",
                "border2": "#1e3558",
                "white": "#c8d8f8",
                "white2": "#6890c0",
                "white3": "#2a4060",
                "glow": "#4080e0",
                "select": "#080c18",
                "select2": "#0c1220",
                "red": "#c04040",
            },
            "AMBER": {
                "bg": "#0d0a05",
                "panel": "#161208",
                "border": "#352808",
                "border2": "#4a380a",
                "white": "#f8e8c0",
                "white2": "#c0a060",
                "white3": "#604820",
                "glow": "#d0a030",
                "select": "#181008",
                "select2": "#20160a",
                "red": "#c04030",
            },
            "VIOLET": {
                "bg": "#0a0510",
                "panel": "#120a18",
                "border": "#251040",
                "border2": "#341858",
                "white": "#e0d0f8",
                "white2": "#9070c0",
                "white3": "#402860",
                "glow": "#9060d0",
                "select": "#0e0818",
                "select2": "#160c20",
                "red": "#c04080",
            },
            "GHOST": {
                "bg": "#f8f8f8",
                "panel": "#eeeeee",
                "border": "#cccccc",
                "border2": "#bbbbbb",
                "white": "#111111",
                "white2": "#444444",
                "white3": "#999999",
                "glow": "#000000",
                "select": "#e8e8e8",
                "select2": "#e0e0e0",
                "red": "#cc2222",
            },
            "MILITARY": {
                "bg": "#080c06",
                "panel": "#0e1209",
                "border": "#1a2210",
                "border2": "#243016",
                "white": "#c8d4a0",
                "white2": "#7a9050",
                "white3": "#3a4820",
                "glow": "#a0c040",
                "select": "#0c1008",
                "select2": "#101408",
                "red": "#c06020",
            },
            "MIKU": {
                "bg": "#03080f",
                "panel": "#071520",
                "border": "#0a3040",
                "border2": "#0d4a5e",
                "white": "#cff8f4",
                "white2": "#5ecfca",
                "white3": "#1e6068",
                "glow": "#39c5bb",
                "select": "#071a24",
                "select2": "#0c2535",
                "red": "#ff6eb4",
            },
            "NERV": {
                "bg": "#000000",
                "panel": "#0a0000",
                "border": "#3a0000",
                "border2": "#550000",
                "white": "#f0f0f0",
                "white2": "#cc0000",
                "white3": "#660000",
                "glow": "#ff0000",
                "select": "#140000",
                "select2": "#1e0000",
                "red": "#ff0000",
            },
            "NIER": {
                "bg": "#0e0d09",
                "panel": "#161510",
                "border": "#2e2a1a",
                "border2": "#3e3820",
                "white": "#e8e4d0",
                "white2": "#a09878",
                "white3": "#504838",
                "glow": "#c8b878",
                "select": "#1c1a12",
                "select2": "#26231a",
                "red": "#c85030",
            },
            "ANGEL": {
                "bg": "#fdf6fb",
                "panel": "#f7edf5",
                "border": "#e8cce0",
                "border2": "#d9aace",
                "white": "#1a0e18",
                "white2": "#6b3d62",
                "white3": "#b07aa0",
                "glow": "#d4449a",
                "select": "#f0dcea",
                "select2": "#e8cce0",
                "red": "#c0305a",
            },
        }

        self._load_data()
        try:
            set_debug(bool(self.settings.get("debug", False)))
        except Exception:
            pass

        # Init scrobbler with loaded credentials
        self._scrobbler = LastFmScrobbler(
            api_key=self.settings.get("lastfm_api_key", ""),
            api_secret=self.settings.get("lastfm_api_secret", ""),
            session_key=self.settings.get("lastfm_session_key", ""),
        )

        self._build_ui()

        self.root.after(200, self._attach_hover_sounds)
        self._poll()
        self._start_audio_capture()
        self._apply_settings()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Alt-F4>", lambda e: self._on_close())
        self.root.bind("<Alt-space>", lambda e: self._show_system_menu())
        # Boot text sequence on sidebar status label
        self.root.after(400, self._boot_status_sequence)

        # Discord RPC — delay so it doesn't slow startup
        self.root.after(
            3000,
            lambda: threading.Thread(target=self._discord_connect, daemon=True).start(),
        )

        # Start folder watchers for any saved watch dirs
        for d in self.settings.get("watch_dirs", []):
            if Path(d).is_dir():
                self._watcher.watch(d)

        # Global media key hotkeys
        try:
            self._hotkeys = GlobalHotkeys(
                {
                    1: lambda: self.root.after(0, self._toggle_play),
                    2: lambda: self.root.after(0, self._next),
                    3: lambda: self.root.after(0, self._prev),
                    4: lambda: self.root.after(0, self._toggle_play),
                }
            )
            self._hotkeys.start()
        except Exception:
            # Hotkeys unavailable (non-Windows or permissions issue) — continue without them
            self._hotkeys = None
        if self.sp_auth.is_authenticated():
            self.root.after(
                4000, lambda: self._sp_poll_np() if self._sp_np_job is None else None
            )

        # Global keyboard shortcuts
        self.root.bind("<Control-p>", lambda e: self._open_palette())
        self.root.bind("<Control-k>", lambda e: self._open_palette())

        def _guard(fn):
            def _inner(e):
                fw = self.root.focus_get()
                if fw and fw.winfo_class() in ("Entry", "Text", "TEntry"):
                    return
                fn()

            return _inner

        self.root.bind("<space>", _guard(lambda: (self._toggle_play(), self._show_ghost("[ ▶ PLAY ]" if not self.engine.is_playing else "[ ⏸ PAUSE ]"))))
        self.root.bind("<KeyPress-n>", _guard(lambda: (self._next(), self._show_ghost("[ ⏭ NEXT ]"))))
        self.root.bind("<KeyPress-p>", _guard(lambda: (self._prev(), self._show_ghost("[ ⏮ PREV ]"))))
        self.root.bind("<Right>", _guard(lambda: (self._seek_relative(5), self._show_ghost("[ → +5s ]"))))
        self.root.bind("<Left>", _guard(lambda: (self._seek_relative(-5), self._show_ghost("[ ← -5s ]"))))
        self.root.bind("<Shift-Right>", _guard(lambda: (self._seek_relative(30), self._show_ghost("[ → +30s ]"))))
        self.root.bind("<Shift-Left>", _guard(lambda: (self._seek_relative(-30), self._show_ghost("[ ← -30s ]"))))
        self.root.bind(
            "<Up>",
            _guard(
                lambda: (
                    self.engine.set_volume(min(1.0, self.engine.volume + 0.05)),
                    self._upd_vol(),
                    self._show_ghost(f"[ VOL {int(min(1.0, self.engine.volume + 0.05)*100)}% ]"),
                )
            ),
        )
        self.root.bind(
            "<Down>",
            _guard(
                lambda: (
                    self.engine.set_volume(max(0.0, self.engine.volume - 0.05)),
                    self._upd_vol(),
                    self._show_ghost(f"[ VOL {int(max(0.0, self.engine.volume - 0.05)*100)}% ]"),
                )
            ),
        )
        self.root.bind("<Control-l>", _guard(lambda: self._switch_view("library")))
        self.root.bind("<Control-q>", _guard(lambda: self._switch_view("queue")))
        self.root.bind("<Control-y>", _guard(lambda: self._switch_view("lyrics")))
        self.root.bind("<Control-m>", _guard(self._toggle_mini_player))
        self.root.bind("<Control-v>", _guard(lambda: self._switch_view("visualizer")))
        self.root.bind("<Control-f>", lambda e: self._focus_search())

    def _focus_search(self):
        """Switch to library view and focus the search entry."""
        if self.view not in ("library", "playlist"):
            self._switch_view("library")
        def _do_focus():
            try:
                for w in self.lib_frame.winfo_children():
                    for child in w.winfo_children():
                        if child.winfo_class() == "Entry":
                            child.focus_set()
                            child.selection_range(0, "end")
                            return
            except Exception:
                pass
        self.root.after(60, _do_focus)

    def _on_close(self):
        # Set closing flag first — all polling callbacks check this
        self._closing = True
        # Signal all background threads to stop
        self._fft_active = False
        self._fft_file_active = False
        # Stop NetStream server + discovery before Tk teardown
        if hasattr(self, '_netstream_view'):
            try:
                self._netstream_view.server.stop()
                self._netstream_view.client.stop_discovery()
            except Exception:
                pass

        # Clean up AudioFX temp files
        if hasattr(self, '_audiofx_view'):
            try:
                self._audiofx_view.cleanup()
            except Exception:
                pass

        for attr in (
            "_scrobble_job",
            "_sleep_job",
            "_sp_np_job",
            "_lyrics_job",
            "_lyrics_sync_job",
            "_lp_sync_job",
            "_lyric_ticker_job",
            "_notif_dismiss_job",
            "_xfade_job",
            "_vol_hover_job",
            "_vol_anim_job",
            "_repeat_mode_job",
            "_tl_zoom_job",
            "_prog_hover_job",
            "_sp_vol_job",
            "_viz_job",
            "_scan_job",
            "_ghost_job",
            "_status_type_job",
            "_yt_load_anim_job",
            "_seek_rel_job",
            "_seek_rel_sp_job",
        ):
            job = getattr(self, attr, None)
            if job:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
                setattr(self, attr, None)
        self._save()
        self._cursor_trail_stop()
        if getattr(self, "_hotkeys", None):
            self._hotkeys.stop()
        if getattr(self, "_mini_win", None):
            try:
                self._mini_win.destroy()
            except:
                pass
        try:
            if self.root.overrideredirect():
                self.root.overrideredirect(False)
        except Exception:
            pass
        self.root.destroy()

    # ── PERSISTENCE ───────────────────────
    def _load_data(self):
        self.settings = {
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
            # New
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
        if DATA_FILE.exists():
            try:
                d = json.loads(DATA_FILE.read_text())
                self.library = [
                    t for t in d.get("library", []) if Path(t["path"]).exists()
                ]
                self.playlists = d.get("playlists", {})
                self.settings.update(d.get("settings", {}))
                self._history = d.get("history", [])[-self._history_max :]
                self._bookmarks = {int(k): v for k, v in d.get("bookmarks", {}).items()}
                self._sc_favorites = d.get("sc_favorites", [])
                self._album_meta = d.get("album_meta", {})
                self.shuffle = d.get("shuffle", False)
                self.repeat_mode = d.get("repeat_mode", "off")
            except Exception as exc:
                try:
                    log_exception("load_data_failed", exc)
                except Exception:
                    pass

        # Restore BPM/mood caches and gain_db from saved library entries
        for t in self.library:
            p = t.get("path", "")
            if p:
                if t.get("bpm"):  self._bpm_cache[p]  = float(t["bpm"])
                if t.get("mood"): self._mood_cache[p] = t["mood"]
                # gain_db stays in library entry directly — no separate cache needed

        self.ui_sounds = UISounds(volume=self.settings.get("ui_sound_volume", 0.18))
        self.ui_sounds.set_enabled(bool(self.settings.get("ui_sounds_enabled", True)))

    def _save(self):
        try:
            DATA_FILE.write_text(
                json.dumps(
                    {
                        "library": self.library,
                        "playlists": self.playlists,
                        "settings": self.settings,
                        "history": self._history[-self._history_max :],
                        "bookmarks": {str(k): v for k, v in self._bookmarks.items()},
                        "sc_favorites": getattr(self, "_sc_favorites", []),
                        "album_meta": getattr(self, "_album_meta", {}),
                        "shuffle": self.shuffle,
                        "repeat_mode": self.repeat_mode,
                    },
                    indent=2,
                )
            )
        except Exception as exc:
            try:
                log_exception("save_failed", exc)
            except Exception:
                pass

    # ── POPUP ANIMATION HELPERS ───────────
    def _popup_fadein(self, win, duration_ms=110, start=0.0, end=1.0):
        """Fade a Toplevel from start alpha to end alpha over duration_ms."""
        steps = 12
        delay = max(6, duration_ms // steps)
        def _step(i=0):
            if not win.winfo_exists():
                return
            t = i / steps
            # ease-out curve
            t_eased = 1 - (1 - t) ** 2
            alpha = start + (end - start) * t_eased
            try:
                win.attributes("-alpha", alpha)
            except Exception:
                return
            if i < steps:
                win.after(delay, lambda: _step(i + 1))
        win.attributes("-alpha", start)
        win.after(8, lambda: _step(1))

    def _popup_fadeout(self, win, duration_ms=80, on_done=None):
        """Fade a Toplevel out then destroy it."""
        if not win.winfo_exists():
            return
        try:
            start = float(win.attributes("-alpha"))
        except Exception:
            start = 1.0
        steps = 8
        delay = max(6, duration_ms // steps)
        def _step(i=0):
            if not win.winfo_exists():
                if on_done:
                    on_done()
                return
            t = i / steps
            alpha = start * (1 - t)
            try:
                win.attributes("-alpha", alpha)
            except Exception:
                pass
            if i < steps:
                win.after(delay, lambda: _step(i + 1))
            else:
                try:
                    win.destroy()
                except Exception:
                    pass
                if on_done:
                    on_done()
        _step(1)

    def _popup_setup(self, win, title="", w=None, h=None, resizable=False,
                     transient=True, grab=False, center=True):
        """
        Standard popup scaffold:
          - overrideredirect so it uses our own chrome
          - centered over the main window
          - cybercore header bar with title + animated [ ✕ ] close
          - fade-in entrance, fade-out on close
        Returns the inner content frame to pack widgets into.
        """
        win.overrideredirect(True)
        win.configure(bg=C["bg"])
        if transient:
            win.transient(self.root)

        # Size + center
        if w and h:
            if center:
                rx = self.root.winfo_x()
                ry = self.root.winfo_y()
                rw = self.root.winfo_width()
                rh = self.root.winfo_height()
                x = rx + (rw - w) // 2
                y = ry + (rh - h) // 3
                win.geometry(f"{w}x{h}+{x}+{y}")
            else:
                win.geometry(f"{w}x{h}")

        # 1px glow border via outer frame
        outer = tk.Frame(win, bg=C["border2"], padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        chrome = tk.Frame(outer, bg=C["bg"])
        chrome.pack(fill="both", expand=True)

        # ── Header bar ────────────────────────────────────────────────────
        hdr = tk.Frame(chrome, bg=C["panel"], height=32)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(chrome, bg=C["border2"], height=1).pack(fill="x")

        # Drag to move — per-window state stored on the widget itself
        _drag = {}
        def _drag_start(e):
            _drag["x"] = e.x_root - win.winfo_x()
            _drag["y"] = e.y_root - win.winfo_y()
        def _drag_move(e):
            win.geometry(f"+{e.x_root - _drag['x']}+{e.y_root - _drag['y']}")
        hdr.bind("<ButtonPress-1>", _drag_start)
        hdr.bind("<B1-Motion>", _drag_move)

        # Left accent stripe
        tk.Frame(hdr, bg=C["border2"], width=3).pack(side="left", fill="y")

        # Title
        title_lbl = tk.Label(hdr, text=title, font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["panel"], padx=8)
        title_lbl.pack(side="left")
        # 1-frame title glitch on open
        if title:
            import random as _r2
            _gc = "▓░▒█◈"
            _g = "".join(_r2.choice(_gc) if _r2.random() < 0.35 else c for c in title)
            title_lbl.config(text=_g)
            title_lbl.after(80, lambda: title_lbl.config(text=title))

        # Close button with ColorAnim
        def _close():
            self._popup_fadeout(win)

        cl = tk.Label(hdr, text="[ ✕ ]", font=("Courier New", 8),
                      fg=C["white3"], bg=C["panel"], cursor="hand2", padx=8)
        cl.pack(side="right")
        cl.bind("<Button-1>", lambda e: _close())
        cl.bind("<Enter>", lambda e: ColorAnim.run(self.root, cl, "fg", C["white3"], C["red"], duration_ms=60))
        cl.bind("<Leave>", lambda e: ColorAnim.run(self.root, cl, "fg", C["red"], C["white3"], duration_ms=60))
        win.bind("<Escape>", lambda e: _close())

        # [13] Animated boot bar — sweeps across header bottom on open
        _load_cv = tk.Canvas(chrome, bg=C["bg"], height=1, highlightthickness=0)
        _load_cv.pack(fill="x")
        def _run_load_bar(step=0, steps=24):
            try:
                _load_cv.delete("all")
                W = _load_cv.winfo_width() or (w or 400)
                filled = int(W * step / steps)
                _load_cv.create_rectangle(0, 0, filled, 1, fill=C["glow"], outline="")
                if step < steps:
                    win.after(9, lambda: _run_load_bar(step + 1, steps))
            except Exception:
                pass
        win.after(40, _run_load_bar)

        # Content area
        content = tk.Frame(chrome, bg=C["bg"])
        content.pack(fill="both", expand=True)

        # Fade in
        self._popup_fadein(win)

        return content, _close

    # ── SETTINGS ──────────────────────────
    def _open_settings(self):
        if (
            hasattr(self, "_settings_win")
            and self._settings_win
            and self._settings_win.winfo_exists()
        ):
            self._settings_win.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("OTERNOS // SETTINGS")
        win.configure(bg=C["bg"])
        win.geometry("600x700")
        win.resizable(False, False)
        self._settings_win = win
        self._popup_fadein(win)

        # ── scanline header canvas ───────────────────────────────────────
        hdr_cv = tk.Canvas(win, bg=C["panel"], height=56, highlightthickness=0)
        hdr_cv.pack(fill="x")

        def _draw_settings_hdr(e=None):
            hdr_cv.delete("all")
            W = hdr_cv.winfo_width() or 600
            # scanlines
            for y in range(0, 56, 3):
                hdr_cv.create_line(0, y, W, y, fill="#0a0a0a", width=1)
            # bottom borders
            hdr_cv.create_line(0, 54, W, 54, fill=C["border2"], width=2)
            hdr_cv.create_line(0, 56, W, 56, fill=C["border"], width=1)
            # bracket title
            hdr_cv.create_text(
                20,
                28,
                text="[",
                font=("Courier New", 14, "bold"),
                fill=C["white3"],
                anchor="w",
            )
            hdr_cv.create_text(
                34,
                28,
                text="SYS::CONFIG",
                font=("Courier New", 12, "bold"),
                fill=C["white"],
                anchor="w",
            )
            hdr_cv.create_text(
                168,
                28,
                text="]",
                font=("Courier New", 14, "bold"),
                fill=C["white3"],
                anchor="w",
            )
            hdr_cv.create_text(
                W - 20,
                28,
                text="v1.1",
                font=("Courier New", 8),
                fill=C["white3"],
                anchor="e",
            )

        hdr_cv.bind("<Configure>", lambda e: _draw_settings_hdr())
        win.after(10, _draw_settings_hdr)

        # Animated scan line sweeps down through header every 2.5s
        _scan_state = [0]
        def _sweep_scan():
            if not win.winfo_exists():
                return
            try:
                hdr_cv.delete("hdr_scan")
                W = hdr_cv.winfo_width() or 600
                sy = (_scan_state[0] % 56)
                bv = int(0x30 + (1 - sy / 56) * 0x28)
                hdr_cv.create_line(0, sy, W, sy,
                    fill=f"#{bv:02x}{bv:02x}{bv:02x}", width=1, tags="hdr_scan")
                _scan_state[0] += 2
            except Exception:
                pass
            win.after(40, _sweep_scan)
        win.after(200, _sweep_scan)

        cl = tk.Label(
            hdr_cv,
            text="[ ✕ ]",
            font=("Courier New", 10),
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
            padx=10,
        )
        cl.place(relx=1.0, rely=0.5, anchor="e", x=-8)
        cl.bind("<Button-1>", lambda e: self._popup_fadeout(win))
        cl.bind("<Enter>", lambda e: ColorAnim.run(self.root, cl, "fg", C["white3"], C["red"], duration_ms=60))
        cl.bind("<Leave>", lambda e: ColorAnim.run(self.root, cl, "fg", C["red"], C["white3"], duration_ms=60))

        # ── scrollable body ─────────────────────────────────────────────
        body_outer = tk.Frame(win, bg=C["bg"])
        body_outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(body_outer, bg=C["bg"], highlightthickness=0)
        sb = tk.Scrollbar(
            body_outer,
            orient="vertical",
            command=canvas.yview,
            bg=C["panel"],
            troughcolor=C["bg"],
            width=8,
            relief="flat",
            bd=0,
        )
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(canvas, bg=C["bg"])
        body_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(body_id, width=e.width))

        def _settings_scroll(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)) * 3, "units")

        canvas.bind("<MouseWheel>", _settings_scroll)
        body.bind("<MouseWheel>", _settings_scroll)

        # Rebind all children whenever body resizes (new widgets added)
        def _bind_children(w):
            w.bind("<MouseWheel>", _settings_scroll)
            for child in w.winfo_children():
                _bind_children(child)

        body.bind(
            "<Configure>",
            lambda e: (
                _bind_children(body),
                canvas.configure(scrollregion=canvas.bbox("all")),
            ),
        )

        # ── footer ──────────────────────────────────────────────────────
        foot = tk.Frame(win, bg=C["panel"], height=48)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)
        tk.Frame(foot, bg=C["border2"], height=2).pack(fill="x")
        tk.Frame(foot, bg=C["border"], height=1).pack(fill="x")
        save_btn = tk.Label(
            foot,
            text="▸ WRITE CONFIG",
            font=("Courier New", 9, "bold"),
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
            padx=18,
        )
        save_btn.pack(side="right", pady=10)
        save_btn.bind("<Button-1>", lambda e: self._save_settings(vars_map, win))
        save_btn.bind("<Enter>", lambda e: save_btn.config(fg=C["glow"]))
        save_btn.bind("<Leave>", lambda e: save_btn.config(fg=C["white3"]))
        reset_btn = tk.Label(
            foot,
            text="[ RESET ]",
            font=FM,
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
            padx=18,
        )
        reset_btn.pack(side="left", pady=10)
        reset_btn.bind("<Button-1>", lambda e: self._open_settings())
        reset_btn.bind("<Enter>", lambda e: reset_btn.config(fg=C["white"]))
        reset_btn.bind("<Leave>", lambda e: reset_btn.config(fg=C["white3"]))

        # ── helper builders ─────────────────────────────────────────────
        vars_map = {}
        s = self.settings

        _SECTION_ICONS = {
            ">> PLAYBACK": "▶",
            ">> EQUALIZER": "◈",
            ">> INTERFACE": "□",
            ">> LIBRARY": "▪",
            ">> INTEGRATIONS": "◉",
            ">> ADVANCED": "△",
            ">> CONVERT": "⇄",
        }

        def section(title):
            tk.Frame(body, bg=C["bg"], height=10).pack(fill="x")
            hf = tk.Frame(body, bg=C["bg"])
            hf.pack(fill="x", padx=20)
            icon = _SECTION_ICONS.get(title, "▸")
            tk.Label(
                hf,
                text=icon,
                font=("Courier New", 9, "bold"),
                fg=C["white3"],
                bg=C["bg"],
            ).pack(side="left", padx=(0, 6))
            tk.Label(
                hf,
                text=title.lstrip("> ").upper(),
                font=("Courier New", 8, "bold"),
                fg=C["white3"],
                bg=C["bg"],
            ).pack(side="left")
            tk.Frame(body, bg=C["border2"], height=1).pack(
                fill="x", padx=20, pady=(3, 0)
            )
            tk.Frame(body, bg=C["border"], height=1).pack(
                fill="x", padx=20, pady=(1, 3)
            )

        def row(label, widget_fn, key, hint=""):
            rf = tk.Frame(body, bg=C["bg"])
            rf.pack(fill="x", padx=28, pady=(4, 0))
            lf = tk.Frame(rf, bg=C["bg"])
            lf.pack(side="left", padx=(0, 16))
            tk.Label(
                lf,
                text=label,
                font=("Courier New", 9),
                fg=C["white2"],
                bg=C["bg"],
                anchor="w",
                width=24,
                justify="left",
            ).pack(anchor="w")
            if hint:
                tk.Label(
                    lf,
                    text=hint,
                    font=("Courier New", 8),
                    fg=C["white3"],
                    bg=C["bg"],
                    anchor="w",
                ).pack(anchor="w")
            wf = tk.Frame(rf, bg=C["bg"])
            wf.pack(side="left", fill="x", expand=True)
            var = widget_fn(wf, key)
            vars_map[key] = var
            tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=28)
            return var

        def make_toggle(parent, key):
            var = tk.BooleanVar(value=s.get(key, False))
            tf = tk.Frame(parent, bg=C["bg"])
            tf.pack(side="left")

            def _toggle():
                var.set(not var.get())
                lbl.config(
                    text="[ ON  ]" if var.get() else "[ OFF ]",
                    fg=C["white"] if var.get() else C["white3"],
                )

            lbl = tk.Label(
                tf,
                text="[ ON  ]" if var.get() else "[ OFF ]",
                font=FM,
                fg=C["white"] if var.get() else C["white3"],
                bg=C["bg"],
                cursor="hand2",
            )
            lbl.pack()
            lbl.bind("<Button-1>", lambda e: _toggle())
            return var

        def make_dropdown(parent, key, options):
            var = tk.StringVar(value=s.get(key, options[0]))
            frame = tk.Frame(parent, bg=C["bg"])
            frame.pack(side="left")
            lbl = tk.Label(
                frame,
                text=f"[ {var.get().upper()} ]",
                font=FM,
                fg=C["white2"],
                bg=C["bg"],
                cursor="hand2",
            )
            lbl.pack()

            def _cycle(e=None):
                idx = options.index(var.get()) if var.get() in options else 0
                var.set(options[(idx + 1) % len(options)])
                lbl.config(text=f"[ {var.get().upper()} ]")

            lbl.bind("<Button-1>", _cycle)
            return var

        def make_slider(parent, key, mn, mx, step, fmt="{:.2f}"):
            val = s.get(key, mn)
            var = tk.DoubleVar(value=val)
            sf = tk.Frame(parent, bg=C["bg"])
            sf.pack(side="left", fill="x", expand=True)
            disp = tk.Label(
                sf, text=fmt.format(val), font=FM, fg=C["white2"], bg=C["bg"], width=6
            )
            disp.pack(side="right")
            cv = tk.Canvas(
                sf,
                bg=C["border"],
                height=4,
                width=130,
                highlightthickness=0,
                cursor="hand2",
            )
            cv.pack(side="left", padx=(0, 8), pady=8)
            fill_id = cv.create_rectangle(0, 0, 0, 4, fill=C["white"], outline="")
            dot_id = cv.create_oval(-4, -2, 4, 6, fill=C["glow"], outline="")

            def _draw(v):
                frac = (v - mn) / (mx - mn)
                x = int(frac * 130)
                cv.coords(fill_id, 0, 0, max(1, x), 4)
                cv.coords(dot_id, x - 4, -2, x + 4, 6)
                disp.config(text=fmt.format(v))

            def _set(x):
                frac = max(0.0, min(1.0, x / 130))
                v = mn + round((frac * (mx - mn)) / step) * step
                var.set(v)
                _draw(v)

            cv.bind("<ButtonPress-1>", lambda e: _set(e.x))
            cv.bind("<B1-Motion>", lambda e: _set(e.x))
            _draw(val)
            return var

        def make_int_slider(parent, key, mn, mx):
            val = int(s.get(key, mn))
            var = tk.IntVar(value=val)
            sf = tk.Frame(parent, bg=C["bg"])
            sf.pack(side="left", fill="x", expand=True)
            disp = tk.Label(
                sf, text=str(val), font=FM, fg=C["white2"], bg=C["bg"], width=4
            )
            disp.pack(side="right")
            cv = tk.Canvas(
                sf,
                bg=C["border"],
                height=4,
                width=130,
                highlightthickness=0,
                cursor="hand2",
            )
            cv.pack(side="left", padx=(0, 8), pady=8)
            fill_id = cv.create_rectangle(0, 0, 0, 4, fill=C["white"], outline="")
            dot_id = cv.create_oval(-4, -2, 4, 6, fill=C["glow"], outline="")

            def _draw(v):
                frac = (v - mn) / (mx - mn)
                x = int(frac * 130)
                cv.coords(fill_id, 0, 0, max(1, x), 4)
                cv.coords(dot_id, x - 4, -2, x + 4, 6)
                disp.config(text=str(v))

            def _set(x):
                frac = max(0.0, min(1.0, x / 160))
                v = mn + round(frac * (mx - mn))
                var.set(v)
                _draw(v)

            cv.bind("<ButtonPress-1>", lambda e: _set(e.x))
            cv.bind("<B1-Motion>", lambda e: _set(e.x))
            _draw(val)
            return var

        def make_entry(parent, key):
            var = tk.StringVar(value=s.get(key, ""))
            e = tk.Entry(
                parent,
                textvariable=var,
                font=FM,
                bg=C["panel"],
                fg=C["white"],
                insertbackground=C["white"],
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=C["border"],
                width=28,
            )
            e.pack(side="left", ipady=3)
            return var

        section(">> PLAYBACK")
        row("Autoplay next track", make_toggle, "autoplay")
        row(
            "Crossfade",
            lambda p, k: make_int_slider(p, k, 0, 12),
            "crossfade_sec",
            hint="seconds  (0 = off)",
        )
        row("Normalize volume", make_toggle, "normalize", hint="level-match tracks")
        row(
            "Output device",
            lambda p, k: make_dropdown(
                p, k, ["default", "hdmi", "speakers", "headphones", "aux"]
            ),
            "output_device",
        )

        # ════════════════════════════════════════════════════════════════
        #  EQUALIZER
        # ════════════════════════════════════════════════════════════════
        section(">> EQUALIZER")
        _eq_sf = tk.Frame(body, bg=C["bg"])
        _eq_sf.pack(fill="x", padx=24, pady=(0, 4))
        if SCIPY_AVAILABLE:
            tk.Label(
                _eq_sf,
                text="● scipy + soundfile  [ ACTIVE ]",
                font=("Courier New", 7),
                fg="#44aa44",
                bg=C["bg"],
            ).pack(side="left")
        else:
            tk.Label(
                _eq_sf,
                text="● EQ DISABLED — run:  pip install scipy soundfile",
                font=("Courier New", 7),
                fg=C["red"],
                bg=C["bg"],
            ).pack(side="left")
        row(
            "EQ preset",
            lambda p, k: make_dropdown(
                p,
                k,
                [
                    "flat",
                    "bass boost",
                    "treble boost",
                    "vocal",
                    "electronic",
                    "rock",
                    "classical",
                    "podcast",
                ],
            ),
            "eq_preset",
        )

        # EQ band display (visual only — shows what each preset does)
        eq_frame = tk.Frame(body, bg=C["bg"])
        eq_frame.pack(fill="x", padx=24, pady=(2, 10))
        EQ_PRESETS = {
            "flat": [0] * 8,
            "bass boost": [6, 5, 3, 1, 0, 0, 0, 0],
            "treble boost": [0, 0, 0, 0, 1, 3, 5, 6],
            "vocal": [-2, -1, 2, 4, 4, 2, -1, -2],
            "electronic": [4, 3, 0, -2, -1, 2, 4, 3],
            "rock": [3, 2, 1, 0, 0, 1, 2, 3],
            "classical": [3, 2, 0, 0, 0, 0, 2, 3],
            "podcast": [-1, -1, 2, 4, 3, 1, 0, -1],
        }
        BANDS = ["60", "150", "400", "1k", "2.4k", "6k", "12k", "16k"]
        eq_cv = tk.Canvas(
            eq_frame,
            bg=C["panel2"],
            height=70,
            width=460,
            highlightthickness=1,
            highlightbackground=C["border"],
        )
        eq_cv.pack()

        def _draw_eq(preset="flat"):
            eq_cv.delete("all")
            bands = EQ_PRESETS.get(preset, [0] * 8)
            W2, H2 = 460, 70
            bw = W2 / len(bands)
            mid = H2 / 2
            for i, db in enumerate(bands):
                x1 = i * bw + 4
                x2 = (i + 1) * bw - 4
                bar_h = (db / 12.0) * (H2 / 2 - 6)
                y1 = mid - bar_h
                y2 = mid
                if db >= 0:
                    br = 120 + int(db / 12 * 135)
                    col = f"#{br:02x}{br:02x}{br:02x}"
                else:
                    br = 80 + int(abs(db) / 12 * 60)
                    col = f"#{br // 2:02x}{br // 2:02x}{br:02x}"
                eq_cv.create_rectangle(
                    x1, min(y1, y2), x2, max(y1, y2), fill=col, outline=""
                )
                eq_cv.create_text(
                    (x1 + x2) / 2,
                    H2 - 6,
                    text=BANDS[i],
                    font=("Courier New", 7),
                    fill=C["white3"],
                    anchor="s",
                )
            # centre line
            eq_cv.create_line(0, mid, W2, mid, fill=C["border"], width=1)

        _draw_eq(s.get("eq_preset", "flat"))
        # hook dropdown to redraw eq
        eq_var = vars_map.get("eq_preset")
        if eq_var:
            eq_var.trace("w", lambda *a: _draw_eq(eq_var.get()))

        # ════════════════════════════════════════════════════════════════
        #  VISUALIZER
        # ════════════════════════════════════════════════════════════════
        section(">> VISUALIZER")
        row(
            "FFT sensitivity",
            lambda p, k: make_slider(p, k, 0.5, 3.0, 0.1, fmt="{:.1f}x"),
            "viz_sensitivity",
            hint="scales bar heights",
        )
        row(
            "Smoothing",
            lambda p, k: make_slider(p, k, 0.05, 0.6, 0.01, fmt="{:.2f}"),
            "viz_smoothing",
            hint="lower = smoother",
        )
        row(
            "Visualizer FPS",
            lambda p, k: make_dropdown(p, k, ["15", "30", "60", "120", "144", "240"]),
            "viz_fps",
            hint="target frame rate — higher = smoother but more CPU",
        )

        # ════════════════════════════════════════════════════════════════
        #  SPOTIFY
        # ════════════════════════════════════════════════════════════════
        section(">> SPOTIFY")
        row(
            "Streaming quality",
            lambda p, k: make_dropdown(p, k, ["low", "normal", "high", "very high"]),
            "spotify_quality",
            hint="requires Spotify Premium for very high",
        )
        row("Crossfade", make_toggle, "spotify_crossfade", hint="blend between tracks")
        row(
            "Normalize volume",
            make_toggle,
            "spotify_normalize",
            hint="loud normalization on/off",
        )

        # ════════════════════════════════════════════════════════════════
        #  YOUTUBE
        # ════════════════════════════════════════════════════════════════
        section(">> YOUTUBE")

        # File-path widget for cookies.txt — uses StringVar so vars_map saves it
        def make_cookies_path(parent, key):
            var = tk.StringVar(value=s.get(key, ""))
            rf = tk.Frame(parent, bg=C["bg"])
            rf.pack(side="left", fill="x", expand=True)
            entry = tk.Label(
                rf,
                textvariable=var,
                font=("Courier New", 7),
                fg=C["white2"],
                bg=C["select"],
                anchor="w",
                width=32,
                padx=4,
                pady=2,
            )
            entry.pack(side="left", padx=(0, 6))

            def _browse():
                path = filedialog.askopenfilename(
                    title="Select YouTube cookies.txt",
                    filetypes=[("Netscape cookies", "*.txt"), ("All files", "*.*")],
                )
                if path:
                    var.set(path)

            def _clear():
                var.set("")

            browse_lbl = tk.Label(
                rf,
                text="[ BROWSE ]",
                font=FMS,
                fg=C["white3"],
                bg=C["bg"],
                cursor="hand2",
            )
            browse_lbl.pack(side="left", padx=2)
            browse_lbl.bind("<Button-1>", lambda e: _browse())
            clear_lbl = tk.Label(
                rf,
                text="[ CLEAR ]",
                font=FMS,
                fg=C["white3"],
                bg=C["bg"],
                cursor="hand2",
            )
            clear_lbl.pack(side="left")
            clear_lbl.bind("<Button-1>", lambda e: _clear())
            return var

        row(
            "YouTube cookies.txt",
            make_cookies_path,
            "yt_cookies_path",
            hint="for age-restricted videos — export from browser extension",
        )

        # ════════════════════════════════════════════════════════════════
        #  INTERFACE
        # ════════════════════════════════════════════════════════════════
        section(">> PERFORMANCE")
        row(
            "Hardware Accelerator",
            make_toggle,
            "hw_accel",
            hint="high FPS animations, GPU rendering hints, fast poll rate",
        )
        row(
            "Viz bars (HW off: 12)",
            make_toggle,
            "hw_accel_viz_reduce",
            hint="reduce visualizer bars when HW off for lower CPU use",
        )

        section(">> INTERFACE")
        row(
            "Boot animation",
            make_toggle,
            "boot_enabled",
            hint="show TronBoot sequence on launch",
        )
        row(
            "Boot fullscreen",
            make_toggle,
            "boot_fullscreen",
            hint="fullscreen boot or windowed",
        )
        row(
            "Desktop notifications",
            make_toggle,
            "show_notifications",
            hint="show track change popups",
        )
        row(
            "Borderless fullscreen",
            make_toggle,
            "borderless_fullscreen",
            hint="fills screen, no title bar or taskbar",
        )
        row(
            "Accent colour",
            lambda p, k: make_dropdown(
                p, k, ["white", "cyan", "green", "amber", "red", "purple"]
            ),
            "theme_accent",
        )
        row(
            "Show CLAUDE tab",
            make_toggle,
            "show_claude_tab",
            hint="AI diagnostic interface (restart to apply)",
        )
        row(
            "Cursor trail",
            make_toggle,
            "cursor_trail",
            hint="hex glyph particles follow the cursor",
        )

        # ════════════════════════════════════════════════════════════════
        #  PLAYBACK MODES
        # ════════════════════════════════════════════════════════════════
        section(">> PLAYBACK MODES")
        row(
            "Flow Mode",
            make_toggle,
            "flow_mode",
            hint="auto-queues similar tracks when library ends",
        )
        row(
            "Smart Skip",
            make_toggle,
            "smart_skip",
            hint="tracks you skip often get deprioritised",
        )
        row(
            "Voice Control",
            make_toggle,
            "voice_ctrl",
            hint="control playback with voice commands",
        )
        row(
            "Ambient Mode",
            make_toggle,
            "ambient_mode",
            hint="fullscreen visualizer with clock overlay",
        )

        # ════════════════════════════════════════════════════════════════
        #  LAST.FM
        # ════════════════════════════════════════════════════════════════
        section(">> LAST.FM SCROBBLING")
        row(
            "Enable scrobbling",
            make_toggle,
            "lastfm_enabled",
            hint="send played tracks to Last.fm",
        )
        row(
            "API Key",
            lambda p, k: make_entry(p, k),
            "lastfm_api_key",
            hint="from last.fm/api/accounts",
        )
        row("API Secret", lambda p, k: make_entry(p, k), "lastfm_api_secret")

        # Auth button
        auth_f = tk.Frame(body, bg=C["bg"])
        auth_f.pack(fill="x", padx=24, pady=(2, 8))
        ab = tk.Label(
            auth_f,
            text="[ CONNECT LAST.FM ]",
            font=FM,
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
            padx=8,
            pady=4,
        )
        ab.pack(side="left")
        ab.bind("<Button-1>", lambda e: (win.destroy(), self._open_lastfm_auth()))
        ab.bind("<Enter>", lambda e: ab.config(fg=C["white"]))
        ab.bind("<Leave>", lambda e: ab.config(fg=C["white3"]))
        sk_status = "✓ Connected" if s.get("lastfm_session_key") else "Not connected"
        tk.Label(auth_f, text=sk_status, font=FMS, fg=C["white3"], bg=C["bg"]).pack(
            side="left", padx=10
        )

        # ════════════════════════════════════════════════════════════════
        #  DISCORD
        # ════════════════════════════════════════════════════════════════
        section(">> DISCORD RICH PRESENCE")
        row(
            "Enable Discord RPC",
            make_toggle,
            "discord_enabled",
            hint="show now-playing in Discord status",
        )

        # ════════════════════════════════════════════════════════════════
        #  UI SOUNDS
        # ════════════════════════════════════════════════════════════════
        section(">> UI SOUNDS")
        row(
            "UI sounds enabled",
            make_toggle,
            "ui_sounds_enabled",
            hint="hover, click, and play chimes",
        )
        row(
            "UI sound volume",
            lambda p, k: make_slider(p, k, 0.0, 1.0, 0.01, fmt="{:.2f}"),
            "ui_sound_volume",
            hint="0 = silent  /  1 = loud",
        )

        # ════════════════════════════════════════════════════════════════
        #  CONVERT
        # ════════════════════════════════════════════════════════════════
        section(">> CONVERT")

        _conv_file      = tk.StringVar(value="")
        _conv_fmt       = tk.StringVar(value="mp3")
        _conv_bitrate   = tk.StringVar(value="320k")
        _conv_outdir    = tk.StringVar(value="")
        _conv_status    = tk.StringVar(value="")
        _conv_running   = [False]

        CONV_FORMATS  = ["mp3", "flac", "wav", "ogg", "aac", "m4a"]
        CONV_BITRATES = ["128k", "192k", "256k", "320k"]
        CONV_INPUT_TYPES = [
            ("Audio / Video", "*.mp3 *.mp4 *.wav *.flac *.ogg *.m4a *.aac *.wma *.opus *.mkv *.webm *.avi *.mov *.wmv"),
            ("All files", "*.*"),
        ]

        # ── input file row ───────────────────────────────────────────
        in_row = tk.Frame(body, bg=C["bg"])
        in_row.pack(fill="x", padx=28, pady=(6, 0))
        tk.Label(in_row, text="Input file", font=("Courier New", 9), fg=C["white2"],
                 bg=C["bg"], width=24, anchor="w").pack(side="left")
        in_lbl = tk.Label(in_row, textvariable=_conv_file, font=("Courier New", 7),
                          fg=C["white2"], bg=C["select"], anchor="w",
                          width=30, padx=4, pady=2)
        in_lbl.pack(side="left", padx=(0, 6))

        def _conv_browse_in():
            p = filedialog.askopenfilename(title="Select file to convert",
                                           filetypes=CONV_INPUT_TYPES)
            if p:
                _conv_file.set(p)
                if not _conv_outdir.get():
                    _conv_outdir.set(str(Path(p).parent))
                out_lbl.config(fg=C["white2"])

        browse_in = tk.Label(in_row, text="[ BROWSE ]", font=FMS, fg=C["white3"],
                             bg=C["bg"], cursor="hand2")
        browse_in.pack(side="left")
        browse_in.bind("<Button-1>", lambda e: _conv_browse_in())
        browse_in.bind("<Enter>", lambda e: browse_in.config(fg=C["white"]))
        browse_in.bind("<Leave>", lambda e: browse_in.config(fg=C["white3"]))
        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=28)

        # ── output dir row ───────────────────────────────────────────
        out_row = tk.Frame(body, bg=C["bg"])
        out_row.pack(fill="x", padx=28, pady=(4, 0))
        tk.Label(out_row, text="Output folder", font=("Courier New", 9), fg=C["white2"],
                 bg=C["bg"], width=24, anchor="w").pack(side="left")
        out_lbl = tk.Label(out_row, textvariable=_conv_outdir, font=("Courier New", 7),
                           fg=C["white3"], bg=C["select"], anchor="w",
                           width=30, padx=4, pady=2)
        out_lbl.pack(side="left", padx=(0, 6))

        def _conv_browse_out():
            d = filedialog.askdirectory(title="Select output folder")
            if d:
                _conv_outdir.set(d)
                out_lbl.config(fg=C["white2"])

        browse_out = tk.Label(out_row, text="[ BROWSE ]", font=FMS, fg=C["white3"],
                              bg=C["bg"], cursor="hand2")
        browse_out.pack(side="left")
        browse_out.bind("<Button-1>", lambda e: _conv_browse_out())
        browse_out.bind("<Enter>", lambda e: browse_out.config(fg=C["white"]))
        browse_out.bind("<Leave>", lambda e: browse_out.config(fg=C["white3"]))
        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=28)

        # ── format + bitrate row ─────────────────────────────────────
        fmt_row = tk.Frame(body, bg=C["bg"])
        fmt_row.pack(fill="x", padx=28, pady=(4, 0))
        tk.Label(fmt_row, text="Output format", font=("Courier New", 9), fg=C["white2"],
                 bg=C["bg"], width=24, anchor="w").pack(side="left")

        fmt_lbl = tk.Label(fmt_row, text=f"[ {_conv_fmt.get().upper()} ]",
                           font=FM, fg=C["white2"], bg=C["bg"], cursor="hand2")
        fmt_lbl.pack(side="left", padx=(0, 16))

        def _cycle_fmt(e=None):
            idx = CONV_FORMATS.index(_conv_fmt.get())
            _conv_fmt.set(CONV_FORMATS[(idx + 1) % len(CONV_FORMATS)])
            fmt_lbl.config(text=f"[ {_conv_fmt.get().upper()} ]")

        fmt_lbl.bind("<Button-1>", _cycle_fmt)
        fmt_lbl.bind("<Enter>", lambda e: fmt_lbl.config(fg=C["white"]))
        fmt_lbl.bind("<Leave>", lambda e: fmt_lbl.config(fg=C["white2"]))

        tk.Label(fmt_row, text="Bitrate", font=("Courier New", 9), fg=C["white2"],
                 bg=C["bg"], padx=(8)).pack(side="left")
        br_lbl = tk.Label(fmt_row, text=f"[ {_conv_bitrate.get()} ]",
                          font=FM, fg=C["white2"], bg=C["bg"], cursor="hand2")
        br_lbl.pack(side="left", padx=(4, 0))

        def _cycle_br(e=None):
            idx = CONV_BITRATES.index(_conv_bitrate.get())
            _conv_bitrate.set(CONV_BITRATES[(idx + 1) % len(CONV_BITRATES)])
            br_lbl.config(text=f"[ {_conv_bitrate.get()} ]")

        br_lbl.bind("<Button-1>", _cycle_br)
        br_lbl.bind("<Enter>", lambda e: br_lbl.config(fg=C["white"]))
        br_lbl.bind("<Leave>", lambda e: br_lbl.config(fg=C["white2"]))
        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", padx=28)

        # ── convert button + status ──────────────────────────────────
        ctrl_row = tk.Frame(body, bg=C["bg"])
        ctrl_row.pack(fill="x", padx=28, pady=(8, 2))

        status_lbl = tk.Label(ctrl_row, textvariable=_conv_status, font=FMS,
                              fg=C["white3"], bg=C["bg"], anchor="w")
        status_lbl.pack(side="left", fill="x", expand=True)

        def _run_convert():
            import subprocess
            import shutil
            if _conv_running[0]:
                return
            src = _conv_file.get().strip()
            outdir = _conv_outdir.get().strip()
            fmt = _conv_fmt.get()
            br = _conv_bitrate.get()
            if not src:
                _conv_status.set("⚠  No input file selected.")
                status_lbl.config(fg=C["red"])
                return
            if not Path(src).exists():
                _conv_status.set("⚠  Input file not found.")
                status_lbl.config(fg=C["red"])
                return
            if not outdir:
                outdir = str(Path(src).parent)
            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                # Try next to the exe (bundled)
                import sys as _sys
                for _d in [
                    str(Path(_sys.executable).parent),
                    getattr(_sys, "_MEIPASS", ""),
                ]:
                    _candidate = Path(_d) / "ffmpeg.exe"
                    if _candidate.exists():
                        ffmpeg = str(_candidate)
                        break
            if not ffmpeg:
                _conv_status.set("⚠  ffmpeg not found. Install ffmpeg and add to PATH.")
                status_lbl.config(fg=C["red"])
                return

            stem = Path(src).stem
            out_path = Path(outdir) / f"{stem}.{fmt}"
            # Avoid overwrite collision
            counter = 1
            while out_path.exists():
                out_path = Path(outdir) / f"{stem}_{counter}.{fmt}"
                counter += 1

            _conv_running[0] = True
            _conv_status.set("▸ Converting…")
            status_lbl.config(fg=C["white3"])
            conv_btn.config(fg=C["white3"])

            def _do():
                try:
                    cmd = [ffmpeg, "-y", "-i", src]
                    if fmt in ("mp3",):
                        cmd += ["-codec:a", "libmp3lame", "-b:a", br]
                    elif fmt in ("aac", "m4a"):
                        cmd += ["-codec:a", "aac", "-b:a", br]
                    elif fmt == "ogg":
                        cmd += ["-codec:a", "libvorbis", "-b:a", br]
                    elif fmt == "flac":
                        cmd += ["-codec:a", "flac"]
                    elif fmt == "wav":
                        cmd += ["-codec:a", "pcm_s16le"]
                    cmd += ["-vn", str(out_path)]
                    result = subprocess.run(cmd, capture_output=True, timeout=600)
                    if result.returncode == 0:
                        def _ok():
                            _conv_status.set(f"✓  Saved: {out_path.name}")
                            status_lbl.config(fg=C["white"])
                            conv_btn.config(fg=C["white3"])
                            _conv_running[0] = False
                        win.after(0, _ok)
                    else:
                        err = result.stderr.decode(errors="replace")[-120:]
                        def _fail(e=err):
                            _conv_status.set(f"⚠  ffmpeg error: {e}")
                            status_lbl.config(fg=C["red"])
                            conv_btn.config(fg=C["white3"])
                            _conv_running[0] = False
                        win.after(0, _fail)
                except subprocess.TimeoutExpired:
                    win.after(0, lambda: (
                        _conv_status.set("⚠  Timed out (>10 min)."),
                        status_lbl.config(fg=C["red"]),
                    ))
                    _conv_running[0] = False
                except Exception as ex:
                    def _ex(e=str(ex)):
                        _conv_status.set(f"⚠  {e}")
                        status_lbl.config(fg=C["red"])
                        conv_btn.config(fg=C["white3"])
                        _conv_running[0] = False
                    win.after(0, _ex)

            import threading as _thr
            _thr.Thread(target=_do, daemon=True).start()

        conv_btn = tk.Label(ctrl_row, text="▸ CONVERT", font=("Courier New", 9, "bold"),
                            fg=C["white3"], bg=C["panel"], cursor="hand2",
                            padx=14, pady=4)
        conv_btn.pack(side="right")
        conv_btn.bind("<Button-1>", lambda e: _run_convert())
        conv_btn.bind("<Enter>", lambda e: conv_btn.config(fg=C["glow"]) if not _conv_running[0] else None)
        conv_btn.bind("<Leave>", lambda e: conv_btn.config(fg=C["white3"]))

        # bottom padding
        tk.Frame(body, bg=C["bg"], height=20).pack()

    def _save_settings(self, vars_map, win):
        for key, var in vars_map.items():
            self.settings[key] = var.get()
        # Apply live settings
        self._apply_settings()
        self._save()
        win.destroy()

    def _apply_settings(self):
        global HW_ACCEL
        s = self.settings
        self._viz_sensitivity = float(s.get("viz_sensitivity", 1.0))
        self._viz_smooth = float(s.get("viz_smoothing", 0.18))
        try:
            self._viz_interval = max(4, int(1000 / int(s.get("viz_fps", 60))))
        except (ValueError, ZeroDivisionError):
            self._viz_interval = 16  # 60 fps fallback
        self._apply_borderless(s.get("borderless_fullscreen", False))
        self._apply_accent(s.get("theme_accent", "white"))
        # Restore saved theme on startup
        active = s.get("active_theme", "").upper()
        if active and active in {k.upper() for k in self._theme_presets}:
            preset_key = next(k for k in self._theme_presets if k.upper() == active)
            C.update(self._theme_presets[preset_key])
            C["panel2"] = C["panel"]
            self._rebuild_ui_colors()
        # Hardware Accelerator
        # Patch the constants module so widgets.py (which imported HW_ACCEL by value)
        # picks up the change on its next after() tick.
        import sys as _sys
        _constants_mod = None
        for _key in ("oternos.constants", "constants"):
            _constants_mod = _sys.modules.get(_key)
            if _constants_mod is not None:
                break
        new_hw = bool(s.get("hw_accel", True))
        if new_hw != HW_ACCEL:
            HW_ACCEL = new_hw
            if _constants_mod is not None:
                _constants_mod.HW_ACCEL = new_hw
            self._apply_hw_accel(HW_ACCEL)
        # Discord toggle
        if s.get("discord_enabled") and not self._discord_enabled:
            threading.Thread(target=self._discord_connect, daemon=True).start()
        elif not s.get("discord_enabled") and self._discord_enabled:
            self._discord.clear()
            self._discord_enabled = False
        # Last.fm credentials update
        if self._scrobbler:
            self._scrobbler.api_key = s.get("lastfm_api_key", "")
            self._scrobbler.api_secret = s.get("lastfm_api_secret", "")
            self._scrobbler.session_key = s.get("lastfm_session_key", "")
        # UI sounds
        if hasattr(self, "ui_sounds"):
            self.ui_sounds.set_enabled(bool(s.get("ui_sounds_enabled", True)))
            self.ui_sounds.set_volume(float(s.get("ui_sound_volume", 0.18)))
        # Playback modes
        self._flow_mode       = bool(s.get("flow_mode",   False))
        self._smart_skip_on   = bool(s.get("smart_skip",  False))
        self._voice_on        = bool(s.get("voice_ctrl",  False))
        if bool(s.get("ambient_mode", False)) and not getattr(self, "_ambient_win", None):
            self.root.after(0, self._open_ambient_mode)
        elif not bool(s.get("ambient_mode", False)) and getattr(self, "_ambient_win", None):
            try:
                self._ambient_win.destroy()
            except Exception:
                pass
            self._ambient_win = None
        # Cursor trail
        if bool(s.get("cursor_trail", True)):
            self._cursor_trail_start()
        else:
            self._cursor_trail_stop()
        # Restore shuffle / repeat button visuals from saved state
        if hasattr(self, "btn_shuf"):
            col = C["glow"] if self.shuffle else C["white3"]
            self.btn_shuf._active_fg = col
            self.btn_shuf.config(fg=col)
        if hasattr(self, "btn_repeat"):
            icon = {"off": "↺", "all": "↺", "one": "↻"}.get(self.repeat_mode, "↺")
            col = C["white3"] if self.repeat_mode == "off" else C["glow"]
            self.btn_repeat._active_fg = col
            self.btn_repeat.config(text=icon, fg=col)

    # ══════════════════════════════════════
    #  CURSOR TRAIL
    # ══════════════════════════════════════
    _TRAIL_GLYPHS = [
        "◈", "▪", "·", "▫", "○", "▸", "△", "◇",
        "□", "◌", "◦", "✦", "✧", "▵", "⬡", "▹",
    ]

    def _cursor_trail_start(self):
        if getattr(self, "_trail_active", False):
            return
        self._trail_active = True
        self._trail_particles = []   # {"x","y","vx","vy","life","decay","glyph","size","lbl"}
        self._trail_last_xy   = (0, 0)
        self._trail_spawn_dist = 0.0
        self._trail_lbl_pool  = []   # recycled Label widgets
        self._trail_motion_id = self.root.bind("<Motion>", self._trail_on_motion, add="+")
        self._trail_tick()

    def _cursor_trail_stop(self):
        if not getattr(self, "_trail_active", False):
            return
        self._trail_active = False
        try:
            self.root.unbind("<Motion>", self._trail_motion_id)
        except Exception:
            pass
        for p in self._trail_particles:
            try:
                p["lbl"].place_forget()
            except Exception:
                pass
        for lbl in self._trail_lbl_pool:
            try:
                lbl.place_forget()
            except Exception:
                pass
        self._trail_particles  = []
        self._trail_lbl_pool   = []

    def _trail_on_motion(self, event):
        if not getattr(self, "_trail_active", False):
            return
        cx, cy = event.x_root, event.y_root
        lx, ly = self._trail_last_xy
        dist = math.sqrt((cx - lx) ** 2 + (cy - ly) ** 2)
        self._trail_spawn_dist += dist
        self._trail_last_xy = (cx, cy)
        while self._trail_spawn_dist >= 18:
            self._trail_spawn_dist -= 18
            self._spawn_trail_particle(cx, cy, dist)

    def _trail_get_lbl(self):
        """Reuse a hidden label or create a new one."""
        if self._trail_lbl_pool:
            return self._trail_lbl_pool.pop()
        lbl = tk.Label(
            self.root,
            font=("Courier New", 9),
            fg=C["white3"],
            bg=C["bg"],
            bd=0,
            padx=0,
            pady=0,
        )
        # No bindings — clicks fall through to whatever is underneath
        return lbl

    def _spawn_trail_particle(self, cx, cy, speed):
        spread = min(10, 3 + speed * 0.15)
        rx = self.root.winfo_rootx()
        ry = self.root.winfo_rooty()
        lbl = self._trail_get_lbl()
        glyph = random.choice(self._TRAIL_GLYPHS)
        size  = random.choice([7, 8, 9])
        lbl.config(text=glyph, font=("Courier New", size), fg=C["white"], bg=C["bg"])
        px = int(cx - rx + random.uniform(-spread, spread))
        py = int(cy - ry + random.uniform(-spread, spread))
        lbl.place(x=px, y=py, anchor="center")
        lbl.lift()
        self._trail_particles.append({
            "x": float(px), "y": float(py),
            "vx": random.uniform(-0.4, 0.4),
            "vy": random.uniform(-1.6, -0.3),
            "life": 1.0,
            "decay": random.uniform(0.06, 0.10),
            "glyph": glyph,
            "size":  size,
            "lbl":   lbl,
        })
        if len(self._trail_particles) > 30:
            old = self._trail_particles.pop(0)
            try:
                old["lbl"].place_forget()
                self._trail_lbl_pool.append(old["lbl"])
            except Exception:
                pass

    def _trail_tick(self):
        if not getattr(self, "_trail_active", False):
            return
        try:
            alive = []
            for p in self._trail_particles:
                p["life"] -= p["decay"]
                if p["life"] <= 0:
                    try:
                        p["lbl"].place_forget()
                        self._trail_lbl_pool.append(p["lbl"])
                    except Exception:
                        pass
                    continue
                p["x"] += p["vx"]
                p["y"] += p["vy"]
                p["vx"] *= 0.96
                p["vy"] *= 0.96
                t = p["life"]
                if t > 0.7:
                    br = int(140 + (t - 0.7) / 0.3 * 115)
                elif t > 0.3:
                    br = int(36  + (t - 0.3) / 0.4 * 104)
                else:
                    br = int(t / 0.3 * 36)
                br  = max(2, min(255, br))
                col = f"#{br:02x}{br:02x}{br:02x}"
                try:
                    p["lbl"].config(fg=col)
                    p["lbl"].place(x=int(p["x"]), y=int(p["y"]), anchor="center")
                except Exception:
                    pass
                alive.append(p)
            self._trail_particles = alive
        except Exception:
            pass
        self.root.after(32, self._trail_tick)

    def _apply_hw_accel(self, enabled):
        """Apply hardware accelerator state live."""
        try:
            # Update wavevis bar count
            bars = 48 if enabled else 12
            if hasattr(self, "wavevis"):
                self.wavevis.bars = bars
                self.wavevis.phases = [
                    __import__("random").uniform(0, __import__("math").pi * 2)
                    for _ in range(bars)
                ]
                self.wavevis.speeds = [
                    __import__("random").uniform(0.03, 0.09) for _ in range(bars)
                ]
            # Update status in sidebar
            if hasattr(self, "_sidebar_status_lbl"):
                hw_txt = "[ HW:ON ]" if enabled else "[ HW:OFF ]"
                self._sidebar_status_lbl.config(
                    text=hw_txt, fg=C["white2"] if enabled else C["white3"]
                )
            self._set_status("Hardware Accelerator: " + ("ON" if enabled else "OFF"))
        except Exception:
            pass

    def _attach_hover_sounds(self, widget=None):
        """Walk the entire widget tree and attach hover/click sound to anything with cursor=hand2."""
        if widget is None:
            widget = self.root
        try:
            if str(widget.cget("cursor")) == "hand2":
                widget.bind("<Enter>", lambda e: self.ui_sounds.play("hover"), add="+")
                widget.bind("<Button-1>", lambda e: self.ui_sounds.play("click"), add="+")
        except Exception:
            pass
        for child in widget.winfo_children():
            self._attach_hover_sounds(child)

    def _apply_accent(self, name):
        # Monochrome only — glow is always white
        C["glow"] = "#ffffff"
        C["white"] = "#f0f0f0"

    def _show_system_menu(self):
        """Native Win32 system menu at Alt+Space (Move, Minimize, Maximize, Close)."""
        try:
            import ctypes

            hwnd = getattr(self, "_hwnd", None) or self.root.winfo_id()
            user32 = ctypes.windll.user32
            TPM_RETURNCMD = 0x0100
            hmenu = user32.GetSystemMenu(hwnd, False)
            x = self.root.winfo_x()
            y = self.root.winfo_y() + 44
            cmd = user32.TrackPopupMenu(hmenu, TPM_RETURNCMD, x, y, 0, hwnd, None)
            if cmd:
                user32.PostMessageW(hwnd, 0x0112, cmd, 0)  # WM_SYSCOMMAND
        except Exception:
            pass

    def _get_monitors(self):
        monitors = []
        try:
            import ctypes
            import ctypes.wintypes as wt

            MONITORENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.c_bool,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.POINTER(wt.RECT),
                ctypes.c_double,
            )

            def _cb(hM, hdcM, lp, d):
                r = lp.contents
                monitors.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
                return True

            ctypes.windll.user32.EnumDisplayMonitors(
                None, None, MONITORENUMPROC(_cb), 0
            )
        except Exception:
            pass
        if not monitors:
            monitors = [
                (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())
            ]
        return monitors

    def _monitor_from_point(self, x, y):
        """Return (mx, my, mw, mh) of the monitor containing screen point (x, y)."""
        try:
            import ctypes
            import ctypes.wintypes as wt

            MONITOR_DEFAULTTONEAREST = 2

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", wt.RECT),
                    ("rcWork", wt.RECT),
                    ("dwFlags", ctypes.c_ulong),
                ]

            pt = wt.POINT(x, y)
            hmon = ctypes.windll.user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(MONITORINFO)
            ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info))
            r = info.rcMonitor
            return (r.left, r.top, r.right - r.left, r.bottom - r.top)
        except Exception:
            monitors = self._get_monitors()
            for mx, my, mw, mh in monitors:
                if mx <= x < mx + mw and my <= y < my + mh:
                    return mx, my, mw, mh
            return monitors[0]

    def _get_target_monitor(self):
        monitors = self._get_monitors()
        idx = int(self.settings.get("preferred_monitor", 0))
        return monitors[max(0, min(idx, len(monitors) - 1))]

    def _apply_borderless(self, enable):
        """Toggle borderless fullscreen. Keeps overrideredirect(True) throughout."""
        if enable:
            self._restore_geo = self.root.geometry()
            self.root.overrideredirect(True)
            mx, my, mw, mh = self._get_target_monitor()
            self.root.geometry(f"{mw}x{mh}+{mx}+{my}")
        else:
            self.root.overrideredirect(True)
            self.root.geometry(getattr(self, "_restore_geo", "1100x700+100+100"))

    # ── TOP BAR ───────────────────────────
    def _build_ui(self):
        self._build_topbar()
        main = tk.Frame(self.root, bg=C["bg"])
        main.pack(fill="both", expand=True)
        self._build_sidebar(main)
        self._build_content(main)
        self._build_playerbar()
        # [06] Ghost HUD label — floats near center of playerbar, fades on keypress
        self._ghost_lbl = tk.Label(
            self.root,
            text="",
            font=("Courier New", 11, "bold"),
            fg=C["white"],
            bg=C["panel"],
            padx=12, pady=4,
        )
        self._ghost_lbl.place(relx=0.5, rely=0.94, anchor="center")
        self._ghost_lbl.place_forget()
        self._ghost_job = None
        # Overlay lives on top of content for view transitions
        self._fade_overlay = FadeOverlay(self.root, self.content)
        # Scanline overlay — drawn once, covers full window, never intercepts input
        self._build_scanline_overlay()

    def _build_scanline_overlay(self):
        """CRT scanline + edge vignette. Drawn once, redrawn only on resize."""
        cv = tk.Canvas(self.root, highlightthickness=0, bg=C["bg"], bd=0)
        cv.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self._scanline_cv = cv
        # Lower as a widget (not a canvas item) — place it behind all pack children
        cv.tk.call("lower", cv._w)

        _last_size = [0, 0]

        def _draw(e=None):
            w = cv.winfo_width()
            h = cv.winfo_height()
            if w < 2 or h < 2:
                return
            if w == _last_size[0] and h == _last_size[1]:
                return  # nothing changed, skip
            _last_size[0], _last_size[1] = w, h
            cv.delete("all")

            # Horizontal scanlines — #0e0e0e on #050505 bg (~+9 brightness)
            line_col = "#0e0e0e"
            for y in range(0, h, 3):
                cv.create_line(0, y, w, y, fill=line_col)

            # Edge vignette — soft darkening at all four edges
            vw = max(1, int(w * 0.055))
            vh = max(1, int(h * 0.038))
            for i in range(vw):
                br = int(((1.0 - i / vw) ** 1.6) * 18)
                col = f"#{br:02x}{br:02x}{br:02x}"
                cv.create_line(i, 0, i, h, fill=col)
                cv.create_line(w - 1 - i, 0, w - 1 - i, h, fill=col)
            for i in range(vh):
                br = int(((1.0 - i / vh) ** 1.6) * 18)
                col = f"#{br:02x}{br:02x}{br:02x}"
                cv.create_line(0, i, w, i, fill=col)
                cv.create_line(0, h - 1 - i, w, h - 1 - i, fill=col)

        cv.bind("<Configure>", _draw)
        self.root.after(350, _draw)

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=C["panel"], height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        # Signalis-style double bottom border — thick rule then hairline
        tk.Frame(self.root, bg=C["border2"], height=2).pack(fill="x")
        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x")

        # Left accent column — vertical status stripe
        tk.Frame(bar, bg=C["border2"], width=3).pack(side="left", fill="y")

        # Wordmark — [SYS] prefix + angular tracked name
        sys_lbl = tk.Label(
            bar,
            text="[SYS]",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["panel"],
            padx=6,
        )
        sys_lbl.pack(side="left")
        wm = tk.Label(
            bar,
            text="OTERNOS",
            font=("Courier New", 10, "bold"),
            fg=C["white"],
            bg=C["panel"],
            padx=4,
        )
        wm.pack(side="left")
        # Angular divider
        tk.Label(
            bar,
            text="◂",
            font=("Courier New", 8),
            fg=C["border2"],
            bg=C["panel"],
            padx=2,
        ).pack(side="left")
        tk.Frame(bar, bg=C["border2"], width=1).pack(side="left", fill="y", pady=8)

        self.tab_btns = {}
        self._tab_keys = []
        _tabs = [
            ("LIBRARY",    "library"),
            ("QUEUE",      "queue"),
            ("VISUALIZER", "visualizer"),
            ("LYRICS",     "lyrics"),
            ("HISTORY",    "history"),
            ("ALBUMS",     "albums"),
            ("SPOTIFY",    "spotify"),
            ("STREAM",     "stream"),
            ("AIDJ",       "aidj"),
            ("NET",        "netstream"),
            ("FX",         "fx"),
        ]
        if self.settings.get("show_claude_tab", False):
            _tabs.append(("CLAUDE", "claude"))
        for label, key in _tabs:
            # Tab frame with bottom glow bar
            tbf = tk.Frame(bar, bg=C["panel"], cursor="hand2")
            tbf.pack(side="left")
            b = tk.Label(
                tbf,
                text=label,
                font=("Courier New", 8, "bold"),
                fg=C["white3"],
                bg=C["panel"],
                cursor="hand2",
                padx=8,
                pady=12,
            )
            b.pack()
            # Glow underline — hidden by default
            glow_bar = tk.Frame(tbf, bg=C["panel"], height=2)
            glow_bar.pack(fill="x")
            b._glow_bar = glow_bar
            b._frame = tbf
            b.bind("<Button-1>", lambda e, k=key: self._switch_view(k))
            b.bind("<Enter>", lambda e, w=b, k=key: self._tab_hover(w, k, True))
            b.bind("<Leave>", lambda e, w=b, k=key: self._tab_hover(w, k, False))
            tbf.bind("<Button-1>", lambda e, k=key: self._switch_view(k))
            self.tab_btns[key] = b
            self._tab_keys.append(key)

        # Right side — window controls + CFG
        # ── Close ──
        close_btn = tk.Label(
            bar,
            text=" ✕ ",
            font=("Courier New", 9, "bold"),
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
        )
        close_btn.pack(side="right", padx=(0, 4))
        close_btn.bind("<Button-1>", lambda e: self._on_close())
        close_btn.bind(
            "<Enter>", lambda e: close_btn.config(fg="#cc2222", bg="#1a0000")
        )
        close_btn.bind(
            "<Leave>", lambda e: close_btn.config(fg=C["white3"], bg=C["panel"])
        )

        # ── Maximize / Restore ──
        def _get_current_monitor():
            cx = self.root.winfo_x() + self.root.winfo_width() // 2
            cy = self.root.winfo_y() + self.root.winfo_height() // 2
            return self._monitor_from_point(cx, cy)

        def _toggle_max(e=None):
            if self._is_maximized:
                self.root.geometry(self._restore_geo)
                self._is_maximized = False
                max_btn.config(text=" □ ")
            else:
                self._restore_geo = self.root.geometry()
                mx, my, mw, mh = _get_current_monitor()
                self.root.geometry(f"{mw}x{mh}+{mx}+{my}")
                self._is_maximized = True
                max_btn.config(text=" ❐ ")

        self._toggle_max = _toggle_max

        max_btn = tk.Label(
            bar,
            text=" □ ",
            font=("Courier New", 9),
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
        )
        max_btn.pack(side="right")
        max_btn.bind("<Button-1>", _toggle_max)
        max_btn.bind("<Enter>", lambda e: max_btn.config(fg=C["white"]))
        max_btn.bind("<Leave>", lambda e: max_btn.config(fg=C["white3"]))
        bar.bind("<Double-Button-1>", _toggle_max)

        # ── Minimize ──
        min_btn = tk.Label(
            bar,
            text=" — ",
            font=("Courier New", 9),
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
        )
        min_btn.pack(side="right")

        def _minimize(e=None):
            try:
                import ctypes

                hwnd = getattr(self, "_hwnd", None) or self.root.winfo_id()
                # SW_MINIMIZE via Win32 — works cleanly with overrideredirect
                ctypes.windll.user32.ShowWindow(hwnd, 6)
            except Exception:
                # Fallback: brief overrideredirect toggle for iconify
                self.root.overrideredirect(False)
                self.root.iconify()

                def _restore(e=None):
                    self.root.overrideredirect(True)
                    self.root.deiconify()
                    self.root.unbind("<Map>")

                self.root.bind("<Map>", _restore)

        min_btn.bind("<Button-1>", _minimize)
        min_btn.bind("<Enter>", lambda e: min_btn.config(fg=C["white"]))
        min_btn.bind("<Leave>", lambda e: min_btn.config(fg=C["white3"]))

        tk.Frame(bar, bg=C["border2"], width=1).pack(side="right", fill="y", pady=8)
        gear = tk.Label(
            bar,
            text="[CFG]",
            font=("Courier New", 8, "bold"),
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
            padx=12,
        )
        gear.pack(side="right")
        gear.bind("<Button-1>", lambda e: self._open_settings())
        gear.bind(
            "<Enter>",
            lambda e: ColorAnim.run(self.root, gear, "fg", C["white3"], C["white"]),
        )
        gear.bind(
            "<Leave>",
            lambda e: ColorAnim.run(self.root, gear, "fg", C["white"], C["white3"]),
        )
        help_btn = tk.Label(
            bar,
            text="[?]",
            font=("Courier New", 8, "bold"),
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
            padx=8,
        )
        help_btn.pack(side="right")
        help_btn.bind("<Button-1>", lambda e: self._switch_view("help"))
        help_btn.bind("<Enter>", lambda e: ColorAnim.run(self.root, help_btn, "fg", C["white3"], C["white"]))
        help_btn.bind("<Leave>", lambda e: ColorAnim.run(self.root, help_btn, "fg", C["white"], C["white3"]))

        # Live clock + session uptime readout
        tk.Frame(bar, bg=C["border"], width=1).pack(side="right", fill="y", pady=8)
        self._clock_lbl = tk.Label(
            bar,
            text="00:00:00  UP:00:00:00",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["panel"],
            padx=8,
        )
        self._clock_lbl.pack(side="right")
        self._tick_clock()
        # BinaryRain strip — subtle scrolling binary between clock and hw toggle
        tk.Frame(bar, bg=C["border"], width=1).pack(side="right", fill="y", pady=8)
        self._binary_rain = BinaryRain(bar, width=100, height=8, bg=C["panel"])
        self._binary_rain.pack(side="right", padx=4, pady=18)
        # HW Accelerator quick toggle — Signalis system readout style
        tk.Frame(bar, bg=C["border"], width=1).pack(side="right", fill="y", pady=8)
        self._hw_btn = tk.Label(
            bar,
            text="[HW:ON]",
            font=("Courier New", 8, "bold"),
            fg=C["white2"],
            bg=C["panel"],
            cursor="hand2",
            padx=8,
        )
        self._hw_btn.pack(side="right")

        def _toggle_hw(e):
            global HW_ACCEL
            import sys as _sys
            _constants_mod = None
            for _key in ("oternos.constants", "constants"):
                _constants_mod = _sys.modules.get(_key)
                if _constants_mod is not None:
                    break
            HW_ACCEL = not HW_ACCEL
            if _constants_mod is not None:
                _constants_mod.HW_ACCEL = HW_ACCEL
            self.settings["hw_accel"] = HW_ACCEL
            self._hw_btn.config(
                text="[HW:ON]" if HW_ACCEL else "[HW:OFF]",
                fg=C["white2"] if HW_ACCEL else C["white3"],
            )
            self._apply_hw_accel(HW_ACCEL)
            self._save()

        self._hw_btn.bind("<Button-1>", _toggle_hw)
        self._hw_btn.bind("<Enter>", lambda e: self._hw_btn.config(fg=C["white"]))
        self._hw_btn.bind(
            "<Leave>",
            lambda e: self._hw_btn.config(fg=C["white2"] if HW_ACCEL else C["white3"]),
        )

        _drag_state = {}
        _monitors_cache = [None]

        def _bar_press(e):
            if _drag_state.get("resize_active"):
                return
            _monitors_cache[0] = None
            _drag_state["bar_active"] = True
            _drag_state["start_x"] = e.x_root
            _drag_state["start_y"] = e.y_root
            _drag_state["win_x"]   = self.root.winfo_x()
            _drag_state["win_y"]   = self.root.winfo_y()
            _drag_state["unsnaped"] = False

        def _bar_drag(e):
            if not _drag_state.get("bar_active"):
                return

            if self._is_maximized and not _drag_state.get("unsnaped"):
                geo = getattr(self, "_restore_geo", "1100x700+100+100")
                try:
                    rw = int(geo.split("x")[0])
                    rh = int(geo.split("x")[1].split("+")[0])
                except Exception:
                    rw, rh = 1100, 700
                frac = e.x_root / max(1, self.root.winfo_width())
                nx = e.x_root - int(rw * frac)
                ny = e.y_root - 16
                self.root.geometry(f"{rw}x{rh}+{nx}+{ny}")
                self._is_maximized = False
                max_btn.config(text=" □ ")
                _drag_state["start_x"] = e.x_root
                _drag_state["start_y"] = e.y_root
                _drag_state["win_x"]   = nx
                _drag_state["win_y"]   = ny
                _drag_state["unsnaped"] = True
                return

            dx = e.x_root - _drag_state["start_x"]
            dy = e.y_root - _drag_state["start_y"]
            self.root.geometry(
                f"+{_drag_state['win_x'] + dx}+{_drag_state['win_y'] + dy}"
            )

            if _monitors_cache[0] is None:
                _monitors_cache[0] = self._get_monitors()
            # Find which monitor the cursor is actually on, check if near ITS top edge
            mx, my, mw, mh = self._monitor_from_point(e.x_root, e.y_root)
            if e.y_root - my <= 8:
                _drag_state["snap_mon"] = (mx, my, mw, mh)
            else:
                _drag_state.pop("snap_mon", None)

        def _bar_release(e):
            if not _drag_state.get("bar_active"):
                return
            mon = _drag_state.pop("snap_mon", None)
            if mon:
                mx, my, mw, mh = mon
                self._restore_geo = self.root.geometry()
                self.root.geometry(f"{mw}x{mh}+{mx}+{my}")
                self._is_maximized = True
                max_btn.config(text=" ❐ ")
            _drag_state.clear()

        bar.bind("<ButtonPress-1>", _bar_press)
        bar.bind("<B1-Motion>", _bar_drag)
        bar.bind("<ButtonRelease-1>", _bar_release)

        # Store shared drag state so resize handler can coordinate
        self._win_drag_state = _drag_state

        self._update_tabs()
        # Edge resize cursors — detect mouse near window border
        self.root.after(200, self._bind_resize_cursors)

    def _bind_resize_cursors(self):
        """Show resize cursor arrows when hovering within 6px of window edge."""
        EDGE = 6
        cur_map = {
            "nw": "size_nw_se",
            "ne": "size_ne_sw",
            "sw": "size_ne_sw",
            "se": "size_nw_se",
            "n": "size_ns",
            "s": "size_ns",
            "e": "size_we",
            "w": "size_we",
        }
        _resize = {}

        def _edge(x, y, w, h):
            l = x < EDGE
            r = x > w - EDGE
            t = y < EDGE
            b = y > h - EDGE
            if t and l:
                return "nw"
            if t and r:
                return "ne"
            if b and l:
                return "sw"
            if b and r:
                return "se"
            if t:
                return "n"
            if b:
                return "s"
            if l:
                return "w"
            if r:
                return "e"
            return None

        def _motion(e):
            if _resize.get("active"):
                return
            if getattr(self, "_win_drag_state", {}).get("bar_active"):
                return
            x = e.x_root - self.root.winfo_rootx()
            y = e.y_root - self.root.winfo_rooty()
            ed = _edge(x, y, self.root.winfo_width(), self.root.winfo_height())
            self.root.config(cursor=cur_map.get(ed, ""))

        def _press(e):
            if getattr(self, "_win_drag_state", {}).get("bar_active"):
                return
            x = e.x_root - self.root.winfo_rootx()
            y = e.y_root - self.root.winfo_rooty()
            ed = _edge(x, y, self.root.winfo_width(), self.root.winfo_height())
            if ed:
                _resize.update(
                    active=True,
                    edge=ed,
                    sx=e.x_root,
                    sy=e.y_root,
                    ox=self.root.winfo_x(),
                    oy=self.root.winfo_y(),
                    ow=self.root.winfo_width(),
                    oh=self.root.winfo_height(),
                )

        def _drag(e):
            if not _resize.get("active"):
                return
            if getattr(self, "_win_drag_state", {}).get("bar_active"):
                _resize.clear()
                return
            dx = e.x_root - _resize["sx"]
            dy = e.y_root - _resize["sy"]
            ed = _resize["edge"]
            nx, ny = _resize["ox"], _resize["oy"]
            nw, nh = _resize["ow"], _resize["oh"]
            if "e" in ed:
                nw = max(900, _resize["ow"] + dx)
            if "s" in ed:
                nh = max(600, _resize["oh"] + dy)
            if "w" in ed:
                nx = _resize["ox"] + dx
                nw = max(900, _resize["ow"] - dx)
            if "n" in ed:
                ny = _resize["oy"] + dy
                nh = max(600, _resize["oh"] - dy)
            self.root.geometry(f"{nw}x{nh}+{nx}+{ny}")

        def _release(e):
            _resize.clear()
            if not getattr(self, "_win_drag_state", {}).get("bar_active"):
                self.root.config(cursor="")

        self.root.bind("<Motion>", _motion, add="+")
        self.root.bind("<ButtonPress-1>", _press, add="+")
        self.root.bind("<B1-Motion>", _drag, add="+")
        self.root.bind("<ButtonRelease-1>", _release, add="+")

    def _tab_hover(self, widget, key, entering):
        active_key = "library" if self.view in ("library", "playlist") else self.view
        is_active = key == active_key
        if entering:
            ColorAnim.run(
                self.root, widget, "fg", widget.cget("fg"), C["glow"], duration_ms=60
            )
            if hasattr(widget, "_glow_bar") and not is_active:
                widget._glow_bar.config(bg=C["border2"])
            if key == "youtube":
                self._yt_show_dropdown(widget)
        else:
            to_col = C["white"] if is_active else C["white3"]
            ColorAnim.run(
                self.root, widget, "fg", widget.cget("fg"), to_col, duration_ms=50
            )
            if hasattr(widget, "_glow_bar") and not is_active:
                widget._glow_bar.config(bg=C["panel"])
            if key == "youtube":
                self.root.after(300, self._yt_maybe_close_dropdown)

    def _yt_show_dropdown(self, widget):
        """Show SEARCH / SAVED dropdown under the YOUTUBE tab button."""
        try:
            if (
                hasattr(self, "_yt_dropdown")
                and self._yt_dropdown
                and self._yt_dropdown.winfo_exists()
            ):
                return
        except Exception:
            pass
        dd = tk.Frame(
            self.root,
            bg=C["panel"],
            bd=0,
            highlightthickness=1,
            highlightbackground=C["border"],
        )
        self._yt_dropdown = dd
        x = widget.winfo_rootx() - self.root.winfo_rootx()
        y = widget.winfo_rooty() - self.root.winfo_rooty() + widget.winfo_height()
        dd.place(x=x, y=y, width=90)

        def _btn(text, cmd):
            b = tk.Label(
                dd,
                text=text,
                font=("Courier New", 7),
                fg=C["white3"],
                bg=C["panel"],
                cursor="hand2",
                anchor="w",
                padx=8,
                pady=3,
            )
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e: (self._yt_close_dropdown(), cmd()))
            b.bind("<Enter>", lambda e: b.config(fg=C["white"], bg=C["select2"]))
            b.bind("<Leave>", lambda e: b.config(fg=C["white3"], bg=C["panel"]))

        _btn("/ SEARCH", lambda: self._yt_set_subview("search"))
        _btn("* SAVED", lambda: self._yt_set_subview("saved"))

        # Auto-close when mouse leaves dropdown
        def _leave(e):
            try:
                wx, wy = dd.winfo_rootx(), dd.winfo_rooty()
                ww, wh = dd.winfo_width(), dd.winfo_height()
                mx, my = e.x_root, e.y_root
                if not (wx <= mx <= wx + ww and wy <= my <= wy + wh):
                    self._yt_close_dropdown()
            except Exception:
                pass

        dd.bind("<Leave>", _leave)

        # Poll to close if mouse leaves both button and dropdown
        def _poll_close():
            try:
                if (
                    getattr(self, "_yt_dropdown", None)
                    and self._yt_dropdown.winfo_exists()
                ):
                    self._yt_maybe_close_dropdown()
                    self.root.after(150, _poll_close)
            except Exception:
                pass

        self.root.after(500, _poll_close)

    def _yt_close_dropdown(self):
        try:
            if hasattr(self, "_yt_dropdown") and self._yt_dropdown:
                self._yt_dropdown.destroy()
                self._yt_dropdown = None
        except Exception:
            pass

    def _yt_maybe_close_dropdown(self):
        """Close dropdown only if mouse is not over it."""
        try:
            dd = getattr(self, "_yt_dropdown", None)
            if not dd or not dd.winfo_exists():
                return
            mx = self.root.winfo_pointerx() - self.root.winfo_rootx()
            my = self.root.winfo_pointery() - self.root.winfo_rooty()
            dx = dd.winfo_x()
            dy = dd.winfo_y()
            dw = dd.winfo_width()
            dh = dd.winfo_height()
            # Also check if mouse is over the YOUTUBE tab button
            yt_btn = self.tab_btns.get("youtube")
            over_btn = False
            if yt_btn:
                bx = yt_btn.winfo_x()
                by = yt_btn.winfo_y()
                bw = yt_btn.winfo_width()
                bh = yt_btn.winfo_height()
                over_btn = bx <= mx <= bx + bw and by <= my <= by + bh
            over_dd = dx <= mx <= dx + dw and dy <= my <= dy + dh
            if not over_dd and not over_btn:
                self._yt_close_dropdown()
        except Exception:
            pass

    def _yt_set_subview(self, subview):
        """Switch between search and saved within YouTube view."""
        self._switch_view("youtube")
        self._yt_subview = subview
        if subview == "saved":
            self._yt_show_saved()
        else:
            self._yt_show_search()

    def _yt_show_search(self):
        """Show the search UI."""
        if hasattr(self, "yt_search_frame"):
            self.yt_search_frame.pack(fill="x", padx=20, pady=(8, 0))
        self.yt_content_lbl.config(text="Search for music above")
        self._yt_render_list()

    def _yt_show_saved(self):
        """Show saved YouTube tracks."""
        if hasattr(self, "yt_search_frame"):
            self.yt_search_frame.pack_forget()
        saved = self._yt_load_saved()
        if not saved:
            self.yt_content_lbl.config(
                text="No saved tracks yet — search and click ★ to save"
            )
            self._yt_tracks = []
            self._yt_clear_list()
            return
        self.yt_content_lbl.config(
            text=f"{len(saved)} saved tracks  —  double-click to play"
        )
        self._yt_tracks = saved
        self._yt_render_list()
        for i, t in enumerate(saved):
            vid_id = t.get("id", "")
            if vid_id:
                url = f"https://i.ytimg.com/vi/{vid_id}/default.jpg"
                threading.Thread(
                    target=self._yt_fetch_thumb, args=(i, url), daemon=True
                ).start()

    def _yt_save_track(self, track):
        """Save a track to the saved list."""
        import json as _json

        path = Path.home() / ".voidplayer_yt_saved.json"
        try:
            saved = _json.loads(path.read_text()) if path.exists() else []
        except Exception:
            saved = []
        # Avoid duplicates
        if not any(t.get("id") == track.get("id") for t in saved):
            saved.append(track)
            path.write_text(_json.dumps(saved))

    def _yt_unsave_track(self, track_id):
        """Remove a track from saved."""
        import json as _json

        path = Path.home() / ".voidplayer_yt_saved.json"
        try:
            saved = _json.loads(path.read_text()) if path.exists() else []
            saved = [t for t in saved if t.get("id") != track_id]
            path.write_text(_json.dumps(saved))
        except Exception:
            pass

    def _yt_load_saved(self):
        import json as _json

        path = Path.home() / ".voidplayer_yt_saved.json"
        try:
            return _json.loads(path.read_text()) if path.exists() else []
        except Exception:
            return []

    def _yt_is_saved(self, track_id):
        return any(t.get("id") == track_id for t in self._yt_load_saved())

    def _update_tabs(self):
        active_key = "library" if self.view in ("library", "playlist") else self.view
        _labels = {
            "library":    "LIBRARY",
            "queue":      "QUEUE",
            "visualizer": "VISUALIZER",
            "lyrics":     "LYRICS",
            "history":    "HISTORY",
            "albums":     "ALBUMS",
            "spotify":    "SPOTIFY",
            "stream":     "STREAM",
            "soundcloud": "STREAM",
            "youtube":    "STREAM",
            "deezer":     "STREAM",
            "archive":    "STREAM",
            "bandcamp":   "STREAM",
            "claude":     "CLAUDE",
            "aidj":       "AIDJ",
            "netstream":  "NET",
            "fx":         "FX",
            "help":       "HELP",
        }
        for k, b in self.tab_btns.items():
            is_active = k == active_key
            lbl = _labels.get(k, k.upper())
            b.config(text=f"▸{lbl}" if is_active else lbl)
            target_fg = C["white"] if is_active else C["white3"]
            target_bg = C["select"] if is_active else C["panel"]
            try:
                current_fg = b.cget("fg")
            except:
                current_fg = target_fg
            ColorAnim.run(self.root, b, "fg", current_fg, target_fg, duration_ms=80)
            ColorAnim.run(self.root, b, "bg", b.cget("bg"), target_bg, duration_ms=80)
            if hasattr(b, "_frame"):
                ColorAnim.run(
                    self.root,
                    b._frame,
                    "bg",
                    b._frame.cget("bg"),
                    target_bg,
                    duration_ms=80,
                )
            # Glow underline bar
            if hasattr(b, "_glow_bar"):
                b._glow_bar.config(bg=C["glow"] if is_active else C["panel"])

    # ── SIDEBAR ───────────────────────────
    def _build_sidebar(self, parent):
        # Outer shell — fixed width, no propagate
        shell = tk.Frame(parent, bg=C["panel"], width=200)
        shell.pack(side="left", fill="y")
        shell.pack_propagate(False)
        self._sidebar_shell = shell

        # Thin right border line
        tk.Frame(shell, bg=C["border"], width=1).pack(side="right", fill="y")

        # [08] Left-edge VU meter stripe — 3px Canvas, FFT-driven in _spec_tick
        self._sidebar_vu_cv = tk.Canvas(
            shell, bg=C["panel"], width=3, highlightthickness=0
        )
        self._sidebar_vu_cv.pack(side="left", fill="y")

        # Slim scrollbar on the right edge
        self._side_sb = tk.Scrollbar(
            shell,
            orient="vertical",
            bg=C["panel"],
            troughcolor=C["panel"],
            width=3,
            bd=0,
            highlightthickness=0,
            relief="flat",
            activerelief="flat",
        )
        self._side_sb.pack(side="right", fill="y")

        # Scrollable canvas
        self._side_cv = tk.Canvas(
            shell, bg=C["panel"], highlightthickness=0, yscrollcommand=self._side_sb.set
        )
        self._side_cv.pack(side="left", fill="both", expand=True)
        self._side_sb.config(command=self._side_cv.yview)

        # Inner content frame
        side = tk.Frame(self._side_cv, bg=C["panel"])
        self._side_win = self._side_cv.create_window(0, 0, anchor="nw", window=side)

        def _on_inner(e):
            self._side_cv.configure(scrollregion=self._side_cv.bbox("all"))

        def _on_outer(e):
            self._side_cv.itemconfig(self._side_win, width=e.width)

        side.bind("<Configure>", _on_inner)
        self._side_cv.bind("<Configure>", _on_outer)

        def _scroll(e):
            self._scroller.scroll(self._side_cv, e.delta)

        self._side_cv.bind("<MouseWheel>", _scroll)
        side.bind("<MouseWheel>", _scroll)
        self._side_scroll_fn = _scroll
        self._side_frame = side

        # ── Animated hex logo at top ──
        logo_frame = tk.Frame(side, bg=C["panel"])
        logo_frame.pack(fill="x", pady=(10, 4))
        self._sidebar_logo = OternosLogo(logo_frame, size=52, bg=C["panel"])
        self._sidebar_logo.pack(side="left", padx=(14, 8))
        # Signalis: vertical system readout panel next to logo
        sys_col = tk.Frame(logo_frame, bg=C["panel"])
        sys_col.pack(side="left", fill="y", pady=4)
        tk.Label(
            sys_col,
            text="OTERNOS",
            font=("Courier New", 8, "bold"),
            fg=C["white"],
            bg=C["panel"],
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            sys_col,
            text="SYS::v1.1",
            font=("Courier New", 7),
            fg=C["white3"],
            bg=C["panel"],
            anchor="w",
        ).pack(anchor="w")
        self._sidebar_status_lbl = tk.Label(
            sys_col,
            text="[  IDLE  ]",
            font=("Courier New", 8, "bold"),
            fg=C["white3"],
            bg=C["panel"],
            anchor="w",
        )
        self._sidebar_status_lbl.pack(anchor="w")
        # Hex memory address readout — slowly mutating fake addresses
        self._hex_addr_lbl = tk.Label(
            sys_col,
            text="0xA3F2·0x0044·0xFF1C",
            font=("Courier New", 6),
            fg=C["white3"],
            bg=C["panel"],
            anchor="w",
        )
        self._hex_addr_lbl.pack(anchor="w")
        self._tick_hex_addr()

        # ── Cybercore sidebar widgets ──────────────────────────────────────
        # Circuit trace network
        self._circuit = CircuitLines(side, width=188, height=44, bg=C["panel"])
        self._circuit.pack(fill="x", pady=(6, 0))

        # Radar sweep
        self._radar = RadarSweep(side, size=72, bg=C["panel"])
        self._radar.pack(pady=(4, 0))

        # Plasma ring — Lissajous curve next to radar
        self._plasma = PlasmaRing(side, size=72, bg=C["panel"])
        self._plasma.pack(pady=(2, 0))

        # Scrolling status matrix
        self._status_matrix = StatusMatrix(side, width=188, height=60, bg=C["panel"])
        self._status_matrix.pack(fill="x", pady=(4, 0))

        # Signalis: double-line separator
        tk.Frame(side, bg=C["border2"], height=2).pack(fill="x", padx=0, pady=(6, 0))
        tk.Frame(side, bg=C["border"], height=1).pack(fill="x", padx=0, pady=(1, 0))

        # ── Content ──
        self._slbl(side, "LIBRARY")
        self._sbtn(side, "All Tracks", lambda: self._switch_view("library"))
        self._sbtn(side, "Add Files", self._add_files)
        self._sbtn(side, "Add Folder", self._add_folder)
        tk.Frame(side, bg=C["border"], height=1).pack(fill="x", padx=12, pady=8)
        self._slbl(side, "PLAYLISTS")
        self._sbtn(side, "+ New Playlist", self._create_playlist)

        self.pl_sidebar = tk.Frame(side, bg=C["panel"])
        self.pl_sidebar.pack(fill="x")
        self._refresh_pl_sidebar()
        tk.Frame(side, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))
        self._ctx_frame = tk.Frame(side, bg=C["panel"])
        self._ctx_frame.pack(fill="x", pady=(4, 0))

        tk.Frame(side, bg=C["border"], height=1).pack(fill="x", padx=12, pady=8)
        self._slbl(side, "TOOLS")
        self._sbtn(side, "Sleep Timer",    self._open_sleep_timer)
        self._sbtn(side, "Mini Player",    self._toggle_mini_player)
        self._sbtn(side, "Watch Folders",  self._open_watch_dirs)
        self._sbtn(side, "Smart Playlist", self._open_smart_playlist)
        self._sbtn(side, "Find Dupes",     self._open_duplicate_detector)
        self._sbtn(side, "Export M3U",     self._export_playlist_m3u)
        self._sbtn(side, "Hotkeys",        self._open_hotkey_editor)
        self._sbtn(side, "Recommend",      self._open_recommendations)
        self._sbtn(side, "Neural Map",     self._open_neural_graph)
        self._sbtn(side, "Themes",         self._open_theme_editor)
        self._sbtn(side, "Bookmarks",      self._open_bookmarks)
        self._sbtn(side, "Auto-Playlist",  self._open_auto_playlist)
        tk.Frame(side, bg=C["panel"], height=12).pack()

    def _slbl(self, p, t):
        f = tk.Frame(p, bg=C["panel"])
        f.pack(fill="x", padx=0, pady=(14, 2))
        # Signalis: full-width thick rule + label with angle brackets
        tk.Frame(f, bg=C["border2"], height=2).pack(fill="x")
        lf = tk.Frame(f, bg=C["panel"])
        lf.pack(fill="x", padx=10, pady=(3, 0))
        lbl = tk.Label(
            lf,
            text=f"<< {t} >>",
            font=("Courier New", 8, "bold"),
            fg=C["white3"],
            bg=C["panel"],
            anchor="w",
        )
        lbl.pack(fill="x")

        # Occasional glitch flicker — corrupts text for 1 frame every ~8s
        import random as _r
        _glyphs = "▓░▒█◈◉╳"
        def _glitch():
            try:
                if not lbl.winfo_exists():
                    return
                # corrupt: replace 1-2 chars with glyphs
                chars = list(f"<< {t} >>")
                for idx in _r.sample(range(len(chars)), min(2, len(chars))):
                    chars[idx] = _r.choice(_glyphs)
                lbl.config(text="".join(chars))
                lbl.after(60, lambda: lbl.config(text=f"<< {t} >>"))
            except Exception:
                return
            lbl.after(_r.randint(6000, 12000), _glitch)
        lbl.after(_r.randint(3000, 8000), _glitch)

    def _sbtn(self, p, t, cmd):
        f = tk.Frame(p, bg=C["panel"], cursor="hand2")
        f.pack(fill="x")
        accent = tk.Frame(f, bg=C["border"], width=3)
        accent.pack(side="left", fill="y")
        l = tk.Label(
            f,
            text=f"  › {t}",
            font=("Courier New", 8),
            fg=C["white2"],
            bg=C["panel"],
            anchor="w",
            padx=10,
            pady=4,
        )
        l.pack(fill="x", side="left", expand=True)

        def _enter(e):
            accent.config(bg=C["glow"])
            ColorAnim.run(self.root, l, "fg", l.cget("fg"), C["glow"], duration_ms=60)
            ColorAnim.run(
                self.root, l, "bg", l.cget("bg"), C["select2"], duration_ms=60
            )
            ColorAnim.run(
                self.root, f, "bg", f.cget("bg"), C["select2"], duration_ms=60
            )

        def _leave(e):
            accent.config(bg=C["border"])
            ColorAnim.run(self.root, l, "fg", l.cget("fg"), C["white2"], duration_ms=60)
            ColorAnim.run(self.root, l, "bg", l.cget("bg"), C["panel"], duration_ms=60)
            ColorAnim.run(self.root, f, "bg", f.cget("bg"), C["panel"], duration_ms=60)

        for w in (f, l, accent):
            w.bind("<Button-1>", lambda e: cmd())
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
            if hasattr(self, "_side_scroll_fn"):
                w.bind("<MouseWheel>", self._side_scroll_fn)

    def _load_playlist(self, name):
        self._open_playlist(name)

    # ── CONTENT AREA ──────────────────────
    def _build_content(self, parent):
        content_shell = tk.Frame(parent, bg=C["bg"])
        content_shell.pack(side="left", fill="both", expand=True)
        # Ambient ticker strip at very top of content area
        _ct = DataTicker(content_shell, width=1200, height=10, bg=C["bg"])
        _ct.pack(fill="x")
        self.content = tk.Frame(content_shell, bg=C["bg"])
        self.content.pack(fill="both", expand=True)

        # GlyphWall — ambient dim glyph background behind all content
        self._glyph_wall = GlyphWall(self.content, bg=C["bg"])
        self._glyph_wall.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self._glyph_wall.tk.call("lower", self._glyph_wall._w)

        # Corner bracket decoration — single Canvas over content_shell,
        # fully transparent to clicks, never affects layout.
        import math as _cm
        _corner_cv = tk.Canvas(
            content_shell, bg=C["bg"],
            highlightthickness=0, bd=0
        )
        _corner_cv.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        _corner_cv.tk.call("lower", _corner_cv._w)  # below everything — purely decorative
        self._corner_cv = _corner_cv
        self._corner_t = 0

        def _draw_corners():
            try:
                _corner_cv.delete("all")
                W = _corner_cv.winfo_width()
                H = _corner_cv.winfo_height()
                if W < 4 or H < 4:
                    return
                t = self._corner_t
                L = 18   # arm length
                M = 4    # margin
                pulse = _cm.sin(t * 0.05) * 0.5 + 0.5
                base = int(30 + pulse * 24)
                # glitch offset every ~47 frames
                gx = ((t % 3) - 1) if t % 47 < 3 else 0
                gy = (t % 2) if t % 47 < 3 else 0
                col = f"#{base:02x}{base:02x}{base:02x}"
                W2 = W - 1  # right edge
                H2 = H - 1  # bottom edge
                # top-left
                _corner_cv.create_line(M, M, M+L, M, fill=col, width=2)
                _corner_cv.create_line(M, M, M, M+L, fill=col, width=2)
                # top-right
                _corner_cv.create_line(W2-M+gx, M+gy, W2-M-L+gx, M+gy, fill=col, width=2)
                _corner_cv.create_line(W2-M+gx, M+gy, W2-M+gx, M+L+gy, fill=col, width=2)
                # bottom-left
                _corner_cv.create_line(M+gy, H2-M, M+L+gy, H2-M, fill=col, width=2)
                _corner_cv.create_line(M+gy, H2-M, M+gy, H2-M-L, fill=col, width=2)
                # bottom-right
                _corner_cv.create_line(W2-M, H2-M, W2-M-L, H2-M, fill=col, width=2)
                _corner_cv.create_line(W2-M, H2-M, W2-M, H2-M-L, fill=col, width=2)
                self._corner_t += 1
            except Exception:
                pass
            try:
                _corner_cv.after(40, _draw_corners)
            except Exception:
                pass

        _corner_cv.after(400, _draw_corners)
        self._build_lib_view()
        self._build_queue_view()
        self._switch_view("library")
        self.root.after(100, self._build_deferred_views)

    def _build_deferred_views(self):
        """Build non-essential views sequentially after the UI is visible."""
        _steps = [
            self._build_visualizer_view,
            self._build_lyrics_view,
            self._build_history_view,
            self._build_album_view,
            self._build_spotify_view,
            self._build_soundcloud_view,
            self._build_youtube_view,
            self._build_stream_view,
            self._build_claude_view,
            self._build_deezer_view,
            self._build_archive_view,
            self._build_bandcamp_view,
            self._build_aidj_view,
            self._build_netstream_view,
            self._build_fx_view,
            self._build_help_view,
        ]

        def _run_next(steps):
            if not steps:
                return
            try:
                steps[0]()
            except Exception as exc:
                try:
                    log_exception(f"deferred_build:{steps[0].__name__}", exc)
                except Exception:
                    pass
            self.root.after(15, lambda: _run_next(steps[1:]))

        self.root.after(0, lambda: _run_next(_steps))

    def _build_lib_view(self):
        self.lib_frame = tk.Frame(self.content, bg=C["bg"])

        hdr = tk.Frame(self.lib_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(10, 0))
        # Signalis: header with system prefix and bracket title
        sys_row = tk.Frame(hdr, bg=C["bg"])
        sys_row.pack(fill="x")
        tk.Label(
            sys_row, text="VIEW::", font=("Courier New", 8), fg=C["white2"], bg=C["bg"]
        ).pack(side="left")
        self.view_title = tk.Label(
            sys_row,
            text="ALL TRACKS",
            font=("Courier New", 12, "bold"),
            fg=C["white"],
            bg=C["bg"],
        )
        self.view_title.pack(side="left")
        self.count_lbl = tk.Label(
            hdr, text="", font=("Courier New", 7), fg=C["white3"], bg=C["bg"]
        )
        self.count_lbl.pack(side="left", padx=12, pady=6)
        self.pl_actions = tk.Frame(hdr, bg=C["bg"])
        self.pl_actions.pack(side="right")

        sf = tk.Frame(self.lib_frame, bg=C["bg"])
        sf.pack(fill="x", padx=20, pady=(6, 0))
        tk.Label(
            sf, text="⌕", font=("Courier New", 11), fg=C["white3"], bg=C["bg"]
        ).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._refresh_tracks())
        _search_entry = tk.Entry(
            sf,
            textvariable=self.search_var,
            font=FM,
            bg=C["panel"],
            fg=C["white"],
            insertbackground=C["white"],
            relief="flat",
            bd=0,
            width=30,
            highlightthickness=1,
            highlightbackground=C["border"],
            highlightcolor=C["border2"],
        )
        _search_entry.pack(side="left", padx=6, ipady=3)
        # Escape clears search; focus ring gives visual feedback
        _search_entry.bind("<Escape>", lambda e: self.search_var.set(""))
        # Clear button
        _search_clr = tk.Label(
            sf, text="✕", font=("Courier New", 8), fg=C["white3"],
            bg=C["bg"], cursor="hand2"
        )
        _search_clr.pack(side="left")
        _search_clr.bind("<Button-1>", lambda e: (self.search_var.set(""), _search_entry.focus_set()))
        _search_clr.bind("<Enter>", lambda e: _search_clr.config(fg=C["white"]))
        _search_clr.bind("<Leave>", lambda e: _search_clr.config(fg=C["white3"]))
        tk.Frame(self.lib_frame, bg=C["border"], height=1).pack(
            fill="x", padx=20, pady=(4, 0)
        )

        # SpectrumBars — FFT accent strip below library header
        self._lib_spectrum = SpectrumBars(self.lib_frame, height=16, bg=C["bg"])
        self._lib_spectrum.pack(fill="x", padx=20, pady=(0, 0))

        ch = tk.Frame(self.lib_frame, bg=C["border"])
        ch.pack(fill="x", padx=20, pady=(6, 0))
        self._col_header_frame = ch  # ref for FFT brightness pulse
        self._sort_col = None
        self._sort_rev = False
        self._col_lbls = {}
        _COLS = [
            ("#", None, 3),
            ("TITLE", "title", 32),
            ("ARTIST", "artist", 20),
            ("ALBUM", "album", 20),
            ("TIME", "duration", 6),
        ]
        for t, sort_key, w in _COLS:
            lbl = tk.Label(
                ch,
                text=t,
                font=("Courier New", 7, "bold"),
                fg=C["white3"],
                bg=C["border"],
                width=w,
                anchor="w",
                cursor="hand2" if sort_key else "arrow",
            )
            lbl.pack(side="left", padx=(8, 0), pady=2)
            if sort_key:
                self._col_lbls[sort_key] = lbl

                def _on_col_click(e, key=sort_key):
                    if self._sort_col == key:
                        self._sort_rev = not self._sort_rev
                    else:
                        self._sort_col = key
                        self._sort_rev = False
                    self._update_col_headers()
                    self._tracks_dirty = True
                    self._refresh_tracks()

                lbl.bind("<Button-1>", _on_col_click)
                lbl.bind("<Enter>", lambda e, lb=lbl: lb.config(fg=C["white"]))
                lbl.bind(
                    "<Leave>",
                    lambda e: (
                        self._update_col_headers()
                        if hasattr(self, "_col_lbls")
                        else None
                    ),
                )

        lf = tk.Frame(self.lib_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        sb = tk.Scrollbar(
            lf, bg=C["panel"], troughcolor=C["bg"], width=6, relief="flat", bd=0
        )
        sb.pack(side="right", fill="y")
        _tl_scroll_job = [None]

        def _tl_yscroll(lo, hi):
            sb.set(lo, hi)
            # Debounce _refresh_tracks — only redraw when scrolling pauses
            if _tl_scroll_job[0]:
                try: self.root.after_cancel(_tl_scroll_job[0])
                except Exception: pass
            _tl_scroll_job[0] = self.root.after(
                120, lambda: (setattr(self, "_tracks_dirty", True),
                              self._refresh_tracks()))

        self.track_list = tk.Canvas(
            lf, bg=C["bg"], highlightthickness=0, yscrollcommand=_tl_yscroll
        )
        self.track_list.pack(fill="both", expand=True)
        sb.config(command=self.track_list.yview)
        self.track_list.bind("<Double-Button-1>", self._on_dbl)
        self.track_list.bind("<Button-3>", self._on_rclick)
        self.track_list.bind(
            "<MouseWheel>",
            lambda e: self.track_list.yview_scroll(
                int(-1 * (e.delta / 120)) * 3, "units"
            ),
        )
        self.track_list.bind("<Motion>", self._tl_on_motion)
        self.track_list.bind("<Leave>", self._tl_on_leave)
        self.track_list.bind("<Configure>", lambda e: self._refresh_tracks())
        # state for canvas list
        self._tl_row_h = 26  # default (collapsed) row height
        self._tl_hover_idx = -1  # row index currently hovered
        self._tl_sel_idx = -1  # selected row index
        self._tl_art_cache = {}  # lib_idx -> PhotoImage (small)
        self._tl_zoom_job = None
        self._tl_zoom_row = -1
        self._tl_zoom_h = 26  # current animated height of hover row
        self._scan_x = 0.0   # [03] radar sweep position 0→1
        self._scan_job = None
        self._refresh_tracks()

    def _build_queue_view(self):
        self.queue_frame = tk.Frame(self.content, bg=C["bg"])

        # Header
        hdr = tk.Frame(self.queue_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(12, 4))
        tk.Label(hdr, text="QUEUE", font=FMX, fg=C["white"], bg=C["bg"]).pack(
            side="left"
        )
        cl = tk.Label(
            hdr, text="clear all", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2"
        )
        cl.pack(side="right")
        cl.bind("<Button-1>", lambda e: self._clear_queue())
        cl.bind("<Enter>", lambda e: cl.config(fg=C["white"]))
        cl.bind("<Leave>", lambda e: cl.config(fg=C["white3"]))

        tk.Frame(self.queue_frame, bg=C["border"], height=1).pack(
            fill="x", padx=20, pady=(0, 4)
        )

        # Scrollable canvas area for two-tier list
        outer = tk.Frame(self.queue_frame, bg=C["bg"])
        outer.pack(fill="both", expand=True, padx=20)
        sb = tk.Scrollbar(
            outer, bg=C["panel"], troughcolor=C["bg"], width=6, relief="flat", bd=0
        )
        sb.pack(side="right", fill="y")
        self.queue_canvas = tk.Canvas(
            outer, bg=C["bg"], highlightthickness=0, yscrollcommand=sb.set
        )
        self.queue_canvas.pack(side="left", fill="both", expand=True)
        sb.config(command=self.queue_canvas.yview)
        self.queue_inner = tk.Frame(self.queue_canvas, bg=C["bg"])
        self._queue_inner_win = self.queue_canvas.create_window(
            (0, 0), window=self.queue_inner, anchor="nw"
        )
        self.queue_inner.bind(
            "<Configure>",
            lambda e: self.queue_canvas.configure(
                scrollregion=self.queue_canvas.bbox("all")
            ),
        )
        self.queue_canvas.bind(
            "<Configure>",
            lambda e: self.queue_canvas.itemconfig(
                self._queue_inner_win, width=e.width
            ),
        )
        self.queue_canvas.bind(
            "<MouseWheel>",
            lambda e: self.queue_canvas.yview_scroll(
                int(-1 * (e.delta / 120)) * 3, "units"
            ),
        )

        # Drag state
        self._q_drag_start = None
        self._q_drag_source = None
        self._q_drag_data = None
        self._q_rows = []
        self._q_drop_ind = None

    def _build_visualizer_view(self):
        self.viz_frame = tk.Frame(self.content, bg=C["bg"])

        # Header row
        hdr = tk.Frame(self.viz_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(hdr, text="VISUALIZER", font=FMX, fg=C["white"], bg=C["bg"]).pack(
            side="left"
        )
        self.viz_mode_lbl = tk.Label(
            hdr, text="[ HEXCORE ]", font=FMS, fg=C["white2"], bg=C["bg"]
        )
        self.viz_mode_lbl.pack(side="left", padx=10)

        # Cybercore mode buttons (shown by default)
        self._viz_mf_cyber = tk.Frame(hdr, bg=C["bg"])
        self._viz_mf_cyber.pack(side="right")

        # Miku mode buttons (hidden by default)
        self._viz_mf_miku = tk.Frame(hdr, bg=C["bg"])
        # (not packed until miku theme activates)
        self._viz_mf_nerv = tk.Frame(hdr, bg=C["bg"])
        # (not packed until nerv theme activates)
        self._viz_mf_nier = tk.Frame(hdr, bg=C["bg"])
        # (not packed until nier theme activates)

        self._viz_mode = "hexcore"
        self._viz_mode_btns = {}

        for label, mode in [
            ("HEXCORE", "hexcore"),
            ("PULSE", "pulse"),
            ("ORBIT", "orbit"),
            ("GRID", "grid"),
            ("SPECTRUM", "spectrum"),
            ("SCOPE", "oscilloscope"),
            ("PARTICLES", "particles"),
            ("GLITCH", "glitch"),
            ("CIPHER", "cipher"),
            ("ARASAKA", "arasaka"),
        ]:
            b = tk.Label(
                self._viz_mf_cyber,
                text=label,
                font=FMS,
                fg=C["white3"],
                bg=C["bg"],
                cursor="hand2",
                padx=8,
            )
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, m=mode: self._set_viz_mode(m))
            b.bind("<Enter>", lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=C["white3"]))
            self._viz_mode_btns[mode] = b

        for label, mode in [
            ("TAILS", "miku_tails"),
            ("SAKURA", "miku_sakura"),
            ("STARFALL", "miku_starfall"),
            ("RIBBON", "miku_ribbon"),
            ("WAVEFORM", "miku_wave"),
        ]:
            b = tk.Label(
                self._viz_mf_miku,
                text=label,
                font=("Yu Gothic UI", 8, "bold")
                if self._font_exists("Yu Gothic UI")
                else ("Consolas", 8, "bold"),
                fg=C["glow"] if mode == "miku_tails" else "#1e6068",
                bg=C["bg"],
                cursor="hand2",
                padx=8,
            )
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, m=mode: self._set_viz_mode(m))
            b.bind("<Enter>", lambda e, w=b: w.config(fg=C["glow"]))
            b.bind("<Leave>", lambda e, w=b: w.config(fg="#1e6068"))
            self._viz_mode_btns[mode] = b

        for _nl, _nm in [
            ("MAGI", "nerv_magi"),
            ("AT-FIELD", "nerv_angel"),
            ("EVA-01", "nerv_eva"),
        ]:
            _nb = tk.Label(
                self._viz_mf_nerv,
                text=_nl,
                font=("Consolas", 8, "bold"),
                fg="#660000",
                bg=C["bg"],
                cursor="hand2",
                padx=8,
            )
            _nb.pack(side="left")
            _nb.bind("<Button-1>", lambda e, m=_nm: self._set_viz_mode(m))
            _nb.bind("<Enter>", lambda e, w=_nb: w.config(fg="#ff0000"))
            _nb.bind("<Leave>", lambda e, w=_nb: w.config(fg="#660000"))
            self._viz_mode_btns[_nm] = _nb

        NIER_GOLD = "#c8b878"
        NIER_DIM = "#504838"
        for _nl, _nm in [
            ("YORHA", "nier_yorha"),
            ("MACHINE", "nier_machine"),
            ("RUINS", "nier_ruins"),
        ]:
            _nb = tk.Label(
                self._viz_mf_nier,
                text=_nl,
                font=("Consolas", 8, "bold"),
                fg=NIER_DIM,
                bg=C["bg"],
                cursor="hand2",
                padx=8,
            )
            _nb.pack(side="left")
            _nb.bind("<Button-1>", lambda e, m=_nm: self._set_viz_mode(m))
            _nb.bind("<Enter>", lambda e, w=_nb: w.config(fg=NIER_GOLD))
            _nb.bind("<Leave>", lambda e, w=_nb: w.config(fg=NIER_DIM))
            self._viz_mode_btns[_nm] = _nb

        # Angel mode buttons (hidden by default)
        self._viz_mf_angel = tk.Frame(hdr, bg=C["bg"])
        ANGEL_GLOW = "#ffb3d9"
        ANGEL_DIM = "#7a5070"
        for _al, _am in [
            ("FEATHERS", "angel_feathers"),
            ("HALO", "angel_halo"),
            ("WINGS", "angel_wings"),
        ]:
            _ab = tk.Label(
                self._viz_mf_angel,
                text=_al,
                font=("Consolas", 8, "bold"),
                fg=ANGEL_DIM,
                bg=C["bg"],
                cursor="hand2",
                padx=8,
            )
            _ab.pack(side="left")
            _ab.bind("<Button-1>", lambda e, m=_am: self._set_viz_mode(m))
            _ab.bind("<Enter>", lambda e, w=_ab: w.config(fg=ANGEL_GLOW))
            _ab.bind("<Leave>", lambda e, w=_ab: w.config(fg=ANGEL_DIM))
            self._viz_mode_btns[_am] = _ab

        tk.Frame(self.viz_frame, bg=C["border"], height=1).pack(
            fill="x", padx=0, pady=(8, 0)
        )

        # Main canvas — full remaining space
        self.viz_cv = tk.Canvas(self.viz_frame, bg=C["bg"], highlightthickness=0)
        self.viz_cv.pack(fill="both", expand=True)

        # Track info bar at very bottom
        info_bar = tk.Frame(self.viz_frame, bg=C["panel"], height=26)
        info_bar.pack(fill="x")
        info_bar.pack_propagate(False)
        self.viz_track_lbl = tk.Label(
            info_bar,
            text="— NO TRACK —",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["panel"],
        )
        self.viz_track_lbl.pack(side="left", padx=16)
        self.viz_pos_lbl = tk.Label(
            info_bar, text="", font=("Courier New", 8), fg=C["white3"], bg=C["panel"]
        )
        self.viz_pos_lbl.pack(side="right", padx=16)

        # Animation state
        self._viz_t = 0
        self._viz_job = None
        self._viz_bars = [0.0] * 48
        self._viz_interval = 16  # ms — overwritten by _apply_settings from viz_fps
        self._viz_phases = [random.uniform(0, math.pi * 2) for _ in range(48)]
        self._viz_speeds = [random.uniform(0.025, 0.075) for _ in range(48)]
        self._viz_orb_ang = 0.0
        self._viz_hex_r = 0.0
        self._viz_glow = 0.0
        self._viz_grid_particles = [
            [
                random.uniform(0, 1),
                random.uniform(0, 1),
                random.uniform(-1, 1) * 0.4,
                random.uniform(-1, 1) * 0.4,
            ]
            for _ in range(35)
        ]

    def _font_exists(self, name):
        try:
            import tkinter.font as tkfont

            return name in tkfont.families()
        except Exception:
            return False

    def _set_viz_mode(self, mode):
        self._viz_mode = mode
        names = {
            "hexcore": "[ HEXCORE ]",
            "pulse": "[ PULSE ]",
            "orbit": "[ ORBIT ]",
            "grid": "[ GRID ]",
            "spectrum": "[ SPECTRUM ]",
            "oscilloscope": "[ SCOPE ]",
            "particles": "[ PARTICLES ]",
            "miku_tails": "♪ TWIN TAILS ♪",
            "miku_sakura": "✦ SAKURA ✦",
            "miku_starfall": "✧ STARFALL ✧",
            "miku_ribbon": "♫ RIBBON ♫",
            "miku_wave": "♬ WAVEFORM ♬",
            "miku": "♪ MIKU ♪",
            "nerv_magi": "⬡ MAGI SYSTEM ⬡",
            "nerv_angel": "⬡ AT-FIELD ⬡",
            "nerv_eva": "⬡ EVA-01 STATUS ⬡",
            "nier_yorha": "// YoRHa //",
            "nier_machine": "// MACHINE //",
            "nier_ruins": "// RUINS //",
            "angel_feathers": "✦ FEATHERS ✦",
            "angel_halo": "✧ HALO ✧",
            "angel_wings": "✦ WINGS ✦",
            "glitch": "[ GLITCH ]",
            "cipher": "[ CIPHER ]",
            "arasaka": "[ ARASAKA ]",
        }
        self.viz_mode_lbl.config(text=names.get(mode, f"[ {mode.upper()} ]"))

    def _viz_tick(self):
        if self.view != "visualizer":
            self._viz_job = None
            return
        self._draw_visualizer()
        self._viz_t += 1
        interval = getattr(self, "_viz_interval", 16 if HW_ACCEL else 150)
        self._viz_job = self.viz_cv.after(interval, self._viz_tick)

    def _start_fft_file_decoder(self, path):
        import threading as _th

        self._fft_file_active = False
        old_t = getattr(self, "_fft_file_thread", None)
        if old_t and old_t.is_alive():
            old_t.join(timeout=0.3)
        self._fft_file_bars = [0.0] * 48
        self._fft_file_lock = _th.Lock()
        self._fft_file_active = True
        _path = path

        def _worker():
            try:
                import numpy as np
                import soundfile as _sf
                import time as _t

                info = _sf.info(_path)
                sr = info.samplerate
                CHUNK = 4096
                edges = np.logspace(np.log10(40.0), np.log10(16000.0), 49)
                bars = [0.0] * 48
                while self._fft_file_active:
                    if self.engine.is_paused:
                        _t.sleep(0.05)
                        continue
                    pos = self.engine.get_position() if self.engine.is_playing else 0.0
                    frame = max(0, int(pos * sr))
                    try:
                        data, _ = _sf.read(
                            _path,
                            start=frame,
                            frames=CHUNK,
                            dtype="float32",
                            always_2d=True,
                        )
                    except Exception:
                        break
                    if data.shape[0] < 256:
                        break
                    mono = data.mean(axis=1)
                    mag = np.abs(np.fft.rfft(mono * np.hanning(len(mono)))) / (
                        len(mono) / 2
                    )
                    freqs = np.fft.rfftfreq(len(mono), d=1.0 / sr)
                    sens = getattr(self, "_viz_sensitivity", 1.0)
                    nb = []
                    for b in range(48):
                        mask = (freqs >= edges[b]) & (freqs < edges[b + 1])
                        v = (
                            float(np.mean(mag[mask])) * 90.0 * sens
                            if mask.any()
                            else 0.0
                        )
                        nb.append(min(1.0, v))
                    with self._fft_file_lock:
                        for i in range(48):
                            bars[i] += (nb[i] - bars[i]) * 0.25
                        self._fft_file_bars = list(bars)
                    _t.sleep(0.04)
            except Exception:
                pass

        self._fft_file_thread = _th.Thread(target=_worker, daemon=True)
        self._fft_file_thread.start()

    def _stop_fft_file_decoder(self):
        self._fft_file_active = False
        self._fft_file_bars = [0.0] * 48

    # ── real FFT audio analyser ────────────
    def _start_audio_capture(self):
        """Capture loopback audio via WASAPI (Windows, no extra packages)
        and push 48-band FFT magnitudes into self._fft_bars."""
        try:
            import numpy as np
        except ImportError:
            self._fft_bars = None
            return

        N_BARS = 48
        SMOOTH = 0.15

        self._fft_bars = [0.0] * N_BARS
        self._fft_lock = threading.Lock()
        self._fft_active = True

        def _run():
            import numpy as np
            import ctypes
            import ctypes.wintypes
            import time as _t

            # ── WASAPI loopback via COM ──────────────────────────────
            ole32 = ctypes.WinDLL("ole32")
            ole32.CoInitialize(None)

            # GUIDs
            def GUID(s):
                import uuid as _u

                return (ctypes.c_byte * 16)(*_u.UUID(s).bytes_le)

            CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
            IID_IMMDeviceEnumerator = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
            IID_IAudioClient = GUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
            IID_IAudioCaptureClient = GUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")

            AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
            AUDCLNT_SHAREMODE_SHARED = 0
            CLSCTX_ALL = 0x17

            # WAVEFORMATEX
            class WAVEFORMATEX(ctypes.Structure):
                _fields_ = [
                    ("wFormatTag", 2),
                    ("nChannels", 2),
                    ("nSamplesPerSec", 4),
                    ("nAvgBytesPerSec", 4),
                    ("nBlockAlign", 2),
                    ("wBitsPerSample", 2),
                    ("cbSize", 2),
                ]
                _fields_ = [
                    ("wFormatTag", ctypes.c_uint16),
                    ("nChannels", ctypes.c_uint16),
                    ("nSamplesPerSec", ctypes.c_uint32),
                    ("nAvgBytesPerSec", ctypes.c_uint32),
                    ("nBlockAlign", ctypes.c_uint16),
                    ("wBitsPerSample", ctypes.c_uint16),
                    ("cbSize", ctypes.c_uint16),
                ]

            # REFERENCE_TIME is 100-nanosecond units
            REFTIMES_PER_SEC = 10_000_000

            try:
                # Create IMMDeviceEnumerator
                enumerator = ctypes.c_void_p()
                hr = ole32.CoCreateInstance(
                    ctypes.byref(CLSID_MMDeviceEnumerator),
                    None,
                    CLSCTX_ALL,
                    ctypes.byref(IID_IMMDeviceEnumerator),
                    ctypes.byref(enumerator),
                )
                if hr != 0:
                    raise OSError(f"CoCreateInstance hr={hr:#010x}")

                # vtable: IMMDeviceEnumerator::GetDefaultAudioEndpoint (index 4)
                vtbl_enum = ctypes.cast(enumerator, ctypes.POINTER(ctypes.c_void_p))
                GetDefaultAudioEndpoint = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,
                    ctypes.c_void_p,
                    ctypes.c_uint,
                    ctypes.c_uint,
                    ctypes.POINTER(ctypes.c_void_p),
                )(vtbl_enum[0][4])

                device = ctypes.c_void_p()
                hr = GetDefaultAudioEndpoint(enumerator, 0, 0, ctypes.byref(device))
                if hr != 0:
                    raise OSError(f"GetDefaultAudioEndpoint hr={hr:#010x}")

                # vtable: IMMDevice::Activate (index 3)
                vtbl_dev = ctypes.cast(device, ctypes.POINTER(ctypes.c_void_p))
                Activate = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_byte * 16),
                    ctypes.c_uint,
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p),
                )(vtbl_dev[0][3])

                audio_client = ctypes.c_void_p()
                hr = Activate(
                    device,
                    ctypes.byref(IID_IAudioClient),
                    CLSCTX_ALL,
                    None,
                    ctypes.byref(audio_client),
                )
                if hr != 0:
                    raise OSError(f"IMMDevice::Activate hr={hr:#010x}")

                # vtable: IAudioClient::GetMixFormat (index 8)
                vtbl_ac = ctypes.cast(audio_client, ctypes.POINTER(ctypes.c_void_p))
                GetMixFormat = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
                )(vtbl_ac[0][8])

                pwfx_ptr = ctypes.c_void_p()
                hr = GetMixFormat(audio_client, ctypes.byref(pwfx_ptr))
                if hr != 0:
                    raise OSError(f"GetMixFormat hr={hr:#010x}")

                pwfx = ctypes.cast(pwfx_ptr, ctypes.POINTER(WAVEFORMATEX))
                rate = pwfx.contents.nSamplesPerSec
                channels = pwfx.contents.nChannels
                bits = pwfx.contents.wBitsPerSample

                # vtable: IAudioClient::Initialize (index 3)
                Initialize = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,
                    ctypes.c_void_p,
                    ctypes.c_uint,
                    ctypes.c_uint,
                    ctypes.c_longlong,
                    ctypes.c_longlong,
                    ctypes.c_void_p,
                    ctypes.c_void_p,
                )(vtbl_ac[0][3])

                buf_dur = REFTIMES_PER_SEC  # 1 second buffer
                hr = Initialize(
                    audio_client,
                    AUDCLNT_SHAREMODE_SHARED,
                    AUDCLNT_STREAMFLAGS_LOOPBACK,
                    buf_dur,
                    0,
                    pwfx_ptr,
                    None,
                )
                if hr != 0:
                    raise OSError(f"IAudioClient::Initialize hr={hr:#010x}")

                # GetService → IAudioCaptureClient (index 14)
                GetService = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_byte * 16),
                    ctypes.POINTER(ctypes.c_void_p),
                )(vtbl_ac[0][14])

                capture_client = ctypes.c_void_p()
                hr = GetService(
                    audio_client,
                    ctypes.byref(IID_IAudioCaptureClient),
                    ctypes.byref(capture_client),
                )
                if hr != 0:
                    raise OSError(f"GetService hr={hr:#010x}")

                # Start (index 11)
                Start = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p)(
                    vtbl_ac[0][11]
                )
                hr = Start(audio_client)
                if hr != 0:
                    raise OSError(f"IAudioClient::Start hr={hr:#010x}")

                # IAudioCaptureClient vtable
                vtbl_cc = ctypes.cast(capture_client, ctypes.POINTER(ctypes.c_void_p))
                # GetNextPacketSize (index 3)
                GetNextPacketSize = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)
                )(vtbl_cc[0][3])
                # GetBuffer (index 4) — returns pointer to audio data
                GetBuffer = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint64),
                )(vtbl_cc[0][4])  # actually index 3 in IAudioCaptureClient
                # ReleaseBuffer (index 4)
                ReleaseBuffer = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p, ctypes.c_uint32
                )(vtbl_cc[0][4])

                # Fix: correct vtable indices for IAudioCaptureClient
                # 0=QI, 1=AddRef, 2=Release, 3=GetBuffer, 4=ReleaseBuffer, 5=GetNextPacketSize
                GetBuffer = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT,
                    ctypes.c_void_p,
                    ctypes.POINTER(ctypes.c_void_p),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint32),
                    ctypes.POINTER(ctypes.c_uint64),
                )(vtbl_cc[0][3])
                ReleaseBuffer = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p, ctypes.c_uint32
                )(vtbl_cc[0][4])
                GetNextPacketSize = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)
                )(vtbl_cc[0][5])

                CHUNK = 1024
                freqs = np.fft.rfftfreq(CHUNK, d=1.0 / rate)
                edges = np.logspace(math.log10(40.0), math.log10(16000.0), N_BARS + 1)
                accum = np.zeros(0, dtype=np.float32)

                while self._fft_active:
                    pkt_size = ctypes.c_uint32()
                    GetNextPacketSize(capture_client, ctypes.byref(pkt_size))
                    if pkt_size.value == 0:
                        _t.sleep(0.01)
                        continue

                    data_ptr = ctypes.c_void_p()
                    num_frames = ctypes.c_uint32()
                    flags = ctypes.c_uint32()
                    dev_pos = ctypes.c_uint32()
                    qpc_pos = ctypes.c_uint64()

                    hr = GetBuffer(
                        capture_client,
                        ctypes.byref(data_ptr),
                        ctypes.byref(num_frames),
                        ctypes.byref(flags),
                        ctypes.byref(dev_pos),
                        ctypes.byref(qpc_pos),
                    )
                    if hr != 0 or data_ptr.value is None:
                        _t.sleep(0.01)
                        continue

                    n = num_frames.value * channels
                    if bits == 32:
                        raw = np.frombuffer(
                            (ctypes.c_float * n).from_address(data_ptr.value),
                            dtype=np.float32,
                        ).copy()
                    else:
                        raw = (
                            np.frombuffer(
                                (ctypes.c_int16 * n).from_address(data_ptr.value),
                                dtype=np.int16,
                            ).astype(np.float32)
                            / 32768.0
                        )

                    ReleaseBuffer(capture_client, num_frames)

                    # mix to mono
                    if channels > 1:
                        raw = raw.reshape(-1, channels).mean(axis=1)

                    accum = np.concatenate([accum, raw])

                    while len(accum) >= CHUNK:
                        chunk = accum[:CHUNK]
                        accum = accum[CHUNK:]
                        mag = np.abs(np.fft.rfft(chunk * np.hanning(CHUNK))) / (
                            CHUNK / 2
                        )
                        new_bars = []
                        for b in range(N_BARS):
                            mask = (freqs >= edges[b]) & (freqs < edges[b + 1])
                            val = (
                                float(np.mean(mag[mask])) * 120.0 if mask.any() else 0.0
                            )
                            new_bars.append(min(1.0, val))
                        with self._fft_lock:
                            for i in range(N_BARS):
                                self._fft_bars[i] += (
                                    new_bars[i] - self._fft_bars[i]
                                ) * SMOOTH

                # Stop
                Stop = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p)(
                    vtbl_ac[0][12]
                )
                Stop(audio_client)

            except Exception:
                # WASAPI failed — fall back to soundcard if available
                try:
                    import soundcard as sc

                    loopbacks = [
                        m
                        for m in sc.all_microphones(include_loopback=True)
                        if getattr(m, "isloopback", False)
                    ]
                    if not loopbacks:
                        loopbacks = [
                            sc.get_microphone(
                                sc.default_speaker().name, include_loopback=True
                            )
                        ]
                    mic = loopbacks[0]
                    RATE2 = 44100
                    CHUNK2 = 1024
                    f2 = np.fft.rfftfreq(CHUNK2, d=1.0 / RATE2)
                    e2 = np.logspace(math.log10(40.0), math.log10(16000.0), N_BARS + 1)
                    with mic.recorder(
                        samplerate=RATE2, channels=1, blocksize=CHUNK2
                    ) as rec:
                        while self._fft_active:
                            data = rec.record(numframes=CHUNK2)[:, 0].astype(np.float32)
                            mag = np.abs(np.fft.rfft(data * np.hanning(CHUNK2))) / (
                                CHUNK2 / 2
                            )
                            nb = []
                            for b in range(N_BARS):
                                mask = (f2 >= e2[b]) & (f2 < e2[b + 1])
                                v = (
                                    float(np.mean(mag[mask])) * 120.0
                                    if mask.any()
                                    else 0.0
                                )
                                nb.append(min(1.0, v))
                            with self._fft_lock:
                                for i in range(N_BARS):
                                    self._fft_bars[i] += (
                                        nb[i] - self._fft_bars[i]
                                    ) * SMOOTH
                except Exception:
                    pass

        self._fft_thread = threading.Thread(target=_run, daemon=True)
        self._fft_thread.start()

    def _sim_bars(self, t, playing):
        """Return 48 bar heights — real FFT data if available, else simulation."""
        # Try real FFT data first
        if hasattr(self, "_fft_bars") and self._fft_bars is not None:
            with self._fft_lock:
                bars = list(self._fft_bars)
            sens = getattr(self, "_viz_sensitivity", 1.0)
            bars = [min(1.0, v * sens) for v in bars]
            if max(bars) > 0.005:
                # Real audio data is flowing — use it
                self._viz_bars = bars
                return self._viz_bars
            # FFT returned all zeros (capture not working) — fall through to simulation

        # Tier 2: file-decode FFT (background thread, in sync)
        if playing and hasattr(self, "_fft_file_bars") and self._fft_file_bars:
            with self._fft_file_lock:
                fb = list(self._fft_file_bars)
            if max(fb) > 0.002:
                self._viz_bars = fb
                self._viz_last_real_bars = fb  # remember last good frame
                return self._viz_bars
        # If FFT thread just started, hold last real frame instead of simulating
        if playing and getattr(self, "_viz_last_real_bars", None):
            # Decay slowly to zero rather than jumping to fake sin waves
            held = self._viz_last_real_bars
            self._viz_bars = [v * 0.85 for v in held]
            self._viz_last_real_bars = self._viz_bars
            return self._viz_bars
        # Tier 3: simulation fallback (no audio data at all)
        for i in range(48):
            if playing:
                a = math.sin(t * self._viz_speeds[i] * 7 + self._viz_phases[i])
                b = math.sin(t * self._viz_speeds[i] * 2.5 + self._viz_phases[i] * 1.4)
                c = math.sin(t * self._viz_speeds[i] * 15 + self._viz_phases[i] * 0.6)
                raw = (a * 0.5 + b * 0.3 + c * 0.2) * 0.5 + 0.5
                bass = math.exp(-i / 7.0) * 0.45 * abs(math.sin(t * 0.038))
                raw = max(0.06, min(1.0, raw + bass))
            else:
                raw = 0.04 + 0.025 * math.sin(t * 0.35 + i * 0.6)
            self._viz_bars[i] += (raw - self._viz_bars[i]) * 0.16
        return self._viz_bars

    def _draw_visualizer(self):
        cv = self.viz_cv
        cv.delete("all")
        W = cv.winfo_width()
        H = cv.winfo_height()
        if W < 4 or H < 4:
            self._viz_job = cv.after(100, self._viz_tick)
            return
        t = self._viz_t
        playing = self.engine.is_playing or self._sp_playing
        bars = self._sim_bars(t, playing)

        # smooth glow
        glow_tgt = (sum(bars[:8]) / 8) if playing else 0.05
        self._viz_glow += (glow_tgt - self._viz_glow) * 0.08

        if self._viz_mode == "hexcore":
            self._viz_hexcore(cv, W, H, t, playing, bars)
        elif self._viz_mode == "pulse":
            self._viz_pulse(cv, W, H, t, playing, bars)
        elif self._viz_mode == "orbit":
            self._viz_orbit(cv, W, H, t, playing, bars)
        elif self._viz_mode == "grid":
            self._viz_grid(cv, W, H, t, playing, bars)
        elif self._viz_mode == "spectrum":
            self._viz_spectrum(cv, W, H, t, playing, bars)
        elif self._viz_mode == "oscilloscope":
            self._viz_oscilloscope(cv, W, H, t, playing, bars)
        elif self._viz_mode == "particles":
            self._viz_particles(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku":
            self._viz_miku(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku_tails":
            self._viz_miku_tails(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku_sakura":
            self._viz_miku_sakura(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku_starfall":
            self._viz_miku_starfall(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku_ribbon":
            self._viz_miku_ribbon(cv, W, H, t, playing, bars)
        elif self._viz_mode == "miku_wave":
            self._viz_miku_wave(cv, W, H, t, playing, bars)
        elif self._viz_mode == "nerv_magi":
            self._viz_nerv_magi(cv, W, H, t, playing, bars)
        elif self._viz_mode == "nerv_angel":
            self._viz_nerv_angel(cv, W, H, t, playing, bars)
        elif self._viz_mode == "nerv_eva":
            self._viz_nerv_eva(cv, W, H, t, playing, bars)
        elif self._viz_mode == "nier_yorha":
            self._viz_nier_yorha(cv, W, H, t, playing, bars)
        elif self._viz_mode == "nier_machine":
            self._viz_nier_machine(cv, W, H, t, playing, bars)
        elif self._viz_mode == "nier_ruins":
            self._viz_nier_ruins(cv, W, H, t, playing, bars)
        elif self._viz_mode == "angel_feathers":
            self._viz_angel_feathers(cv, W, H, t, playing, bars)
        elif self._viz_mode == "angel_halo":
            self._viz_angel_halo(cv, W, H, t, playing, bars)
        elif self._viz_mode == "angel_wings":
            self._viz_angel_wings(cv, W, H, t, playing, bars)
        elif self._viz_mode == "glitch":
            self._viz_glitch(cv, W, H, t, playing, bars)
        elif self._viz_mode == "cipher":
            self._viz_cipher(cv, W, H, t, playing, bars)
        elif self._viz_mode == "arasaka":
            self._viz_arasaka(cv, W, H, t, playing, bars)

        # ── FFT HUD overlay — live stats painted on top of every mode ──
        self._viz_draw_hud(cv, W, H, t, playing, bars)

        # Track label update
        sym = chr(9654) if playing else chr(9646) + chr(9646)
        if self._sp_mode and self._sp_dur_ms > 0:
            title = self.now_title.cget("text")
            artist = self.now_artist.cget("text")
            self.viz_track_lbl.config(text=f"{sym}  {title[:44]}  —  {artist[:28]}")
            self.viz_pos_lbl.config(
                text=f"{self._fmt(self._sp_pos_ms / 1000)} / {self._fmt(self._sp_dur_ms / 1000)}"
            )
        elif 0 <= self.current_idx < len(self.library):
            tr = self.library[self.current_idx]
            self.viz_track_lbl.config(
                text=f"{sym}  {tr['title'][:44]}  —  {tr['artist'][:28]}"
            )
            pos = self.engine.get_position()
            dur = self.engine.duration
            self.viz_pos_lbl.config(text=f"{self._fmt(pos)} / {self._fmt(dur)}")
        else:
            self.viz_track_lbl.config(text="— NO TRACK —")
            self.viz_pos_lbl.config(text="")

    def _viz_draw_hud(self, cv, W, H, t, playing, bars):
        """Persistent cybercore HUD overlay — FFT bands, BPM est, stats."""
        try:
            # Only draw on cybercore modes; skip miku/angel/nier styles
            mode = self._viz_mode
            if any(x in mode for x in ("miku", "angel", "nerv", "nier")):
                return

            energy = sum(bars[:8]) / 8 if bars else 0.0
            bass   = min(1.0, sum(bars[:4]) / 4 * 3.5) if bars else 0.0
            mid    = sum(bars[8:24]) / 16 if bars else 0.0
            hi     = sum(bars[24:]) / 24 if bars else 0.0

            # ── top-left: 8-band mini spectrum bars ──
            bx, by = 14, 14
            bw, bh = 3, 20
            gap = 2
            for bi in range(8):
                mag = min(1.0, bars[bi * 3] * 4.0) if bars else 0.0
                fh = max(2, int(mag * bh))
                bv = int(0x28 + mag * (0xd0 - 0x28))
                col = f"#{bv:02x}{bv:02x}{bv:02x}"
                x0 = bx + bi * (bw + gap)
                cv.create_rectangle(x0, by + bh - fh, x0 + bw, by + bh,
                                    fill=col, outline="")

            # ── top-left labels ──
            cv.create_text(bx, by + bh + 7, text="FFT",
                           font=("Courier New", 6), fill=C["white3"], anchor="w")

            # ── bottom-left: band readouts ──
            pad = 10
            lh = 12
            for li, (label, val) in enumerate([
                ("BASS", bass), ("MID", mid), ("HI", hi), ("RMS", energy)
            ]):
                y = H - pad - li * lh
                bv = int(0x30 + val * (0xcc - 0x30))
                col = f"#{bv:02x}{bv:02x}{bv:02x}"
                bar_w = int(val * 48)
                cv.create_rectangle(pad, y - 6, pad + bar_w, y - 2,
                                    fill=col, outline="")
                cv.create_text(pad, y, text=f"{label} {val:.2f}",
                               font=("Courier New", 6), fill=C["white3"], anchor="w")

            # ── top-right: mode + frame counter ──
            cv.create_text(W - 10, 12,
                           text=f"[ {mode.upper()} ]  F:{t:04d}",
                           font=("Courier New", 6), fill=C["white3"], anchor="e")

            # ── bottom-right: track position hex ──
            pos = self.engine.get_position() if self.engine.is_playing else 0
            dur = self.engine.duration if self.engine.duration > 0 else 1
            cv.create_text(W - 10, H - 10,
                           text=f"0x{int(pos):04X} / 0x{int(dur):04X}",
                           font=("Courier New", 6), fill=C["white3"], anchor="se")

            # ── subtle corner tick marks ──
            tick = 8
            tick_col = C["border2"]
            for cx2, cy2, dx, dy in [
                (0, 0, 1, 1), (W, 0, -1, 1), (0, H, 1, -1), (W, H, -1, -1)
            ]:
                cv.create_line(cx2, cy2, cx2 + dx * tick, cy2, fill=tick_col)
                cv.create_line(cx2, cy2, cx2, cy2 + dy * tick, fill=tick_col)
        except Exception:
            pass

    # ══════════════════════════════════════
    #  MODE: HEXCORE
    #  Big rotating hex + bar spikes + rings
    # ══════════════════════════════════════
    def _viz_hexcore(self, cv, W, H, t, playing, bars):
        cx, cy = W / 2, H / 2
        base_r = min(W, H) * 0.28
        glow = self._viz_glow

        # ── outer decoration rings ──
        for ri in range(4):
            frac = (ri + 1) / 4
            r = base_r * (1.55 + frac * 0.55)
            br = int(18 + 12 * (1 - frac)) if not playing else int(28 + 20 * (1 - frac))
            col = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_oval(
                cx - r, cy - r, cx + r, cy + r, outline=col, fill="", width=1
            )

        # ── bar spikes radiating outward from hex ──
        n_bars = 48
        for i in range(n_bars):
            angle = (i / n_bars) * math.pi * 2 - math.pi / 2
            h_val = bars[i]
            # spike starts at hex perimeter, extends outward
            inner_r = base_r * 1.05
            outer_r = inner_r + h_val * base_r * 0.85
            x1 = cx + inner_r * math.cos(angle)
            y1 = cy + inner_r * math.sin(angle)
            x2 = cx + outer_r * math.cos(angle)
            y2 = cy + outer_r * math.sin(angle)
            # brightness by height
            if playing:
                br = int(60 + 195 * h_val)
            else:
                br = int(25 + 30 * h_val)
            br = max(0, min(255, br))
            col = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_line(x1, y1, x2, y2, fill=col, width=1)

            # peak dot
            if playing and h_val > 0.4:
                pk = int(200 + 55 * h_val)
                pk = min(255, pk)
                cv.create_oval(
                    x2 - 2,
                    y2 - 2,
                    x2 + 2,
                    y2 + 2,
                    fill=f"#{pk:02x}{pk:02x}{pk:02x}",
                    outline="",
                )

        # ── rotating hexagon — multiple layers ──
        for layer in range(3):
            lf = layer / 3
            r = base_r * (1.0 - lf * 0.2)
            spd = 0.008 * (1 + layer * 0.5) * (1.8 if playing else 0.4)
            rot = t * spd + layer * math.pi / 6
            pts = []
            for i in range(6):
                a = i / 6 * math.pi * 2 + rot
                pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
            if playing:
                br = int(120 + 80 * (1 - lf) + glow * 55)
            else:
                br = int(45 + 25 * (1 - lf))
            br = min(255, br)
            lw = 2 if layer == 0 else 1
            cv.create_polygon(
                pts, outline=f"#{br:02x}{br:02x}{br:02x}", fill="", width=lw
            )

        # ── inner crosshair ──
        ch_r = base_r * 0.45
        ch_br = 60 if not playing else int(80 + glow * 80)
        ch_br = min(255, ch_br)
        ch_col = f"#{ch_br:02x}{ch_br:02x}{ch_br:02x}"
        cv.create_line(cx - ch_r, cy, cx + ch_r, cy, fill=ch_col, width=1)
        cv.create_line(cx, cy - ch_r, cx, cy + ch_r, fill=ch_col, width=1)
        # diagonal ticks
        tk_r = ch_r * 0.3
        for ang in [math.pi / 4, 3 * math.pi / 4, 5 * math.pi / 4, 7 * math.pi / 4]:
            cv.create_line(
                cx + (ch_r - tk_r) * math.cos(ang),
                cy + (ch_r - tk_r) * math.sin(ang),
                cx + ch_r * math.cos(ang),
                cy + ch_r * math.sin(ang),
                fill=ch_col,
                width=1,
            )

        # ── centre pulse dot ──
        pulse_r = 3 + glow * 6 if playing else 3
        p_br = int(180 + glow * 75) if playing else 80
        p_br = min(255, p_br)
        cv.create_oval(
            cx - pulse_r,
            cy - pulse_r,
            cx + pulse_r,
            cy + pulse_r,
            fill=f"#{p_br:02x}{p_br:02x}{p_br:02x}",
            outline="",
        )

        # ── corner hex accents ──
        for ox, oy in [(50, 50), (W - 50, 50), (50, H - 50), (W - 50, H - 50)]:
            sr = 16
            rot2 = t * 0.006
            spts = []
            for i in range(6):
                a = i / 6 * math.pi * 2 + rot2
                spts += [ox + sr * math.cos(a), oy + sr * math.sin(a)]
            cv.create_polygon(spts, outline=C["border2"], fill="", width=1)
            cv.create_oval(
                ox - 2, oy - 2, ox + 2, oy + 2, fill=C["border2"], outline=""
            )

    # ══════════════════════════════════════
    #  MODE: PULSE — concentric hex rings
    # ══════════════════════════════════════
    def _viz_pulse(self, cv, W, H, t, playing, bars):
        cx, cy = W / 2, H / 2
        glow = self._viz_glow
        n = 10
        base = min(W, H) * 0.08

        for ri in range(n):
            frac = (ri + 1) / n
            # radius pulses with bass
            pulse = bars[ri % 8] * 0.18 if playing else 0
            r = base * (ri + 1) * (1 + pulse)
            rot = t * 0.006 * (1 if ri % 2 == 0 else -1) * (1.6 if playing else 0.3)
            pts = []
            for i in range(6):
                a = i / 6 * math.pi * 2 + rot + frac
                pts += [cx + r * math.cos(a), cy + r * math.sin(a)]
            if playing:
                br = int(30 + 100 * (1 - frac) + glow * 80 * (1 - frac))
            else:
                br = int(20 + 30 * (1 - frac))
            br = min(255, br)
            lw = 2 if ri == 0 else 1
            cv.create_polygon(
                pts, outline=f"#{br:02x}{br:02x}{br:02x}", fill="", width=lw
            )

        # connecting spokes
        r_outer = base * n
        for i in range(6):
            a = i / 6 * math.pi * 2 + t * 0.006
            x2 = cx + r_outer * math.cos(a)
            y2 = cy + r_outer * math.sin(a)
            br = 40 if not playing else int(50 + glow * 60)
            cv.create_line(cx, cy, x2, y2, fill=f"#{br:02x}{br:02x}{br:02x}", width=1)

        # centre
        p = 4 + glow * 8 if playing else 4
        br = int(160 + glow * 95) if playing else 70
        br = min(255, br)
        cv.create_oval(
            cx - p,
            cy - p,
            cx + p,
            cy + p,
            fill=f"#{br:02x}{br:02x}{br:02x}",
            outline="",
        )

    # ══════════════════════════════════════
    #  MODE: ORBIT
    # ══════════════════════════════════════
    def _viz_orbit(self, cv, W, H, t, playing, bars):
        cx, cy = W / 2, H / 2
        n_rings = 5
        glow = self._viz_glow

        for ang in range(0, 360, 30):
            r2 = math.radians(ang)
            R = min(W, H) * 0.46
            br = 20 if not playing else int(22 + glow * 18)
            cv.create_line(
                cx,
                cy,
                cx + R * math.cos(r2),
                cy + R * math.sin(r2),
                fill=f"#{br:02x}{br:02x}{br:02x}",
                width=1,
            )

        for ri in range(n_rings):
            frac = (ri + 1) / n_rings
            r = frac * min(W, H) * 0.42
            br = (
                int(30 + 25 * (1 - frac))
                if not playing
                else int(45 + 40 * (1 - frac) + glow * 30)
            )
            br = min(255, br)
            cv.create_oval(
                cx - r,
                cy - r,
                cx + r,
                cy + r,
                outline=f"#{br:02x}{br:02x}{br:02x}",
                fill="",
                width=1,
            )
            # hex markers on ring
            n_dots = 6
            spd = 0.012 * (1 + ri * 0.4) * (1.6 if playing else 0.3)
            rot = t * spd * (1 if ri % 2 == 0 else -1)
            for di in range(n_dots):
                angle = (di / n_dots) * math.pi * 2 + rot
                dx = cx + r * math.cos(angle)
                dy = cy + r * math.sin(angle)
                # mini hexagon
                hpts = []
                hr = 5 + bars[di % 48] * 6 if playing else 4
                for hi in range(6):
                    ha = hi / 6 * math.pi * 2
                    hpts += [dx + hr * math.cos(ha), dy + hr * math.sin(ha)]
                hbr = int(100 + bars[di % 48] * 155) if playing else 55
                hbr = min(255, hbr)
                cv.create_polygon(
                    hpts, outline=f"#{hbr:02x}{hbr:02x}{hbr:02x}", fill="", width=1
                )

        p = 4 + glow * 7 if playing else 3
        br = int(180 + glow * 75) if playing else 80
        br = min(255, br)
        cv.create_oval(
            cx - p,
            cy - p,
            cx + p,
            cy + p,
            fill=f"#{br:02x}{br:02x}{br:02x}",
            outline="",
        )

    # ══════════════════════════════════════
    #  MODE: GRID — Tron perspective
    # ══════════════════════════════════════
    def _viz_grid(self, cv, W, H, t, playing, bars):
        hz = H * 0.50
        vpx = W * 0.50
        cols = 18
        rows = 12
        glow = self._viz_glow
        spd = 0.007 if playing else 0.002

        # update particles
        for p in self._viz_grid_particles:
            p[0] += p[2] * spd
            p[1] += p[3] * spd
            if p[0] < 0 or p[0] > 1:
                p[2] = -p[2]
                p[0] = max(0, min(1, p[0]))
            if p[1] < 0 or p[1] > 1:
                p[3] = -p[3]
                p[1] = max(0, min(1, p[1]))

        bg_gr = 25 if playing else 16
        bg_c = f"#{bg_gr:02x}{bg_gr:02x}{bg_gr:02x}"
        for i in range(cols + 1):
            bx = (i / cols) * W
            cv.create_line(vpx, hz, bx, H, fill=bg_c, width=1)
        for j in range(rows + 1):
            frac = (j / rows) ** 1.9
            y = hz + frac * (H - hz)
            xl = vpx - frac * vpx
            xr = vpx + frac * (W - vpx)
            cv.create_line(xl, y, xr, y, fill=bg_c, width=1)

        # particle web above horizon
        pts_s = [(p[0] * W, p[1] * hz * 0.92 + 6) for p in self._viz_grid_particles]
        for i, (ax, ay) in enumerate(pts_s):
            for j, (bx, by) in enumerate(pts_s):
                if j <= i:
                    continue
                d = math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)
                if d < W * 0.20:
                    alpha = int((1 - d / (W * 0.20)) * (100 if playing else 40))
                    alpha = max(0, min(255, alpha))
                    cv.create_line(
                        ax,
                        ay,
                        bx,
                        by,
                        fill=f"#{alpha:02x}{alpha:02x}{alpha:02x}",
                        width=1,
                    )
        for ax, ay in pts_s:
            r = 2 if playing else 1
            br = int(120 + glow * 100) if playing else 50
            br = min(255, br)
            cv.create_oval(
                ax - r,
                ay - r,
                ax + r,
                ay + r,
                fill=f"#{br:02x}{br:02x}{br:02x}",
                outline="",
            )

        # horizon line + pulse
        h_br = int(60 + glow * 80) if playing else 28
        cv.create_line(0, hz, W, hz, fill=f"#{h_br:02x}{h_br:02x}{h_br:02x}", width=1)
        if playing:
            px = W * (math.sin(t * 0.04) * 0.5 + 0.5)
            cv.create_oval(px - 4, hz - 4, px + 4, hz + 4, fill="#ffffff", outline="")

        # ── SPOTIFY VIEW ──────────────────────

    def _build_spotify_view(self):
        self.sp_frame = tk.Frame(self.content, bg=C["bg"])

        # Top bar: header + login status
        top = tk.Frame(self.sp_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="SPOTIFY", font=FMX, fg=C["white"], bg=C["bg"]).pack(
            side="left"
        )
        self.sp_status_lbl = tk.Label(
            top, text="[ NOT CONNECTED ]", font=FMS, fg=C["white2"], bg=C["bg"]
        )
        self.sp_status_lbl.pack(side="left", padx=12)
        self.sp_login_btn = tk.Label(
            top, text="CONNECT", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2"
        )
        self.sp_login_btn.pack(side="right", padx=4)
        self.sp_login_btn.bind("<Button-1>", lambda e: self._sp_login())
        self.sp_login_btn.bind(
            "<Enter>", lambda e: self.sp_login_btn.config(fg=C["white"])
        )
        self.sp_login_btn.bind(
            "<Leave>", lambda e: self.sp_login_btn.config(fg=C["white3"])
        )

        tk.Frame(self.sp_frame, bg=C["border"], height=1).pack(
            fill="x", padx=0, pady=(8, 0)
        )

        # Sub-nav row
        nav = tk.Frame(self.sp_frame, bg=C["bg"])
        nav.pack(fill="x", padx=20, pady=(8, 0))
        self._sp_nav_btns = {}
        for label, key in [("HOME", "home"), ("LIKED", "liked"), ("SEARCH", "search")]:
            b = tk.Label(
                nav,
                text=label,
                font=FMS,
                fg=C["white3"],
                bg=C["bg"],
                cursor="hand2",
                padx=10,
            )
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self._sp_nav(k))
            b.bind("<Enter>", lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=C["white3"]))
            self._sp_nav_btns[key] = b
        # Device picker button
        dev_btn = tk.Label(
            nav,
            text="[ DEVICES ]",
            font=FMS,
            fg=C["white3"],
            bg=C["bg"],
            cursor="hand2",
            padx=10,
        )
        dev_btn.pack(side="right")
        dev_btn.bind("<Button-1>", lambda e: self._sp_show_devices())
        dev_btn.bind("<Enter>", lambda e: dev_btn.config(fg=C["white"]))
        dev_btn.bind("<Leave>", lambda e: dev_btn.config(fg=C["white3"]))

        # Search bar (hidden until search nav selected)
        self.sp_search_frame = tk.Frame(self.sp_frame, bg=C["bg"])
        tk.Label(
            self.sp_search_frame,
            text="⌕",
            font=("Courier New", 12),
            fg=C["white3"],
            bg=C["bg"],
        ).pack(side="left", padx=(20, 4))
        self.sp_search_var = tk.StringVar()
        self.sp_search_entry = tk.Entry(
            self.sp_search_frame,
            textvariable=self.sp_search_var,
            font=FM,
            bg=C["panel"],
            fg=C["white"],
            insertbackground=C["white"],
            relief="flat",
            bd=0,
            width=40,
        )
        self.sp_search_entry.pack(side="left", ipady=4)
        self.sp_search_entry.bind(
            "<Return>", lambda e: (self._sp_do_search(), "break")[1]
        )
        go = tk.Label(
            self.sp_search_frame,
            text="[GO]",
            font=FMS,
            fg=C["white3"],
            bg=C["bg"],
            cursor="hand2",
            padx=8,
        )
        go.pack(side="left")
        go.bind("<Button-1>", lambda e: self._sp_do_search())

        tk.Frame(self.sp_frame, bg=C["border"], height=1).pack(
            fill="x", padx=20, pady=(6, 0)
        )

        # Content label
        self.sp_content_lbl = tk.Label(
            self.sp_frame,
            text="",
            font=("Courier New", 7, "bold"),
            fg=C["white3"],
            bg=C["bg"],
            anchor="w",
        )
        self.sp_content_lbl.pack(fill="x", padx=20, pady=(8, 2))

        # Track list
        lf = tk.Frame(self.sp_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        sb = tk.Scrollbar(
            lf, bg=C["panel"], troughcolor=C["bg"], width=8, relief="flat", bd=0
        )
        sb.pack(side="right", fill="y")
        self.sp_list_cv = tk.Canvas(
            lf,
            bg=C["bg"],
            highlightthickness=1,
            highlightbackground=C["border"],
            yscrollcommand=sb.set,
        )
        self.sp_list_cv.pack(fill="both", expand=True)
        sb.config(command=self.sp_list_cv.yview)
        self.sp_list_cv.bind(
            "<MouseWheel>",
            lambda e: self.sp_list_cv.yview_scroll(
                int(-1 * (e.delta / 120)) * 3, "units"
            ),
        )
        self.sp_list_cv.bind("<Double-Button-1>", self._sp_play_selected)
        self.sp_list_cv.bind("<Button-3>", self._sp_rclick)
        self.sp_list_cv.bind("<Button-1>", self._sp_list_click)
        self._sp_row_height = 64
        self._sp_thumb_cache = {}  # url -> PhotoImage
        self._sp_selected_idx = -1
        self._sp_list_width = 0
        self.sp_list_cv.bind("<Configure>", self._sp_list_resize)

        # Now-playing bar at bottom
        np = tk.Frame(self.sp_frame, bg=C["panel"], height=28)
        np.pack(fill="x")
        np.pack_propagate(False)
        self.sp_np_lbl = tk.Label(
            np,
            text="— SPOTIFY NOT PLAYING —",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["panel"],
        )
        self.sp_np_lbl.pack(side="left", padx=16)
        # controls
        ctrl = tk.Frame(np, bg=C["panel"])
        ctrl.pack(side="right", padx=10)
        for sym, cmd in [
            ("⏮", self._sp_prev),
            ("⏯", self._sp_playpause),
            ("⏭", self._sp_next),
        ]:
            b = tk.Label(
                ctrl,
                text=sym,
                font=("Courier New", 11),
                fg=C["white3"],
                bg=C["panel"],
                cursor="hand2",
                padx=6,
            )
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=C["white3"]))

        # Poll now-playing
        self._sp_np_job = None
        self._sp_playlists_cache = []

    # ── Spotify helpers ──────────────────
    def _sp_nav(self, key):
        self._sp_view = key
        # update nav highlight
        for k, b in self._sp_nav_btns.items():
            b.config(fg=C["white"] if k == key else C["white3"])
        if key == "search":
            self.sp_search_frame.pack(fill="x", pady=(4, 0))
        else:
            self.sp_search_frame.pack_forget()
        self._sp_refresh_view()

    def _sp_refresh_view(self):
        if not self.sp_auth.is_authenticated():
            self.sp_status_lbl.config(text="[ NOT CONNECTED ]")
            self.sp_login_btn.config(text="CONNECT")
            self.sp_content_lbl.config(
                text="Connect your Spotify account to get started."
            )
            self._sp_clear_list()
            return

        # Check/refresh token
        if not self.sp_auth.token_valid() and self.sp_auth.refresh_token:
            self.sp_auth.refresh(lambda ok, *a: self._sp_refresh_view() if ok else None)
            return

        self.sp_status_lbl.config(text="[ CONNECTED ]", fg=C["white"])
        self.sp_login_btn.config(text="DISCONNECT")

        if self._sp_view == "home":
            self._sp_load_home()
        elif self._sp_view == "liked":
            self._sp_load_liked()
        elif self._sp_view == "search":
            pass  # wait for user input
        # start now-playing poll
        if self._sp_np_job is None:
            self._sp_poll_np()

    def _sp_load_home(self):
        self.sp_content_lbl.config(text="YOUR PLAYLISTS")
        self._sp_clear_list()
        self._sp_status_msg("Loading...")
        self._sp_tracks = []

        def _fetch():
            self.sp_auth.reload_from_disk()
            if self.sp_api._is_rate_limited():
                remaining = int(self.sp_auth.rate_limited_until - time.time())
                self.root.after(
                    0,
                    lambda: self._sp_status_msg(
                        f"[ Rate limited — retry in {remaining}s ]"
                    ),
                )
                return
            data = self.sp_api.playlists(50)
            if not data:
                self.root.after(
                    0, lambda: self._sp_status_msg("[ Error loading playlists ]")
                )
                return
            items = data.get("items", [])
            self._sp_playlists_cache = items
            self.root.after(0, lambda: self._sp_show_playlists(items))

        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_show_playlists(self, items):
        self._sp_clear_list()
        self._sp_tracks = []
        self._sp_selected_idx = -1
        self._sp_pl_thumb_cache = {}  # playlist cover cache (separate from track thumbs)
        self._sp_pl_items = items  # keep reference for redraw
        cv = self.sp_list_cv
        RH = self._sp_row_height
        W = max(self._sp_list_width, cv.winfo_width(), 400)
        cv.configure(scrollregion=(0, 0, W, RH * len(items)))
        for i, pl in enumerate(items):
            self._sp_draw_pl_row(i, pl, W)
            # kick off cover art fetch
            images = pl.get("images") or []
            url = images[0].get("url") if images else None
            if url:
                threading.Thread(
                    target=self._sp_fetch_pl_thumb, args=(i, url), daemon=True
                ).start()
            # count comes straight from the playlist object — no extra API calls
        # double-click opens playlist (only while playlists are shown)
        self.sp_list_cv.bind("<Double-Button-1>", self._sp_open_playlist)

    def _sp_draw_pl_row(self, i, pl, W):
        cv = self.sp_list_cv
        RH = self._sp_row_height
        y0 = i * RH
        y1 = y0 + RH
        tag = f"row{i}"
        cv.delete(tag)
        bg = (
            C["select"]
            if i == self._sp_selected_idx
            else (C["panel2"] if i % 2 == 0 else C["bg"])
        )
        cv.create_rectangle(0, y0, W, y1, fill=bg, outline="", tags=tag)

        # cover art square (same layout as track rows)
        TH = RH - 8
        cv.create_rectangle(
            4, y0 + 4, 4 + TH, y1 - 4, fill=C["panel"], outline=C["border"], tags=tag
        )
        if i in self._sp_pl_thumb_cache:
            photo = self._sp_pl_thumb_cache[i]
            cx = 4 + TH // 2
            cy = y0 + RH // 2
            cv.create_image(cx, cy, image=photo, anchor="center", tags=tag)
        else:
            cv.create_text(
                4 + TH // 2,
                y0 + RH // 2,
                text="▤",
                font=("Courier New", 11),
                fill=C["white3"],
                anchor="center",
                tags=tag,
            )

        # text — offset past image
        tx = 4 + TH + 10
        name = pl.get("name", "?")
        owner = (pl.get("owner") or {}).get("id", "")
        count = (pl.get("tracks") or {}).get("total", None)
        # Spotify-owned algorithmic playlists are API-blocked
        spotify_owned = owner == "spotify"
        name_col = C["white3"] if spotify_owned else C["white"]
        count_str = (
            "[ spotify — no api access ]"
            if spotify_owned
            else (f"{count} tracks" if count else "—")
        )
        cv.create_text(
            tx,
            y0 + RH // 2 - 7,
            text=name[:55],
            font=("Courier New", 9, "bold"),
            fill=name_col,
            anchor="w",
            tags=tag,
        )
        cv.create_text(
            tx,
            y0 + RH // 2 + 7,
            text=count_str,
            font=("Courier New", 8),
            fill=C["white3"],
            anchor="w",
            tags=tag,
        )
        cv.create_line(0, y1 - 1, W, y1 - 1, fill=C["border"], tags=tag)

    def _sp_fetch_pl_thumb(self, idx, url):
        """Fetch a playlist cover image in a background thread."""
        try:
            import urllib.request as _ur
            import tempfile

            data = _ur.urlopen(url, timeout=8).read()
            suffix = ".png" if b"PNG" in data[:8] else ".jpg"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(data)
            tmp.close()
            self.root.after(0, lambda p=tmp.name, i=idx: self._sp_load_pl_thumb(i, p))
        except Exception:
            pass

    def _sp_load_pl_thumb(self, idx, path):
        """Load playlist cover from temp file, cache it, redraw the row."""
        try:
            import tkinter as _tk

            RH = self._sp_row_height - 8
            try:
                img = _tk.PhotoImage(file=path)
                iw, ih = img.width(), img.height()
                factor = max(1, max(iw, ih) // RH)
                img = img.subsample(factor, factor)
            except Exception:
                from PIL import Image, ImageTk

                img = Image.open(path).resize((RH, RH))
                img = ImageTk.PhotoImage(img)
            self._sp_pl_thumb_cache[idx] = img
            self._sp_redraw_pl_row(idx)
        except Exception:
            pass
        finally:
            try:
                import os

                os.unlink(path)
            except Exception:
                pass

    def _sp_redraw_pl_row(self, idx):
        """Redraw a single playlist row (called after image/count arrives)."""
        if not hasattr(self, "_sp_pl_items") or idx >= len(self._sp_pl_items):
            return
        W = max(self._sp_list_width, self.sp_list_cv.winfo_width(), 400)
        self._sp_draw_pl_row(idx, self._sp_pl_items[idx], W)

    def _sp_open_playlist(self, event=None):
        idx = self._sp_selected_idx
        if idx < 0 or idx >= len(self._sp_playlists_cache):
            return
        pl = self._sp_playlists_cache[idx]
        pl_id = pl["id"]
        pl_name = pl.get("name", "?")
        pl_uri = pl.get("uri") or f"spotify:playlist:{pl_id}"

        self.sp_content_lbl.config(text=f"▸ {pl_name.upper()}")
        self._sp_clear_list()
        print(f"[SPOTIFY] playing playlist via context_uri: '{pl_name}' id={pl_id}")

        # First try to load track list so user can see and pick songs
        # If that 403s, fall back to playing the whole playlist as a context
        def _fetch():
            tracks = []
            offset = 0
            while True:
                self.sp_api._last_error = ""
                data = self.sp_api.playlist_tracks(pl_id, limit=50, offset=offset)
                if not data:
                    err = getattr(self.sp_api, "_last_error", "")
                    if "403" in err:
                        # Track list blocked — play via context_uri instead
                        print(
                            "[SPOTIFY] track list 403 — falling back to context_uri play"
                        )
                        self.root.after(
                            0, lambda: self._sp_play_context(pl_uri, pl_name)
                        )
                    break
                items = data.get("items", [])
                for it in items:
                    t = it.get("track")
                    if t and t.get("uri"):
                        tracks.append(t)
                offset += len(items)
                if not items or not data.get("next"):
                    break
            if tracks:
                self._sp_tracks = tracks
                self.root.after(0, lambda: self._sp_show_tracks(tracks))
            elif not getattr(self.sp_api, "_last_error", ""):
                self.root.after(
                    0,
                    lambda: self._sp_status_msg("No playable tracks in this playlist."),
                )

        self._sp_status_msg("Loading...")
        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_play_context(self, context_uri, name):
        """Play a Spotify context (playlist/album) directly — bypasses track list API."""
        self._sp_status_msg(f"▶  Playing '{name}'")
        self._stop_all_sources()
        self._active_source = "spotify"
        self._sp_mode = True
        self.root.after(0, lambda: self.sp_np_lbl.config(text=f"▶  {name}"))

        def _do():
            import time as _t

            devices = []
            for _ in range(4):
                data = self.sp_api.devices()
                devices = (data or {}).get("devices", [])
                if devices:
                    break
                _t.sleep(0.7)

            active = [d for d in devices if d.get("is_active")]
            dev_id = (
                active[0]["id"] if active else (devices[0]["id"] if devices else None)
            )
            if not dev_id:
                self.root.after(0, self._sp_no_device_error)
                return

            if not active:
                self.sp_api.transfer(dev_id, play=False)
                _t.sleep(0.5)

            self.sp_api.play_on(dev_id, context_uri=context_uri)

            # Reset position and force a fresh poll after 1.5s
            now = _t.time()
            self.root.after(
                0,
                lambda: (
                    setattr(self, "_sp_pos_ms", 0),
                    setattr(self, "_sp_dur_ms", 0),
                    setattr(self, "_sp_poll_at", now),
                ),
            )
            _t.sleep(1.5)
            if self._sp_np_job:
                try:
                    self.root.after_cancel(self._sp_np_job)
                except:
                    pass
                self._sp_np_job = None
            self.root.after(0, self._sp_poll_np)

        threading.Thread(target=_do, daemon=True).start()

    def _sp_load_liked(self):
        self.sp_content_lbl.config(text="LIKED SONGS")
        self._sp_clear_list()
        self._sp_status_msg("Loading...")

        def _fetch():
            tracks = []
            offset = 0
            while len(tracks) < 200:
                data = self.sp_api.liked_songs(limit=50, offset=offset)
                if not data:
                    break
                items = data.get("items", [])
                for it in items:
                    t = it.get("track")
                    if t and t.get("uri"):
                        tracks.append(t)
                offset += len(items)
                if not items:
                    break
            self._sp_tracks = tracks
            self.root.after(0, lambda: self._sp_show_tracks(tracks))

        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_do_search(self):
        q = self.sp_search_var.get().strip()
        if not q:
            return
        if not self.sp_auth.is_authenticated():
            self._sp_status_msg("[ Not connected — click CONNECT first ]")
            return
        self.sp_content_lbl.config(text=f'SEARCH: "{q}"')
        self._sp_clear_list()
        self._sp_status_msg("Searching...")

        def _fetch():
            # Diagnose token state before searching
            auth = self.sp_auth
            has_token = bool(auth.access_token)
            token_valid = auth.token_valid()
            has_refresh = bool(auth.refresh_token)
            expires_in = int(auth.expires_at - time.time()) if auth.expires_at else 0

            if not has_token and not has_refresh:
                self.root.after(
                    0,
                    lambda: self._sp_status_msg(
                        "[ Not logged in — please DISCONNECT and reconnect ]"
                    ),
                )
                return
            if not token_valid and not has_refresh:
                self.root.after(
                    0,
                    lambda: self._sp_status_msg(
                        "[ Token expired and no refresh token — please reconnect ]"
                    ),
                )
                return

            data = self.sp_api.search(q, limit=20)
            if not data:
                err = getattr(self.sp_api, "_last_error", None)
                if err:
                    msg = f"[ Search failed: {err} ]"
                else:
                    # Extra diagnostics
                    msg = (
                        f"[ Search returned nothing — "
                        f"token={'ok' if token_valid else 'expired'}, "
                        f"refresh={'yes' if has_refresh else 'no'}, "
                        f"expires_in={expires_in}s, "
                        f"client_id={'set' if SPOTIFY_CLIENT_ID else 'MISSING'} ]"
                    )
                self.root.after(0, lambda m=msg: self._sp_status_msg(m))
                return
            tracks = [
                it
                for it in data.get("tracks", {}).get("items", [])
                if it and it.get("uri")
            ]
            if not tracks:
                self.root.after(0, lambda: self._sp_status_msg("[ No tracks found ]"))
                return
            self._sp_tracks = tracks
            self.root.after(0, lambda: self._sp_show_tracks(tracks))

        threading.Thread(target=_fetch, daemon=True).start()

    def _sp_clear_list(self):
        if hasattr(self, "sp_list_cv"):
            self.sp_list_cv.delete("all")
            self.sp_list_cv.configure(scrollregion=(0, 0, 100, 40))
        self._sp_thumb_cache = {}
        self._sp_pl_thumb_cache = {}
        self._sp_pl_items = []
        self._sp_selected_idx = -1

    def _sp_status_msg(self, msg):
        cv = self.sp_list_cv
        cv.delete("all")
        cv.create_text(20, 20, text=msg, anchor="nw", font=FM, fill=C["white3"])
        cv.configure(scrollregion=(0, 0, 100, 40))

    def _sp_show_tracks(self, tracks):
        self._sp_tracks = tracks
        self._sp_selected_idx = -1
        self._sp_thumb_cache = {}
        # Restore play binding (may have been overridden by playlist view)
        self.sp_list_cv.bind("<Double-Button-1>", self._sp_play_selected)
        self._sp_render_list()
        # kick off thumbnail fetches
        for i, t in enumerate(tracks):
            images = t.get("album", {}).get("images", [])
            url = None
            for img in sorted(images, key=lambda x: x.get("width", 9999)):
                if img.get("width", 0) >= 48:
                    url = img.get("url")
                    break
            if not url and images:
                url = images[-1].get("url")
            if url:
                threading.Thread(
                    target=self._sp_fetch_thumb, args=(i, url), daemon=True
                ).start()

    def _sp_fetch_thumb(self, idx, url):
        try:
            import urllib.request as _ur
            import tempfile

            data = _ur.urlopen(url, timeout=6).read()
            suffix = ".png" if b"PNG" in data[:8] else ".jpg"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(data)
            tmp.close()
            self.root.after(0, lambda p=tmp.name, i=idx: self._sp_load_thumb(i, p))
        except Exception:
            pass

    def _sp_load_thumb(self, idx, path):
        try:
            import tkinter as _tk

            RH = self._sp_row_height - 8
            try:
                img = _tk.PhotoImage(file=path)
                iw, ih = img.width(), img.height()
                factor = max(1, max(iw, ih) // RH)
                img = img.subsample(factor, factor)
            except Exception:
                from PIL import Image, ImageTk

                img = Image.open(path).resize((RH, RH))
                img = ImageTk.PhotoImage(img)
            self._sp_thumb_cache[idx] = img
            self._sp_redraw_row(idx)
        except Exception:
            pass
        finally:
            try:
                import os

                os.unlink(path)
            except Exception:
                pass

    def _sp_render_list(self):
        cv = self.sp_list_cv
        cv.delete("all")
        if not hasattr(self, "_sp_tracks") or not self._sp_tracks:
            cv.create_text(
                20, 20, text="No tracks loaded.", anchor="nw", font=FM, fill=C["white3"]
            )
            cv.configure(scrollregion=(0, 0, 100, 40))
            return
        RH = self._sp_row_height
        W = max(self._sp_list_width, cv.winfo_width(), 400)
        total_h = RH * len(self._sp_tracks)
        cv.configure(scrollregion=(0, 0, W, total_h))
        for i, t in enumerate(self._sp_tracks):
            self._sp_draw_row(i, t, W)
        cv.update_idletasks()
        cv.update_idletasks()

    def _sp_draw_row(self, i, t, W):
        cv = self.sp_list_cv
        RH = self._sp_row_height
        y0 = i * RH
        y1 = y0 + RH
        tag = f"row{i}"
        cv.delete(tag)

        bg = (
            C["select"]
            if i == self._sp_selected_idx
            else (C["panel2"] if i % 2 == 0 else C["bg"])
        )
        cv.create_rectangle(0, y0, W, y1, fill=bg, outline="", tags=tag)

        TH = RH - 8
        cv.create_rectangle(
            4, y0 + 4, 4 + TH, y1 - 4, fill=C["panel"], outline=C["border"], tags=tag
        )
        if i in self._sp_thumb_cache:
            photo = self._sp_thumb_cache[i]
            cx = 4 + TH // 2
            cy = y0 + RH // 2
            cv.create_image(cx, cy, image=photo, anchor="center", tags=tag)
        else:
            cv.create_text(
                4 + TH // 2,
                y0 + RH // 2,
                text="o",
                font=("Courier New", 12),
                fill=C["white3"],
                anchor="center",
                tags=tag,
            )

        tx = 4 + TH + 8
        cv.create_text(
            tx,
            y0 + RH // 2,
            text=f"{i + 1:>3}.",
            font=("Courier New", 8),
            fill=C["white3"],
            anchor="w",
            tags=tag,
        )

        title = t.get("name", "?")
        artists = t.get("artists", [])
        artist = ", ".join(a["name"] for a in artists)
        album = t.get("album", {}).get("name", "")
        dur_ms = t.get("duration_ms", 0)
        dur_s = dur_ms // 1000
        dur_str = f"{dur_s // 60}:{dur_s % 60:02d}"
        tx2 = tx + 36
        # Title row
        cv.create_text(
            tx2,
            y0 + 14,
            text=title[:70],
            font=("Courier New", 9, "bold"),
            fill=C["white"],
            anchor="w",
            tags=tag,
        )
        # Artist row
        cv.create_text(
            tx2,
            y0 + 32,
            text=artist[:70],
            font=("Courier New", 8),
            fill=C["white2"],
            anchor="w",
            tags=tag,
        )
        # Album row
        cv.create_text(
            tx2,
            y0 + 48,
            text=album[:70],
            font=("Courier New", 7),
            fill=C["white3"],
            anchor="w",
            tags=tag,
        )

        cv.create_text(
            W - 12,
            y0 + RH // 2,
            text=dur_str,
            font=("Courier New", 8),
            fill=C["white3"],
            anchor="e",
            tags=tag,
        )

        cv.create_line(0, y1 - 1, W, y1 - 1, fill=C["border"], tags=tag)

    def _sp_redraw_row(self, idx):
        if not hasattr(self, "_sp_tracks") or idx >= len(self._sp_tracks):
            return
        W = max(self._sp_list_width, self.sp_list_cv.winfo_width(), 400)
        self._sp_draw_row(idx, self._sp_tracks[idx], W)

    def _sp_list_resize(self, event):
        self._sp_list_width = event.width
        self._sp_render_list()

    def _sp_list_click(self, event):
        RH = self._sp_row_height
        idx = int(self.sp_list_cv.canvasy(event.y) // RH)
        max(self._sp_list_width, self.sp_list_cv.winfo_width(), 400)
        # ── playlist home view: single click opens the playlist ──
        if hasattr(self, "_sp_pl_items") and self._sp_pl_items and not self._sp_tracks:
            if idx < 0 or idx >= len(self._sp_pl_items):
                return
            self._sp_selected_idx = idx
            self._sp_open_playlist()
            return
        # ── track view ──
        if not hasattr(self, "_sp_tracks") or idx >= len(self._sp_tracks):
            return
        old = self._sp_selected_idx
        self._sp_selected_idx = idx
        if old >= 0:
            self._sp_redraw_row(old)
        self._sp_redraw_row(idx)

    def _sp_play_selected(self, event=None):
        idx = self._sp_selected_idx
        if idx < 0 or not self._sp_tracks:
            return
        if idx >= len(self._sp_tracks):
            return
        uris = [t["uri"] for t in self._sp_tracks]
        self._sp_play_with_device(uris, idx)

    def _sp_play_with_device(self, uris, idx):
        """Fetch devices, pick one, then play. Retries a few times so the
        Spotify desktop app has time to register itself as an active device."""
        # Stop any local/YT/SC playback immediately before handing off to Spotify
        self._stop_all_sources()
        self._active_source = "spotify"
        self._sp_mode = True

        def _do():
            import time as _t

            devices = []
            for attempt in range(6):  # try up to ~5 seconds
                data = self.sp_api.devices()
                devices = (data or {}).get("devices", [])
                if devices:
                    break
                _t.sleep(0.9)

            active = [d for d in devices if d.get("is_active")]
            if active:
                dev_id = active[0]["id"]
                self.sp_api.play_on(dev_id, uris=uris, offset={"position": idx})
            elif devices:
                # Transfer to first available device then play
                dev_id = devices[0]["id"]
                self.sp_api.transfer(dev_id, play=False)
                _t.sleep(0.8)
                self.sp_api.play_on(dev_id, uris=uris, offset={"position": idx})
            else:
                self.root.after(0, self._sp_no_device_error)

        threading.Thread(target=_do, daemon=True).start()

    def _sp_no_device_error(self):
        messagebox.showwarning(
            "OTERNOS // SPOTIFY",
            "No active Spotify device found."
            + chr(10)
            + chr(10)
            + "Open Spotify on your phone, PC, or any device first,"
            + chr(10)
            + "then try playing again.",
        )

    def _sp_rclick(self, event):
        RH = self._sp_row_height
        sel = int(self.sp_list_cv.canvasy(event.y) // RH)
        old = self._sp_selected_idx
        self._sp_selected_idx = sel
        if old >= 0:
            self._sp_redraw_row(old)
        self._sp_redraw_row(sel)
        if sel >= len(self._sp_tracks):
            return
        track = self._sp_tracks[sel]
        m = tk.Menu(
            self.root,
            tearoff=0,
            bg=C["panel"],
            fg=C["white"],
            font=FM,
            bd=0,
            relief="flat",
            activebackground=C["select"],
            activeforeground=C["white"],
        )
        m.add_command(label="▶  Play Now", command=lambda: self._sp_play_selected())
        m.add_command(
            label="＋  Add to Local Library",
            command=lambda: self._sp_add_to_local(track),
        )
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _sp_add_to_local(self, track):
        title = track.get("name", "?")
        artist = ", ".join(a["name"] for a in track.get("artists", []))
        note = "Spotify tracks cannot be downloaded. Play them via the Spotify tab while Spotify is open."
        msg = title + " by " + artist + chr(10) + chr(10) + note
        messagebox.showinfo("OTERNOS // SPOTIFY", msg)

    def _sp_playpause(self):
        def _do():
            np = self.sp_api.now_playing()
            if np and np.get("is_playing"):
                self.sp_api.pause()
            else:
                self.sp_api.play()

        threading.Thread(target=_do, daemon=True).start()

    def _sp_next(self):
        threading.Thread(target=self.sp_api.next_track, daemon=True).start()

    def _sp_prev(self):
        threading.Thread(target=self.sp_api.prev_track, daemon=True).start()

    def _sp_poll_np(self):
        """Poll Spotify now-playing every 10 seconds."""
        if not self.sp_auth.is_authenticated():
            self._sp_np_job = None
            return

        def _fetch():
            if not self.sp_auth.token_valid():
                return
            if self.sp_api._is_rate_limited():
                remaining = int(self.sp_auth.rate_limited_until - time.time())
                self.root.after(
                    0,
                    lambda: self.sp_np_lbl.config(
                        text=f"⏸  Rate limited — {remaining}s"
                    ),
                )
                return
            np = self.sp_api.now_playing()
            if np and np.get("item"):
                t = np["item"]
                title = t.get("name", "?")
                artist = ", ".join(a["name"] for a in t.get("artists", []))
                is_play = np.get("is_playing", False)
                pos_ms = np.get("progress_ms", 0) or 0
                dur_ms = t.get("duration_ms", 0) or 0
                dev = (np.get("device") or {}).get("name", "")
                dev_s = ("  //  " + dev[:20]) if dev else ""
                sym = "▶" if is_play else "⏸"
                sp_lbl = sym + "  " + title[:38] + "  —  " + artist[:24] + dev_s
                # grab smallest image that's still at least 64px
                images = t.get("album", {}).get("images", [])
                art_url = None
                for img in sorted(images, key=lambda x: x.get("width", 0)):
                    if img.get("width", 0) >= 64:
                        art_url = img.get("url")
                        break
                if not art_url and images:
                    art_url = images[-1].get("url")

                # Push into main player bar — only if Spotify is actually playing
                def _update():
                    self._sp_pos_ms = pos_ms
                    self._sp_dur_ms = dur_ms
                    self._sp_playing = is_play
                    self.sp_np_lbl.config(text=sp_lbl)
                    # Only take over the main bar if:
                    #   - Spotify is already the active source, OR
                    #   - No local playback is happening at all
                    local_active = (
                        self.engine.is_playing
                        or self.engine.is_paused
                        or self._active_source in ("library", "youtube", "soundcloud")
                    )
                    if is_play and self._active_source == "spotify":
                        pass  # already spotify — always update
                    elif is_play and not local_active and self._active_source == "none":
                        pass  # nothing local running — spotify can take over
                    else:
                        return  # local/YT/SC is active — don't hijack
                    self._sp_mode = True
                    self._active_source = "spotify"
                    self._set_source_badge("spotify")
                    t_disp = (title[:36] + "…") if len(title) > 37 else title
                    self.now_title.config(text=t_disp)
                    self.now_artist.config(text=artist)
                    self.lbl_tot.config(text=self._fmt(dur_ms / 1000))
                    self.btn_play.config(text="⏸")
                    self.wavevis.set_active(True)
                    self.status_lbl.config(text="[ SPOTIFY ]")
                    if art_url:
                        self._set_album_art(art_url)
                    # History + lyrics
                    last = self._history[-1] if self._history else {}
                    if is_play and last.get("title") != title:
                        self._history_add(
                            {"title": title, "artist": artist, "album": ""},
                            source="spotify",
                        )
                        # Fetch lyrics for new track — works same as library/_do_load_track
                        self._set_current_track_for_lyrics(artist, title)
                        self._start_lyric_ticker()
                        if getattr(self, "view", "") == "lyrics":
                            self._refresh_lyrics_view()

                self.root.after(0, _update)
            else:
                devs = (self.sp_api.devices() or {}).get("devices", [])
                if devs:
                    names = ", ".join(d.get("name", "?") for d in devs[:3])
                    lbl = "⏸  No track playing  //  devices: " + names
                else:
                    lbl = "— NO SPOTIFY DEVICE FOUND — open Spotify on a device —"
                self.root.after(0, lambda: self.sp_np_lbl.config(text=lbl))
                self.root.after(0, self._draw_art_placeholder)

        threading.Thread(target=_fetch, daemon=True).start()
        self._sp_np_job = self.root.after(10000, self._sp_poll_np)

    def _sp_show_devices(self):
        def _do():
            data = self.sp_api.devices()
            devices = (data or {}).get("devices", [])
            if not devices:
                self.root.after(
                    0,
                    lambda: messagebox.showwarning(
                        "OTERNOS // SPOTIFY DEVICES",
                        "No Spotify devices found."
                        + chr(10)
                        + chr(10)
                        + "Make sure Spotify is open and playing on at least one device.",
                    ),
                )
                return
            lines = ["AVAILABLE DEVICES", ""]
            for d in devices:
                active = " [ACTIVE]" if d.get("is_active") else ""
                lines.append(
                    d.get("name", "?") + "  //  " + d.get("type", "?") + active
                )
            self.root.after(
                0,
                lambda: messagebox.showinfo(
                    "OTERNOS // SPOTIFY DEVICES", chr(10).join(lines)
                ),
            )

        threading.Thread(target=_do, daemon=True).start()

    def _sp_login(self):
        if self.sp_auth.is_authenticated():
            # Disconnect
            self.sp_auth.access_token = None
            self.sp_auth.refresh_token = None
            self.sp_auth.expires_at = 0
            try:
                Path(SpotifyAuth.TOKEN_FILE).unlink()
            except:
                pass
            self.sp_status_lbl.config(text="[ NOT CONNECTED ]", fg=C["white3"])
            self.sp_login_btn.config(text="CONNECT")
            self._sp_clear_list()
            return

        url = self.sp_auth.get_auth_url()
        self.sp_status_lbl.config(text="[ WAITING FOR LOGIN... ]")

        def on_code(code):
            self.sp_auth.exchange_code(code, callback=self._sp_on_auth)

        self.sp_auth.start_callback_server(on_code)
        webbrowser.open(url)

    def _sp_on_auth(self, ok, err=None):
        if ok:
            self.root.after(0, self._sp_refresh_view)
        else:
            self.root.after(
                0,
                lambda: self.sp_status_lbl.config(text="[ AUTH FAILED ]", fg=C["red"]),
            )


    # ── SOUNDCLOUD VIEW ───────────────────
    def _build_soundcloud_view(self):
        self.sc_frame = tk.Frame(self.content, bg=C["bg"])
        self._sc_hover_idx = -1

        # ── Header ────────────────────────────────────────────────────────
        top = tk.Frame(self.sc_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="SOUNDCLOUD", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")

        # Status pill: ● dot + text badge
        self._sc_status_dot = tk.Label(top, text="●", font=FMS, fg=C["white3"], bg=C["bg"])
        self._sc_status_dot.pack(side="left", padx=(12, 2))
        self.sc_status_lbl = tk.Label(top, text="PUBLIC", font=FMS, fg=C["white2"], bg=C["bg"])
        self.sc_status_lbl.pack(side="left")

        self.sc_queue_lbl = tk.Label(top, text="", font=FMS, fg=C["white3"], bg=C["bg"])
        self.sc_queue_lbl.pack(side="left", padx=(12, 0))

        # ── Collapsible auth row (hidden by default) ──────────────────────
        self._sc_auth_visible = False
        self.sc_auth_row = tk.Frame(self.sc_frame, bg=C["panel"])
        inner_auth = tk.Frame(self.sc_auth_row, bg=C["panel"])
        inner_auth.pack(fill="x", padx=20, pady=6)
        tk.Label(inner_auth, text="OAuth Token:", font=FMS, fg=C["white3"], bg=C["panel"]).pack(side="left", padx=(0, 6))
        self.sc_token_var = tk.StringVar(value=self.sc_api.oauth_token or "")
        _tok_wrap = tk.Frame(inner_auth, bg=C["border"], padx=1, pady=1)
        _tok_wrap.pack(side="left", padx=(0, 6))
        sc_tok_entry = tk.Entry(_tok_wrap, textvariable=self.sc_token_var,
                                font=FMS, bg=C["panel"], fg=C["white"],
                                insertbackground=C["white"], relief="flat", bd=0, width=36, show="*")
        sc_tok_entry.pack(ipady=3)
        sc_tok_entry.bind("<FocusIn>",  lambda e: _tok_wrap.config(bg=C["white3"]))
        sc_tok_entry.bind("<FocusOut>", lambda e: _tok_wrap.config(bg=C["border"]))
        sc_tok_entry.bind("<Return>", lambda e: self._sc_save_token())
        self.sc_save_btn = tk.Label(inner_auth, text="SAVE", font=FMS, fg=C["white3"], bg=C["panel"], cursor="hand2")
        self.sc_save_btn.pack(side="left")
        self.sc_save_btn.bind("<Button-1>", lambda e: self._sc_save_token())
        self.sc_save_btn.bind("<Enter>", lambda e: self.sc_save_btn.config(fg=C["white"]))
        self.sc_save_btn.bind("<Leave>", lambda e: self.sc_save_btn.config(fg=C["white3"]))
        tk.Label(inner_auth, text="  from sc-inspector or browser devtools",
                 font=("Courier New", 7), fg=C["white3"], bg=C["panel"]).pack(side="left")

        tk.Frame(self.sc_frame, bg=C["border"], height=1).pack(fill="x", pady=(6, 0))

        # ── Sub-nav with animated underline ──────────────────────────────
        nav = tk.Frame(self.sc_frame, bg=C["bg"])
        nav.pack(fill="x", padx=20, pady=(6, 0))
        self._sc_nav_btns = {}
        self._sc_nav_underlines = {}
        for label, key in [("SEARCH", "search"), ("LIKES", "likes"), ("FAVORITES", "favorites")]:
            tf = tk.Frame(nav, bg=C["bg"])
            tf.pack(side="left", padx=(0, 2))
            b = tk.Label(tf, text=label, font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=10)
            b.pack()
            uline = tk.Canvas(tf, height=2, bg=C["bg"], highlightthickness=0)
            uline.pack(fill="x")
            b.bind("<Button-1>", lambda e, k=key: self._sc_nav(k))
            b.bind("<Enter>",  lambda e, w=b, k=key: w.config(fg=C["white"]) if self._sc_view != k else None)
            b.bind("<Leave>",  lambda e, w=b, k=key: w.config(fg=C["white"]) if self._sc_view == k else w.config(fg=C["white3"]))
            self._sc_nav_btns[key] = b
            self._sc_nav_underlines[key] = uline

        # CLR QUEUE button — right side
        self._sc_clr_btn = tk.Label(nav, text="CLR QUEUE", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=6)
        self._sc_clr_btn.pack(side="right")
        self._sc_clr_btn.bind("<Button-1>", lambda e: self._sc_clear_queue())
        self._sc_clr_btn.bind("<Enter>", lambda e: self._sc_clr_btn.config(fg=C["white"]))
        self._sc_clr_btn.bind("<Leave>", lambda e: self._sc_clr_btn.config(fg=C["white3"]))

        # TOKEN toggle — right side
        self._sc_tok_btn = tk.Label(nav, text="TOKEN", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=6)
        self._sc_tok_btn.pack(side="right")
        self._sc_tok_btn.bind("<Button-1>", lambda e: self._sc_toggle_auth())
        self._sc_tok_btn.bind("<Enter>", lambda e: self._sc_tok_btn.config(fg=C["white"]))
        self._sc_tok_btn.bind("<Leave>", lambda e: self._sc_tok_btn.config(fg=C["white3"]))

        # Draw initial underline on active tab
        self.sc_frame.after(50, lambda: self._sc_draw_nav_underline("search"))

        # ── Search bar with focus ring ────────────────────────────────────
        self.sc_search_frame = tk.Frame(self.sc_frame, bg=C["bg"])
        self.sc_search_frame.pack(fill="x", pady=(4, 0))
        tk.Label(self.sc_search_frame, text="⌕", font=("Courier New", 12), fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(20, 4))
        _search_ring = tk.Frame(self.sc_search_frame, bg=C["border"], padx=1, pady=1)
        _search_ring.pack(side="left", padx=(0, 6))
        self.sc_search_var = tk.StringVar()
        sc_entry = tk.Entry(_search_ring, textvariable=self.sc_search_var,
                            font=FM, bg=C["panel"], fg=C["white"],
                            insertbackground=C["white"], relief="flat", bd=0, width=40)
        sc_entry.pack(ipady=4)
        sc_entry.bind("<FocusIn>",  lambda e: _search_ring.config(bg=C["white3"]))
        sc_entry.bind("<FocusOut>", lambda e: _search_ring.config(bg=C["border"]))
        sc_entry.bind("<Return>", lambda e: (self._sc_do_search(), "break")[1])
        sc_go = tk.Label(self.sc_search_frame, text="GO", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=8)
        sc_go.pack(side="left")
        sc_go.bind("<Button-1>", lambda e: self._sc_do_search())
        sc_go.bind("<Enter>", lambda e: sc_go.config(fg=C["white"]))
        sc_go.bind("<Leave>", lambda e: sc_go.config(fg=C["white3"]))

        tk.Frame(self.sc_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))

        self.sc_content_lbl = tk.Label(self.sc_frame, text="Search for tracks above",
                                        font=("Courier New", 8, "bold"), fg=C["white3"], bg=C["bg"], anchor="w")
        self.sc_content_lbl.pack(fill="x", padx=20, pady=(8, 2))

        # ── Track list ────────────────────────────────────────────────────
        lf = tk.Frame(self.sc_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"], width=8, relief="flat", bd=0)
        sb.pack(side="right", fill="y")
        self.sc_list = tk.Listbox(lf, bg=C["bg"], fg=C["white2"],
                                   selectbackground=C["select"], selectforeground=C["white"],
                                   font=FM, relief="flat", bd=0, activestyle="none",
                                   yscrollcommand=sb.set,
                                   highlightthickness=1, highlightcolor=C["border"],
                                   highlightbackground=C["border"])
        self.sc_list.pack(fill="both", expand=True)
        sb.config(command=self.sc_list.yview)
        self.sc_list.bind("<Double-Button-1>", self._sc_play_selected)
        self.sc_list.bind("<Button-1>", self._sc_list_click)
        self.sc_list.bind("<MouseWheel>", lambda e: self._scroller.scroll(self.sc_list, e.delta))
        self.sc_list.bind("<Button-3>", self._sc_right_click)
        self.sc_list.bind("<Return>", self._sc_play_selected)
        self.sc_list.bind("<space>", lambda e: (self._sc_ctx_queue(), "break")[1])
        self.sc_list.bind("<Delete>", lambda e: self._sc_kb_delete())
        self.sc_list.bind("<FocusIn>",  lambda e: self.sc_list.config(highlightcolor=C["white3"]))
        self.sc_list.bind("<FocusOut>", lambda e: self.sc_list.config(highlightcolor=C["border"]))
        self.sc_list.bind("<Motion>", self._sc_list_hover)
        self.sc_list.bind("<Leave>",  self._sc_list_unhover)
        # Detail panel state
        self._sc_detail_idx = -1
        self._sc_detail_win = None

        # ── Right-click context menu ──────────────────────────────────────
        self._sc_ctx = tk.Menu(self.sc_frame, tearoff=0, bg=C["panel"], fg=C["white"],
                                activebackground=C["select2"], activeforeground=C["glow"],
                                font=FMS, bd=0, relief="flat")
        self._sc_ctx.add_command(label="▶  Play",                  command=self._sc_ctx_play)
        self._sc_ctx.add_command(label="⊕  Add to Queue",          command=self._sc_ctx_queue)
        self._sc_ctx.add_separator()
        self._sc_ctx.add_command(label="♥  Add to Favorites",      command=self._sc_ctx_favorite)
        self._sc_ctx.add_command(label="✕  Remove from Favorites", command=self._sc_ctx_unfavorite)
        self._sc_ctx.add_separator()
        self._sc_ctx.add_command(label="⬇  Save to Library",       command=self._sc_ctx_save)
        self._sc_ctx.add_command(label="⎘  Open on SoundCloud",    command=self._sc_ctx_open)

        # ── Now-playing bar ───────────────────────────────────────────────
        np = tk.Frame(self.sc_frame, bg=C["panel"], height=36)
        np.pack(fill="x")
        np.pack_propagate(False)
        # Left accent stripe
        tk.Frame(np, bg=C["border2"], width=3).pack(side="left", fill="y")
        self.sc_np_lbl = tk.Label(np, text="— SOUNDCLOUD —", font=("Courier New", 8),
                                   fg=C["white3"], bg=C["panel"])
        self.sc_np_lbl.pack(side="left", padx=12)
        self.sc_np_artist_btn = tk.Label(np, text="", font=("Courier New", 8),
                                          fg=C["white3"], bg=C["panel"], cursor="hand2")
        self.sc_np_artist_btn.pack(side="right", padx=16)
        self.sc_np_artist_btn.bind("<Button-1>", lambda e: self._sc_np_artist_click())
        self.sc_np_artist_btn.bind("<Enter>", lambda e: self.sc_np_artist_btn.config(fg=C["white"]))
        self.sc_np_artist_btn.bind("<Leave>", lambda e: self.sc_np_artist_btn.config(fg=C["white3"]))

        # Restore NP bar if a track is already playing when view is first built
        self.sc_frame.after(50, self._sc_restore_np_bar)

    def _sc_toggle_auth(self):
        self._sc_auth_visible = not self._sc_auth_visible
        if self._sc_auth_visible:
            self.sc_auth_row.pack(fill="x", pady=(2, 0), after=self.sc_frame.winfo_children()[0])
            self._sc_tok_btn.config(fg=C["white"])
        else:
            self.sc_auth_row.pack_forget()
            self._sc_tok_btn.config(fg=C["white3"] if not self.sc_api.oauth_token else C["white"])

    def _sc_draw_nav_underline(self, key):
        """Draw a 2px white underline bar under the active nav tab."""
        for k, uline in self._sc_nav_underlines.items():
            uline.delete("all")
            if k == key:
                w = uline.winfo_width() or 60
                uline.create_rectangle(0, 0, w, 2, fill=C["white"], outline="")

    def _sc_list_hover(self, event):
        """Highlight row under cursor on mouse motion."""
        if not self._sc_tracks:
            return
        idx = self.sc_list.nearest(event.y)
        if idx == self._sc_hover_idx:
            return
        self._sc_list_unhover(event)
        self._sc_hover_idx = idx
        if 0 <= idx < len(self._sc_tracks):
            playing_id = (getattr(self, "_sc_current_track", None) or {}).get("id")
            t = self._sc_tracks[idx]
            is_playing = t.get("id") == playing_id
            if not is_playing:
                self.sc_list.itemconfig(idx, bg=C["select"], fg=C["white"])

    def _sc_list_unhover(self, event=None):
        """Restore previous hovered row to its normal color."""
        idx = self._sc_hover_idx
        self._sc_hover_idx = -1
        if 0 <= idx < len(self._sc_tracks):
            self._sc_restore_row_color(idx)

    def _sc_restore_row_color(self, idx):
        """Restore alternating row color, respecting playing state."""
        if idx < 0 or idx >= len(self._sc_tracks):
            return
        playing_id = (getattr(self, "_sc_current_track", None) or {}).get("id")
        t = self._sc_tracks[idx]
        if t.get("id") == playing_id:
            self.sc_list.itemconfig(idx, bg=C["bg"], fg=C["white"])
        else:
            row_bg = C["panel"] if idx % 2 == 1 else C["bg"]
            self.sc_list.itemconfig(idx, bg=row_bg, fg=C["white2"])

    # ── Inline detail panel ───────────────────────────────────────────────

    def _sc_list_click(self, event):
        """Single click plays. Click ⋯ at far right to open detail panel."""
        if not self._sc_tracks:
            self._sc_detail_close()
            return
        idx = self.sc_list.nearest(event.y)
        if idx < 0 or idx >= len(self._sc_tracks):
            self._sc_detail_close()
            return
        self.sc_list.selection_clear(0, "end")
        self.sc_list.selection_set(idx)
        list_w = self.sc_list.winfo_width()
        if event.x >= list_w - 28:
            self._sc_detail_toggle(idx)
        else:
            self._sc_detail_close()
            track = self._sc_tracks[idx]
            threading.Thread(target=lambda: self._sc_stream(track), daemon=True).start()

    def _sc_detail_toggle(self, idx):
        """Open detail for idx, or close it if already open for same row."""
        if self._sc_detail_idx == idx and self._sc_detail_win is not None:
            self._sc_detail_close()
        else:
            self._sc_detail_open(idx)

    def _sc_detail_close(self):
        """Destroy the floating detail panel."""
        if self._sc_detail_win is not None:
            try:
                self._sc_detail_win.destroy()
            except Exception:
                pass
            self._sc_detail_win = None
        self._sc_detail_idx = -1

    def _sc_detail_open(self, idx):
        """Build and position the floating detail panel below the selected row."""
        self._sc_detail_close()
        if idx < 0 or idx >= len(self._sc_tracks):
            return
        track = self._sc_tracks[idx]
        self._sc_detail_idx = idx

        # ── Compute position: just below the selected row in listbox coords ──
        try:
            bbox = self.sc_list.bbox(idx)
            if not bbox:
                return
            row_x, row_y, row_w, row_h = bbox
        except Exception:
            return

        # Convert listbox-relative → root-relative
        lx = self.sc_list.winfo_rootx()
        ly = self.sc_list.winfo_rooty()
        lw = self.sc_list.winfo_width()
        lh = self.sc_list.winfo_height()

        panel_w = lw - 2
        panel_x = lx + 1
        panel_y = ly + row_y + row_h  # immediately below the row

        # Clamp: if it would overflow the bottom of the listbox, show above instead
        panel_h_est = 96
        if panel_y + panel_h_est > ly + lh:
            panel_y = ly + row_y - panel_h_est

        # ── Build as a Toplevel so it floats over the listbox ──────────────
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", False)
        win.configure(bg=C["border"])
        self._sc_detail_win = win

        # 1px border via bg + inner frame
        inner = tk.Frame(win, bg=C["panel2"] if "panel2" in C else C["panel"], padx=14, pady=8)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        bg = inner["bg"]

        # ── Row 1: title + duration ────────────────────────────────────────
        r1 = tk.Frame(inner, bg=bg)
        r1.pack(fill="x", pady=(0, 4))
        title = (track.get("title") or "")
        tk.Label(r1, text=title, font=("Courier New", 9, "bold"),
                 fg=C["white"], bg=bg, anchor="w").pack(side="left", fill="x", expand=True)
        dur_ms = track.get("duration", 0)
        dur_s = dur_ms // 1000
        dur_str = f"{dur_s // 60}:{dur_s % 60:02d}"
        tk.Label(r1, text=dur_str, font=FMS, fg=C["white3"], bg=bg).pack(side="right")

        # ── Row 2: artist ──────────────────────────────────────────────────
        r2 = tk.Frame(inner, bg=bg)
        r2.pack(fill="x", pady=(0, 4))
        artist = (track.get("user", {}).get("username") or "")
        artist_lbl = tk.Label(r2, text=artist, font=FMS, fg=C["white3"], bg=bg,
                               cursor="hand2", anchor="w")
        artist_lbl.pack(side="left")
        artist_lbl.bind("<Button-1>", lambda e: (self._sc_detail_close(),
                                                  self.sc_search_var.set(artist),
                                                  self._sc_nav("search"),
                                                  self._sc_do_search()))
        artist_lbl.bind("<Enter>", lambda e: artist_lbl.config(fg=C["white"]))
        artist_lbl.bind("<Leave>", lambda e: artist_lbl.config(fg=C["white3"]))

        # Genre pill
        genre = (track.get("genre") or "").strip()
        if genre:
            tk.Label(r2, text=f"  {genre}", font=("Courier New", 7),
                     fg=C["white3"], bg=bg).pack(side="left")

        # ── Row 3: stats ───────────────────────────────────────────────────
        r3 = tk.Frame(inner, bg=bg)
        r3.pack(fill="x", pady=(0, 5))

        def _fmt(n):
            if n is None:
                return "—"
            if n >= 1_000_000:
                return f"{n/1_000_000:.1f}M"
            if n >= 1_000:
                return f"{n//1000}k"
            return str(n)

        plays    = track.get("playback_count")
        likes    = track.get("likes_count") or track.get("favoritings_count")
        comments = track.get("comment_count")
        reposts  = track.get("reposts_count")

        stats = [
            ("▸", _fmt(plays),    "plays"),
            ("♥", _fmt(likes),    "likes"),
            ("◉", _fmt(comments), "comments"),
            ("⇄", _fmt(reposts),  "reposts"),
        ]
        for icon, val, tip in stats:
            cell = tk.Frame(r3, bg=bg)
            cell.pack(side="left", padx=(0, 16))
            tk.Label(cell, text=f"{icon} {val}", font=FMS,
                     fg=C["white2"], bg=bg).pack(side="left")

        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", pady=(0, 5))

        # ── Row 4: description snippet ────────────────────────────────────
        desc = (track.get("description") or "").strip().replace("\n", "  ")
        if desc:
            snippet = desc[:120] + ("…" if len(desc) > 120 else "")
            tk.Label(inner, text=snippet, font=("Courier New", 7),
                     fg=C["white3"], bg=bg, anchor="w", wraplength=panel_w - 40,
                     justify="left").pack(fill="x", pady=(0, 4))

        # ── Row 5: action buttons ─────────────────────────────────────────
        r5 = tk.Frame(inner, bg=bg)
        r5.pack(fill="x")

        def _btn(parent, text, cmd):
            b = tk.Label(parent, text=text, font=FMS, fg=C["white3"], bg=bg,
                          cursor="hand2", padx=6)
            b.pack(side="left", padx=(0, 4))
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.config(fg=C["white"]))
            b.bind("<Leave>", lambda e: b.config(fg=C["white3"]))
            return b

        def _play():
            self._sc_detail_close()
            threading.Thread(target=lambda: self._sc_stream(track), daemon=True).start()

        def _queue():
            self._sc_ctx_queue()
            self._sc_detail_close()

        def _fav():
            fav_ids = {t.get("id") for t in self._sc_favorites}
            if track.get("id") in fav_ids:
                self._sc_ctx_unfavorite()
            else:
                self._sc_ctx_favorite()
            self._sc_detail_close()

        def _open():
            url = track.get("permalink_url") or ""
            if url:
                import webbrowser
                webbrowser.open(url)

        _btn(r5, "▶ PLAY",    _play)
        _btn(r5, "⊕ QUEUE",   _queue)
        fav_ids = {t.get("id") for t in self._sc_favorites}
        fav_text = "✕ UNFAV" if track.get("id") in fav_ids else "♥ FAV"
        _btn(r5, fav_text, _fav)
        _btn(r5, "⎘ OPEN",    _open)

        # ── Position and show ─────────────────────────────────────────────
        win.update_idletasks()
        actual_h = win.winfo_reqheight()

        # Re-clamp with real height
        if panel_y + actual_h > ly + lh:
            panel_y = ly + row_y - actual_h
        panel_y = max(ly, panel_y)

        win.geometry(f"{panel_w}x{actual_h}+{panel_x}+{panel_y}")

        # Close if user clicks anywhere outside the panel.
        # We use FocusOut on the panel window — no root-level binding needed,
        # which avoids clobbering other root Button-1 handlers.
        win.bind("<FocusOut>", lambda e: self.root.after(120, self._sc_detail_maybe_close))
        self.sc_list.bind("<Configure>", lambda e: self._sc_detail_close(), add="+")
        self.sc_list.bind("<MouseWheel>",
            lambda e: (self.sc_list.yview_scroll(int(-1*(e.delta/120))*3, "units"),
                       self._sc_detail_close()), add="+")
        # Give the panel focus so FocusOut fires when user clicks elsewhere
        win.after(50, lambda: win.focus_force() if win.winfo_exists() else None)

    def _sc_detail_maybe_close(self):
        """Close detail panel if focus has left it."""
        if self._sc_detail_win is None:
            return
        try:
            focused = self.root.focus_get()
            # If focus is inside the detail window, don't close
            win = self._sc_detail_win
            w = focused
            while w is not None:
                if w == win:
                    return
                try:
                    w = w.master
                except Exception:
                    break
        except Exception:
            pass
        self._sc_detail_close()

    def _sc_detail_outside_click(self, event):
        """Close detail panel if click lands outside it."""
        if self._sc_detail_win is None:
            return
        try:
            win = self._sc_detail_win
            wx = win.winfo_rootx()
            wy = win.winfo_rooty()
            ww = win.winfo_width()
            wh = win.winfo_height()
            if not (wx <= event.x_root <= wx + ww and wy <= event.y_root <= wy + wh):
                self._sc_detail_close()
        except Exception:
            self._sc_detail_close()

    def _sc_save_token(self):
        tok = self.sc_token_var.get().strip()
        self.sc_api.oauth_token = tok or None
        self.sc_api._save_token()
        if tok:
            self._sc_status_dot.config(fg=C["white"])
            self.sc_status_lbl.config(text="AUTH", fg=C["white"])
        else:
            self._sc_status_dot.config(fg=C["white3"])
            self.sc_status_lbl.config(text="PUBLIC", fg=C["white3"])
        self._sc_tok_btn.config(fg=C["white"] if tok else C["white3"])
        # Flash SAVED ✓ then revert, and auto-collapse after a moment
        self.sc_save_btn.config(text="SAVED ✓", fg=C["white"])
        def _revert_btn():
            try:
                self.sc_save_btn.config(text="SAVE", fg=C["white3"])
            except Exception:
                pass
        def _collapse():
            if self._sc_auth_visible:
                self._sc_toggle_auth()
        self.root.after(1200, _revert_btn)
        self.root.after(1600, _collapse)

    def _sc_nav(self, key):
        # Save current view's track list and label before switching
        prev = getattr(self, "_sc_view", "search")
        if prev == "search":
            self._sc_search_tracks = list(self._sc_tracks)
            self._sc_search_label = self.sc_content_lbl.cget("text") if hasattr(self, "sc_content_lbl") else ""
        elif prev == "likes":
            self._sc_likes_tracks = list(self._sc_tracks)
            self._sc_likes_label = self.sc_content_lbl.cget("text") if hasattr(self, "sc_content_lbl") else ""

        self._sc_view = key
        self._sc_detail_close()
        for k, b in self._sc_nav_btns.items():
            b.config(fg=C["white"] if k == key else C["white3"])
        self._sc_draw_nav_underline(key)
        if key == "search":
            self.sc_search_frame.pack(fill="x", pady=(4, 0))
        else:
            self.sc_search_frame.pack_forget()
        self._sc_restore_np_bar()
        self._sc_refresh_view()

    def _sc_restore_np_bar(self):
        """Restore NP bar labels from _sc_current_track after tab switches."""
        t = getattr(self, "_sc_current_track", None)
        if t:
            title  = (t.get("title") or "")[:48]
            artist = (t.get("user", {}).get("username") or "")
            self.sc_np_lbl.config(text=f"  ▶  {title}", fg=C["white"])
            self.sc_np_artist_btn.config(text=artist, fg=C["white2"])
            self.sc_frame.after(120, lambda: self.sc_np_lbl.config(fg=C["white2"]))
        else:
            self.sc_np_lbl.config(text="— SOUNDCLOUD —", fg=C["white3"])
            self.sc_np_artist_btn.config(text="")

    def _sc_refresh_view(self):
        tok = self.sc_api.oauth_token
        cid = bool(self.sc_api.client_id)
        if tok:
            dot_col, status = C["white"], "AUTH"
        elif cid:
            dot_col, status = C["white3"], "PUBLIC"
        else:
            dot_col, status = C["white3"], "CONNECTING..."
        self._sc_status_dot.config(fg=dot_col)
        self.sc_status_lbl.config(text=status, fg=dot_col)
        if self._sc_view == "search":
            # Restore cached search results — don't re-search
            cached = getattr(self, "_sc_search_tracks", [])
            label  = getattr(self, "_sc_search_label", "Search for tracks above")
            self._sc_tracks = list(cached)
            if cached:
                self._sc_show_tracks(cached, label)
            else:
                self._sc_tracks = []
                self.sc_list.delete(0, "end")
                self.sc_content_lbl.config(text="Search for tracks above")
        elif self._sc_view == "likes":
            cached = getattr(self, "_sc_likes_tracks", [])
            label  = getattr(self, "_sc_likes_label", "YOUR LIKES")
            if cached:
                # Restore without re-fetching
                self._sc_tracks = list(cached)
                self._sc_show_tracks(cached, label)
            else:
                self._sc_load_likes()
        elif self._sc_view == "favorites":
            self._sc_nav_favorites()

    def _sc_do_search(self):
        q = self.sc_search_var.get().strip()
        if not q:
            return
        self._sc_last_query = q
        self._sc_search_offset = 0
        self._sc_can_load_more = False
        self.sc_content_lbl.config(text=f'SEARCH: "{q}"')
        self.sc_list.delete(0, "end")
        self.sc_list.insert("end", "  Searching...")
        self._sc_tracks = []

        def _fetch():
            if not self.sc_api.client_id:
                self.root.after(0, lambda: [
                    self.sc_list.delete(0, "end"),
                    self.sc_list.insert("end", "  Fetching SoundCloud credentials..."),
                ])
                self.sc_api.refresh_client_id()
                if not self.sc_api.client_id:
                    self.root.after(0, lambda: [
                        self.sc_list.delete(0, "end"),
                        self.sc_list.insert("end", "  Could not connect to SoundCloud."),
                    ])
                    return
            tracks = self.sc_api.search(q, limit=40)
            self._sc_tracks = tracks
            self._sc_search_tracks = list(tracks)
            self._sc_search_label = f'RESULTS FOR "{q.upper()}"'
            self._sc_search_offset = len(tracks)
            more = len(tracks) >= 40
            def _show():
                self._sc_show_tracks(tracks, f'RESULTS FOR "{q.upper()}"')
                if more:
                    self._sc_append_load_more()
            self.root.after(0, _show)

        threading.Thread(target=_fetch, daemon=True).start()

    def _sc_append_load_more(self):
        """Append a [ LOAD MORE ] sentinel row to the bottom of the list."""
        self._sc_can_load_more = True
        self.sc_list.insert("end", "")
        self.sc_list.insert("end", "          [ LOAD MORE ]")
        self.sc_list.itemconfig("end", fg=C["white3"])

    def _sc_load_more(self):
        if not self._sc_last_query or not self._sc_can_load_more:
            return
        self._sc_can_load_more = False
        # Replace the load-more rows with a loading indicator
        list_size = self.sc_list.size()
        if list_size >= 2:
            self.sc_list.delete(list_size - 2, "end")
        self.sc_list.insert("end", "  Loading more...")
        q = self._sc_last_query
        offset = self._sc_search_offset

        def _fetch():
            tracks = self.sc_api.search(q + f" offset={offset}", limit=40)
            # SC api-v2 uses linked_partitioning — fall back to re-search with offset param
            if not tracks:
                tracks = self.sc_api._get(
                    "/search/tracks",
                    {"q": q, "limit": 40, "offset": offset}
                )
                tracks = (tracks or {}).get("collection", [])
            new_tracks = [t for t in tracks if t.get("id") not in
                          {x.get("id") for x in self._sc_tracks}]
            self._sc_tracks.extend(new_tracks)
            self._sc_search_tracks = list(self._sc_tracks)
            self._sc_search_offset += len(new_tracks)
            more = len(new_tracks) >= 40

            def _show():
                label = self.sc_content_lbl.cget("text")
                self._sc_search_label = label
                self._sc_show_tracks(self._sc_tracks, label)
                if more:
                    self._sc_append_load_more()
                elif new_tracks:
                    self.sc_list.insert("end", "")
                    self.sc_list.insert("end", "  — end of results —")
                    self.sc_list.itemconfig("end", fg=C["white3"])
                else:
                    self.sc_list.insert("end", "  — no more results —")
                    self.sc_list.itemconfig("end", fg=C["white3"])

            self.root.after(0, _show)

        threading.Thread(target=_fetch, daemon=True).start()

    def _sc_load_likes(self):
        if not self.sc_api.oauth_token:
            self._sc_tracks = []
            self.sc_list.delete(0, "end")
            self.sc_content_lbl.config(text="YOUR LIKES")
            self.sc_list.insert("end", "")
            self.sc_list.insert("end", "  An OAuth token is required to load your likes.")
            self.sc_list.insert("end", "")
            self.sc_list.insert("end", "  HOW TO GET YOUR TOKEN:")
            self.sc_list.insert("end", "  1. Open soundcloud.com in your browser and log in.")
            self.sc_list.insert("end", "  2. Open DevTools  (F12)  → Application → Cookies.")
            self.sc_list.insert("end", "  3. Find the cookie named  oauth_token  and copy its value.")
            self.sc_list.insert("end", "     — or — open the Network tab, make any request,")
            self.sc_list.insert("end", "       and look for  Authorization: OAuth <token>  in the headers.")
            self.sc_list.insert("end", "")
            self.sc_list.insert("end", "  Then click  [ TOKEN ]  (top-right) and paste it in.")
            for i in range(self.sc_list.size()):
                row = self.sc_list.get(i)
                if row.startswith("  HOW") or row.startswith("  Then"):
                    self.sc_list.itemconfig(i, fg=C["white2"])
                elif row.startswith("  1.") or row.startswith("  2.") or \
                     row.startswith("  3.") or row.startswith("     "):
                    self.sc_list.itemconfig(i, fg=C["white3"])
            return
        self.sc_content_lbl.config(text="YOUR LIKES")
        self.sc_list.delete(0, "end")
        self.sc_list.insert("end", "  Loading likes...")
        self._sc_tracks = []

        def _fetch():
            tracks = self.sc_api.likes(limit=100)
            self._sc_tracks = tracks
            self._sc_likes_tracks = list(tracks)
            self._sc_likes_label = "YOUR LIKES"
            self.root.after(0, lambda: self._sc_show_tracks(tracks, "YOUR LIKES"))

        threading.Thread(target=_fetch, daemon=True).start()

    def _sc_show_tracks(self, tracks, label=""):
        self._sc_hover_idx = -1
        self._sc_detail_close()
        self.sc_list.delete(0, "end")
        if label:
            self.sc_content_lbl.config(text=label, fg=C["white2"])
            self.sc_frame.after(80, lambda: self.sc_content_lbl.config(fg=C["white3"]))
        if not tracks:
            self.sc_list.insert("end", "  No results.")
            return
        fav_ids    = {t.get("id") for t in self._sc_favorites}
        queue_ids  = {t.get("id") for t in self._sc_stream_queue}
        playing_id = (getattr(self, "_sc_current_track", None) or {}).get("id")
        for i, t in enumerate(tracks):
            title      = (t.get("title") or "?")[:36]
            artist     = (t.get("user", {}).get("username") or "?")[:22]
            dur_ms     = t.get("duration", 0)
            dur_s      = dur_ms // 1000
            dur_str    = f"{dur_s // 60}:{dur_s % 60:02d}"
            plays      = t.get("playback_count") or 0
            plays_str  = f"{plays//1000}k" if plays >= 1000 else str(plays)
            genre      = (t.get("genre") or "")[:12]
            heart      = "♥" if t.get("id") in fav_ids   else " "
            queued     = "⊕" if t.get("id") in queue_ids  else " "
            playing    = "►" if t.get("id") == playing_id else " "
            genre_part = f"  [{genre}]" if genre else ""
            self.sc_list.insert(
                "end",
                f" {heart}{queued}{playing}{i+1:>3}.  {title:<36}  {artist:<22}  {dur_str}  ▸{plays_str}{genre_part}  ⋯"
            )
            row_bg = C["panel"] if i % 2 == 1 else C["bg"]
            if t.get("id") == playing_id:
                self.sc_list.itemconfig(i, fg=C["white"], bg=C["bg"])
            else:
                self.sc_list.itemconfig(i, bg=row_bg)

    def _sc_update_queue_lbl(self):
        n = len(self._sc_stream_queue)
        if n:
            self.sc_queue_lbl.config(text=f"{n} queued", fg=C["white2"])
        else:
            self.sc_queue_lbl.config(text="")

    def _sc_clear_queue(self):
        self._sc_stream_queue.clear()
        self._sc_update_queue_lbl()
        self.sc_np_lbl.config(text="  Queue cleared.")
        # Redraw list to remove ⊕ markers
        self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))

    def _sc_nav_favorites(self):
        self._sc_tracks = list(self._sc_favorites)
        self._sc_show_tracks(self._sc_tracks, f"FAVORITES  ({len(self._sc_favorites)})")

    def _sc_right_click(self, event):
        idx = self.sc_list.nearest(event.y)
        if idx < 0 or idx >= len(self._sc_tracks):
            return
        self.sc_list.selection_clear(0, "end")
        self.sc_list.selection_set(idx)
        track = self._sc_tracks[idx]
        fav_ids = {t.get("id") for t in self._sc_favorites}
        already_fav = track.get("id") in fav_ids
        self._sc_ctx.entryconfig("♥  Add to Favorites",      state="disabled" if already_fav else "normal")
        self._sc_ctx.entryconfig("✕  Remove from Favorites", state="normal" if already_fav else "disabled")
        try:
            self._sc_ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self._sc_ctx.grab_release()

    def _sc_ctx_play(self):
        idx = self.sc_list.curselection()
        if not idx:
            return
        track = self._sc_tracks[idx[0]]
        threading.Thread(target=lambda: self._sc_stream(track), daemon=True).start()

    def _sc_ctx_queue(self):
        idx = self.sc_list.curselection()
        if not idx or not self._sc_tracks:
            return
        track = self._sc_tracks[idx[0]]
        # Don't duplicate
        if track.get("id") not in {t.get("id") for t in self._sc_stream_queue}:
            self._sc_stream_queue.append(track)
            self._sc_update_queue_lbl()
            self.sc_np_lbl.config(text=f"  ⊕ Queued: {(track.get('title') or '')[:40]}")
            # Refresh list to show ⊕ marker
            self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
        else:
            self.sc_np_lbl.config(text="  Already in queue.")

    def _sc_ctx_favorite(self):
        idx = self.sc_list.curselection()
        if not idx:
            return
        track = self._sc_tracks[idx[0]]
        fav_ids = {t.get("id") for t in self._sc_favorites}
        if track.get("id") not in fav_ids:
            self._sc_favorites.append(track)
            self._save()
        self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
        self.sc_np_lbl.config(text=f"  ♥  Added: {(track.get('title') or '')[:40]}")

    def _sc_ctx_unfavorite(self):
        idx = self.sc_list.curselection()
        if not idx:
            return
        track = self._sc_tracks[idx[0]]
        self._sc_favorites = [t for t in self._sc_favorites if t.get("id") != track.get("id")]
        self._save()
        if self._sc_view == "favorites":
            self._sc_tracks = list(self._sc_favorites)
        self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
        self.sc_np_lbl.config(text=f"  Removed: {(track.get('title') or '')[:40]}")

    def _sc_kb_delete(self):
        """Delete key handler: remove from favorites (favorites view) or queue (any view)."""
        idx = self.sc_list.curselection()
        if not idx or not self._sc_tracks or idx[0] >= len(self._sc_tracks):
            return
        track = self._sc_tracks[idx[0]]
        if self._sc_view == "favorites":
            self._sc_ctx_unfavorite()
        else:
            # Remove from queue if queued
            tid = track.get("id")
            if tid in {t.get("id") for t in self._sc_stream_queue}:
                self._sc_stream_queue = [t for t in self._sc_stream_queue if t.get("id") != tid]
                self._sc_update_queue_lbl()
                self.sc_np_lbl.config(text=f"  Removed from queue: {(track.get('title') or '')[:40]}")
                self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))

    def _sc_skip(self, direction):
        """Skip forward (+1) or backward (-1) through _sc_tracks. Called by _next/_prev."""
        tracks = self._sc_tracks
        if not tracks:
            return
        current = getattr(self, "_sc_current_track", None)
        current_id = current.get("id") if current else None
        current_idx = next(
            (i for i, t in enumerate(tracks) if t.get("id") == current_id), -1
        )
        if direction == -1:
            # Prev: if more than 3s in, restart current track instead
            if self.engine.get_position() > 3 and current_idx >= 0:
                self.engine.seek(0)
                return
            next_idx = max(0, current_idx - 1)
        else:
            if self.shuffle and len(tracks) > 1:
                import random
                candidates = [i for i in range(len(tracks)) if i != current_idx]
                next_idx = random.choice(candidates)
            else:
                next_idx = current_idx + 1
                if next_idx >= len(tracks):
                    if self.repeat_mode == "all":
                        next_idx = 0
                    else:
                        return
        track = tracks[next_idx]
        threading.Thread(target=lambda t=track: self._sc_stream(t), daemon=True).start()
        try:
            self.sc_list.see(next_idx)
            self.sc_list.selection_clear(0, "end")
            self.sc_list.selection_set(next_idx)
        except Exception:
            pass

    def _sc_autoplay_next(self):
        """
        Called by _watch_end when a SoundCloud track finishes.
        Priority: manual queue → shuffle → next in list → repeat-all wraps → stop.
        Guard flag prevents double-firing from concurrent watchers.
        """
        # Guard: only fire once per track completion
        fired_token = getattr(self, "_sc_autoplay_fired_token", -1)
        current_token = getattr(self, "_sc_stream_token", 0)
        if fired_token == current_token:
            return
        self._sc_autoplay_fired_token = current_token

        # 0. Repeat one — replay the same track
        if self.repeat_mode == "one":
            t = getattr(self, "_sc_current_track", None)
            if t:
                threading.Thread(target=lambda: self._sc_stream(t), daemon=True).start()
            return

        # 1. Manual queue always wins
        if self._sc_stream_queue:
            next_track = self._sc_stream_queue.pop(0)
            self._sc_update_queue_lbl()
            # Refresh list to remove ⊕ marker
            self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
            threading.Thread(target=lambda t=next_track: self._sc_stream(t), daemon=True).start()
            return

        # 2. No list to advance through
        tracks = self._sc_tracks
        if not tracks:
            self._active_source = "none"
            self._set_source_badge("none")
            return

        current = getattr(self, "_sc_current_track", None)
        current_id = current.get("id") if current else None

        # Find current position in the visible list
        current_idx = next(
            (i for i, t in enumerate(tracks) if t.get("id") == current_id), -1
        )

        # 3. Shuffle — pick a random track that isn't the current one
        if self.shuffle and len(tracks) > 1:
            import random
            candidates = [i for i in range(len(tracks)) if i != current_idx]
            next_idx = random.choice(candidates)
            next_track = tracks[next_idx]
            threading.Thread(target=lambda t=next_track: self._sc_stream(t), daemon=True).start()
            return

        # 4. Advance to next track in list
        next_idx = current_idx + 1

        if next_idx < len(tracks):
            next_track = tracks[next_idx]
            threading.Thread(target=lambda t=next_track: self._sc_stream(t), daemon=True).start()
            # Scroll list to the upcoming track
            try:
                self.sc_list.see(next_idx)
                self.sc_list.selection_clear(0, "end")
                self.sc_list.selection_set(next_idx)
            except Exception:
                pass
            return

        # 5. End of list — wrap if repeat all, else stop
        if self.repeat_mode == "all" and tracks:
            next_track = tracks[0]
            threading.Thread(target=lambda t=next_track: self._sc_stream(t), daemon=True).start()
            try:
                self.sc_list.see(0)
                self.sc_list.selection_clear(0, "end")
                self.sc_list.selection_set(0)
            except Exception:
                pass
        else:
            self._active_source = "none"
            self._set_source_badge("none")
            self._sc_restore_np_bar()

    def _sc_ctx_save(self):
        """Download current track's temp file into the library Music folder."""
        idx = self.sc_list.curselection()
        if not idx or not self._sc_tracks:
            return
        track = self._sc_tracks[idx[0]]
        title  = (track.get("title") or "track").replace("/", "-").replace("\\", "-")
        artist = track.get("user", {}).get("username", "Unknown")
        self.sc_np_lbl.config(text="  ⬇ Fetching stream for save…")

        def _do():
            stream_url = self.sc_api.get_stream_url(track)
            if not stream_url:
                self.root.after(0, lambda: self.sc_np_lbl.config(text="  ⬇ Could not get stream URL."))
                return
            # Determine save folder — first watch_dir, or Music, or home
            dirs = self.settings.get("watch_dirs", [])
            save_dir = Path(dirs[0]) if dirs else Path.home() / "Music"
            save_dir.mkdir(parents=True, exist_ok=True)
            dest = save_dir / f"{artist} - {title}.mp3"
            counter = 1
            while dest.exists():
                dest = save_dir / f"{artist} - {title} ({counter}).mp3"
                counter += 1
            try:
                import urllib.request as _ur
                self.root.after(0, lambda: self.sc_np_lbl.config(text=f"  ⬇ Saving to {dest.name}…"))
                _ur.urlretrieve(stream_url, str(dest))
                # Write ID3 tags if mutagen available
                if MUTAGEN_AVAILABLE:
                    try:
                        from mutagen.id3 import ID3, TIT2, TPE1, TALB
                        tags = ID3()
                        tags["TIT2"] = TIT2(encoding=3, text=title)
                        tags["TPE1"] = TPE1(encoding=3, text=artist)
                        tags["TALB"] = TALB(encoding=3, text="SoundCloud")
                        tags.save(str(dest))
                    except Exception:
                        pass
                # Import into library
                self.root.after(0, lambda d=str(dest): (
                    self._import([d]),
                    self.sc_np_lbl.config(text=f"  ✓ Saved & imported: {dest.name}"),
                ))
            except Exception:
                self.root.after(0, lambda: self.sc_np_lbl.config(text=f"  ⬇ Error: {ex}"))

        threading.Thread(target=_do, daemon=True).start()

    def _sc_ctx_open(self):
        idx = self.sc_list.curselection()
        if not idx or not self._sc_tracks:
            return
        track = self._sc_tracks[idx[0]]
        url = track.get("permalink_url") or track.get("uri") or ""
        if url:
            import webbrowser
            webbrowser.open(url)

    def _sc_np_artist_click(self):
        """Clicking the artist label in the NP bar searches for that artist."""
        track = getattr(self, "_sc_current_track", None)
        if not track:
            return
        artist = track.get("user", {}).get("username", "")
        if not artist:
            return
        self.sc_search_var.set(artist)
        self._sc_nav("search")
        self._sc_do_search()

    def _stop_all_sources(self):
        """Stop all audio sources — Spotify, local engine, SoundCloud, YouTube."""
        self._active_source = "none"
        # Cancel any in-progress SC chunked download
        self._sc_stream_token = getattr(self, "_sc_stream_token", 0) + 1
        if not getattr(self, "_xfade_loading", False):
            self._xfade_fading_in = False
            if self._xfade_job:
                try:
                    self.root.after_cancel(self._xfade_job)
                except Exception:
                    pass
                self._xfade_job = None
        self._sp_mode = False
        self._sp_playing = False
        self._art_url_last = None
        try:
            threading.Thread(target=self.sp_api.pause, daemon=True).start()
        except Exception:
            pass
        self.engine.stop()

    def _sc_play_selected(self, event=None):
        sel = self.sc_list.curselection()
        if not sel or not self._sc_tracks:
            return
        idx = sel[0]
        # Sentinel row — trigger load more instead of playing
        if idx >= len(self._sc_tracks):
            if self._sc_can_load_more:
                self._sc_load_more()
            return
        track = self._sc_tracks[idx]
        threading.Thread(target=lambda: self._sc_stream(track), daemon=True).start()

    def _sc_stream(self, track):
        """Download stream fully then play — pygame holds a file lock so partial loads fail."""
        # Guard: if another stream call just started for the same track, bail out
        import threading as _th
        if not hasattr(self, "_sc_stream_lock"):
            self._sc_stream_lock = _th.Lock()
        track_id = track.get("id")
        with self._sc_stream_lock:
            last = getattr(self, "_sc_stream_last_id", None)
            if last == track_id:
                return
            self._sc_stream_last_id = track_id

        self.root.after(0, lambda: self.sc_np_lbl.config(text="  Resolving stream..."))

        # Clear guard so this track can be replayed again later
        self._sc_stream_last_id = None

        stream_url = self.sc_api.get_stream_url(track)

        if not stream_url and not SoundCloudAPI._cached_cid:
            self.root.after(0, lambda: self.sc_np_lbl.config(text="  Refreshing client ID..."))
            if self.sc_api.refresh_client_id():
                stream_url = self.sc_api.get_stream_url(track)

        if not stream_url:
            self.root.after(0, lambda: (
                self.sc_np_lbl.config(text="  — SOUNDCLOUD —"),
                messagebox.showwarning(
                    "OTERNOS // SOUNDCLOUD",
                    "Could not get stream URL.\n\nThe track may not be streamable, or SoundCloud\nhas changed their API. Try again in a moment.",
                ),
            ))
            return

        title  = track.get("title", "Unknown")
        artist = track.get("user", {}).get("username", "Unknown")
        dur_s  = track.get("duration", 0) // 1000

        # Cancellation token — incremented by _stop_all_sources or a new stream call
        self._sc_stream_token = getattr(self, "_sc_stream_token", 0) + 1
        _my_token = self._sc_stream_token

        def _cancelled():
            return getattr(self, "_sc_stream_token", 0) != _my_token

        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            tmp_path = tmp.name

            import urllib.request as _ur

            CHUNK = 256 * 1024

            req = _ur.Request(
                stream_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )

            with _ur.urlopen(req, timeout=20) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                written = 0
                last_pct = -1
                with open(tmp_path, "wb") as fout:
                    while True:
                        if _cancelled():
                            return
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        fout.write(chunk)
                        written += len(chunk)

                        if total > 0:
                            pct = min(99, int(written * 100 / total))
                            if pct >= last_pct + 5:
                                last_pct = pct
                                self.root.after(0, lambda p=pct: self.sc_np_lbl.config(
                                    text=f"  Buffering... {p}%"))
                        else:
                            mb = written / 1048576
                            self.root.after(0, lambda m=mb: self.sc_np_lbl.config(
                                text=f"  Buffering... {m:.1f} MB"))

            if _cancelled():
                return

            self.root.after(0, lambda: self.sc_np_lbl.config(text="  Buffering... 100%"))

            # ── Full file on disk — now safe to load ──────────────────────
            def _play():
                if _cancelled():
                    return
                # Restore token after _stop_all_sources increments it
                self._stop_all_sources()
                self._sc_stream_token = _my_token

                self._sc_current_track = track
                self._active_source = "soundcloud"
                self._sp_mode = False
                self._set_source_badge("soundcloud")
                if self.engine.load(tmp_path):
                    self._current_play_path = tmp_path
                    # Set duration BEFORE play() so the async reader doesn't race-overwrite it
                    self.engine.duration = float(dur_s)
                    self.engine.play()
                    self.wavevis.set_active(True)
                    self.btn_play.config(text="⏸")
                    self.status_lbl.config(text="[ PLAYING ]")
                    self.now_title.config(text=title[:50])
                    self.now_artist.config(text=artist)
                    self.now_album.config(text="SoundCloud")
                    self.lbl_cur.config(text="0:00")
                    self.lbl_tot.config(text=f"{dur_s // 60}:{dur_s % 60:02d}")
                    self._draw_prog(0)
                    self._sc_restore_np_bar()
                    self.sc_np_artist_btn.config(text=f"[ {artist[:20]} ▸ ]")
                    # Refresh list so ► marker moves to the new track
                    if self._sc_tracks:
                        self._sc_show_tracks(self._sc_tracks, self.sc_content_lbl.cget("text"))
                    art_url = track.get("artwork_url") or ""
                    if not art_url:
                        # Fall back to user avatar if track has no artwork
                        art_url = (track.get("user") or {}).get("avatar_url") or ""
                    if art_url:
                        self._set_album_art(art_url.replace("-large", "-t500x500"))
                    else:
                        # No artwork anywhere — clear to placeholder so previous art doesn't linger
                        self._art_url_last = None
                        self._draw_art_placeholder()
                    self._history_add({"title": title, "artist": artist, "album": "SoundCloud"}, source="soundcloud")
                    self._viz_last_real_bars = [0.0] * 48
                    self._viz_bars = [0.0] * 48
                    threading.Thread(target=lambda p=tmp_path: self._start_fft_file_decoder(p), daemon=True).start()
                    self._set_current_track_for_lyrics(artist, title)
                    self._start_lyric_ticker()
                    if getattr(self, "view", "") == "lyrics":
                        self._refresh_lyrics_view()
                    # ── End-of-track watcher ──────────────────────────────
                    _watch_token = _my_token
                    def _watch_end():
                        try:
                            import pygame as _pg
                            import time as _t
                            for _ in range(40):
                                if getattr(self, "_sc_stream_token", 0) != _watch_token:
                                    return
                                if _pg.mixer.music.get_busy():
                                    break
                                _t.sleep(0.1)
                            else:
                                return
                            while True:
                                if getattr(self, "_sc_stream_token", 0) != _watch_token:
                                    return
                                if not _pg.mixer.music.get_busy():
                                    # get_busy() is also False when paused — ignore that
                                    if self.engine.is_paused:
                                        _t.sleep(0.3)
                                        continue
                                    if (getattr(self, "_active_source", "") == "soundcloud"
                                            and getattr(self, "_sc_stream_token", 0) == _watch_token):
                                        self.root.after(0, self._sc_autoplay_next)
                                    return
                                _t.sleep(0.3)
                        except Exception:
                            pass
                    threading.Thread(target=_watch_end, daemon=True).start()
                else:
                    self.sc_np_lbl.config(text="  — load failed —")

            self.root.after(0, _play)

        except Exception as exc:
            err = str(exc)
            self.root.after(0, lambda: (
                self.sc_np_lbl.config(text="  Stream error."),
                messagebox.showwarning("OTERNOS // SOUNDCLOUD", f"Stream error:\n{err}"),
            ))

    def _build_youtube_view(self):
        self.yt_frame = tk.Frame(self.content, bg=C["bg"])

        # Header
        top = tk.Frame(self.yt_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="YOUTUBE", font=FMX, fg=C["white"], bg=C["bg"]).pack(
            side="left"
        )
        self.yt_status_lbl = tk.Label(
            top, text="", font=FMS, fg=C["white3"], bg=C["bg"]
        )
        self.yt_status_lbl.pack(side="left", padx=12)
        tk.Frame(self.yt_frame, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        # Search bar (named so we can hide it in SAVED view)
        sf = tk.Frame(self.yt_frame, bg=C["bg"])
        self.yt_search_frame = sf
        sf.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(
            sf, text="⌕", font=("Courier New", 11), fg=C["white3"], bg=C["bg"]
        ).pack(side="left", padx=(0, 6))
        self.yt_search_var = tk.StringVar()
        self.yt_search_entry = tk.Entry(
            sf,
            textvariable=self.yt_search_var,
            font=FM,
            bg=C["panel"],
            fg=C["white"],
            insertbackground=C["white"],
            relief="flat",
            bd=0,
            width=44,
        )
        self.yt_search_entry.pack(side="left", ipady=4)
        self.yt_search_entry.bind(
            "<Return>", lambda e: (self._yt_do_search(), "break")[1]
        )
        go = tk.Label(
            sf, text="GO", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=10
        )
        go.pack(side="left")
        go.bind("<Button-1>", lambda e: self._yt_do_search())
        go.bind("<Enter>", lambda e: go.config(fg=C["white"]))
        go.bind("<Leave>", lambda e: go.config(fg=C["white3"]))
        tk.Frame(self.yt_frame, bg=C["border"], height=1).pack(
            fill="x", padx=20, pady=(6, 0)
        )

        # Status / now-playing — pack bottom FIRST
        self.yt_np_lbl = tk.Label(
            self.yt_frame, text="", font=FMS, fg=C["white3"], bg=C["bg"], anchor="w"
        )
        self.yt_np_lbl.pack(side="bottom", fill="x", padx=20, pady=(0, 6))

        self.yt_content_lbl = tk.Label(
            self.yt_frame,
            text="Search for music above",
            font=FMS,
            fg=C["white3"],
            bg=C["bg"],
            anchor="w",
        )
        self.yt_content_lbl.pack(fill="x", padx=20, pady=(6, 2))

        # Loading bar + cancel button — hidden until a track is loading
        self._yt_load_bar_frame = tk.Frame(self.yt_frame, bg=C["bg"])
        self._yt_load_bar_frame.pack(fill="x", padx=20, pady=(0, 4))
        self._yt_load_canvas = tk.Canvas(
            self._yt_load_bar_frame, height=3, bg=C["panel"], highlightthickness=0
        )
        self._yt_load_canvas.pack(side="left", fill="x", expand=True)
        self._yt_cancel_btn = tk.Label(
            self._yt_load_bar_frame,
            text="✕ cancel",
            font=FMS,
            fg=C["white3"],
            bg=C["bg"],
            cursor="hand2",
            padx=8,
        )
        self._yt_cancel_btn.pack(side="right")
        self._yt_cancel_btn.bind("<Button-1>", lambda e: self._yt_cancel())
        self._yt_cancel_btn.bind(
            "<Enter>", lambda e: self._yt_cancel_btn.config(fg=C["red"])
        )
        self._yt_cancel_btn.bind(
            "<Leave>", lambda e: self._yt_cancel_btn.config(fg=C["white3"])
        )
        self._yt_load_bar_frame.pack_forget()  # hidden by default
        self._yt_load_anim_pos = 0.0
        self._yt_load_anim_job = None
        self._yt_cancelled = False
        self._yt_subview = "search"
        self._yt_dropdown = None

        # Canvas list — supports thumbnails
        lf = tk.Frame(self.yt_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        sb2 = tk.Scrollbar(
            lf, bg=C["panel"], troughcolor=C["bg"], width=6, relief="flat", bd=0
        )
        sb2.pack(side="right", fill="y")
        self.yt_list_cv = tk.Canvas(
            lf, bg=C["bg"], highlightthickness=0, yscrollcommand=sb2.set
        )
        self.yt_list_cv.pack(side="left", fill="both", expand=True)
        sb2.config(command=self.yt_list_cv.yview)
        self.yt_list_cv.bind(
            "<MouseWheel>",
            lambda e: self.yt_list_cv.yview_scroll(
                int(-1 * (e.delta / 120)) * 3, "units"
            ),
        )
        self.yt_list_cv.bind("<Double-Button-1>", self._yt_play_selected)
        self.yt_list_cv.bind("<Button-3>", self._yt_rclick)
        self.yt_list_cv.bind("<Button-1>", self._yt_list_click)
        self.yt_list_cv.bind("<Configure>", self._yt_list_resize)
        self._yt_row_height = 52
        self._yt_thumb_cache = {}
        self._yt_selected_idx = -1
        self._yt_list_width = 0
        # Keep yt_list as alias for legacy references (e.g. scroll routing)
        self.yt_list = self.yt_list_cv

    def _yt_refresh_view(self):
        if not self.yt_api.ytdlp_available():
            self.yt_status_lbl.config(
                text="yt-dlp not installed  —  run:  pip install yt-dlp", fg=C["red"]
            )
            self.yt_hint_lbl_ref = None
        else:
            self.yt_status_lbl.config(text="", fg=C["white3"])

    def _yt_cancel(self):
        """Cancel the current YouTube download."""
        self._yt_cancelled = True
        self._yt_load_stop()
        self.yt_content_lbl.config(text="Download cancelled.")

    def _yt_load_start(self):
        """Show and animate the YouTube loading bar."""
        self._yt_cancelled = False
        self._yt_load_bar_frame.pack(fill="x", padx=20, pady=(0, 4))
        self._yt_load_anim_pos = 0.0
        self._yt_load_anim_running = True
        self._yt_load_progress = -1  # -1 = pulse mode, 0-1 = real progress
        self._yt_animate_load()

    def _yt_set_load_progress(self, ratio):
        """Switch loading bar from pulse to real progress fill (0.0 - 1.0)."""
        self._yt_load_progress = max(0.0, min(1.0, ratio))
        self._yt_load_anim_running = False  # stop the pulse loop
        if self._yt_load_anim_job:
            self.root.after_cancel(self._yt_load_anim_job)
            self._yt_load_anim_job = None
        # Draw the real progress bar immediately
        w = self._yt_load_canvas.winfo_width() or 400
        fill_w = int(w * self._yt_load_progress)
        self._yt_load_canvas.delete("all")
        self._yt_load_canvas.create_rectangle(0, 0, w, 3, fill=C["panel"], outline="")
        self._yt_load_canvas.create_rectangle(
            0, 0, fill_w, 3, fill=C["white"], outline=""
        )

    def _yt_start_convert_pulse(self):
        """Animate a fast back-and-forth shimmer during ffmpeg conversion."""
        if self._yt_load_anim_job:
            self.root.after_cancel(self._yt_load_anim_job)
        self._yt_load_anim_running = True
        self._yt_load_anim_pos = 0.0
        self._yt_convert_dir = 1
        self._yt_animate_convert()

    def _yt_animate_convert(self):
        """Shimmer animation — faster back-and-forth to signal active conversion."""
        if not getattr(self, "_yt_load_anim_running", False):
            return
        w = self._yt_load_canvas.winfo_width() or 400
        # Bouncing fill that goes 0→100%→0 repeatedly
        pos = self._yt_load_anim_pos
        fill_w = int(w * pos)
        self._yt_load_canvas.delete("all")
        self._yt_load_canvas.create_rectangle(0, 0, w, 3, fill=C["panel"], outline="")
        self._yt_load_canvas.create_rectangle(
            0, 0, fill_w, 3, fill=C["white3"], outline=""
        )
        # Small bright leading edge
        edge = min(w, fill_w + 6)
        self._yt_load_canvas.create_rectangle(
            fill_w, 0, edge, 3, fill=C["white"], outline=""
        )
        # Advance position
        self._yt_load_anim_pos += 0.04 * self._yt_convert_dir
        if self._yt_load_anim_pos >= 1.0:
            self._yt_load_anim_pos = 1.0
            self._yt_convert_dir = -1
        elif self._yt_load_anim_pos <= 0.0:
            self._yt_load_anim_pos = 0.0
            self._yt_convert_dir = 1
        self._yt_load_anim_job = self.root.after(25, self._yt_animate_convert)

    def _yt_load_stop(self):
        """Hide the YouTube loading bar."""
        self._yt_load_anim_running = False
        if self._yt_load_anim_job:
            self.root.after_cancel(self._yt_load_anim_job)
            self._yt_load_anim_job = None
        self._yt_load_bar_frame.pack_forget()

    def _yt_animate_load(self):
        """Animate a sliding pulse on the loading bar."""
        if not getattr(self, "_yt_load_anim_running", False):
            return
        w = self._yt_load_canvas.winfo_width() or 400
        bar_w = int(w * 0.35)
        x1 = int(self._yt_load_anim_pos * (w + bar_w)) - bar_w
        x2 = x1 + bar_w
        self._yt_load_canvas.delete("all")
        # Background track
        self._yt_load_canvas.create_rectangle(0, 0, w, 3, fill=C["panel"], outline="")
        # Glowing pulse bar
        self._yt_load_canvas.create_rectangle(
            max(0, x1), 0, min(w, x2), 3, fill=C["white"], outline=""
        )
        self._yt_load_anim_pos += 0.018
        if self._yt_load_anim_pos > 1.0:
            self._yt_load_anim_pos = 0.0
        self._yt_load_anim_job = self.root.after(30, self._yt_animate_load)

    def _yt_do_search(self):
        q = self.yt_search_var.get().strip()
        if not q:
            return
        if not self.yt_api.ytdlp_available():
            self.yt_content_lbl.config(
                text="yt-dlp not installed  —  run:  pip install yt-dlp"
            )
            return
        self.yt_content_lbl.config(text="Searching ...")
        self._yt_clear_list()
        self._yt_tracks = []

        def _fetch():
            tracks = self.yt_api.search(q, max_results=50)

            def _show():
                self._yt_tracks = tracks

                if not tracks:
                    self.yt_content_lbl.config(
                        text="No results — try updating yt-dlp:  pip install -U yt-dlp"
                    )
                    self._yt_clear_list()
                    return
                self.yt_content_lbl.config(
                    text=f"{len(tracks)} results  —  double-click to play"
                )
                self._yt_tracks = tracks
                self._yt_render_list()
                # Kick off thumbnail fetches
                for i, t in enumerate(tracks):
                    vid_id = t.get("id", "")
                    if vid_id:
                        url = f"https://i.ytimg.com/vi/{vid_id}/default.jpg"
                        threading.Thread(
                            target=self._yt_fetch_thumb, args=(i, url), daemon=True
                        ).start()

            self.root.after(0, _show)

        threading.Thread(target=_fetch, daemon=True).start()

    def _yt_play_selected(self, event=None):
        # If triggered by a double-click event, recalculate idx from position
        if event is not None:
            canvas_y = self.yt_list_cv.canvasy(event.y)
            idx = int(canvas_y // self._yt_row_height)
            if 0 <= idx < len(self._yt_tracks):
                self._yt_selected_idx = idx
        idx = self._yt_selected_idx
        if idx < 0 or not self._yt_tracks or idx >= len(self._yt_tracks):
            return
        track = self._yt_tracks[idx]
        # Cancel any in-progress download before starting a new one
        self._yt_cancelled = True
        self._yt_load_stop()

        def _start():
            import time as _t

            _t.sleep(0.15)  # let previous thread see the cancel flag
            self._yt_cancelled = False
            self._yt_stream(track)

        threading.Thread(target=_start, daemon=True).start()

    def _yt_play_track(self, track):
        """Cancel any current download then play a track."""
        self._yt_cancelled = True
        self._yt_load_stop()

        def _start():
            import time as _t

            _t.sleep(0.15)
            self._yt_cancelled = False
            self._yt_stream(track)

        threading.Thread(target=_start, daemon=True).start()

    def _yt_list_click(self, event):
        # Convert canvas y to scrolled y
        canvas_y = self.yt_list_cv.canvasy(event.y)
        idx = int(canvas_y // self._yt_row_height)
        if 0 <= idx < len(self._yt_tracks):
            self._yt_selected_idx = idx
            self._yt_render_list()

    def _yt_list_resize(self, event):
        self._yt_list_width = event.width
        self._yt_render_list()

    def _yt_clear_list(self):
        self.yt_list_cv.delete("all")
        self.yt_list_cv.configure(scrollregion=(0, 0, 100, 40))
        self._yt_thumb_cache = {}
        self._yt_selected_idx = -1

    def _yt_render_list(self):
        cv = self.yt_list_cv
        cv.delete("all")
        if not self._yt_tracks:
            cv.create_text(
                20, 20, text="No results.", anchor="nw", font=FM, fill=C["white3"]
            )
            cv.configure(scrollregion=(0, 0, 100, 40))
            return
        RH = self._yt_row_height
        W = max(self._yt_list_width, cv.winfo_width(), 400)
        cv.configure(scrollregion=(0, 0, W, RH * len(self._yt_tracks)))
        for i, t in enumerate(self._yt_tracks):
            self._yt_draw_row(i, t, W)

    def _yt_draw_row(self, i, t, W=None):
        cv = self.yt_list_cv
        RH = self._yt_row_height
        if W is None:
            W = max(self._yt_list_width, cv.winfo_width(), 400)
        y0 = i * RH
        y1 = y0 + RH
        tag = f"ytrow{i}"
        cv.delete(tag)
        bg = (
            C["select"]
            if i == self._yt_selected_idx
            else (C["panel2"] if i % 2 == 0 else C["bg"])
        )
        cv.create_rectangle(0, y0, W, y1, fill=bg, outline="", tags=tag)
        TH = RH - 8
        # Thumbnail placeholder
        cv.create_rectangle(
            4, y0 + 4, 4 + TH, y1 - 4, fill=C["panel"], outline="", tags=tag
        )
        if i in self._yt_thumb_cache:
            cv.create_image(
                4, y0 + 4, image=self._yt_thumb_cache[i], anchor="nw", tags=tag
            )
        else:
            cv.create_text(
                4 + TH // 2,
                y0 + RH // 2,
                text="▶",
                font=("Courier New", 10),
                fill=C["white3"],
                anchor="center",
                tags=tag,
            )
        # Save star button (right side)
        vid_id = t.get("id", "")
        is_saved = self._yt_is_saved(vid_id)
        star_x = W - 24
        star_col = "#f0c040" if is_saved else C["white3"]
        star_tag = f"ytstar{i}"
        cv.delete(star_tag)
        cv.create_text(
            star_x,
            y0 + RH // 2,
            text="★",
            font=("Courier New", 13),
            fill=star_col,
            anchor="center",
            tags=(tag, star_tag),
        )
        cv.tag_bind(
            star_tag, "<Button-1>", lambda e, tr=t, idx=i: self._yt_toggle_save(tr, idx)
        )
        cv.tag_bind(
            star_tag,
            "<Enter>",
            lambda e, st=star_tag: cv.itemconfig(st, fill="#f0c040"),
        )
        cv.tag_bind(
            star_tag,
            "<Leave>",
            lambda e, st=star_tag, sv=is_saved: cv.itemconfig(
                st, fill="#f0c040" if sv else C["white3"]
            ),
        )
        # Title and channel (leave room for star)
        title = (t.get("title") or "Unknown")[:58]
        channel = (t.get("channel") or "")[:35]
        dur = int(t.get("duration") or 0)
        dur_str = f"{dur // 60}:{dur % 60:02d}" if dur else ""
        tx = 4 + TH + 8
        cv.create_text(
            tx,
            y0 + RH // 2 - 8,
            text=title,
            font=("Courier New", 9, "bold"),
            fill=C["white"],
            anchor="w",
            tags=tag,
        )
        sub = f"{channel}  {dur_str}".strip()
        cv.create_text(
            tx,
            y0 + RH // 2 + 8,
            text=sub,
            font=("Courier New", 8),
            fill=C["white3"],
            anchor="w",
            tags=tag,
        )
        cv.create_line(0, y1 - 1, W, y1 - 1, fill=C["border"], tags=tag)

    def _yt_toggle_save(self, track, idx):
        vid_id = track.get("id", "")
        if self._yt_is_saved(vid_id):
            self._yt_unsave_track(vid_id)
        else:
            self._yt_save_track(track)
        # Redraw just this row to update star colour
        W = max(self._yt_list_width, self.yt_list_cv.winfo_width(), 400)
        self._yt_draw_row(idx, track, W)

    def _yt_fetch_thumb(self, idx, url):
        try:
            import urllib.request as _ur
            import tempfile

            data = _ur.urlopen(url, timeout=6).read()
            suffix = ".png" if b"PNG" in data[:8] else ".jpg"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(data)
            tmp.close()
            self.root.after(0, lambda p=tmp.name, i=idx: self._yt_load_thumb(i, p))
        except Exception:
            pass

    def _yt_load_thumb(self, idx, path):
        try:
            import tkinter as _tk

            RH = self._yt_row_height - 8
            try:
                img = _tk.PhotoImage(file=path)
                iw, ih = img.width(), img.height()
                factor = max(1, max(iw, ih) // RH)
                img = img.subsample(factor, factor)
            except Exception:
                from PIL import Image, ImageTk

                img = Image.open(path).resize((RH, RH))
                img = ImageTk.PhotoImage(img)
            self._yt_thumb_cache[idx] = img
            if self._yt_tracks:
                W = max(self._yt_list_width, self.yt_list_cv.winfo_width(), 400)
                self._yt_draw_row(idx, self._yt_tracks[idx], W)
        except Exception:
            pass
        finally:
            try:
                import os

                os.unlink(path)
            except Exception:
                pass

    def _yt_rclick(self, event):
        canvas_y = self.yt_list_cv.canvasy(event.y)
        idx = int(canvas_y // self._yt_row_height)
        if idx < 0 or idx >= len(self._yt_tracks):
            return
        track = self._yt_tracks[idx]
        menu = tk.Menu(
            self.root,
            bg=C["panel"],
            fg=C["white"],
            activebackground=C["select2"],
            activeforeground=C["white"],
            font=FM,
            tearoff=0,
            bd=0,
            relief="flat",
        )
        menu.add_command(label="▶ Play", command=lambda t=track: self._yt_play_track(t))
        menu.add_separator()
        menu.add_command(
            label="Open in browser",
            command=lambda: webbrowser.open(
                f"https://www.youtube.com/watch?v={track.get('id', '')}"
            ),
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _yt_stream(self, track):
        vid_id = track.get("id", "")
        title = track.get("title", "Unknown")
        channel = track.get("channel", "Unknown")
        dur_s = int(track.get("duration") or 0)
        if not vid_id:
            return

        self.root.after(0, self._yt_load_start)

        try:
            # Check cache for any previously downloaded format
            cached_mp3 = YT_CACHE / f"{vid_id}.mp3"
            cached_m4a = YT_CACHE / f"{vid_id}.m4a"

            if cached_mp3.exists():
                self.root.after(
                    0,
                    lambda: self.yt_content_lbl.config(
                        text=f"Loading (cached): {title[:50]} ..."
                    ),
                )
                out_file = str(cached_mp3)

            elif cached_m4a.exists():
                self.root.after(
                    0,
                    lambda: self.yt_content_lbl.config(
                        text=f"Loading (cached): {title[:50]} ..."
                    ),
                )
                out_file = str(cached_m4a)

            else:
                # Download m4a directly — no ffmpeg needed at all
                self.root.after(
                    0,
                    lambda: self.yt_content_lbl.config(
                        text=f"Loading: {title[:60]} ..."
                    ),
                )

                import yt_dlp
                import tempfile as _tf
                import shutil

                tmp_dir = _tf.mkdtemp()

                def _progress_hook(d):
                    if d.get("status") == "downloading":
                        downloaded = d.get("downloaded_bytes") or 0
                        total = (
                            d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                        )
                        if total > 0:
                            pct = int(downloaded / total * 100)
                            self.root.after(
                                0,
                                lambda p=pct: (
                                    self.yt_content_lbl.config(
                                        text=f"Downloading: {title[:40]} ... {p}%"
                                    ),
                                    self._yt_set_load_progress(p / 100),
                                ),
                            )

                import sys as _sys
                import os as _os
                import shutil as _sh

                _ffmpeg_dir = ""
                _ff_candidates = []
                if getattr(_sys, "frozen", False):
                    _ff_candidates.append(_os.path.dirname(_sys.executable))
                if hasattr(_sys, "_MEIPASS"):
                    _ff_candidates.append(_sys._MEIPASS)
                try:
                    _ff_candidates.append(_os.path.dirname(_os.path.abspath(__file__)))
                except Exception:
                    pass
                _ff_candidates += [
                    r"C:\\ffmpeg\\bin",
                    r"C:\\Program Files\\ffmpeg\\bin",
                    r"C:\\Program Files (x86)\\ffmpeg\\bin",
                    _os.path.join(
                        _os.environ.get("LOCALAPPDATA", ""), "Programs", "ffmpeg", "bin"
                    ),
                    _os.path.join(_os.environ.get("USERPROFILE", ""), "ffmpeg", "bin"),
                ]
                for _d in _ff_candidates:
                    if _d and _os.path.isfile(_os.path.join(_d, "ffmpeg.exe")):
                        _ffmpeg_dir = _d
                        break
                if not _ffmpeg_dir:
                    _path_ff = _sh.which("ffmpeg")
                    if _path_ff:
                        _ffmpeg_dir = _os.path.dirname(_path_ff)
                if not _ffmpeg_dir:
                    self.root.after(
                        0,
                        lambda: self.yt_content_lbl.config(
                            text="ffmpeg not found — run:  winget install ffmpeg"
                        ),
                    )
                    self.root.after(0, self._yt_load_stop)
                    return
                ydl_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "format": "bestaudio/best",
                    "outtmpl": str(Path(tmp_dir) / f"{vid_id}.%(ext)s"),
                    "progress_hooks": [_progress_hook],
                    "ffmpeg_location": _ffmpeg_dir,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                }

                import datetime

                logpath = Path.home() / "voidplayer_error.log"
                try:
                    with open(logpath, "a", encoding="utf-8") as _lf:
                        _lf.write(
                            f"[{datetime.datetime.now()}] ffmpeg_dir={_ffmpeg_dir!r} candidates={_ff_candidates}\n"
                        )
                except Exception:
                    pass

                # ── Age-restriction bypass strategy ────────────────────────
                # 1. tv_embedded / web_embedded player clients — bypass age gate
                #    without any login (YouTube's TV/embedded players don't enforce it)
                # 2. User-supplied cookies.txt if provided in Settings
                # 3. Standard no-cookies attempt (works for most normal videos)
                info = None
                _yt_cookies_path = self.settings.get("yt_cookies_path", "").strip()

                def _try_download(extra_opts):
                    opts = dict(ydl_opts)
                    opts.update(extra_opts)
                    opts["quiet"] = True
                    opts["no_warnings"] = True
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        return ydl.extract_info(
                            f"https://www.youtube.com/watch?v={vid_id}", download=True
                        )

                # Pass 1: tv_embedded client — bypasses age gate without login
                for _client in ("tv_embedded", "web_embedded"):
                    try:
                        info = _try_download(
                            {
                                "extractor_args": {
                                    "youtube": {"player_client": [_client]}
                                }
                            }
                        )
                        if info:
                            break
                    except Exception:
                        pass

                # Pass 2: cookies.txt if user provided one
                if (
                    info is None
                    and _yt_cookies_path
                    and Path(_yt_cookies_path).exists()
                ):
                    try:
                        info = _try_download({"cookiefile": _yt_cookies_path})
                    except Exception:
                        pass

                # Pass 3: standard download (no special options)
                if info is None:
                    try:
                        info = _try_download({})
                    except Exception as _e:
                        err_str = str(_e).lower()
                        if (
                            "sign in" in err_str
                            or "age" in err_str
                            or "inappropriate" in err_str
                        ):
                            raise Exception(
                                "Age-restricted video — bypass failed.\n\n"
                                "To fix: Settings → YouTube → cookies.txt → BROWSE\n"
                                "Export cookies.txt from the 'Get cookies.txt LOCALLY' browser extension\n"
                                "while logged into YouTube."
                            )
                        raise

                if getattr(self, "_yt_cancelled", False):
                    return

                if not dur_s:
                    dur_s = int((info or {}).get("duration") or 0)

                # Find the output file (mp3 if ffmpeg ran, otherwise whatever yt-dlp saved)
                files = list(Path(tmp_dir).iterdir())
                if not files:
                    raise FileNotFoundError("No audio file downloaded")
                # Prefer mp3 if it exists
                mp3_files = [f for f in files if f.suffix.lower() == ".mp3"]
                tmp_file = mp3_files[0] if mp3_files else files[0]
                actual_ext = tmp_file.suffix.lower()

                try:
                    with open(logpath, "a", encoding="utf-8") as _lf:
                        _lf.write(
                            f"[{datetime.datetime.now()}] Final ext={actual_ext} size={tmp_file.stat().st_size}\n"
                        )
                except Exception:
                    pass

                dest = YT_CACHE / f"{vid_id}{actual_ext}"
                shutil.move(str(tmp_file), str(dest))
                out_file = str(dest)

            def _play(f=out_file, d=dur_s):
                self._yt_load_stop()
                self._stop_all_sources()
                self._yt_current_track = track  # remember for repeat
                self._active_source = "youtube"
                self._sp_mode = False
                self._set_source_badge("youtube")
                ok = self.engine.load(f)
                if ok:
                    self._current_play_path = f
                    if d > 0:
                        self.engine.duration = float(d)
                    else:
                        d = self.engine.duration
                    self.engine.set_volume(self.engine.volume)
                    self.engine.play()
                    self.wavevis.set_active(True)
                    self._set_logo_playing(True)
                    self.btn_play.config(text="⏸")
                    self.status_lbl.config(text="[ PLAYING ]")
                    self.now_title.config(text=title[:50])
                    self.now_artist.config(text=channel)
                    self.now_album.config(text="YouTube")
                    self.lbl_cur.config(text="0:00")
                    self.lbl_tot.config(text=self._fmt(d))
                    self._draw_prog(0)
                    self.yt_np_lbl.config(text=f"▶  {title[:50]}  —  {channel}")
                    self.yt_content_lbl.config(text=f"NOW PLAYING: {title[:60]}")
                    self.current_idx = -1
                    # Set YouTube thumbnail — must come after _art_url_last was
                    # cleared by _stop_all_sources so the dedup guard doesn't skip it
                    thumb_url = track.get("thumbnail") or track.get("thumb") or ""
                    if thumb_url:
                        self._set_album_art(thumb_url)
                    self._history_add(
                        {"title": title, "artist": channel, "album": "YouTube"},
                        source="youtube",
                    )
                    # Sync visualizer — reset state and start FFT decoder like _do_load_track does
                    self._viz_last_real_bars = [0.0] * 48
                    self._viz_bars = [0.0] * 48
                    threading.Thread(
                        target=lambda p=f: self._start_fft_file_decoder(p), daemon=True
                    ).start()
                    # Fetch lyrics + start ticker — same as _do_load_track
                    self._set_current_track_for_lyrics(channel, title)
                    self._start_lyric_ticker()
                    if getattr(self, "view", "") == "lyrics":
                        self._refresh_lyrics_view()
                else:
                    # MCI can't play this format — user needs K-Lite Codec Pack
                    self.yt_content_lbl.config(
                        text="Playback error — install K-Lite Codec Pack to play YouTube audio: codecguide.com/download_kl.htm"
                    )

            if not getattr(self, "_yt_cancelled", False):
                self.root.after(0, _play)

        except ImportError:
            self.root.after(0, self._yt_load_stop)
            self.root.after(
                0,
                lambda: self.yt_content_lbl.config(
                    text="yt-dlp not installed  —  run: pip install yt-dlp"
                ),
            )
        except Exception as ex:
            import traceback
            import datetime

            err = str(ex)
            tb = traceback.format_exc()
            try:
                logpath = Path.home() / "voidplayer_error.log"
                with open(logpath, "a", encoding="utf-8") as _lf:
                    _lf.write("\n[" + str(datetime.datetime.now()) + "]\n" + tb + "\n")
            except Exception:
                pass
            self.root.after(0, self._yt_load_stop)
            self.root.after(
                0, lambda: self.yt_content_lbl.config(text=f"Error: {err[:120]}")
            )

    # ── CLAUDE DEBUG VIEW ─────────────────
    # ── STREAM VIEW (YouTube + SoundCloud combined) ──
    def _build_stream_view(self):
        self.stream_frame = tk.Frame(self.content, bg=C["bg"])
        self._stream_source = "youtube"  # active sub-source

        # Header
        top = tk.Frame(self.stream_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="STREAM", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        tk.Frame(self.stream_frame, bg=C["border2"], height=1).pack(fill="x", pady=(6, 0))
        tk.Frame(self.stream_frame, bg=C["border"], height=1).pack(fill="x")

        # Sub-source switcher
        sw = tk.Frame(self.stream_frame, bg=C["bg"])
        sw.pack(fill="x", padx=20, pady=(8, 0))
        self._stream_yt_btn  = tk.Label(sw, text="[ YOUTUBE ]",    font=FM, fg=C["white"],  bg=C["bg"], cursor="hand2", padx=4)
        self._stream_sc_btn  = tk.Label(sw, text="[ SOUNDCLOUD ]", font=FM, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=4)
        self._stream_dz_btn  = tk.Label(sw, text="[ DEEZER ]",     font=FM, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=4)
        self._stream_ia_btn  = tk.Label(sw, text="[ ARCHIVE ]",    font=FM, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=4)
        self._stream_bc_btn  = tk.Label(sw, text="[ BANDCAMP ]",   font=FM, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=4)
        self._stream_yt_btn.pack(side="left")
        self._stream_sc_btn.pack(side="left", padx=(8, 0))
        self._stream_dz_btn.pack(side="left", padx=(8, 0))
        self._stream_ia_btn.pack(side="left", padx=(8, 0))
        self._stream_bc_btn.pack(side="left", padx=(8, 0))
        tk.Frame(self.stream_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))

        def _sw_yt(e=None):  self._stream_set_source("youtube")
        def _sw_sc(e=None):  self._stream_set_source("soundcloud")
        def _sw_dz(e=None):  self._stream_set_source("deezer")
        def _sw_ia(e=None):  self._stream_set_source("archive")
        def _sw_bc(e=None):  self._stream_set_source("bandcamp")

        self._stream_yt_btn.bind("<Button-1>", _sw_yt)
        self._stream_sc_btn.bind("<Button-1>", _sw_sc)
        self._stream_dz_btn.bind("<Button-1>", _sw_dz)
        self._stream_ia_btn.bind("<Button-1>", _sw_ia)
        self._stream_bc_btn.bind("<Button-1>", _sw_bc)

        self._stream_refresh()

    def _stream_set_source(self, src):
        self._stream_source = src
        self._stream_refresh()

    def _stream_btn_leave(self, w):
        """Restore dim colour on leave unless this button is the active source."""
        src = getattr(self, "_stream_source", "youtube")
        mapping = {
            "youtube":    "_stream_yt_btn",
            "soundcloud": "_stream_sc_btn",
            "deezer":     "_stream_dz_btn",
            "archive":    "_stream_ia_btn",
            "bandcamp":   "_stream_bc_btn",
        }
        is_active = hasattr(self, mapping.get(src, "")) and getattr(self, mapping[src], None) is w
        w.config(fg=C["white"] if is_active else C["white3"])

    def _stream_refresh(self):
        src = getattr(self, "_stream_source", "youtube")
        # Update switcher button colours
        btn_map = {
            "youtube":    "_stream_yt_btn",
            "soundcloud": "_stream_sc_btn",
            "deezer":     "_stream_dz_btn",
            "archive":    "_stream_ia_btn",
            "bandcamp":   "_stream_bc_btn",
        }
        for key, attr in btn_map.items():
            if hasattr(self, attr):
                getattr(self, attr).config(fg=C["white"] if key == src else C["white3"])
        # Hide all sub-frames
        for attr in ("yt_frame", "sc_frame", "dz_frame", "ia_frame", "bc_frame"):
            if hasattr(self, attr):
                try:
                    getattr(self, attr).pack_forget()
                except Exception:
                    pass
        if getattr(self, "view", None) != "stream":
            return
        if src == "youtube" and hasattr(self, "yt_frame"):
            self.yt_frame.pack(fill="both", expand=True)
            self._yt_refresh_view()
        elif src == "soundcloud" and hasattr(self, "sc_frame"):
            self.sc_frame.pack(fill="both", expand=True)
            self._sc_refresh_view()
        elif src == "deezer" and hasattr(self, "dz_frame"):
            self.dz_frame.pack(fill="both", expand=True)
            self._dz_refresh_view()
        elif src == "archive" and hasattr(self, "ia_frame"):
            self.ia_frame.pack(fill="both", expand=True)
            self._ia_refresh_view()
        elif src == "bandcamp" and hasattr(self, "bc_frame"):
            self.bc_frame.pack(fill="both", expand=True)
            self._bc_refresh_view()

    # ══════════════════════════════════════════════════════
    #  DEEZER VIEW
    # ══════════════════════════════════════════════════════
    def _build_deezer_view(self):
        self.dz_frame = tk.Frame(self.content, bg=C["bg"])

        top = tk.Frame(self.dz_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="DEEZER", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self.dz_status_lbl = tk.Label(top, text="[ 30s PREVIEWS ]", font=FMS, fg=C["white2"], bg=C["bg"])
        self.dz_status_lbl.pack(side="left", padx=12)
        tk.Frame(self.dz_frame, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        # Nav
        nav = tk.Frame(self.dz_frame, bg=C["bg"])
        nav.pack(fill="x", padx=20, pady=(6, 0))
        self._dz_nav_btns = {}
        for label, key in [("SEARCH", "search"), ("CHARTS", "chart")]:
            b = tk.Label(nav, text=label, font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=10)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self._dz_nav(k))
            b.bind("<Enter>", lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=C["white3"]))
            self._dz_nav_btns[key] = b
        self._dz_nav_btns["search"].config(fg=C["white"])

        # Search bar
        self.dz_search_frame = tk.Frame(self.dz_frame, bg=C["bg"])
        self.dz_search_frame.pack(fill="x", pady=(4, 0))
        tk.Label(self.dz_search_frame, text="⌕", font=("Courier New", 12), fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(20, 4))
        self.dz_search_var = tk.StringVar()
        dz_entry = tk.Entry(self.dz_search_frame, textvariable=self.dz_search_var,
                            font=FM, bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                            relief="flat", bd=0, width=40)
        dz_entry.pack(side="left", ipady=4)
        dz_entry.bind("<Return>", lambda e: self._dz_do_search())
        dz_go = tk.Label(self.dz_search_frame, text="[GO]", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=8)
        dz_go.pack(side="left")
        dz_go.bind("<Button-1>", lambda e: self._dz_do_search())
        dz_go.bind("<Enter>", lambda e: dz_go.config(fg=C["white"]))
        dz_go.bind("<Leave>", lambda e: dz_go.config(fg=C["white3"]))

        tk.Frame(self.dz_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))
        self.dz_content_lbl = tk.Label(self.dz_frame, text="Search for tracks above",
                                        font=FMS, fg=C["white3"], bg=C["bg"], anchor="w")
        self.dz_content_lbl.pack(fill="x", padx=20, pady=(6, 2))

        lf = tk.Frame(self.dz_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"], width=8, relief="flat", bd=0)
        sb.pack(side="right", fill="y")
        self.dz_list = tk.Listbox(lf, bg=C["bg"], fg=C["white2"],
                                   selectbackground=C["select"], selectforeground=C["white"],
                                   font=FM, relief="flat", bd=0, activestyle="none",
                                   yscrollcommand=sb.set,
                                   highlightthickness=1, highlightcolor=C["border"],
                                   highlightbackground=C["border"])
        self.dz_list.pack(fill="both", expand=True)
        sb.config(command=self.dz_list.yview)
        self.dz_list.bind("<Double-Button-1>", self._dz_play_selected)
        self.dz_list.bind("<MouseWheel>", lambda e: self._scroller.scroll(self.dz_list, e.delta))
        self.dz_list.bind("<Button-3>", self._dz_rclick)

        self._dz_ctx = tk.Menu(self.dz_frame, tearoff=0, bg=C["panel"], fg=C["white"],
                                activebackground=C["select2"], activeforeground=C["glow"],
                                font=FMS, bd=0, relief="flat")
        self._dz_ctx.add_command(label="▶  Play preview", command=self._dz_ctx_play)

        np = tk.Frame(self.dz_frame, bg=C["panel"], height=28)
        np.pack(fill="x")
        np.pack_propagate(False)
        self.dz_np_lbl = tk.Label(np, text="— DEEZER —", font=("Courier New", 8), fg=C["white3"], bg=C["panel"])
        self.dz_np_lbl.pack(side="left", padx=16)

    def _dz_nav(self, key):
        self._dz_view = key
        for k, b in self._dz_nav_btns.items():
            b.config(fg=C["white"] if k == key else C["white3"])
        if key == "search":
            self.dz_search_frame.pack(fill="x", pady=(4, 0))
        else:
            self.dz_search_frame.pack_forget()
        self._dz_refresh_view()

    def _dz_refresh_view(self):
        view = getattr(self, "_dz_view", "search")
        if view == "chart" and not self._dz_tracks:
            self.dz_content_lbl.config(text="Loading chart…")
            threading.Thread(target=self._dz_load_chart, daemon=True).start()
        elif view == "search":
            self.dz_content_lbl.config(text="Search for tracks above" if not self._dz_tracks else f"{len(self._dz_tracks)} results")
        self._dz_populate()

    def _dz_load_chart(self):
        tracks = self.dz_api.chart(50)
        self._dz_tracks = tracks
        self.root.after(0, lambda: (
            self.dz_content_lbl.config(text=f"{len(tracks)} tracks"),
            self._dz_populate(),
        ))

    def _dz_do_search(self):
        q = self.dz_search_var.get().strip()
        if not q:
            return
        self.dz_content_lbl.config(text="Searching…")
        self.dz_list.delete(0, "end")
        self._dz_tracks = []
        threading.Thread(target=lambda: self._dz_run_search(q), daemon=True).start()

    def _dz_run_search(self, q):
        tracks = self.dz_api.search(q, 50)
        self._dz_tracks = tracks
        self.root.after(0, lambda: (
            self.dz_content_lbl.config(text=f"{len(tracks)} results" if tracks else "No results."),
            self._dz_populate(),
        ))

    def _dz_populate(self):
        self.dz_list.delete(0, "end")
        for t in self._dz_tracks:
            artist = (t.get("artist") or {}).get("name", "") or t.get("artist_name", "")
            title  = t.get("title", t.get("title_short", ""))
            dur    = t.get("duration", 0)
            dur_s  = f"{dur//60}:{dur%60:02d}" if dur else ""
            preview = t.get("preview", "")
            flag   = " ▸" if preview else " ✕"
            self.dz_list.insert("end", f"  {title}  —  {artist}  [{dur_s}]{flag}")

    def _dz_play_selected(self, event=None):
        sel = self.dz_list.curselection()
        if not sel or not self._dz_tracks:
            return
        track = self._dz_tracks[sel[0]]
        threading.Thread(target=lambda: self._dz_stream(track), daemon=True).start()

    def _dz_rclick(self, event):
        idx = self.dz_list.nearest(event.y)
        if idx >= 0:
            self.dz_list.selection_clear(0, "end")
            self.dz_list.selection_set(idx)
        self._dz_ctx.tk_popup(event.x_root, event.y_root)

    def _dz_ctx_play(self):
        sel = self.dz_list.curselection()
        if sel and self._dz_tracks:
            threading.Thread(target=lambda: self._dz_stream(self._dz_tracks[sel[0]]), daemon=True).start()

    def _dz_stream(self, track):
        preview_url = track.get("preview", "")
        if not preview_url:
            self.root.after(0, lambda: self.dz_np_lbl.config(text="  No preview available for this track."))
            return
        artist  = (track.get("artist") or {}).get("name", "") or track.get("artist_name", "Unknown")
        title   = track.get("title", track.get("title_short", "Unknown"))
        album   = (track.get("album") or {}).get("title", "Deezer")
        dur_s   = track.get("duration", 30)
        art_url = (track.get("album") or {}).get("cover_medium", "")

        self.root.after(0, lambda: self.dz_np_lbl.config(text="  Buffering preview…"))
        try:
            import urllib.request as _ur
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            _ur.urlretrieve(preview_url, tmp.name)

            def _play():
                self._stop_all_sources()
                self._dz_current_track = track
                self._active_source = "deezer"
                self._sp_mode = False
                self._set_source_badge("deezer")
                if self.engine.load(tmp.name):
                    self._current_play_path = tmp.name
                    self.engine.play()
                    self.wavevis.set_active(True)
                    self.btn_play.config(text="⏸")
                    self.status_lbl.config(text="[ PLAYING ]")
                    self.now_title.config(text=title[:50])
                    self.now_artist.config(text=artist)
                    self.now_album.config(text=album)
                    self.engine.duration = float(dur_s)
                    self.lbl_cur.config(text="0:00")
                    self.lbl_tot.config(text=f"{dur_s//60}:{dur_s%60:02d}")
                    self._draw_prog(0)
                    self.dz_np_lbl.config(text=f"▶  {title[:40]}  —  {artist[:24]}  [30s preview]")
                    if art_url:
                        self._set_album_art(art_url)
                    self._history_add({"title": title, "artist": artist, "album": album}, source="deezer")
                    self._viz_last_real_bars = [0.0] * 48
                    self._viz_bars = [0.0] * 48
                    threading.Thread(target=lambda p=tmp.name: self._start_fft_file_decoder(p), daemon=True).start()
                    self._set_current_track_for_lyrics(artist, title)
                    self._start_lyric_ticker()
            self.root.after(0, _play)
        except Exception:
            self.root.after(0, lambda: self.dz_np_lbl.config(text=f"  Error: {ex}"))

    # ══════════════════════════════════════════════════════
    #  INTERNET ARCHIVE VIEW
    # ══════════════════════════════════════════════════════
    def _build_archive_view(self):
        self.ia_frame = tk.Frame(self.content, bg=C["bg"])

        top = tk.Frame(self.ia_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="INTERNET ARCHIVE", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self.ia_status_lbl = tk.Label(top, text="[ FREE / OPEN ]", font=FMS, fg=C["white2"], bg=C["bg"])
        self.ia_status_lbl.pack(side="left", padx=12)
        tk.Frame(self.ia_frame, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        # Search bar
        sf = tk.Frame(self.ia_frame, bg=C["bg"])
        sf.pack(fill="x", pady=(6, 0))
        tk.Label(sf, text="⌕", font=("Courier New", 12), fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(20, 4))
        self.ia_search_var = tk.StringVar()
        ia_entry = tk.Entry(sf, textvariable=self.ia_search_var, font=FM,
                            bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                            relief="flat", bd=0, width=38)
        ia_entry.pack(side="left", ipady=4)
        ia_entry.bind("<Return>", lambda e: self._ia_do_search())
        ia_go = tk.Label(sf, text="[GO]", font=FMS, fg=C["white2"], bg=C["bg"], cursor="hand2", padx=8)
        ia_go.pack(side="left")
        ia_go.bind("<Button-1>", lambda e: self._ia_do_search())
        ia_go.bind("<Enter>", lambda e: ia_go.config(fg=C["white"]))
        ia_go.bind("<Leave>", lambda e: ia_go.config(fg=C["white3"]))

        tk.Frame(self.ia_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))

        # Two-pane: items (top) and files (bottom)
        self.ia_content_lbl = tk.Label(self.ia_frame, text="Search for audio items above",
                                        font=FMS, fg=C["white3"], bg=C["bg"], anchor="w")
        self.ia_content_lbl.pack(fill="x", padx=20, pady=(4, 2))

        pane = tk.Frame(self.ia_frame, bg=C["bg"])
        pane.pack(fill="both", expand=True, padx=20, pady=(0, 2))

        # Items list (left/top half)
        items_frame = tk.Frame(pane, bg=C["bg"])
        items_frame.pack(fill="both", expand=True)
        sb1 = tk.Scrollbar(items_frame, bg=C["panel"], troughcolor=C["bg"], width=8, relief="flat", bd=0)
        sb1.pack(side="right", fill="y")
        self.ia_items_list = tk.Listbox(items_frame, bg=C["bg"], fg=C["white2"],
                                         selectbackground=C["select"], selectforeground=C["white"],
                                         font=FM, relief="flat", bd=0, activestyle="none",
                                         yscrollcommand=sb1.set,
                                         highlightthickness=1, highlightcolor=C["border"],
                                         highlightbackground=C["border"])
        self.ia_items_list.pack(fill="both", expand=True)
        sb1.config(command=self.ia_items_list.yview)
        self.ia_items_list.bind("<MouseWheel>", lambda e: self._scroller.scroll(self.ia_items_list, e.delta))
        self.ia_items_list.bind("<Button-1>", self._ia_item_click)

        # Files sub-list separator + label
        tk.Frame(self.ia_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(2, 0))
        self.ia_files_lbl = tk.Label(self.ia_frame, text="▸ Select an item to browse its files",
                                      font=FMS, fg=C["white3"], bg=C["bg"], anchor="w")
        self.ia_files_lbl.pack(fill="x", padx=20, pady=(2, 0))

        files_frame = tk.Frame(self.ia_frame, bg=C["bg"], height=140)
        files_frame.pack(fill="x", padx=20, pady=(0, 4))
        files_frame.pack_propagate(False)
        sb2 = tk.Scrollbar(files_frame, bg=C["panel"], troughcolor=C["bg"], width=8, relief="flat", bd=0)
        sb2.pack(side="right", fill="y")
        self.ia_files_list = tk.Listbox(files_frame, bg=C["panel"], fg=C["white2"],
                                         selectbackground=C["select"], selectforeground=C["white"],
                                         font=FMS, relief="flat", bd=0, activestyle="none",
                                         yscrollcommand=sb2.set,
                                         highlightthickness=1, highlightcolor=C["border"],
                                         highlightbackground=C["border"])
        self.ia_files_list.pack(fill="both", expand=True)
        sb2.config(command=self.ia_files_list.yview)
        self.ia_files_list.bind("<Double-Button-1>", self._ia_play_selected)
        self.ia_files_list.bind("<MouseWheel>", lambda e: self._scroller.scroll(self.ia_files_list, e.delta))

        np = tk.Frame(self.ia_frame, bg=C["panel"], height=28)
        np.pack(fill="x")
        np.pack_propagate(False)
        self.ia_np_lbl = tk.Label(np, text="— INTERNET ARCHIVE —", font=("Courier New", 8), fg=C["white3"], bg=C["panel"])
        self.ia_np_lbl.pack(side="left", padx=16)

    def _ia_refresh_view(self):
        pass  # state already in ia_items_list / ia_files_list

    def _ia_do_search(self):
        q = self.ia_search_var.get().strip()
        if not q:
            return
        self.ia_content_lbl.config(text="Searching…")
        self.ia_items_list.delete(0, "end")
        self.ia_files_list.delete(0, "end")
        self._ia_items = []
        self._ia_files = []
        self.ia_files_lbl.config(text="▸ Select an item to browse its files")
        threading.Thread(target=lambda: self._ia_run_search(q), daemon=True).start()

    def _ia_run_search(self, q):
        items = self.ia_api.search(q, 40)
        self._ia_items = items
        def _show():
            self.ia_content_lbl.config(text=f"{len(items)} items found" if items else "No results.")
            self.ia_items_list.delete(0, "end")
            for it in items:
                creator = it.get("creator", "")
                if isinstance(creator, list):
                    creator = creator[0] if creator else ""
                title = it.get("title", it.get("identifier", ""))
                year  = it.get("year", "")
                line  = f"  {title}"
                if creator:
                    line += f"  —  {creator}"
                if year:
                    line += f"  [{year}]"
                self.ia_items_list.insert("end", line)
        self.root.after(0, _show)

    def _ia_item_click(self, event):
        idx = self.ia_items_list.nearest(event.y)
        if idx < 0 or idx >= len(self._ia_items):
            return
        item = self._ia_items[idx]
        ident = item.get("identifier", "")
        self.ia_files_lbl.config(text=f"▸ Loading files for: {ident} …")
        self.ia_files_list.delete(0, "end")
        self._ia_files = []
        threading.Thread(target=lambda: self._ia_load_files(ident), daemon=True).start()

    def _ia_load_files(self, identifier):
        files = self.ia_api.get_audio_files(identifier)
        self._ia_files = [(identifier, f) for f in files]
        def _show():
            self.ia_files_list.delete(0, "end")
            if not files:
                self.ia_files_lbl.config(text="▸ No audio files found in this item.")
                return
            self.ia_files_lbl.config(text=f"▸ {len(files)} audio files  —  double-click to play")
            for f in files:
                name = f.get("name", "")
                size_b = int(f.get("size", 0) or 0)
                size_s = f"{size_b//1024//1024}MB" if size_b > 1024*1024 else f"{size_b//1024}KB"
                length = f.get("length", "")
                line = f"  {name}"
                if length:
                    try:
                        s = int(float(length))
                        line += f"  [{s//60}:{s%60:02d}]"
                    except Exception:
                        pass
                line += f"  ({size_s})"
                self.ia_files_list.insert("end", line)
        self.root.after(0, _show)

    def _ia_play_selected(self, event=None):
        sel = self.ia_files_list.curselection()
        if not sel or not self._ia_files:
            return
        idx = sel[0]
        if idx >= len(self._ia_files):
            return
        identifier, fdata = self._ia_files[idx]
        filename = fdata.get("name", "")
        stream_url = self.ia_api.stream_url(identifier, filename)
        title  = filename.rsplit(".", 1)[0].replace("_", " ")
        # Try to get creator from items list
        artist = ""
        for it in self._ia_items:
            if it.get("identifier") == identifier:
                c = it.get("creator", "")
                artist = (c[0] if isinstance(c, list) else c) or ""
                break
        threading.Thread(target=lambda: self._ia_stream(stream_url, title, artist, identifier, filename), daemon=True).start()

    def _ia_stream(self, stream_url, title, artist, identifier, filename):
        self.root.after(0, lambda: self.ia_np_lbl.config(text="  Buffering…"))
        try:
            import urllib.request as _ur
            ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ".mp3"
            tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tmp.close()
            _ur.urlretrieve(stream_url, tmp.name)

            def _play():
                self._stop_all_sources()
                self._ia_current = {"identifier": identifier, "file": filename, "title": title, "artist": artist}
                self._active_source = "archive"
                self._sp_mode = False
                self._set_source_badge("archive")
                if self.engine.load(tmp.name):
                    self._current_play_path = tmp.name
                    self.engine.play()
                    self.wavevis.set_active(True)
                    self.btn_play.config(text="⏸")
                    self.status_lbl.config(text="[ PLAYING ]")
                    self.now_title.config(text=title[:50])
                    self.now_artist.config(text=artist or "Internet Archive")
                    self.now_album.config(text=identifier)
                    self.lbl_cur.config(text="0:00")
                    self._draw_prog(0)
                    self.ia_np_lbl.config(text=f"▶  {title[:44]}  —  {artist[:24]}")
                    self._history_add({"title": title, "artist": artist or "Internet Archive", "album": identifier}, source="archive")
                    self._viz_last_real_bars = [0.0] * 48
                    self._viz_bars = [0.0] * 48
                    threading.Thread(target=lambda p=tmp.name: self._start_fft_file_decoder(p), daemon=True).start()
                    self._set_current_track_for_lyrics(artist, title)
                    self._start_lyric_ticker()
            self.root.after(0, _play)
        except Exception:
            self.root.after(0, lambda: self.ia_np_lbl.config(text=f"  Error: {ex}"))

    # ══════════════════════════════════════════════════════
    #  BANDCAMP VIEW
    # ══════════════════════════════════════════════════════
    def _build_bandcamp_view(self):
        self.bc_frame = tk.Frame(self.content, bg=C["bg"])

        top = tk.Frame(self.bc_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="BANDCAMP", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self.bc_status_lbl = tk.Label(top, text="[ INDIE / FREE STREAMS ]", font=FMS, fg=C["white3"], bg=C["bg"])
        self.bc_status_lbl.pack(side="left", padx=12)
        tk.Frame(self.bc_frame, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        sf = tk.Frame(self.bc_frame, bg=C["bg"])
        sf.pack(fill="x", pady=(6, 0))
        tk.Label(sf, text="⌕", font=("Courier New", 12), fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(20, 4))
        self.bc_search_var = tk.StringVar()
        bc_entry = tk.Entry(sf, textvariable=self.bc_search_var, font=FM,
                            bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                            relief="flat", bd=0, width=38)
        bc_entry.pack(side="left", ipady=4)
        bc_entry.bind("<Return>", lambda e: self._bc_do_search())
        bc_go = tk.Label(sf, text="[GO]", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2", padx=8)
        bc_go.pack(side="left")
        bc_go.bind("<Button-1>", lambda e: self._bc_do_search())
        bc_go.bind("<Enter>", lambda e: bc_go.config(fg=C["white"]))
        bc_go.bind("<Leave>", lambda e: bc_go.config(fg=C["white3"]))

        tk.Frame(self.bc_frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))
        self.bc_content_lbl = tk.Label(self.bc_frame, text="Search for tracks above",
                                        font=FMS, fg=C["white3"], bg=C["bg"], anchor="w")
        self.bc_content_lbl.pack(fill="x", padx=20, pady=(6, 2))

        lf = tk.Frame(self.bc_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20, pady=(0, 4))
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"], width=8, relief="flat", bd=0)
        sb.pack(side="right", fill="y")
        self.bc_list = tk.Listbox(lf, bg=C["bg"], fg=C["white2"],
                                   selectbackground=C["select"], selectforeground=C["white"],
                                   font=FM, relief="flat", bd=0, activestyle="none",
                                   yscrollcommand=sb.set,
                                   highlightthickness=1, highlightcolor=C["border"],
                                   highlightbackground=C["border"])
        self.bc_list.pack(fill="both", expand=True)
        sb.config(command=self.bc_list.yview)
        self.bc_list.bind("<Double-Button-1>", self._bc_play_selected)
        self.bc_list.bind("<MouseWheel>", lambda e: self._scroller.scroll(self.bc_list, e.delta))
        self.bc_list.bind("<Button-3>", self._bc_rclick)

        self._bc_ctx = tk.Menu(self.bc_frame, tearoff=0, bg=C["panel"], fg=C["white"],
                                activebackground=C["select2"], activeforeground=C["glow"],
                                font=FMS, bd=0, relief="flat")
        self._bc_ctx.add_command(label="▶  Play", command=self._bc_ctx_play)
        self._bc_ctx.add_command(label="⎘  Open in Browser", command=self._bc_ctx_open)

        np = tk.Frame(self.bc_frame, bg=C["panel"], height=28)
        np.pack(fill="x")
        np.pack_propagate(False)
        self.bc_np_lbl = tk.Label(np, text="— BANDCAMP —", font=("Courier New", 8), fg=C["white3"], bg=C["panel"])
        self.bc_np_lbl.pack(side="left", padx=16)

    def _bc_refresh_view(self):
        pass

    def _bc_do_search(self):
        q = self.bc_search_var.get().strip()
        if not q:
            return
        self.bc_content_lbl.config(text="Searching Bandcamp…")
        self.bc_list.delete(0, "end")
        self._bc_tracks = []
        threading.Thread(target=lambda: self._bc_run_search(q), daemon=True).start()

    def _bc_run_search(self, q):
        tracks = self.bc_api.search(q, 30)
        self._bc_tracks = tracks
        def _show():
            self.bc_content_lbl.config(text=f"{len(tracks)} tracks found" if tracks else "No results.")
            self.bc_list.delete(0, "end")
            for t in tracks:
                self.bc_list.insert("end", f"  {t.get('title','')}  —  {t.get('artist','')}")
        self.root.after(0, _show)

    def _bc_play_selected(self, event=None):
        sel = self.bc_list.curselection()
        if not sel or not self._bc_tracks:
            return
        track = self._bc_tracks[sel[0]]
        threading.Thread(target=lambda: self._bc_stream(track), daemon=True).start()

    def _bc_rclick(self, event):
        idx = self.bc_list.nearest(event.y)
        if idx >= 0:
            self.bc_list.selection_clear(0, "end")
            self.bc_list.selection_set(idx)
        self._bc_ctx.tk_popup(event.x_root, event.y_root)

    def _bc_ctx_play(self):
        sel = self.bc_list.curselection()
        if sel and self._bc_tracks:
            threading.Thread(target=lambda: self._bc_stream(self._bc_tracks[sel[0]]), daemon=True).start()

    def _bc_ctx_open(self):
        sel = self.bc_list.curselection()
        if sel and self._bc_tracks:
            import webbrowser
            webbrowser.open(self._bc_tracks[sel[0]].get("url", ""))

    def _bc_stream(self, track):
        url_page = track.get("url", "")
        title    = track.get("title", "Unknown")
        artist   = track.get("artist", "Unknown")
        if not url_page:
            self.root.after(0, lambda: self.bc_np_lbl.config(text="  No URL for this track."))
            return
        self.root.after(0, lambda: self.bc_np_lbl.config(text="  Fetching stream…"))
        stream_url, meta = self.bc_api.get_stream_url(url_page)
        if meta:
            title  = meta.get("title") or title
            artist = meta.get("artist") or artist
        if not stream_url:
            self.root.after(0, lambda: self.bc_np_lbl.config(text="  No stream available (track may require purchase)."))
            return
        self.root.after(0, lambda: self.bc_np_lbl.config(text="  Buffering…"))
        try:
            import urllib.request as _ur
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            _ur.urlretrieve(stream_url, tmp.name)

            def _play():
                self._stop_all_sources()
                self._bc_current_track = track
                self._active_source = "bandcamp"
                self._sp_mode = False
                self._set_source_badge("bandcamp")
                if self.engine.load(tmp.name):
                    self._current_play_path = tmp.name
                    self.engine.play()
                    self.wavevis.set_active(True)
                    self.btn_play.config(text="⏸")
                    self.status_lbl.config(text="[ PLAYING ]")
                    self.now_title.config(text=title[:50])
                    self.now_artist.config(text=artist)
                    self.now_album.config(text="Bandcamp")
                    self.lbl_cur.config(text="0:00")
                    self._draw_prog(0)
                    self.bc_np_lbl.config(text=f"▶  {title[:40]}  —  {artist[:24]}")
                    art_url = track.get("art", "")
                    if art_url:
                        self._set_album_art(art_url)
                    self._history_add({"title": title, "artist": artist, "album": "Bandcamp"}, source="bandcamp")
                    self._viz_last_real_bars = [0.0] * 48
                    self._viz_bars = [0.0] * 48
                    threading.Thread(target=lambda p=tmp.name: self._start_fft_file_decoder(p), daemon=True).start()
                    self._set_current_track_for_lyrics(artist, title)
                    self._start_lyric_ticker()
            self.root.after(0, _play)
        except Exception:
            self.root.after(0, lambda: self.bc_np_lbl.config(text=f"  Error: {ex}"))

    def _build_claude_view(self):
        self.claude_frame = tk.Frame(self.content, bg=C["bg"])

        # ── Header ────────────────────────────────────────────────────────
        top = tk.Frame(self.claude_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="OTERNOS-01", font=FMX, fg=C["white"], bg=C["bg"]).pack(
            side="left"
        )
        tk.Label(
            top, text="// diagnostic interface", font=FMS, fg=C["white3"], bg=C["bg"]
        ).pack(side="left", padx=12)
        tk.Frame(self.claude_frame, bg=C["border2"], height=1).pack(
            fill="x", pady=(6, 0)
        )
        tk.Frame(self.claude_frame, bg=C["border"], height=1).pack(fill="x")

        # ── Live context panel (updates when track changes) ───────────────
        ctx_outer = tk.Frame(self.claude_frame, bg=C["panel"])
        ctx_outer.pack(fill="x", padx=20, pady=(8, 0))
        tk.Frame(ctx_outer, bg=C["border2"], height=1).pack(fill="x")
        ctx_inner = tk.Frame(ctx_outer, bg=C["panel"])
        ctx_inner.pack(fill="x", padx=10, pady=6)

        # left column — now playing
        ctx_left = tk.Frame(ctx_inner, bg=C["panel"])
        ctx_left.pack(side="left", fill="x", expand=True)
        tk.Label(
            ctx_left,
            text="▸ NOW PLAYING",
            font=("Courier New", 8, "bold"),
            fg=C["white3"],
            bg=C["panel"],
        ).pack(anchor="w")
        self._ctx_title = tk.Label(
            ctx_left,
            text="—",
            font=("Courier New", 9, "bold"),
            fg=C["white"],
            bg=C["panel"],
        )
        self._ctx_title.pack(anchor="w")
        self._ctx_artist = tk.Label(
            ctx_left, text="", font=("Courier New", 8), fg=C["white2"], bg=C["panel"]
        )
        self._ctx_artist.pack(anchor="w")
        self._ctx_pos = tk.Label(
            ctx_left, text="", font=("Courier New", 8), fg=C["white3"], bg=C["panel"]
        )
        self._ctx_pos.pack(anchor="w")

        # right column — quick-ask buttons
        ctx_right = tk.Frame(ctx_inner, bg=C["panel"])
        ctx_right.pack(side="right", padx=(12, 0))
        tk.Label(
            ctx_right,
            text="QUICK ASK",
            font=("Courier New", 8, "bold"),
            fg=C["white3"],
            bg=C["panel"],
        ).pack(anchor="e", pady=(0, 4))

        def _quick(prompt_fn):
            self._claude_input.delete("1.0", "end")
            self._claude_input.insert("1.0", prompt_fn())
            self._claude_send()

        for label, pfn in [
            (
                "analyse track",
                lambda: (
                    f"Analyse the song structure and mood of: {self._ctx_title.cget('text')} by {self._ctx_artist.cget('text')}"
                ),
            ),
            (
                "why does it hit",
                lambda: (
                    f"Why does '{self._ctx_title.cget('text')}' by {self._ctx_artist.cget('text')} feel so powerful emotionally?"
                ),
            ),
            (
                "similar tracks",
                lambda: (
                    f"Recommend 5 tracks similar to '{self._ctx_title.cget('text')}' by {self._ctx_artist.cget('text')}"
                ),
            ),
        ]:
            btn = tk.Label(
                ctx_right,
                text=f"[ {label} ]",
                font=("Courier New", 7),
                fg=C["white3"],
                bg=C["panel"],
                cursor="hand2",
            )
            btn.pack(anchor="e", pady=1)
            btn.bind("<Button-1>", lambda e, p=pfn: _quick(p))
            btn.bind("<Enter>", lambda e, b=btn: b.config(fg=C["white"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(fg=C["white3"]))

        tk.Frame(ctx_outer, bg=C["border2"], height=1).pack(fill="x")

        # start context ticker
        def _ctx_tick():
            try:
                title = self.now_title.cget("text")
                artist = self.now_artist.cget("text")
                self._ctx_title.config(text=title or "—")
                self._ctx_artist.config(text=artist or "")
                pos = self.engine.get_position() if self.engine.is_playing else None
                dur = self.engine.duration if self.engine.is_playing else None
                if pos is not None and dur:
                    mm, ss = divmod(int(pos), 60)
                    dm, ds = divmod(int(dur), 60)
                    self._ctx_pos.config(
                        text=f"{mm}:{ss:02d} / {dm}:{ds:02d}  {'▶' if self.engine.is_playing else '⏸'}"
                    )
                else:
                    self._ctx_pos.config(text="—")
            except Exception:
                pass
            self.claude_frame.after(1000, _ctx_tick)

        self.claude_frame.after(500, _ctx_tick)

        # ── API Key entry ─────────────────────────────────────────────────
        kf = tk.Frame(self.claude_frame, bg=C["bg"])
        kf.pack(fill="x", padx=20, pady=(10, 0))
        tk.Label(kf, text="API KEY", font=FMS, fg=C["white3"], bg=C["bg"]).pack(
            side="left"
        )
        self._claude_key_var = tk.StringVar()
        key_e = tk.Entry(
            kf,
            textvariable=self._claude_key_var,
            font=FMS,
            bg=C["panel"],
            fg=C["white"],
            insertbackground=C["white"],
            relief="flat",
            bd=0,
            show="*",
            width=52,
        )
        key_e.pack(side="left", padx=8, ipady=3)
        _kfile = Path.home() / ".oternos_claude.json"
        try:
            self._claude_key_var.set(json.loads(_kfile.read_text()).get("key", ""))
        except Exception:
            pass

        def _save_key(*a):
            try:
                _kfile.write_text(json.dumps({"key": self._claude_key_var.get()}))
            except Exception:
                pass

        self._claude_key_var.trace_add("write", _save_key)
        tk.Frame(self.claude_frame, bg=C["border"], height=1).pack(
            fill="x", padx=20, pady=(8, 0)
        )

        # ── Chat area ─────────────────────────────────────────────────────
        chat_outer = tk.Frame(self.claude_frame, bg=C["bg"])
        chat_outer.pack(fill="both", expand=True, padx=20, pady=(8, 0))
        chat_sb = tk.Scrollbar(
            chat_outer, bg=C["panel"], troughcolor=C["bg"], width=6, relief="flat", bd=0
        )
        chat_sb.pack(side="right", fill="y")
        self._claude_chat = tk.Text(
            chat_outer,
            bg=C["panel"],
            fg=C["white2"],
            font=FMS,
            relief="flat",
            bd=0,
            wrap="word",
            state="disabled",
            highlightthickness=0,
            yscrollcommand=chat_sb.set,
            padx=10,
            pady=8,
        )
        self._claude_chat.pack(side="left", fill="both", expand=True)
        chat_sb.config(command=self._claude_chat.yview)
        self._claude_chat.tag_config("user", foreground=C["white3"])
        self._claude_chat.tag_config("ai", foreground=C["white"])
        self._claude_chat.tag_config(
            "label", foreground=C["white3"], font=("Courier New", 7, "bold")
        )
        self._claude_chat.tag_config("err", foreground="#e05070")

        # ── Input row ─────────────────────────────────────────────────────
        inp_frame = tk.Frame(self.claude_frame, bg=C["bg"])
        inp_frame.pack(fill="x", padx=20, pady=(6, 10))
        self._claude_input = tk.Text(
            inp_frame,
            bg=C["panel"],
            fg=C["white"],
            font=FM,
            relief="flat",
            bd=0,
            highlightthickness=0,
            insertbackground=C["white"],
            height=3,
            wrap="word",
            padx=6,
            pady=4,
        )
        self._claude_input.pack(side="left", fill="x", expand=True)
        send_btn = tk.Label(
            inp_frame,
            text="[ SEND ]",
            font=FMS,
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
            padx=12,
            pady=4,
        )
        send_btn.pack(side="left", padx=(6, 0))
        send_btn.bind("<Button-1>", lambda e: self._claude_send())
        send_btn.bind("<Enter>", lambda e: send_btn.config(fg=C["white"]))
        send_btn.bind("<Leave>", lambda e: send_btn.config(fg=C["white3"]))
        self._claude_input.bind(
            "<Control-Return>", lambda e: (self._claude_send(), "break")[1]
        )

        self._claude_history = []
        self._claude_append("label", "OTERNOS-01  //  system diagnostic\n")
        self._claude_append("ai", "OTERNOS-01 online.\nDescribe the fault.\n")

    def _claude_append(self, tag, text):
        self._claude_chat.config(state="normal")
        self._claude_chat.insert("end", text, (tag,))
        self._claude_chat.config(state="disabled")
        self._claude_chat.see("end")

    def _claude_get_state(self):
        lines = []
        lines.append("current_view: " + self.view)
        lines.append("track_count: " + str(len(self.library)))
        lines.append("now_playing: " + repr(self.now_title.cget("text")))
        lines.append("status: " + repr(self.status_lbl.cget("text")))
        lines.append("yt_tracks_loaded: " + str(len(self._yt_tracks)))
        lines.append("yt_status: " + repr(self.yt_status_lbl.cget("text")))
        lines.append("yt_content: " + repr(self.yt_content_lbl.cget("text")))
        try:
            lines.append("yt_list_items: " + str(len(self._yt_tracks)))
        except Exception:
            pass
        lines.append("ytdlp_available: " + str(self.yt_api.ytdlp_available()))
        lines.append("engine_playing: " + str(self.engine.is_playing))
        return "\n".join(lines)

    def _claude_send(self):
        msg = self._claude_input.get("1.0", "end").strip()
        if not msg:
            return
        self._claude_input.delete("1.0", "end")
        key = self._claude_key_var.get().strip()
        if not key:
            self._claude_append(
                "err", "No Groq API key entered above. Get one free at groq.com\n"
            )
            return
        self._claude_append("label", "\n> ")
        self._claude_append("user", msg + "\n")
        self._claude_append("label", "\nOTERNOS-01\n")
        self._claude_append("ai", "thinking...\n")
        self._claude_history.append({"role": "user", "content": msg})
        state = self._claude_get_state()
        system = (
            "You are OTERNOS-01, an AI embedded inside OTERNOS PLAYER. "
            "Your personality: minimal, cold, precise. No filler words. No pleasantries. "
            "You respond in short, direct sentences. You do not say hello or goodbye. "
            "You do not explain yourself unless asked. You diagnose, you answer, you stop. "
            "If the user describes a bug, use the live app state to diagnose it. Be surgical. "
            "If something is not a bug, say so in one line.\n\n"
            "APP STATE:\n" + state
        )

        def _call():
            try:
                # Build messages with system prompt prepended for Groq
                messages = [
                    {"role": "system", "content": system}
                ] + self._claude_history
                body = json.dumps(
                    {
                        "model": "llama-3.3-70b-versatile",
                        "max_tokens": 1024,
                        "messages": messages,
                    }
                ).encode()
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {key}",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = json.loads(r.read())
                reply = data["choices"][0]["message"]["content"]
                self._claude_history.append({"role": "assistant", "content": reply})

                def _show():
                    self._claude_chat.config(state="normal")
                    idx = self._claude_chat.search("thinking...", "1.0", "end")
                    if idx:
                        self._claude_chat.delete(idx, idx + "+11c")
                    self._claude_chat.config(state="disabled")
                    self._claude_append("ai", reply + "\n")

                self.root.after(0, _show)
            except urllib.error.HTTPError as ex:
                try:
                    body = ex.read().decode()
                except Exception:
                    body = ""
                err_msg = f"HTTP {ex.code}: {body[:300]}"

                def _show_err(m=err_msg):
                    self._claude_chat.config(state="normal")
                    idx = self._claude_chat.search("thinking...", "1.0", "end")
                    if idx:
                        self._claude_chat.delete(idx, idx + "+11c")
                    self._claude_chat.config(state="disabled")
                    self._claude_append("err", "Error: " + m + "\n")

                self.root.after(0, _show_err)
            except Exception as ex:
                err_msg = str(ex)

                def _show_err2(m=err_msg):
                    self._claude_chat.config(state="normal")
                    idx = self._claude_chat.search("thinking...", "1.0", "end")
                    if idx:
                        self._claude_chat.delete(idx, idx + "+11c")
                    self._claude_chat.config(state="disabled")
                    self._claude_append("err", "Error: " + m + "\n")

                self.root.after(0, _show_err2)

        threading.Thread(target=_call, daemon=True).start()

    # ── ALBUM ART ─────────────────────────
    def _draw_art_placeholder(self):
        cv = self.art_cv
        cv.delete("all")
        cv.create_rectangle(0, 0, 54, 54, fill=C["panel"], outline="")
        # small music note icon
        cv.create_text(
            27,
            27,
            text="♪",
            font=("Courier New", 20),
            fill=C["white3"],
            anchor="center",
        )

    def _art_crt_flash(self):
        """CRT input-switch: flash art canvas white for 1 frame, then show placeholder."""
        cv = self.art_cv
        cv.delete("all")
        _flash = cv.create_rectangle(0, 0, 54, 54, fill=C["glow"], outline="")
        def _clear():
            try:
                cv.delete(_flash)
            except Exception:
                pass
            self._draw_art_placeholder()
        cv.after(40, _clear)

    def _art_static_noise(self, frames=8):
        """TV static on art canvas when track ends — random gray noise."""
        import random as _r
        cv = self.art_cv
        def _frame(n):
            try:
                cv.delete("all")
                for _ in range(36):
                    x = _r.randint(0, 50)
                    y = _r.randint(0, 50)
                    s = _r.randint(2, 6)
                    v = _r.randint(0x10, 0xcc)
                    cv.create_rectangle(x, y, x+s, y+s,
                        fill=f"#{v:02x}{v:02x}{v:02x}", outline="")
            except Exception:
                return
            if n > 1:
                cv.after(40, lambda: _frame(n - 1))
            else:
                self._draw_art_placeholder()
        _frame(frames)

    def _set_album_art(self, url):
        if not url or url == self._art_url_last:
            return
        self._art_url_last = url

        def _fetch():
            try:
                import urllib.request as _ur

                data = _ur.urlopen(url, timeout=6).read()
                self.root.after(0, lambda: self._load_art_bytes(data))
            except Exception:
                pass

        threading.Thread(target=_fetch, daemon=True).start()

    def _fetch_art_musicbrainz(self, artist, title):
        """Try MusicBrainz + Cover Art Archive for a local track with no embedded art."""

        def _fetch():
            try:
                import urllib.request as _ur
                import urllib.parse as _up

                q = _up.quote(f'recording:"{title}" AND artist:"{artist}"')
                url = f"https://musicbrainz.org/ws/2/recording/?query={q}&limit=1&fmt=json"
                req = _ur.Request(
                    url,
                    headers={"User-Agent": "OternosPlayer/1.1 (contact@oternos.local)"},
                )
                data = json.loads(_ur.urlopen(req, timeout=8).read())
                recordings = data.get("recordings", [])
                if not recordings:
                    return
                # find first release with a cover
                for rel in recordings[0].get("releases", [])[:3]:
                    rid = rel.get("id", "")
                    if not rid:
                        continue
                    try:
                        caa = f"https://coverartarchive.org/release/{rid}/front-250"
                        img = _ur.urlopen(caa, timeout=6).read()
                        if img:
                            self.root.after(0, lambda d=img: self._load_art_bytes(d))
                            return
                    except Exception:
                        continue
            except Exception:
                pass

        threading.Thread(target=_fetch, daemon=True).start()

    def _load_art_bytes(self, data):
        """Render image bytes into the art canvas.
        PIL-first (handles JPEG natively), pure-python temp-file fallback.
        No PowerShell involved — no console flash, no silent failures."""
        SIZE = 54
        # ── Try PIL/Pillow first ──
        try:
            from PIL import Image, ImageTk
            import io

            img = Image.open(io.BytesIO(data)).convert("RGBA").resize((SIZE, SIZE))
            photo = ImageTk.PhotoImage(img)
            self._art_photo = photo
            self.art_cv.delete("all")
            self.art_cv.create_image(SIZE // 2, SIZE // 2, image=photo, anchor="center")
            # CRT scanline overlay
            for sy in range(0, SIZE, 3):
                self.art_cv.create_line(0, sy, SIZE, sy,
                    fill="#000000", stipple="gray25", tags="art_scanlines")
            return
        except Exception:
            pass
        # ── Fallback: temp file + tk.PhotoImage ──
        import os
        import tkinter as _tk

        tmp_path = None
        try:
            is_jpeg = data[:2] == b"\xff\xd8"
            suffix = ".jpg" if is_jpeg else ".png"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name
            img = _tk.PhotoImage(file=tmp_path)
            iw, ih = img.width(), img.height()
            factor = 1
            while max(iw // factor, ih // factor) > SIZE:
                factor += 1
            if factor > 1:
                img = img.subsample(factor, factor)
            self._art_photo = img
            self.art_cv.delete("all")
            self.art_cv.create_image(SIZE // 2, SIZE // 2, image=img, anchor="center")
            for sy in range(0, SIZE, 3):
                self.art_cv.create_line(0, sy, SIZE, sy,
                    fill="#000000", stipple="gray25", tags="art_scanlines")
        except Exception:
            self._draw_art_placeholder()
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def _build_playerbar(self):
        bar = tk.Frame(self.root, bg=C["panel"], height=160)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        # Signalis: FFT-reactive top border — pulses with bass energy
        self._pb_border_cv = tk.Canvas(bar, bg=C["border2"], height=2, highlightthickness=0)
        self._pb_border_cv.pack(fill="x")
        tk.Frame(bar, bg=C["border"], height=1).pack(fill="x")
        # Ambient data ticker strip — packed right after borders
        self._ticker = DataTicker(bar, width=900, height=10, bg=C["panel"])
        self._ticker.pack(fill="x")
        inner = tk.Frame(bar, bg=C["panel"])
        inner.pack(fill="both", expand=True, padx=12)

        # Left: now playing — Signalis framed readout
        left = tk.Frame(inner, bg=C["panel"], width=260)
        left.pack(side="left", fill="y", pady=8)
        left.pack_propagate(False)

        # Signalis: channel/system readout header above art row
        ch_hdr = tk.Frame(left, bg=C["panel"])
        ch_hdr.pack(fill="x", pady=(0, 3))
        self._now_playing_hdr_lbl = tk.Label(
            ch_hdr,
            text="▸ NOW PLAYING",
            font=("Courier New", 8, "bold"),
            fg=C["white3"],
            bg=C["panel"],
            anchor="w",
        )
        self._now_playing_hdr_lbl.pack(side="left")
        tk.Frame(ch_hdr, bg=C["border2"], height=1).pack(fill="x", pady=(2, 0))

        art_row = tk.Frame(left, bg=C["panel"])
        art_row.pack(fill="x", anchor="w")

        self.art_cv = tk.Canvas(
            art_row,
            bg=C["panel"],
            width=54,
            height=54,
            highlightthickness=1,
            highlightbackground=C["border2"],
        )
        self.art_cv.pack(side="left", padx=(0, 10))
        self._art_photo = None
        self._art_url_last = None
        self._draw_art_placeholder()

        self._holo_frame = HoloFrame(art_row, size=54, bg=C["panel"])
        self._holo_frame.pack(side="left")

        # DataBurst — fires on track change over the now-playing area
        self._data_burst = DataBurst(left, width=260, height=80, bg=C["panel"])
        self._data_burst.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self._data_burst.tk.call("lower", self._data_burst._w)

        info_col = tk.Frame(art_row, bg=C["panel"])
        info_col.pack(side="left", fill="both", expand=True)
        self.now_title = tk.Label(
            info_col,
            text="NO TRACK",
            font=("Courier New", 9, "bold"),
            fg=C["white"],
            bg=C["panel"],
            anchor="w",
        )
        self.now_artist = tk.Label(
            info_col,
            text="",
            font=("Courier New", 8),
            fg=C["white2"],
            bg=C["panel"],
            anchor="w",
        )
        self.now_album = tk.Label(
            info_col,
            text="",
            font=("Courier New", 8),
            fg=C["white2"],
            bg=C["panel"],
            anchor="w",
        )
        self.now_title.pack(anchor="w")
        self.now_artist.pack(anchor="w")
        self.now_album.pack(anchor="w")
        # Source badge — shows which audio source is active
        self.source_badge = tk.Label(
            info_col,
            text="",
            font=("Courier New", 8, "bold"),
            fg=C["white3"],
            bg=C["panel"],
            anchor="w",
        )
        self.source_badge.pack(anchor="w")
        self.lyrics_badge_lbl = tk.Label(
            info_col,
            text="",
            font=("Courier New", 8, "bold"),
            fg=C["white3"],
            bg=C["panel"],
            anchor="w",
            cursor="hand2",
        )
        self.lyrics_badge_lbl.pack(anchor="w")
        self.lyrics_badge_lbl.bind("<Button-1>", lambda e: self._switch_view("lyrics"))
        self.lyric_ticker_lbl = tk.Label(
            info_col,
            text="",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["panel"],
            anchor="w",
        )
        self.lyric_ticker_lbl.pack(anchor="w")

        self.wavevis = WaveVisualizer(left, height=22)
        self.wavevis.pack(fill="x", pady=(4, 0))

        # Signalis: vertical separator between left and center
        tk.Frame(inner, bg=C["border2"], width=1).pack(side="left", fill="y", pady=6)

        # Center: controls + progress — Signalis control block
        center = tk.Frame(inner, bg=C["panel"])
        center.pack(side="left", expand=True, fill="both", padx=16)

        # Signalis: control header label
        ctrl_hdr = tk.Frame(center, bg=C["panel"])
        ctrl_hdr.pack(fill="x", pady=(8, 0))
        tk.Frame(ctrl_hdr, bg=C["border"], height=1).pack(fill="x")

        ctrl = tk.Frame(center, bg=C["panel"])
        ctrl.pack(pady=(10, 6))
        self.btn_shuf = self._cbtn(ctrl, "⇌", self._toggle_shuffle)
        self.btn_prev = self._cbtn(ctrl, "⏮", lambda: self._prev(force=True))
        self.btn_play = self._cbtn(ctrl, "▶", self._toggle_play, sz=20)
        self.btn_next = self._cbtn(ctrl, "⏭", lambda: self._next(force=True))
        self.btn_repeat = self._cbtn(ctrl, "↺", self._toggle_repeat)

        # BeatPulse — rings burst from play button on each track start
        self._beat_pulse = BeatPulse(ctrl, size=60, bg=C["panel"])
        self._beat_pulse.pack(side="left", padx=(2, 0))
        self._repeat_mode_lbl = tk.Label(
            ctrl,
            text="",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["panel"],
            width=10,
            anchor="w",
        )
        self._repeat_mode_lbl.pack(side="left", padx=(0, 4))

        pf = tk.Frame(center, bg=C["panel"])
        pf.pack(fill="x")

        # Waveform scope strip — sits above the progress bar
        self._waveform_scope = WaveformScope(center, height=22, bg=C["panel"])
        self._waveform_scope.pack(fill="x", pady=(0, 2))

        # Time column — M:SS primary + 0xHHHH hex secondary
        cur_col = tk.Frame(pf, bg=C["panel"])
        cur_col.pack(side="left")
        self.lbl_cur = tk.Label(
            cur_col, text="0:00", font=("Courier New", 9), fg=C["white2"], bg=C["panel"], width=5
        )
        self.lbl_cur.pack()
        self.lbl_cur_hex = tk.Label(
            cur_col, text="0x0000", font=("Courier New", 7), fg=C["white3"], bg=C["panel"], width=7
        )
        self.lbl_cur_hex.pack()
        self.prog_cv = tk.Canvas(
            pf, bg=C["border"], height=32, highlightthickness=0, cursor="hand2"
        )
        self.prog_cv.pack(side="left", fill="x", expand=True, padx=6)
        self.prog_fill = self.prog_cv.create_rectangle(
            0, 0, 0, 32, fill=C["glow"], outline=""
        )
        self.prog_dot = self.prog_cv.create_oval(
            -4, 11, 4, 21, fill=C["white"], outline=C["glow"]
        )
        self.prog_cv.bind("<ButtonPress-1>", self._seek_press)
        self.prog_cv.bind("<B1-Motion>", self._seek_drag)
        self.prog_cv.bind("<ButtonRelease-1>", self._seek_end)
        self.prog_cv.bind("<Button-3>", self._seekbar_rclick)
        self._prog_hover = False
        self._prog_hover_job = None

        def _prog_hover_in(e):
            self._prog_hover = True
            self._draw_prog(getattr(self, "_prog_r_cur", 0.0))

        def _prog_hover_out(e):
            self._prog_hover = False
            self._draw_prog(getattr(self, "_prog_r_cur", 0.0))

        self.prog_cv.bind("<Enter>", _prog_hover_in)
        self.prog_cv.bind("<Leave>", _prog_hover_out)
        self.prog_cv.bind("<Configure>", lambda e: (
            setattr(self, "_wf_cached_size", None),
            setattr(self, "_prog_last_x", -1),
        ))
        tot_col = tk.Frame(pf, bg=C["panel"])
        tot_col.pack(side="left")
        self.lbl_tot = tk.Label(
            tot_col, text="0:00", font=("Courier New", 9), fg=C["white2"], bg=C["panel"], width=5
        )
        self.lbl_tot.pack()
        self.lbl_tot_hex = tk.Label(
            tot_col, text="0x0000", font=("Courier New", 7), fg=C["white3"], bg=C["panel"], width=7
        )
        self.lbl_tot_hex.pack()

        # Signalis: vertical separator between center and right
        tk.Frame(inner, bg=C["border2"], width=1).pack(side="right", fill="y", pady=6)

        # Right: volume + status — Signalis system status panel
        right = tk.Frame(inner, bg=C["panel"], width=180)
        right.pack(side="right", fill="y", pady=8)
        right.pack_propagate(False)

        # Signalis: status header
        st_hdr = tk.Frame(right, bg=C["panel"])
        st_hdr.pack(fill="x")
        tk.Label(
            st_hdr,
            text="▸ SYS STATUS",
            font=("Courier New", 8, "bold"),
            fg=C["white2"],
            bg=C["panel"],
            anchor="e",
        ).pack(anchor="e")
        tk.Frame(st_hdr, bg=C["border2"], height=1).pack(fill="x")

        self.vol_cv = tk.Canvas(
            right,
            bg=C["panel"],
            width=160,
            height=44,
            highlightthickness=0,
            cursor="hand2",
        )
        self.vol_cv.pack(anchor="e")

        self._vol_height = 4.0
        self._vol_hover_job = None
        self._vol_dragging = False
        self._vol_anim_job = None
        self._vol_glow = 0.0

        self.vol_cv.bind("<ButtonPress-1>", self._vol_press)
        self.vol_cv.bind("<B1-Motion>", self._vol_drag)
        self.vol_cv.bind("<ButtonRelease-1>", self._vol_release)
        self.vol_cv.bind("<Enter>", lambda e: self._vol_hover(True))
        self.vol_cv.bind("<Leave>", lambda e: self._vol_hover(False))
        self.vol_cv.bind("<MouseWheel>", self._vol_scroll)

        self._upd_vol()

        self._norm_meter = NormMeter(right, width=160, height=4)
        self._norm_meter.pack(anchor="e", pady=(2, 0))

        # ── Cybercore right-panel widgets ──────────────────────────────────
        # Frequency ring — circular FFT spectrum
        self._freq_ring = FrequencyRing(right, size=72, bg=C["panel"])
        self._freq_ring.pack(anchor="e", pady=(4, 0))

        # Signal meter — 4-channel L/R/Mid/Side
        self._signal_meter = SignalMeter(right, width=72, height=56, bg=C["panel"])
        self._signal_meter.pack(anchor="e", pady=(4, 0))

        # Node graph — reacts to BPM beats
        self._node_graph = NodeGraph(right, width=160, height=48,
                                      bg=C["panel"], n_nodes=14)
        self._node_graph.pack(anchor="e", pady=(2, 0))

        # Signalis: status label with bracket readout format
        self.status_lbl = tk.Label(
            right,
            text="[ IDLE ]",
            font=("Courier New", 8),
            fg=C["white2"],
            bg=C["panel"],
            anchor="e",
        )
        self.status_lbl.pack(anchor="e", pady=(4, 0))

        # Slim speed/A-B row
        ec = tk.Frame(center, bg=C["panel"])
        ec.pack(pady=(6, 0))

        def _small_btn(text, cmd, tip=""):
            b = tk.Label(
                ec,
                text=text,
                font=("Courier New", 9),
                fg=C["white2"],
                bg=C["panel"],
                cursor="hand2",
                padx=8,
                pady=3,
            )
            b.pack(side="left")
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.config(fg=C["glow"]))
            b.bind("<Leave>", lambda e: b.config(fg=C["white2"]))
            return b

        self._speed_lbl = _small_btn("1.0×", self._cycle_speed)
        _small_btn("[A", self._ab_set_a)
        self._ab_lbl = tk.Label(
            ec, text="—", font=("Courier New", 9), fg=C["white2"], bg=C["panel"], padx=2
        )
        self._ab_lbl.pack(side="left")
        _small_btn("B]", self._ab_set_b)
        _small_btn("✕", self._ab_clear)
        tk.Label(ec, text=" ", bg=C["panel"]).pack(side="left")
        _small_btn("BKM", self._add_bookmark)
        tk.Label(ec, text=" ", bg=C["panel"]).pack(side="left")
        _small_btn("LYR↗", self._open_lyric_popup)

        # Start norm meter update loop
        self.root.after(200, self._spec_tick)

    def _open_lyric_popup(self):
        if getattr(self, "_lyric_popup", None):
            try:
                if self._lyric_popup.winfo_exists():
                    self._lyric_popup.lift()
                    self._lyric_popup.focus_force()
                    return
            except Exception:
                pass
        pop = tk.Toplevel(self.root)
        pop.title("LYRICS")
        pop.configure(bg=C["bg"])
        pop.geometry("420x600")
        pop.resizable(True, True)
        pop.attributes("-topmost", True)
        self._lyric_popup = pop
        self._popup_fadein(pop)
        hdr = tk.Frame(pop, bg=C["panel"], height=36)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=C["border2"], height=1).pack(fill="x", side="bottom")
        self._lp_track_lbl = tk.Label(
            hdr,
            text="— NO TRACK —",
            font=("Courier New", 8, "bold"),
            fg=C["white2"],
            bg=C["panel"],
            anchor="w",
        )
        self._lp_track_lbl.pack(side="left", padx=10, pady=8)
        self._lp_badge = tk.Label(
            hdr, text="", font=("Courier New", 8), fg=C["white3"], bg=C["panel"]
        )
        self._lp_badge.pack(side="left")
        self._lp_pinned = tk.BooleanVar(value=True)

        def _toggle_pin():
            self._lp_pinned.set(not self._lp_pinned.get())
            pop.attributes("-topmost", self._lp_pinned.get())
            pin_lbl.config(
                text="[ PIN:ON ]" if self._lp_pinned.get() else "[ PIN:OFF ]",
                fg=C["white"] if self._lp_pinned.get() else C["white3"],
            )

        pin_lbl = tk.Label(
            hdr,
            text="[ PIN:ON ]",
            font=("Courier New", 8),
            fg=C["white"],
            bg=C["panel"],
            cursor="hand2",
            padx=6,
        )
        pin_lbl.pack(side="right", padx=4)
        pin_lbl.bind("<Button-1>", lambda e: _toggle_pin())
        cl = tk.Label(
            hdr,
            text="[ ✕ ]",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
            padx=6,
        )
        cl.pack(side="right")
        cl.bind("<Button-1>", lambda e: self._popup_fadeout(pop))
        cl.bind("<Enter>", lambda e: ColorAnim.run(self.root, cl, "fg", C["white3"], C["red"], duration_ms=60))
        cl.bind("<Leave>", lambda e: ColorAnim.run(self.root, cl, "fg", C["red"], C["white3"], duration_ms=60))
        lf = tk.Frame(pop, bg=C["bg"])
        lf.pack(fill="both", expand=True)
        _sb = tk.Scrollbar(
            lf, bg=C["panel"], troughcolor=C["bg"], width=6, bd=0, highlightthickness=0
        )
        _sb.pack(side="right", fill="y")
        self._lp_cv = tk.Canvas(
            lf, bg=C["bg"], highlightthickness=0, yscrollcommand=_sb.set
        )
        self._lp_cv.pack(side="left", fill="both", expand=True)
        _sb.config(command=self._lp_cv.yview)
        self._lp_inner = tk.Frame(self._lp_cv, bg=C["bg"])
        self._lp_win = self._lp_cv.create_window(
            (0, 0), anchor="nw", window=self._lp_inner
        )
        self._lp_inner.bind(
            "<Configure>",
            lambda e: self._lp_cv.configure(scrollregion=self._lp_cv.bbox("all")),
        )
        self._lp_cv.bind(
            "<Configure>", lambda e: self._lp_cv.itemconfig(self._lp_win, width=e.width)
        )
        self._lp_cv.bind(
            "<MouseWheel>",
            lambda e: self._lp_cv.yview_scroll(
                -1 * (1 if e.delta > 0 else -1), "units"
            ),
        )
        self._lp_lines = []
        self._lp_active = -1
        self._lp_sync_job = None
        self._lp_populate()
        self._lp_sync_tick()
        pop.protocol(
            "WM_DELETE_WINDOW", lambda: (self._lp_cancel_sync(), self._popup_fadeout(pop))
        )

    def _lp_populate(self):
        title = self.now_title.cget("text").replace("…", "").strip()
        artist = self.now_artist.cget("text").strip()
        if not title or title in ("NO TRACK", "— NO TRACK —"):
            self._lp_set_lines(["— play a track to see lyrics —"], synced=False)
            return
        try:
            self._lp_track_lbl.config(text=f"{artist}  //  {title}")
        except Exception:
            pass
        # Use canonical key to avoid truncation mismatch on long titles
        key = self._current_lyrics_key or (
            artist.lower().strip(),
            title.lower().strip(),
        )
        synced = self._synced_cache.get(key)
        plain = self._lyrics_cache.get(key, "MISSING")
        source = self._source_cache.get(key, "")
        if synced:
            self._lp_load_synced(synced)
            try:
                self._lp_badge.config(
                    text=f"[ ◈ SYNCED  {source} ]" if source else "[ ◈ SYNCED ]"
                )
            except Exception:
                pass
        elif plain and plain != "MISSING":
            self._lp_set_lines(plain.splitlines(), synced=False)
            try:
                self._lp_badge.config(text=f"[ {source} ]" if source else "[ STATIC ]")
            except Exception:
                pass
        else:
            # None = stale in-flight; "MISSING" = never fetched — always re-kick
            self._lyrics_cache.pop(key, None)
            self._lp_set_lines(["[ Fetching lyrics… ]"], synced=False)
            self._fetch_lyrics(artist, title)

    def _lp_set_lines(self, lines, synced=False):
        self._lp_cancel_sync()
        try:
            for w in self._lp_inner.winfo_children():
                w.destroy()
        except Exception:
            return
        self._lp_lines = []
        self._lp_active = -1
        fn = ("Courier New", 11)
        fna = ("Courier New", 12, "bold")
        tk.Frame(self._lp_inner, bg=C["bg"], height=20).pack()
        for line in lines:
            text = line.strip()
            if not text:
                tk.Frame(self._lp_inner, bg=C["bg"], height=8).pack()
                continue
            lbl = tk.Label(
                self._lp_inner,
                text=text,
                font=fn,
                fg=C["white3"],
                bg=C["bg"],
                anchor="center",
                justify="center",
                wraplength=370,
                pady=4,
            )
            lbl.pack(fill="x", padx=24)
            lbl._font_normal = fn
            lbl._font_active = fna
        tk.Frame(self._lp_inner, bg=C["bg"], height=60).pack()
        try:
            self._lp_cv.yview_moveto(0)
            self._lp_badge.config(text="[ STATIC ]", fg=C["white3"])
        except Exception:
            pass

    def _lp_load_synced(self, synced_lines):
        self._lp_cancel_sync()
        try:
            for w in self._lp_inner.winfo_children():
                w.destroy()
        except Exception:
            return
        self._lp_lines = []
        self._lp_active = -1
        fn = ("Courier New", 11)
        fna = ("Courier New", 12, "bold")
        tk.Frame(self._lp_inner, bg=C["bg"], height=20).pack()
        for ms, text in synced_lines:
            text = text.strip()
            if not text:
                tk.Frame(self._lp_inner, bg=C["bg"], height=8).pack()
                continue
            lbl = tk.Label(
                self._lp_inner,
                text=text,
                font=fn,
                fg="#222222",
                bg=C["bg"],
                anchor="center",
                justify="center",
                wraplength=370,
                pady=4,
            )
            lbl.pack(fill="x", padx=24)
            lbl._font_normal = fn
            lbl._font_active = fna
            self._lp_lines.append((ms, lbl))
        tk.Frame(self._lp_inner, bg=C["bg"], height=60).pack()
        try:
            self._lp_cv.yview_moveto(0)
            self._lp_badge.config(text="[ ◈ SYNCED ]", fg=C["white3"])
        except Exception:
            pass

    def _lp_cancel_sync(self):
        if getattr(self, "_lp_sync_job", None):
            try:
                self.root.after_cancel(self._lp_sync_job)
            except Exception:
                pass
            self._lp_sync_job = None

    def _decrypt_lrc_line(self, lbl, final_text, steps=7):
        """Animate a lyric label as decrypting text — cipher noise → real chars."""
        import random as _r
        _glyphs = "▓░▒█▐▌╳◈◉01アイウエオΨΦΩ"
        def _step(i=0):
            try:
                if i >= steps:
                    lbl.config(text=final_text, fg=C["glow"])
                    return
                revealed = final_text[:int(len(final_text) * i / steps)]
                noise_len = len(final_text) - len(revealed)
                noise = "".join(_r.choice(_glyphs) for _ in range(noise_len))
                lbl.config(text=revealed + noise, fg=C["white2"])
                lbl.after(28, lambda: _step(i + 1))
            except Exception:
                pass
        _step()

    def _lp_sync_tick(self):
        try:
            if (
                not getattr(self, "_lyric_popup", None)
                or not self._lyric_popup.winfo_exists()
            ):
                return
        except Exception:
            return
        title = self.now_title.cget("text").replace("…", "").strip()
        artist = self.now_artist.cget("text").strip()
        try:
            if (
                self._lp_track_lbl.cget("text") != f"{artist}  //  {title}"
                and title
                and title not in ("NO TRACK", "— NO TRACK —")
            ):
                self._lp_populate()
        except Exception:
            pass
        timed = self._lp_lines
        if timed:
            pos_ms = self._get_pos_ms()
            active = -1
            for i, (ms, _) in enumerate(timed):
                if ms <= pos_ms:
                    active = i
                else:
                    break
            if active != self._lp_active:
                self._lp_active = active
                for i, (ms, lbl) in enumerate(timed):
                    try:
                        dist = i - active
                        if i == active:
                            # [11] Decrypt animation instead of instant highlight
                            self._decrypt_lrc_line(lbl, lbl.cget("text"))
                            lbl.config(font=lbl._font_active)
                        elif dist == 1:
                            lbl.config(fg=C["white3"], font=lbl._font_normal)
                        elif dist == 2:
                            lbl.config(fg="#555555", font=lbl._font_normal)
                        elif dist == -1:
                            lbl.config(fg="#444444", font=lbl._font_normal)
                        else:
                            lbl.config(fg="#222222", font=lbl._font_normal)
                    except Exception:
                        pass
                if 0 <= active < len(timed):
                    try:
                        _, lbl = timed[active]
                        lbl.update_idletasks()
                        y = 0
                        w = lbl
                        while w != self._lp_cv and w is not None:
                            y += w.winfo_y()
                            w = w.master
                        ch = self._lp_inner.winfo_height()
                        th = self._lp_cv.winfo_height()
                        if ch > th:
                            self._lp_cv.yview_moveto(
                                max(0.0, min(1.0, (y - th / 2) / ch))
                            )
                    except Exception:
                        pass
        self._lp_sync_job = self.root.after(80, self._lp_sync_tick)

    def _scroll_to_playing(self):
        if not hasattr(self, "track_list") or self.current_idx < 0:
            return
        try:
            if self.current_idx not in self._display_indices:
                return
            row = self._display_indices.index(self.current_idx)
            total = len(self._display_indices)
            if total == 0:
                return
            frac = row / total
            top, bot = self.track_list.yview()
            if frac < top or frac > bot:
                self.track_list.yview_moveto(max(0.0, frac - 0.1))
        except Exception:
            pass

    def _set_source_badge(self, source):
        """Update the source indicator badge in the player bar."""
        labels = {
            "library":   "",
            "spotify":   "[ SPOTIFY ]",
            "youtube":   "[ YOUTUBE ]",
            "soundcloud":"[ SOUNDCLOUD ]",
            "deezer":    "[ DEEZER ]",
            "archive":   "[ ARCHIVE ]",
            "bandcamp":  "[ BANDCAMP ]",
            "none":      "",
        }
        try:
            self.source_badge.config(text=labels.get(source, ""))
        except Exception:
            pass

    def _set_current_track_for_lyrics(self, artist, title):
        """Call at every track-change point. Stores the canonical (artist, title) key
        so lyrics lookups never use the truncated now_title label. Kicks the fetch."""
        key = (artist.lower().strip(), title.lower().strip())
        self._current_lyrics_key = key
        self._set_lyrics_badge("searching")
        self._fetch_lyrics(artist, title)

    def _set_lyrics_badge(self, state, source=""):
        """Update the lyrics availability badge in the player bar.
        state: 'searching' | 'synced' | 'plain' | 'none' | 'reset'
        """
        try:
            lbl = self.lyrics_badge_lbl
        except AttributeError:
            return
        if state == "reset" or state == "searching":
            lbl.config(text="[ LYR... ]", fg=C["white3"])
        elif state == "synced":
            lbl.config(text="[ ◈ SYNCED ]", fg=C["glow"])
        elif state == "plain":
            src_hint = f" {source}" if source else ""
            lbl.config(text=f"[ LYRICS{src_hint} ]", fg=C["white2"])
        elif state == "none":
            lbl.config(text="[ NO LYR ]", fg=C["white3"])

    def _set_logo_playing(self, playing):
        """Update sidebar logo and status indicator."""
        try:
            self._sidebar_logo.is_playing = playing
            if playing:
                self._sidebar_status_lbl.config(text="[ PLAYING ]", fg=C["glow"])
                ColorAnim.run(
                    self.root,
                    self._sidebar_status_lbl,
                    "fg",
                    C["glow"],
                    C["white2"],
                    duration_ms=800,
                )
            else:
                self._sidebar_status_lbl.config(text="[  IDLE  ]", fg=C["white3"])
        except Exception:
            pass

    def _cbtn(self, p, text, cmd, sz=14):
        # Signalis: control buttons have bracket wrapping, flat mono feel
        b = tk.Label(
            p,
            text=text,
            font=("Courier New", sz),
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
            padx=14,
            pady=8,
            relief="flat",
            bd=0,
        )
        b.pack(side="left", padx=4)

        def _press(e, w=b, c=cmd):
            orig = w.cget("text")
            w.config(text=f"[{orig}]", fg=C["glow"])
            w.after(80, lambda: w.config(text=w.cget("text").strip("[]"), fg=C["white"]))
            c()

        b.bind("<Button-1>", _press)
        b.bind(
            "<Enter>",
            lambda e, w=b: ColorAnim.run(
                self.root, w, "fg", w.cget("fg"), C["white"], duration_ms=40
            ),
        )
        b.bind(
            "<Leave>",
            lambda e, w=b: ColorAnim.run(
                self.root,
                w,
                "fg",
                C["white"],
                getattr(w, "_active_fg", C["white3"]),
                duration_ms=40,
            ),
        )
        return b

    # ── VIEW SWITCHING ────────────────────
    def _route_scroll(self, e):
        """Route mousewheel with smooth momentum."""
        try:
            wx = e.widget.winfo_rootx()
            sidebar_right = self._side_cv.winfo_rootx() + self._side_cv.winfo_width()
            if wx <= sidebar_right: return
        except Exception: pass
        v = self.view; widget = None
        try:
            if v in ("library","playlist"):   widget=self.track_list
            elif v=="queue":                  widget=self.queue_list
            elif v=="history":                widget=self._hist_cv
            elif v=="soundcloud":             widget=self.sc_list
            elif v=="youtube":                widget=self.yt_list
            elif v=="stream":
                src=getattr(self,"_stream_source","youtube")
                widget=self.yt_list if src=="youtube" else self.sc_list
            elif v=="albums":                 widget=self._alb_cv
            elif v=="lyrics":                 widget=self._lyrics_cv
            elif v=="help":                   widget=self._help_cv
        except Exception: pass
        if widget is not None: self._scroller.scroll(widget, e.delta)

    def _switch_view(self, view):
        if view == self.view and hasattr(self, "_fade_overlay"):
            return
        self.ui_sounds.play("tab_switch")
        self._active_tab_key = view  # track for FFT tab underline pulse

        def _do_switch():
            self.view = view
            for _attr in (
                "lib_frame",
                "queue_frame",
                "viz_frame",
                "lyrics_frame",
                "history_frame",
                "album_frame",
                "sp_frame",
                "sc_frame",
                "yt_frame",
                "dz_frame",
                "ia_frame",
                "bc_frame",
                "stream_frame",
                "claude_frame",
                "aidj_frame",
                "netstream_frame",
                "fx_frame",
                "help_frame",
            ):
                if hasattr(self, _attr):
                    try:
                        getattr(self, _attr).pack_forget()
                    except:
                        pass
            if view in ("library", "playlist"):
                self.lib_frame.pack(fill="both", expand=True)
                if view == "library":
                    self.view_title.config(text="ALL TRACKS")
                    self.active_playlist = None
                    self._clear_pl_actions()
                self._refresh_tracks()
            elif view == "queue":
                self.queue_frame.pack(fill="both", expand=True)
                self._refresh_queue()
            elif view == "visualizer":
                self.viz_frame.pack(fill="both", expand=True)
                if self._viz_job:
                    self.viz_cv.after_cancel(self._viz_job)
                self._viz_job = None
                self.viz_cv.after(50, self._viz_tick)
            elif view == "lyrics":
                self.lyrics_frame.pack(fill="both", expand=True)
                self._refresh_lyrics_view()
            elif view == "history":
                self.history_frame.pack(fill="both", expand=True)
                self._refresh_history_view()
            elif view == "albums":
                self.album_frame.pack(fill="both", expand=True)
                self._refresh_album_view()
            elif view == "spotify":
                self.sp_frame.pack(fill="both", expand=True)
                self._sp_refresh_view()
            elif view == "stream":
                if hasattr(self, "stream_frame"):
                    self.stream_frame.pack(fill="both", expand=True)
                    self._stream_refresh()
            elif view == "soundcloud":
                # legacy — redirect to stream tab on SC sub-view
                self.view = "stream"
                if hasattr(self, "stream_frame"):
                    self.stream_frame.pack(fill="both", expand=True)
                    self._stream_set_source("soundcloud")
            elif view == "youtube":
                # legacy — redirect to stream tab on YT sub-view
                self.view = "stream"
                if hasattr(self, "stream_frame"):
                    self.stream_frame.pack(fill="both", expand=True)
                    self._stream_set_source("youtube")
            elif view == "claude":
                self.claude_frame.pack(fill="both", expand=True)
            elif view == "aidj":
                if not hasattr(self, "aidj_frame"):
                    self._build_aidj_view()
                self.aidj_frame.pack(fill="both", expand=True)
                self._aidj_view.on_view_shown()
            elif view == "netstream":
                if not hasattr(self, "netstream_frame"):
                    self._build_netstream_view()
                self.netstream_frame.pack(fill="both", expand=True)
                self._netstream_view.on_view_shown()
            elif view == "fx":
                if not hasattr(self, "fx_frame"):
                    self._build_fx_view()
                self.fx_frame.pack(fill="both", expand=True)
                self._audiofx_view.on_view_shown()
            elif view == "help":
                self.help_frame.pack(fill="both", expand=True)
            self._update_tabs()

        if hasattr(self, "_fade_overlay"):
            self._fade_overlay.flash(_do_switch)
        else:
            _do_switch()

    def _open_playlist(self, name):
        def _do():
            self.active_playlist = name
            self.view = "playlist"
            self.view_title.config(text=f"▸ {name.upper()}")
            self._build_pl_actions(name)
            self.lib_frame.pack_forget()
            self.lib_frame.pack(fill="both", expand=True)
            self._refresh_tracks()
            self._update_tabs()

        if hasattr(self, "_fade_overlay"):
            self._fade_overlay.flash(_do)
        else:
            _do()

    def _clear_pl_actions(self):
        for w in self.pl_actions.winfo_children():
            w.destroy()

    def _build_pl_actions(self, name):
        self._clear_pl_actions()
        pa = tk.Label(
            self.pl_actions,
            text="▶ play all",
            font=FMS,
            fg=C["white2"],
            bg=C["bg"],
            cursor="hand2",
        )
        pa.pack(side="left", padx=6)
        pa.bind("<Button-1>", lambda e: self._play_playlist(name))
        pa.bind("<Enter>", lambda e: pa.config(fg=C["white"]))
        pa.bind("<Leave>", lambda e: pa.config(fg=C["white2"]))
        pd = tk.Label(
            self.pl_actions,
            text="delete",
            font=FMS,
            fg=C["red"],
            bg=C["bg"],
            cursor="hand2",
        )
        pd.pack(side="left", padx=6)
        pd.bind("<Button-1>", lambda e: self._del_playlist(name))

    # ── TRACK LIST ────────────────────────
    def _get_tracks(self):
        q = self.search_var.get().lower()
        if self.view == "playlist" and self.active_playlist:
            idxs = self.playlists.get(self.active_playlist, [])
            tracks = [(i, self.library[i]) for i in idxs if i < len(self.library)]
        else:
            tracks = list(enumerate(self.library))
        if q:
            tracks = [
                (i, t)
                for i, t in tracks
                if q in t["title"].lower()
                or q in t["artist"].lower()
                or q in t.get("album", "").lower()
            ]
        # Apply sort
        col = getattr(self, "_sort_col", None)
        rev = getattr(self, "_sort_rev", False)
        if col == "title":
            tracks.sort(key=lambda x: x[1]["title"].lower(), reverse=rev)
        elif col == "artist":
            tracks.sort(key=lambda x: x[1]["artist"].lower(), reverse=rev)
        elif col == "album":
            tracks.sort(key=lambda x: x[1].get("album", "").lower(), reverse=rev)
        elif col == "duration":
            tracks.sort(key=lambda x: x[1].get("duration", 0), reverse=rev)
        return tracks

    def _update_col_headers(self):
        """Update column header labels to show active sort indicator."""
        if not hasattr(self, "_col_lbls"):
            return
        col = getattr(self, "_sort_col", None)
        rev = getattr(self, "_sort_rev", False)
        _names = {
            "title": "TITLE",
            "artist": "ARTIST",
            "album": "ALBUM",
            "duration": "TIME",
        }
        for key, lbl in self._col_lbls.items():
            if key == col:
                arrow = " ▼" if rev else " ▲"
                lbl.config(text=_names[key] + arrow, fg=C["white"])
            else:
                lbl.config(text=_names[key], fg=C["white3"])

    def _refresh_tracks(self):
        if not hasattr(self, "track_list"):
            return
        # Skip full redraw if nothing changed — just update highlight colours
        if not getattr(self, "_tracks_dirty", True):
            self._tl_update_highlight()
            return
        self._tracks_dirty = False
        self.track_list.delete("all")
        self._display_indices = []
        tracks = self._get_tracks()
        n = len(tracks)
        self.count_lbl.config(text=f"{n} track{'s' if n != 1 else ''}")
        if not tracks:
            return

        RH = self._tl_row_h  # collapsed row height
        ZH = 54  # expanded (hover) row height
        ART = ZH - 6  # art thumbnail size when expanded
        W = max(self.track_list.winfo_width(), 400)
        hover = self._tl_hover_idx
        zoom_h = max(RH, min(ZH, getattr(self, "_tl_zoom_h", RH)))

        y = 0
        # Virtual scrolling: compute visible row range from scroll position
        # Only create canvas items for rows that are actually on-screen
        self.track_list.winfo_height() or 600
        scroll_top, scroll_bot = self.track_list.yview()
        total_est = len(tracks) * RH  # rough estimate for scroll bounds
        vis_top = int(scroll_top * total_est) - RH
        vis_bot = int(scroll_bot * total_est) + RH * 2

        for row, (lib_idx, t) in enumerate(tracks):
            self._display_indices.append(lib_idx)
            is_hover = row == hover
            is_sel = (lib_idx == self.current_idx) and not is_hover
            h = zoom_h if is_hover else RH

            # Skip rows entirely outside the visible viewport
            # Always include hovered and selected rows even if off-screen
            row_bot = y + h
            if not is_hover and not is_sel and (row_bot < vis_top or y > vis_bot):
                y += h
                continue

            # row background
            if is_sel:
                bg = C["select"]
            elif is_hover:
                bg = C["select2"]
            elif row % 2 == 1:
                bg = C["panel2"]
            else:
                bg = C["bg"]

            self.track_list.create_rectangle(
                0, y, W, y + h, fill=bg, outline="", tags=f"row{row}"
            )

            # Scanline overlay on selected row
            if is_sel:
                for sy in range(y, y + h, 3):
                    self.track_list.create_line(
                        0, sy, W, sy, fill=C["border"], width=1, tags=f"row{row}"
                    )

            # Left glow accent stripe
            if is_sel:
                self.track_list.create_rectangle(
                    0, y, 3, y + h, fill=C["glow"], outline="", tags=f"row{row}"
                )
            elif is_hover:
                self.track_list.create_rectangle(
                    0, y, 2, y + h, fill=C["border2"], outline="", tags=f"row{row}"
                )

            # art thumbnail (only when hovered and art exists)
            text_x = 8
            if is_hover:
                art_path = t.get("art_path", "")
                if art_path and Path(art_path).exists():
                    photo = self._tl_get_art(lib_idx, art_path, ART)
                    if photo:
                        cx = 4 + ART // 2
                        cy = y + h // 2
                        self.track_list.create_image(
                            cx, cy, image=photo, anchor="center"
                        )
                        text_x = ART + 10

            # track number — hex address format
            fg_num = C["white3"]
            self.track_list.create_text(
                text_x,
                y + h // 2,
                text=f"0x{row+1:03X}",
                anchor="w",
                font=("Courier New", 7),
                fill=fg_num,
            )
            text_x += 28

            # title
            fg_title = C["white"] if (is_sel or is_hover) else C["white2"]
            title = t["title"]
            max_title = 36 if not is_hover else 30
            if len(title) > max_title:
                title = title[: max_title - 1] + "…"
            self.track_list.create_text(
                text_x,
                y + h // 2,
                text=title,
                anchor="w",
                font=("Courier New", 9, "bold" if is_sel else ""),
                fill=fg_title,
            )

            # artist + album (shown on second line when hovered)
            if is_hover and h > RH + 4:
                artist = t.get("artist", "")[:28]
                album = t.get("album", "")[:22]
                sub = (
                    f"{artist}  —  {album}" if album and album != "Unknown" else artist
                )
                self.track_list.create_text(
                    text_x,
                    y + h // 2 + 13,
                    text=sub,
                    anchor="w",
                    font=("Courier New", 8),
                    fill=C["white3"],
                )
            else:
                artist = t.get("artist", "")[:22]
                self.track_list.create_text(
                    text_x + 260,
                    y + h // 2,
                    text=artist,
                    anchor="w",
                    font=("Courier New", 9),
                    fill=C["white3"],
                )

            # duration + BPM badge (right-aligned)
            dur = self._fmt(t.get("duration", 0))
            bpm_val = self._bpm_cache.get(t.get("path",""), 0)
            bpm_str = f"  {int(bpm_val)}bpm" if bpm_val > 0 else ""
            self.track_list.create_text(
                W - 12,
                y + h // 2,
                text=dur + bpm_str,
                anchor="e",
                font=("Courier New", 8),
                fill=C["white3"],
            )

            # playing indicator
            if is_sel:
                self.track_list.create_text(
                    W - 50,
                    y + h // 2,
                    text="▶",
                    anchor="e",
                    font=("Courier New", 8),
                    fill=C["white"],
                    tags=(f"row{row}", f"play_ind{row}"),
                )

            y += h

        total_h = y
        self.track_list.configure(scrollregion=(0, 0, W, total_h))

    def _tl_update_highlight(self):
        """Repaint only row background colors to reflect current_idx — no full redraw."""
        if getattr(self, "_closing", False):
            return
        try:
            if not self.track_list.winfo_exists():
                return
        except Exception:
            return
        if not hasattr(self, "_display_indices"):
            return
        RH = self._tl_row_h
        hover = self._tl_hover_idx
        zoom_h = max(RH, min(54, getattr(self, "_tl_zoom_h", RH)))
        y = 0
        playing_y = None
        playing_h = RH
        for row, lib_idx in enumerate(self._display_indices):
            is_hover = row == hover
            is_sel = (lib_idx == self.current_idx) and not is_hover
            h = zoom_h if is_hover else RH
            if is_sel:
                bg = C["select"]
                playing_y = y
                playing_h = h
            elif is_hover:
                bg = C["select2"]
            elif row % 2 == 1:
                bg = C["panel2"]
            else:
                bg = C["bg"]
            self.track_list.itemconfig(f"row{row}", fill=bg)
            # update ▶ indicator — delete old, redraw if selected
            self.track_list.delete(f"play_ind{row}")
            if is_sel:
                W = max(self.track_list.winfo_width(), 400)
                self.track_list.create_text(
                    W - 50,
                    y + h // 2,
                    text="▶",
                    anchor="e",
                    font=("Courier New", 8),
                    fill=C["white"],
                    tags=f"play_ind{row}",
                )
            y += h
        # [03] Radar sweep line on playing row
        self.track_list.delete("radar_sweep")
        if playing_y is not None and (self.engine.is_playing or self._sp_playing):
            W = max(self.track_list.winfo_width(), 400)
            sx = int(self._scan_x * W)
            self.track_list.create_line(
                sx, playing_y, sx, playing_y + playing_h,
                fill=C["glow"], width=1, tags="radar_sweep"
            )

    def _scan_tick(self):
        """Advance radar sweep across playing row."""
        if getattr(self, "_closing", False):
            return
        if not (self.engine.is_playing or self._sp_playing):
            self._scan_x = 0.0
            self._scan_job = None
            return
        self._scan_x = (self._scan_x + 0.005) % 1.0
        # Only update the highlight — skip full refresh
        if not getattr(self, "_closing", False):
            self._tl_update_highlight()
        self._scan_job = self.root.after(50, self._scan_tick)

    def _tl_get_art(self, lib_idx, art_path, size):
        """Return a cached PhotoImage for the track art, loading if needed."""
        key = (lib_idx, size)
        if key in self._tl_art_cache:
            return self._tl_art_cache[key]
        try:
            from PIL import Image, ImageTk

            img = Image.open(art_path).convert("RGBA").resize((size, size))
            photo = ImageTk.PhotoImage(img)
        except Exception:
            try:
                photo = tk.PhotoImage(file=art_path)
            except Exception:
                return None
        self._tl_art_cache[key] = photo
        return photo

    def _tl_row_at(self, canvas_y):
        """Return the display row index at a given canvas y coordinate."""
        if not self._display_indices:
            return -1
        RH = self._tl_row_h
        ZH = 54
        hover = self._tl_hover_idx
        zoom_h = max(RH, min(ZH, getattr(self, "_tl_zoom_h", RH)))
        y = 0
        for row in range(len(self._display_indices)):
            h = zoom_h if row == hover else RH
            if y <= canvas_y < y + h:
                return row
            y += h
        return -1

    def _tl_canvas_y(self, event):
        """Convert event.y to canvas coordinate accounting for scroll."""
        return self.track_list.canvasy(event.y)

    def _tl_on_motion(self, event):
        cy = self._tl_canvas_y(event)
        row = self._tl_row_at(cy)
        if row == self._tl_hover_idx:
            return
        self._tl_hover_idx = row
        # animate zoom
        if self._tl_zoom_job:
            self.root.after_cancel(self._tl_zoom_job)
            self._tl_zoom_job = None
        self._tl_zoom_h = self._tl_row_h
        self._tl_zoom_row = row
        self._tl_animate_zoom(row, expanding=True)

    def _tl_on_leave(self, event=None):
        if self._tl_hover_idx == -1:
            return
        self._tl_hover_idx = -1
        if self._tl_zoom_job:
            self.root.after_cancel(self._tl_zoom_job)
            self._tl_zoom_job = None
        self._tl_zoom_h = self._tl_row_h
        self._refresh_tracks()

    def _tl_animate_zoom(self, target_row, expanding=True):
        RH, ZH = self._tl_row_h, 54
        step = 6
        if expanding:
            self._tl_zoom_h = min(ZH, self._tl_zoom_h + step)
            done = self._tl_zoom_h >= ZH
        else:
            self._tl_zoom_h = max(RH, self._tl_zoom_h - step)
            done = self._tl_zoom_h <= RH
        self._refresh_tracks()
        if not done and self._tl_hover_idx == target_row:
            self._tl_zoom_job = self.root.after(
                12, lambda: self._tl_animate_zoom(target_row, expanding)
            )

    def _refresh_queue(self):
        """Render two-tier queue: manual 'Up Next' section then auto 'Playing From'."""
        for w in self.queue_inner.winfo_children():
            w.destroy()
        self._q_rows = []
        self._q_drag_data = None

        def _section_header(text, count, clear_cmd=None):
            row = tk.Frame(self.queue_inner, bg=C["bg"])
            row.pack(fill="x", pady=(10, 2))
            tk.Label(
                row,
                text=text,
                font=("Courier New", 8, "bold"),
                fg=C["white3"],
                bg=C["bg"],
            ).pack(side="left")
            if count > 0:
                tk.Label(
                    row,
                    text=f"[{count}]",
                    font=("Courier New", 8),
                    fg=C["white3"],
                    bg=C["bg"],
                ).pack(side="left", padx=6)
            if clear_cmd:
                lbl = tk.Label(
                    row,
                    text="clear",
                    font=("Courier New", 7),
                    fg=C["white3"],
                    bg=C["bg"],
                    cursor="hand2",
                )
                lbl.pack(side="right")
                lbl.bind("<Button-1>", lambda e: clear_cmd())
                lbl.bind("<Enter>", lambda e: lbl.config(fg=C["white"]))
                lbl.bind("<Leave>", lambda e: lbl.config(fg=C["white3"]))
            tk.Frame(self.queue_inner, bg=C["border"], height=1).pack(
                fill="x", pady=(0, 4)
            )

        def _track_row(
            lib_idx, section, idx_in_section, is_playing=False, is_upcoming=False
        ):
            if lib_idx >= len(self.library):
                return
            t = self.library[lib_idx]
            bg = C["select2"] if is_playing else C["bg"]
            fg = (
                C["white"]
                if is_playing
                else (C["white2"] if is_upcoming else C["white3"])
            )

            row = tk.Frame(self.queue_inner, bg=bg, cursor="hand2")
            row.pack(fill="x", ipady=3)

            # Hex queue position badge
            hex_pos = f"0x{idx_in_section:03X}"
            pos_lbl = tk.Label(
                row,
                text=hex_pos,
                font=("Courier New", 7),
                fg=C["white3"] if not is_playing else C["glow"],
                bg=bg,
                width=6,
                anchor="w",
            )
            pos_lbl.pack(side="left", padx=(6, 0))

            # Playing indicator
            ind = tk.Label(
                row,
                text="▶" if is_playing else ("▸" if is_upcoming and idx_in_section == 0 else " "),
                font=("Courier New", 8),
                fg=C["glow"],
                bg=bg,
                width=2,
            )
            ind.pack(side="left", padx=(2, 2))

            # Title + artist
            title = t["title"][:42]
            artist = t.get("artist", "")[:22]
            info = tk.Label(
                row,
                text=f"{title}  —  {artist}" if artist else title,
                font=FM,
                fg=fg,
                bg=bg,
                anchor="w",
            )
            info.pack(side="left", fill="x", expand=True)

            # Duration
            dur = t.get("duration", 0)
            if dur:
                tk.Label(
                    row,
                    text=f"{int(dur) // 60}:{int(dur) % 60:02d}",
                    font=FMS,
                    fg=C["white3"],
                    bg=bg,
                ).pack(side="right", padx=8)

            # Hover
            def _enter(e, r=row, i=info, d=dur):
                r.config(bg=C["select"])
                i.config(bg=C["select"])
                for c in r.winfo_children():
                    c.config(bg=C["select"])

            def _leave(e, r=row, b=bg, i=info):
                r.config(bg=b)
                i.config(bg=b)
                for c in r.winfo_children():
                    try:
                        c.config(bg=b)
                    except:
                        pass

            for w in (row, ind, info):
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)
                w.bind(
                    "<MouseWheel>",
                    lambda e: self.queue_canvas.yview_scroll(
                        int(-1 * (e.delta / 120)) * 3, "units"
                    ),
                )

            # Double-click to play
            def _dbl(e, s=section, i=idx_in_section):
                self._queue_item_activate(s, i)

            for w in (row, ind, info):
                w.bind("<Double-Button-1>", _dbl)

            # Right-click to remove
            def _rmenu(e, s=section, i=idx_in_section):
                m = tk.Menu(
                    self.root,
                    tearoff=0,
                    bg=C["panel"],
                    fg=C["white"],
                    font=FMS,
                    relief="flat",
                    bd=0,
                    activebackground=C["select"],
                    activeforeground=C["white"],
                )
                m.add_command(
                    label="Remove from queue", command=lambda: self._queue_remove(s, i)
                )
                m.tk_popup(e.x_root, e.y_root)

            for w in (row, ind, info):
                w.bind("<Button-3>", _rmenu)

            def _drag_press(e, sec=section, i=idx_in_section):
                self._q_drag_data = {
                    "section": sec,
                    "from_idx": i,
                    "target": i,
                    "start_y": e.y_root,
                    "moved": False,
                }

            def _drag_motion(e, sec=section):
                d = self._q_drag_data
                if not d or d["section"] != sec:
                    return
                if abs(e.y_root - d["start_y"]) > 4:
                    d["moved"] = True
                if not d["moved"]:
                    return
                try:
                    ey = e.y_root - self.queue_canvas.winfo_rooty()
                    canvas_y = self.queue_canvas.canvasy(ey)
                    section_rows = [
                        (idx, r) for (sc, idx, r) in self._q_rows if sc == sec
                    ]
                    best_idx = d["from_idx"]
                    for idx, r in section_rows:
                        if canvas_y < r.winfo_y() + (r.winfo_height() or 28) // 2:
                            best_idx = idx
                            break
                        best_idx = idx + 1
                    d["target"] = max(0, min(best_idx, len(section_rows)))
                    cw = self.queue_canvas.winfo_width() or 400
                    if section_rows:
                        ind_y = (
                            section_rows[d["target"]][1].winfo_y() - 1
                            if d["target"] < len(section_rows)
                            else section_rows[-1][1].winfo_y()
                            + (section_rows[-1][1].winfo_height() or 28)
                        )
                        if self._q_drop_ind is None:
                            self._q_drop_ind = self.queue_canvas.create_rectangle(
                                4,
                                ind_y,
                                cw - 4,
                                ind_y + 2,
                                fill=C["glow"],
                                outline="",
                                tags="drop_ind",
                            )
                        else:
                            self.queue_canvas.coords(
                                self._q_drop_ind, 4, ind_y, cw - 4, ind_y + 2
                            )
                        self.queue_canvas.tag_raise("drop_ind")
                except Exception:
                    pass

            def _drag_release(e, sec=section):
                d = self._q_drag_data
                if self._q_drop_ind is not None:
                    try:
                        self.queue_canvas.delete(self._q_drop_ind)
                    except Exception:
                        pass
                    self._q_drop_ind = None
                if not d or d["section"] != sec or not d.get("moved"):
                    self._q_drag_data = None
                    return
                from_i, to_i = d["from_idx"], d["target"]
                self._q_drag_data = None
                if from_i != to_i and from_i != to_i - 1:
                    self._queue_reorder(
                        sec, from_i, to_i if to_i < from_i else to_i - 1
                    )

            for w in (row, ind, info):
                w.bind("<ButtonPress-1>", _drag_press)
                w.bind("<B1-Motion>", _drag_motion)
                w.bind("<ButtonRelease-1>", _drag_release)
            self._q_rows.append((section, idx_in_section, row))

        # ── MANUAL "UP NEXT" section ──────────────────────────────────────
        _section_header(
            "UP NEXT",
            len(self._manual_queue),
            clear_cmd=self._clear_manual_queue if self._manual_queue else None,
        )
        if self._manual_queue:
            for i, li in enumerate(self._manual_queue):
                _track_row(li, "manual", i, is_upcoming=True)
        else:
            _idle = tk.Label(
                self.queue_inner,
                text="  [ QUEUE EMPTY — AWAITING TRANSMISSION ]",
                font=("Courier New", 7),
                fg=C["white3"],
                bg=C["bg"],
            )
            _idle.pack(anchor="w", padx=8, pady=4)
            _msgs = [
                "  [ QUEUE EMPTY — AWAITING TRANSMISSION ]",
                "  [ NO SIGNAL — RIGHT-CLICK TRACK TO QUEUE ]",
                "  [ BUFFER CLEAR — STANDING BY ]",
                "  [ QUEUE EMPTY — AWAITING TRANSMISSION ]",
            ]
            _mi = [0]
            def _cycle_idle():
                try:
                    if not _idle.winfo_exists():
                        return
                    _mi[0] = (_mi[0] + 1) % len(_msgs)
                    _idle.config(text=_msgs[_mi[0]])
                    _idle.after(2200, _cycle_idle)
                except Exception:
                    pass
            _idle.after(2200, _cycle_idle)

        # ── AUTO "PLAYING FROM" section ───────────────────────────────────
        _section_header("PLAYING FROM", len(self.queue))
        if self.queue:
            for pos, li in enumerate(self.queue):
                _track_row(li, "auto", pos, is_playing=(pos == self.queue_pos))
        else:
            _idle2 = tk.Label(
                self.queue_inner,
                text="  [ NO ACTIVE SOURCE — SYS::STANDBY ]",
                font=("Courier New", 7),
                fg=C["white3"],
                bg=C["bg"],
            )
            _idle2.pack(anchor="w", padx=8, pady=4)
            _msgs2 = [
                "  [ NO ACTIVE SOURCE — SYS::STANDBY ]",
                "  [ PLAY ANY TRACK TO POPULATE ]",
                "  [ AUDIO ENGINE IDLE — 0 TRACKS LOADED ]",
                "  [ NO ACTIVE SOURCE — SYS::STANDBY ]",
            ]
            _mi2 = [0]
            def _cycle_idle2():
                try:
                    if not _idle2.winfo_exists():
                        return
                    _mi2[0] = (_mi2[0] + 1) % len(_msgs2)
                    _idle2.config(text=_msgs2[_mi2[0]])
                    _idle2.after(2800, _cycle_idle2)
                except Exception:
                    pass
            _idle2.after(2800, _cycle_idle2)

        self.queue_canvas.update_idletasks()
        self.queue_canvas.configure(scrollregion=self.queue_canvas.bbox("all"))

    # ── PLAYLISTS ─────────────────────────
    def _create_playlist(self):
        dlg = tk.Toplevel(self.root)
        content, _close = self._popup_setup(dlg, "SYS::NEW PLAYLIST", w=320, h=160)

        tk.Label(content, text="PLAYLIST NAME", font=FM, fg=C["white3"], bg=C["bg"]).pack(pady=(16, 6))
        var = tk.StringVar()
        e = tk.Entry(
            content,
            textvariable=var,
            font=FM,
            bg=C["panel"],
            fg=C["white"],
            insertbackground=C["white"],
            relief="flat",
            bd=4,
            width=28,
        )
        e.pack()
        e.focus()

        def ok():
            n = var.get().strip()
            if n and n not in self.playlists:
                self.playlists[n] = []
                self._save()
                self._refresh_pl_sidebar()
            self._popup_fadeout(dlg)

        b = tk.Label(content, text="CREATE", font=FM, fg=C["white3"], bg=C["panel"],
                     cursor="hand2", padx=12, pady=4)
        b.pack(pady=10)
        b.bind("<Button-1>", lambda e: ok())
        b.bind("<Enter>", lambda ev: ColorAnim.run(self.root, b, "fg", C["white3"], C["white"], duration_ms=60))
        b.bind("<Leave>", lambda ev: ColorAnim.run(self.root, b, "fg", C["white"], C["white3"], duration_ms=60))
        e.bind("<Return>", lambda e: ok())

    def _del_playlist(self, name):
        if messagebox.askyesno("Delete", f'Delete playlist "{name}"?'):
            del self.playlists[name]
            self._save()
            self._refresh_pl_sidebar()
            self._switch_view("library")

    def _play_playlist(self, name):
        idxs = self.playlists.get(name, [])
        if idxs:
            self.queue = list(idxs)
            self.queue_pos = 0
            self._play_item(0)

    def _add_to_pl_dialog(self, lib_idx):
        if not self.playlists:
            messagebox.showinfo("No Playlists", "Create a playlist first.")
            return
        dlg = tk.Toplevel(self.root)
        content, _close = self._popup_setup(dlg, "SYS::ADD TO PLAYLIST", w=260, h=220)

        tk.Label(content, text="SELECT PLAYLIST", font=FM, fg=C["white3"], bg=C["bg"]).pack(pady=(12, 6))
        lb = tk.Listbox(
            content,
            bg=C["panel"],
            fg=C["white2"],
            font=FM,
            selectbackground=C["select"],
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        lb.pack(fill="both", expand=True, padx=12)
        for n in self.playlists:
            lb.insert("end", n)

        def add():
            s = lb.curselection()
            if s:
                n = lb.get(s[0])
                if lib_idx not in self.playlists[n]:
                    self.playlists[n].append(lib_idx)
                    self._save()
            self._popup_fadeout(dlg)

        b = tk.Label(content, text="ADD", font=FM, fg=C["white3"], bg=C["panel"],
                     cursor="hand2", padx=12, pady=4)
        b.pack(pady=8)
        b.bind("<Button-1>", lambda e: add())
        b.bind("<Enter>", lambda ev: ColorAnim.run(self.root, b, "fg", C["white3"], C["white"], duration_ms=60))
        b.bind("<Leave>", lambda ev: ColorAnim.run(self.root, b, "fg", C["white"], C["white3"], duration_ms=60))

    # ── FILE IMPORT ───────────────────────
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Add Audio Files",
            filetypes=[
                (
                    "Audio Files",
                    "*.mp3 *.flac *.wav *.ogg *.m4a *.aac *.wma *.opus *.webm",
                ),
                ("MP3 Files", "*.mp3"),
                ("FLAC Files", "*.flac"),
                ("WAV Files", "*.wav"),
                ("All Files", "*.*"),
            ],
        )
        if paths:
            self._import(list(paths))

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select Music Folder")
        if folder:
            AUDIO_EXT = {".mp3", ".flac", ".wav", ".ogg", ".m4a", ".aac", ".wma"}
            paths = [
                str(p) for p in Path(folder).rglob("*") if p.suffix.lower() in AUDIO_EXT
            ]
            self._import(paths)

    def _import(self, paths):
        existing = {t["path"] for t in self.library}
        new_paths = [p for p in paths if p not in existing]
        if not new_paths:
            self._set_status("NO NEW FILES")
            return
        total = len(new_paths)
        # For small imports, process synchronously; for large ones, use a thread
        if total <= 20:
            self._import_batch(new_paths)
        else:
            self.status_lbl.config(text=f"[ IMPORTING {total} FILES… ]")

            def _worker():
                self._import_batch(new_paths, progress=True)

            threading.Thread(target=_worker, daemon=True).start()

    def _import_batch(self, paths, progress=False):
        """Process a list of new (non-duplicate) paths into the library."""
        added = 0
        total = len(paths)
        for i, p in enumerate(paths):
            try:
                m = self.engine.get_metadata(p)
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
            except Exception:
                pass
            if progress and (i + 1) % 10 == 0:
                self.root.after(
                    0,
                    lambda n=i + 1, t=total: self.status_lbl.config(
                        text=f"[ {n}/{t} ]"
                    ),
                )
        self._save()
        self._tracks_dirty = True
        self.root.after(0, self._refresh_tracks)
        self.root.after(0, lambda: self.status_lbl.config(text=f"[+{added} TRACKS]"))
        # Kick off background BPM/mood + loudness analysis for newly added tracks
        def _analyse_new():
            import time as _t
            for i, t in enumerate(self.library):
                p = t.get("path", "")
                if not p:
                    continue
                if p not in self._bpm_cache:
                    self._analyse_track(p, i)
                    _t.sleep(0.08)
                if "gain_db" not in t:
                    self._measure_loudness(p, i)
                    _t.sleep(0.08)
        threading.Thread(target=_analyse_new, daemon=True).start()

    # ── PLAYBACK ──────────────────────────
    def _on_dbl(self, event):
        cy = self.track_list.canvasy(event.y)
        row = self._tl_row_at(cy)
        if row < 0 or row >= len(self._display_indices):
            return
        lib_idx = self._display_indices[row]
        self.queue = list(self._display_indices)
        self.queue_pos = self.queue.index(lib_idx)
        self._play_item(self.queue_pos, force=True)

    def _queue_reorder(self, section, from_idx, to_idx):
        lst = self._manual_queue if section == "manual" else self.queue
        if from_idx < 0 or from_idx >= len(lst):
            return
        to_idx = max(0, min(to_idx, len(lst) - 1))
        if from_idx == to_idx:
            return
        item = lst.pop(from_idx)
        lst.insert(to_idx, item)
        if section == "auto":
            p = self.queue_pos
            if from_idx == p:
                self.queue_pos = to_idx
            elif from_idx < p <= to_idx:
                self.queue_pos -= 1
            elif to_idx <= p < from_idx:
                self.queue_pos += 1
        self._refresh_queue()

    def _on_queue_dbl(self, event):
        """Double-click on queue canvas — delegate to _queue_item_activate."""
        try:
            canvas_y = self.queue_list.canvasy(event.y)
            RH = 36  # matches queue row height
            idx = int(canvas_y // RH)
            n_manual = len(self._manual_queue)
            if idx < n_manual:
                self._queue_item_activate("manual", idx)
            else:
                auto_idx = idx - n_manual
                if 0 <= auto_idx < len(self.queue):
                    self._queue_item_activate("auto", auto_idx)
        except Exception:
            pass

    def _queue_item_activate(self, section, idx):
        """Double-click handler for queue rows."""
        if section == "manual":
            if 0 <= idx < len(self._manual_queue):
                li = self._manual_queue.pop(idx)
                insert_at = (self.queue_pos + 1) if self.queue_pos >= 0 else 0
                self.queue.insert(insert_at, li)
                self.queue_pos = insert_at
                self._play_item(self.queue_pos, force=True)
                self._refresh_queue()
        else:
            self._play_item(idx, force=True)
            self._refresh_queue()

    def _queue_remove(self, section, idx):
        """Right-click remove from queue."""
        if section == "manual":
            if 0 <= idx < len(self._manual_queue):
                self._manual_queue.pop(idx)
                self._refresh_queue()
        else:
            if 0 <= idx < len(self.queue):
                if idx < self.queue_pos:
                    self.queue_pos -= 1
                elif idx == self.queue_pos:
                    self.queue_pos = max(0, self.queue_pos - 1)
                self.queue.pop(idx)
                self._refresh_queue()

    def _clear_manual_queue(self):
        self._manual_queue = []
        self._refresh_queue()

    def _play_item(self, pos, force=False):
        if not self.queue or pos < 0 or pos >= len(self.queue):
            return
        self.queue_pos = pos
        lib_idx = self.queue[pos]
        if lib_idx >= len(self.library):
            return
        track = self.library[lib_idx]
        self.current_idx = lib_idx

        xfade = int(self.settings.get("crossfade_sec", 0))
        if xfade > 0 and self.engine.is_playing and not force:
            self._start_crossfade(
                xfade, lambda: self._do_load_track(track, user_initiated=False)
            )
            return
        if self._xfade_job:
            try:
                self.root.after_cancel(self._xfade_job)
            except Exception:
                pass
            self._xfade_job = None
        self._xfade_fading_in = False
        self._xfade_loading = False
        self.engine._volume = self.engine.volume
        self._do_load_track(track, user_initiated=force)

    def _do_load_track(self, track, user_initiated=False):
        """Actually load + play a track. EQ runs async."""
        play_path = track["path"]
        eq_preset = self.settings.get("eq_preset", "flat")
        prev_tmp = getattr(self, "_eq_tmp_path", None)
        if prev_tmp:
            try:
                os.unlink(prev_tmp)
            except:
                pass
        self._eq_tmp_path = None

        self._stop_all_sources()
        # Reset to silence rather than None so the hold-and-decay path runs during
        # the FFT startup gap instead of falling through to the sine-wave simulation.
        # This stops the "plays on its own" ghost animation between tracks.
        self._viz_last_real_bars = [0.0] * 48
        self._viz_bars = [0.0] * 48
        self._waveform_data    = None  # clear stale waveform
        self._wf_cached_size   = None  # force rebuild on new track
        self._wf_img_played    = None
        self._wf_arr_played    = None
        self._wf_arr_unplayed  = None
        self._wf_photo         = None
        self._wf_canvas_img    = None
        self._prog_last_x      = -1
        if hasattr(self, "_stop_fft_file_decoder"):
            self._stop_fft_file_decoder()
        self._active_source = "library"
        self._set_source_badge("library")
        self._playback_speed = 1.0
        if hasattr(self, "_speed_lbl"):
            self._speed_lbl.config(text="1.0×")
        t = track["title"]
        self._anim_label_change(self.now_title, (t[:36] + "…") if len(t) > 37 else t)
        self._anim_label_change(self.now_artist, track.get("artist", ""))
        self._anim_label_change(self.now_album, track.get("album", ""))

        # ── Cyberui: pulse node graph + push to status matrix ─────────────
        try:
            if hasattr(self, "_node_graph"):
                bpm = self._bpm_cache.get(track.get("path", ""), 120)
                self._node_graph.pulse(float(bpm))
        except Exception:
            pass
        try:
            if hasattr(self, "_beat_pulse"):
                self._beat_pulse.fire(intensity=0.9)
        except Exception:
            pass
        try:
            if hasattr(self, "_data_burst"):
                self._data_burst.burst(n=12)
        except Exception:
            pass
        try:
            if hasattr(self, "_status_matrix"):
                artist = track.get("artist", "")
                label  = f"{t[:28]}  {('— ' + artist[:20]) if artist else ''}"
                self._status_matrix.push(f"TRACK: {label}")
        except Exception:
            pass
        if hasattr(self, "viz_track_lbl"):
            self.viz_track_lbl.config(
                text=f"▶  {t[:40]}  —  {track.get('artist', '')[:24]}"
            )
        self.lbl_tot.config(text=self._fmt(track.get("duration", 0)))
        self.btn_play.config(text="⏸")
        loaded = self.engine.load(play_path)
        if loaded:
            self._current_play_path = play_path
            # Set duration immediately from library metadata so seekbar works
            # right away — the async _read_duration thread will refine it if needed
            if track.get("duration", 0) > 0:
                self.engine.duration = float(track["duration"])
        played = loaded and self.engine.play()
        if eq_preset not in ("flat", "") and SCIPY_AVAILABLE and loaded and played:
            _raw = play_path

            def _eq_bg(_r=_raw, _ep=eq_preset):
                import tempfile

                fd, tmp = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                if EQProcessor.process(_r, _ep, tmp):
                    self.root.after(0, lambda t=tmp, r=_r: _eq_swap(t, r))
                else:
                    try:
                        os.unlink(tmp)
                    except:
                        pass

            def _eq_swap(tmp, raw):
                if self._current_play_path != raw:
                    try:
                        os.unlink(tmp)
                    except:
                        pass
                    return
                pos = self.engine.get_position()
                self.engine.load(tmp)
                self.engine.play(start_ms=int(pos * 1000))
                self._current_play_path = tmp
                self._eq_tmp_path = tmp

            threading.Thread(target=_eq_bg, daemon=True).start()
        elif eq_preset not in ("flat", "") and not SCIPY_AVAILABLE:
            self._set_status("EQ N/A — pip install scipy soundfile")
        if loaded and played:
            self.wavevis.set_active(True)
            self._set_logo_playing(True)
            self._set_status("PLAYING")
            # [03] Start radar sweep
            self._scan_x = 0.0
            if not getattr(self, "_scan_job", None):
                self._scan_job = self.root.after(100, self._scan_tick)
            # [01] Decode waveform async
            self._waveform_data = None
            _wf_path = track["path"]
            def _decode_waveform(p=_wf_path):
                try:
                    import wave
                    import struct
                    with wave.open(p, "rb") as wf:
                        n_frames = wf.getnframes()
                        n_ch = wf.getnchannels()
                        sw = wf.getsampwidth()
                        raw = wf.readframes(n_frames)
                    fmt = {1: "b", 2: "h", 4: "i"}.get(sw, "h")
                    samples = struct.unpack(f"{len(raw)//sw}{fmt}", raw)
                    if n_ch > 1:
                        samples = samples[::n_ch]
                    N = 300
                    chunk = max(1, len(samples) // N)
                    pts = []
                    peak = max(abs(s) for s in samples) or 1
                    for i in range(N):
                        sl = samples[i*chunk:(i+1)*chunk]
                        pts.append(max(abs(s) for s in sl) / peak if sl else 0.0)
                    self.root.after(0, lambda d=pts: setattr(self, "_waveform_data", d))
                except Exception:
                    try:
                        import soundfile as _sf
                        data, sr = _sf.read(p, always_2d=True)
                        mono = data[:, 0]
                        N = 300
                        chunk = max(1, len(mono) // N)
                        peak = max(abs(mono)) or 1.0
                        pts = [float(max(abs(mono[i*chunk:(i+1)*chunk])) / peak)
                               for i in range(N)]
                        self.root.after(0, lambda d=pts: setattr(self, "_waveform_data", d))
                    except Exception:
                        pass
            threading.Thread(target=_decode_waveform, daemon=True).start()

            # ── Album art async ──
            self._art_url_last = None
            self._art_crt_flash()  # CRT input-switch flash

            def _load_art_bg(t=track):
                _loaded = False
                art_path = t.get("art_path", "")
                if art_path:
                    try:
                        data = Path(art_path).read_bytes()
                        self.root.after(0, lambda d=data: self._load_art_bytes(d))
                        _loaded = True
                    except Exception:
                        pass
                if not _loaded:
                    try:
                        from mutagen.id3 import ID3

                        tags = ID3(t["path"])
                        for tag in tags.values():
                            if hasattr(tag, "data") and tag.data:
                                data = tag.data
                                self.root.after(
                                    0, lambda d=data: self._load_art_bytes(d)
                                )
                                _loaded = True
                                break
                    except Exception:
                        pass
                if not _loaded:
                    self.root.after(
                        0,
                        lambda: self._fetch_art_musicbrainz(
                            t.get("artist", ""), t.get("title", "")
                        ),
                    )

            threading.Thread(target=_load_art_bg, daemon=True).start()

            # ── History ──
            self._history_add(track)

            # ── Last.fm ──
            if (
                self._scrobbler
                and self.settings.get("lastfm_enabled")
                and self._scrobbler.ready
            ):
                self._scrobbler.track_started(track)
                self._schedule_scrobble()

            # ── Discord RPC ──
            if self._discord_enabled:
                threading.Thread(
                    target=lambda: self._discord.set_activity(
                        track.get("title", ""),
                        track.get("artist", ""),
                        elapsed_s=0,
                        duration_s=track.get("duration", 0),
                    ),
                    daemon=True,
                ).start()

            # ── Waveform seekbar ──
            self._load_waveform(play_path)

            # ── Lyrics + mini player ──
            self._set_current_track_for_lyrics(track.get("artist", ""), t)
            self._mini_update()
            if getattr(self, "_flow_mode", False):
                self._flow_enqueue(track)
            if getattr(self, "_smart_skip_on", False):
                if self._skip_counts.get(track["path"], 0) >= 3:
                    self.root.after(200, self._next)
                    return
            self._start_lyric_ticker()
            self._update_context_sidebar(track)
            if not user_initiated:
                self.root.after(300, lambda: self._show_track_notification(track))
            self.root.after(0, self._refresh_tracks)
            self.root.after(50, self._scroll_to_playing)
            threading.Thread(
                target=lambda p=play_path: self._start_fft_file_decoder(p), daemon=True
            ).start()
            # BPM + mood analysis (background, only if not already cached)
            if play_path not in self._bpm_cache:
                threading.Thread(
                    target=lambda p=play_path, i=self.current_idx: self._analyse_track(p, i),
                    daemon=True
                ).start()
            # Apply replay gain normalization if enabled
            if self.settings.get("normalize") and "gain_db" in track:
                self._apply_replay_gain(track["gain_db"])
        else:
            self._active_source = "none"
            self._set_source_badge("none")
            self._set_status("LOAD FAILED")
            fname = Path(play_path).name
            self.now_title.config(text="⚠  LOAD FAILED")
            self.now_artist.config(text=fname[:50])
            self.now_album.config(text="")
            err = getattr(self.engine, "_last_error", "")
            if not getattr(self.engine, "_pygame", None):
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
        self._tl_update_highlight()
        if self.view == "queue":
            self._refresh_queue()

    def _anim_label_change(self, widget, new_text, base_col=None):
        """Fade label out, glitch 3 frames of corrupted text, then resolve to new title."""
        if base_col is None:
            base_col = widget.cget("fg")

        _glitch_chars = "█▓░▒▐▌╳╬◼◻"

        def _corrupt(text):
            import random as _r
            chars = list(text)
            for i in _r.sample(range(len(chars)), min(3, max(1, len(chars) // 3))):
                chars[i] = _r.choice(_glitch_chars)
            return "".join(chars)

        def _do_glitch():
            # 3 rapid glitch frames at 40ms each, then resolve
            frames = [_corrupt(new_text), _corrupt(new_text), new_text]
            def _gf(i=0):
                try:
                    widget.config(text=frames[i], fg=C["white2"] if i < 2 else base_col)
                except Exception:
                    pass
                if i < len(frames) - 1:
                    widget.after(40, lambda: _gf(i + 1))
                else:
                    ColorAnim.run(self.root, widget, "fg", C["white2"], base_col, duration_ms=100)
            _gf()

        ColorAnim.run(
            self.root,
            widget,
            "fg",
            base_col,
            C["bg"],
            duration_ms=80,
            on_done=_do_glitch,
        )

    def _show_track_notification(self, track):
        if not self.settings.get("show_notifications", True):
            return
        if getattr(self, "_notif_win", None):
            try:
                if self._notif_dismiss_job:
                    self.root.after_cancel(self._notif_dismiss_job)
                self._notif_win.destroy()
            except Exception:
                pass
            self._notif_win = None
            self._notif_dismiss_job = None
        try:
            import time as _t2

            W, H = 300, 74
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            win = tk.Toplevel(self.root)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(bg=C["bg"])
            win.geometry(f"{W}x{H}+{sw - W - 18}+{sh - H - 52}")
            self._notif_win = win
            outer = tk.Frame(win, bg=C["border2"], padx=1, pady=1)
            outer.pack(fill="both", expand=True)
            inner = tk.Frame(outer, bg=C["bg"])
            inner.pack(fill="both", expand=True)
            tk.Frame(inner, bg=C["glow"], width=3).pack(side="left", fill="y")
            body = tk.Frame(inner, bg=C["bg"])
            body.pack(side="left", fill="both", expand=True, padx=(8, 6), pady=6)
            hdr = tk.Frame(body, bg=C["bg"])
            hdr.pack(fill="x")
            tk.Label(
                hdr,
                text="▸ NOW PLAYING",
                font=("Courier New", 8, "bold"),
                fg=C["white3"],
                bg=C["bg"],
            ).pack(side="left")
            cl = tk.Label(
                hdr,
                text="✕",
                font=("Courier New", 7),
                fg=C["white3"],
                bg=C["bg"],
                cursor="hand2",
            )
            cl.pack(side="right")
            cl.bind("<Button-1>", lambda e: self._dismiss_notification())
            cl.bind("<Enter>", lambda e: cl.config(fg=C["white"]))
            cl.bind("<Leave>", lambda e: cl.config(fg=C["white3"]))
            title = track.get("title", "Unknown")
            artist = track.get("artist", "")
            tk.Label(
                body,
                text=(title[:32] + "…") if len(title) > 33 else title,
                font=("Courier New", 9, "bold"),
                fg=C["white"],
                bg=C["bg"],
                anchor="w",
            ).pack(fill="x")
            if artist:
                tk.Label(
                    body,
                    text=(artist[:38] + "…") if len(artist) > 39 else artist,
                    font=("Courier New", 7),
                    fg=C["white2"],
                    bg=C["bg"],
                    anchor="w",
                ).pack(fill="x")
            prog_cv = tk.Canvas(win, bg=C["bg"], height=2, highlightthickness=0)
            prog_cv.pack(fill="x", side="bottom")
            prog_fill = prog_cv.create_rectangle(
                0, 0, W, 2, fill=C["white3"], outline=""
            )
            for w in (win, outer, inner, body):
                w.bind("<Button-1>", lambda e: self._dismiss_notification())
            win.update_idletasks()
            win.attributes("-alpha", 0.01)
            win.lift()
            win.update_idletasks()

            def _fade_in(a=0.01):
                a = min(round(a + 0.10, 2), 0.93)
                try:
                    if not win.winfo_exists():
                        return
                    win.attributes("-alpha", a)
                except Exception:
                    return
                if a < 0.93:
                    self.root.after(18, lambda: _fade_in(a))

            _t0 = [_t2.time()]
            _dur = 4.5

            def _prog():
                try:
                    if not win.winfo_exists():
                        return
                    r = max(0.0, 1.0 - (_t2.time() - _t0[0]) / _dur)
                    cw = prog_cv.winfo_width() or W
                    prog_cv.coords(prog_fill, 0, 0, int(cw * r), 2)
                    if r > 0:
                        self.root.after(50, _prog)
                except Exception:
                    pass

            self.root.after(10, _fade_in)
            self.root.after(60, _prog)
            self._notif_dismiss_job = self.root.after(
                int(_dur * 1000), self._dismiss_notification
            )
        except Exception as ex:
            print(f"[notif] {ex}")

    def _dismiss_notification(self):
        win = getattr(self, "_notif_win", None)
        if not win:
            return
        if getattr(self, "_notif_dismiss_job", None):
            try:
                self.root.after_cancel(self._notif_dismiss_job)
            except Exception:
                pass
            self._notif_dismiss_job = None

        def _fade_out(a=0.93):
            a = max(a - 0.15, 0.0)
            try:
                win.wm_attributes("-alpha", a)
            except Exception:
                self._notif_win = None
                return
            if a > 0:
                self.root.after(16, lambda: _fade_out(a))
            else:
                try:
                    win.destroy()
                except Exception:
                    pass
                self._notif_win = None

        _fade_out()

    def _show_ghost(self, text):
        """Flash a ghost HUD label near the playerbar for 600ms then fade."""
        try:
            if self._ghost_job:
                self.root.after_cancel(self._ghost_job)
                self._ghost_job = None
            self._ghost_lbl.config(text=text, fg=C["white"])
            self._ghost_lbl.place(relx=0.5, rely=0.94, anchor="center")
            self._ghost_lbl.lift()
            ColorAnim.run(self.root, self._ghost_lbl, "fg", C["white"], C["panel"],
                          duration_ms=600, on_done=lambda: self._ghost_lbl.place_forget())
        except Exception:
            pass

    def _tick_clock(self):
        """Update the live clock and session uptime in the topbar every second."""
        try:
            import time as _t
            now = _t.strftime("%H:%M:%S")
            up_s = int(_t.time() - self._session_start)
            uh, rem = divmod(up_s, 3600)
            um, us_ = divmod(rem, 60)
            up_str = f"{uh:02d}:{um:02d}:{us_:02d}"
            self._clock_lbl.config(text=f"{now}  UP:{up_str}")
        except Exception:
            pass
        self.root.after(1000, self._tick_clock)

    def _boot_status_sequence(self):
        """Cycle boot messages on sidebar status label at startup."""
        _msgs = [
            "[ INIT ]",
            "[ LOADING MODULES ]",
            "[ AUDIO ENGINE READY ]",
            "[ IDLE ]",
        ]
        def _step(i=0):
            try:
                self._sidebar_status_lbl.config(text=_msgs[i])
            except Exception:
                return
            if i < len(_msgs) - 1:
                self.root.after(220, lambda: _step(i + 1))
            else:
                # settle into blinking cursor idle state
                self._blink_cursor()
        _step()

    def _tick_hex_addr(self):
        """Slowly mutate the fake hex address readout in the sidebar."""
        try:
            import random as _r
            vals = [_r.randint(0, 0xFFFF) for _ in range(3)]
            txt = "·".join(f"0x{v:04X}" for v in vals)
            self._hex_addr_lbl.config(text=txt)
        except Exception:
            pass
        self.root.after(2000, self._tick_hex_addr)

    def _blink_cursor(self):
        """Blink a trailing cursor on the sidebar status label when idle."""
        try:
            playing = self.engine.is_playing or self._sp_playing
            if playing:
                self._sidebar_status_lbl.config(text="[ PLAYING  ]")
                self.root.after(500, self._blink_cursor)
                return
            cur = self._sidebar_status_lbl.cget("text")
            if cur.endswith("▌"):
                self._sidebar_status_lbl.config(text="[  IDLE   ]")
            else:
                self._sidebar_status_lbl.config(text="[  IDLE  ▌]")
        except Exception:
            pass
        self.root.after(500, self._blink_cursor)

    def _set_status(self, text):
        """Typewrite status text char-by-char, then fade to white2."""
        try:
            if hasattr(self, "_status_type_job") and self._status_type_job:
                self.root.after_cancel(self._status_type_job)
                self._status_type_job = None
        except Exception:
            pass
        # Short messages resolve instantly
        if len(text) <= 6:
            self.status_lbl.config(text=f"[ {text} ]", fg=C["white"])
            ColorAnim.run(self.root, self.status_lbl, "fg", C["white"], C["white2"], duration_ms=800)
            return
        def _type(i=0):
            try:
                if i <= len(text):
                    self.status_lbl.config(
                        text=f"[ {text[:i]}{'▌' if i < len(text) else ''} ]",
                        fg=C["white"]
                    )
                    if i < len(text):
                        self._status_type_job = self.root.after(18, lambda: _type(i + 1))
                    else:
                        self._status_type_job = None
                        ColorAnim.run(self.root, self.status_lbl, "fg",
                                      C["white"], C["white2"], duration_ms=800)
            except Exception:
                pass
        _type()

    def _toggle_play(self):
        self.ui_sounds.play("play")
        if self._sp_mode or self._active_source == "spotify":
            self._sp_playpause()
            return
        # YouTube / SoundCloud / library all use the local engine
        if self.engine.is_playing:
            self.engine.pause()
            self.btn_play.config(text="▶")
            self.wavevis.set_active(False)
            self._set_logo_playing(False)
            self._set_status("PAUSED")
            self._mini_update()
        elif self.engine.is_paused:
            self.engine.unpause()
            self.btn_play.config(text="⏸")
            self.wavevis.set_active(True)
            self._set_logo_playing(True)
            self._set_status("PLAYING")
            self._mini_update()
            try:
                if hasattr(self, "_beat_pulse"):
                    self._beat_pulse.fire(intensity=0.6)
            except Exception:
                pass
        elif self.queue and self._active_source in ("library", "none"):
            self._play_item(max(0, self.queue_pos))

    def _next(self, force=False):
        if self._sp_mode or self._active_source == "spotify":
            threading.Thread(target=self.sp_api.next_track, daemon=True).start()
            return
        if self._active_source == "soundcloud":
            self._sc_skip(+1)
            return
        if self._active_source == "youtube":
            return
        if getattr(self, "_smart_skip_on", False):
            idx = self.current_idx
            if 0 <= idx < len(self.library):
                pos = self.engine.get_position()
                dur = self.engine.duration
                if dur > 0 and pos / dur < 0.35:
                    path = self.library[idx]["path"]
                    self._skip_counts[path] = self._skip_counts.get(path, 0) + 1
        # Drain manual queue first
        if self._manual_queue:
            next_idx = self._manual_queue.pop(0)
            # Insert at front of auto-queue (just past current pos) so _play_item works
            insert_at = (self.queue_pos + 1) if self.queue_pos >= 0 else 0
            self.queue.insert(insert_at, next_idx)
            self.queue_pos = insert_at
            self._play_item(self.queue_pos)
            if self.view == "queue":
                self._refresh_queue()
            return
        if not self.queue:
            return
        if self.shuffle:
            if len(self.queue) > 1:
                choices = [i for i in range(len(self.queue)) if i != self.queue_pos]
                self.queue_pos = random.choice(choices)
            else:
                self.queue_pos = 0
        else:
            self.queue_pos = (self.queue_pos + 1) % len(self.queue)
        self._play_item(self.queue_pos, force=force)

    def _prev(self, force=False):
        if self._sp_mode or self._active_source == "spotify":
            threading.Thread(target=self.sp_api.prev_track, daemon=True).start()
            return
        if self._active_source == "soundcloud":
            self._sc_skip(-1)
            return
        if self._active_source == "youtube":
            return
        if self.engine.get_position() > 5 and not force:
            self.engine.seek(0)
        else:
            self.queue_pos = (self.queue_pos - 1) % len(self.queue)
            self._play_item(self.queue_pos, force=force)

    def _seek_relative(self, delta_s):
        """
        Seek forward/backward by delta_s seconds.
        Debounced: accumulates keypresses, commits one seek 150ms after the
        last keypress. Never spawns more than one seek thread at a time.
        """
        if self._sp_mode and self._sp_dur_ms > 0:
            ms = max(0, min(self._sp_dur_ms,
                            self._sp_pos_ms + int(delta_s * 1000)))
            self._sp_pos_ms = ms
            self.lbl_cur.config(text=self._fmt(ms / 1000))
            job = getattr(self, "_seek_rel_sp_job", None)
            if job:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
            self._seek_rel_sp_job = self.root.after(
                150,
                lambda m=ms: threading.Thread(
                    target=lambda: self.sp_api.seek(m), daemon=True
                ).start(),
            )
            return

        # Get current position — use pos_cache if engine doesn't know yet
        cur_pos = self.engine.get_position()
        if cur_pos <= 0:
            cur_pos = getattr(self.engine, "_pos_cache", 0.0)

        # Duration — use lbl_tot as fallback if engine hasn't read it yet
        dur = self.engine.duration
        if dur <= 0:
            try:
                parts = self.lbl_tot.cget("text").strip().split(":")
                dur = int(parts[0]) * 60 + int(parts[1])
            except Exception:
                dur = 0

        # Still no duration — can't seek
        if dur <= 0:
            return

        # Accumulate: snapshot position on first keypress of a burst,
        # then add delta to the accumulator on each repeat
        if not getattr(self, "_seek_rel_active", False):
            self._seek_rel_base = cur_pos
            self._seek_rel_active = True

        self._seek_rel_base = max(0.0, min(float(dur),
                                           self._seek_rel_base + delta_s))
        target = self._seek_rel_base
        r = target / dur

        # Update UI immediately — feels responsive even while debouncing
        self.lbl_cur.config(text=self._fmt(target))
        self._prog_r_cur = r
        self._draw_prog(r)
        self.seeking = True
        self._set_status(f"{'→' if delta_s > 0 else '←'}  {self._fmt(target)}")

        # Cancel previous pending commit, schedule a new one
        job = getattr(self, "_seek_rel_job", None)
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass

        def _commit(t=target, rv=r):
            self._seek_rel_active = False
            self._seek_rel_base = t      # reset base to committed position
            self._seek_rel_job = None
            def _do():
                self.engine.seek(t)
                self.root.after(0, lambda: self._seek_done(rv))
            threading.Thread(target=_do, daemon=True).start()

        self._seek_rel_job = self.root.after(150, _commit)

    def _toggle_shuffle(self):
        self.shuffle = not self.shuffle
        col = C["glow"] if self.shuffle else C["white3"]
        self.btn_shuf._active_fg = col
        self.btn_shuf.config(fg=col)

    def _toggle_repeat(self):
        modes = ["off", "all", "one"]
        self.repeat_mode = modes[(modes.index(self.repeat_mode) + 1) % 3]
        icon = {"off": "↺", "all": "↺", "one": "↻"}[self.repeat_mode]
        col = C["white3"] if self.repeat_mode == "off" else C["glow"]
        self.btn_repeat._active_fg = col
        self.btn_repeat.config(text=icon, fg=col)
        # Show brief mode label next to the button
        mode_label = {"off": "repeat off", "all": "repeat all", "one": "repeat one"}[
            self.repeat_mode
        ]
        if hasattr(self, "_repeat_mode_lbl"):
            self._repeat_mode_lbl.config(text=mode_label, fg=col)
            job = getattr(self, "_repeat_mode_job", None)
            if job:
                try:
                    self.root.after_cancel(job)
                except Exception:
                    pass
        self._repeat_mode_job = self.root.after(
            1800,
            lambda: (
                self._repeat_mode_lbl.config(text="")
                if hasattr(self, "_repeat_mode_lbl")
                else None
            ),
        )

    def _clear_queue(self):
        self.queue = []
        self._manual_queue = []
        self.queue_pos = -1
        self._refresh_queue()

    # ── SEEK ──────────────────────────────
    def _seek_press(self, event):
        """Mark seeking on press; actual seek happens on release."""
        self.seeking = True
        w = self.prog_cv.winfo_width() or 1
        r = max(0, min(1, event.x / w))
        self._prog_r_cur = r  # snap immediately — no easing during seek
        self._draw_prog(r)
        # Update time label immediately for responsiveness
        if self._sp_mode and self._sp_dur_ms > 0:
            self._sp_pos_ms = int(r * self._sp_dur_ms)
            self.lbl_cur.config(text=self._fmt(self._sp_pos_ms / 1000))
        elif self.engine.duration > 0:
            self.lbl_cur.config(text=self._fmt(r * self.engine.duration))

    def _seek_drag(self, event):
        if not self.seeking:
            return
        w = self.prog_cv.winfo_width() or 1
        r = max(0, min(1, event.x / w))
        self._prog_r_cur = r  # snap immediately — no easing during drag
        self._draw_prog(r)
        # Update time label during drag
        if self._sp_mode and self._sp_dur_ms > 0:
            self._sp_pos_ms = int(r * self._sp_dur_ms)
            self.lbl_cur.config(text=self._fmt(self._sp_pos_ms / 1000))
        elif self.engine.duration > 0:
            self.lbl_cur.config(text=self._fmt(r * self.engine.duration))

    def _seek_end(self, event):
        if not self.seeking:
            return
        w = self.prog_cv.winfo_width() or 1
        r = max(0, min(1, event.x / w))
        self._prog_r_cur = r
        if self._sp_mode and self._sp_dur_ms > 0:
            self.seeking = False
            ms = int(r * self._sp_dur_ms)
            self._sp_pos_ms = ms
            self.lbl_cur.config(text=self._fmt(ms / 1000))
            threading.Thread(target=lambda: self.sp_api.seek(ms), daemon=True).start()
        else:
            # Get duration — prefer engine value, fall back to parsing the
            # time label which is always populated even if engine.duration is 0
            dur = self.engine.duration
            if dur <= 0:
                try:
                    txt = self.lbl_tot.cget("text")  # e.g. "3:45"
                    parts = txt.strip().split(":")
                    dur = int(parts[0]) * 60 + int(parts[1])
                except Exception:
                    dur = 0
            if dur <= 0:
                self.seeking = False
                return
            # Seed engine with duration so future seeks don't need this fallback
            if self.engine.duration <= 0:
                self.engine.duration = float(dur)
            target = r * dur
            self.lbl_cur.config(text=self._fmt(target))
            def _do_seek(t=target, rv=r):
                self.engine.seek(t)
                self.root.after(0, lambda: self._seek_done(rv))
            threading.Thread(target=_do_seek, daemon=True).start()

    def _seek_done(self, r):
        """Called on the main thread after engine.seek() completes."""
        self._prog_r_cur = r
        self._draw_prog(r)
        # Don't release seeking immediately — engine.get_position() takes a
        # few frames to settle after seek(), so _poll would read stale values
        # and snap the bar back.  Hold seeking=True for 3 more poll cycles
        # (300ms at 100ms poll rate) then release.
        self._seek_settle_r = r          # target ratio to hold during settle
        self._seek_settle_ticks = 3      # countdown
        self.seeking = False             # allow _poll to run, but with settle guard

    def _draw_prog(self, r):
        w = self.prog_cv.winfo_width()
        h = self.prog_cv.winfo_height() or 32
        if w < 2:
            return
        if not hasattr(self, "_prog_r_cur"):
            self._prog_r_cur = r
        if self.seeking or abs(r - self._prog_r_cur) > 0.05:
            self._prog_r_cur = r
        else:
            self._prog_r_cur += (r - self._prog_r_cur) * 0.25

        # Skip redraw if position pixel hasn't moved — saves a full waveform
        # composite per frame when the track is paused or nearly still
        new_x = int(self._prog_r_cur * w)
        last_x = getattr(self, "_prog_last_x", -1)
        if new_x == last_x and not self.seeking:
            return
        self._prog_last_x = new_x

        x = float(new_x)
        if getattr(self, "_waveform_data", None):
            self._draw_waveform_seekbar(w, h, x)
        else:
            # fallback plain bar
            self.prog_cv.coords(self.prog_fill, 0, 0, x, h)
            dot_r = 5 if getattr(self, "_prog_hover", False) or self.seeking else 4
            self.prog_cv.coords(self.prog_dot,
                x - dot_r, h // 2 - dot_r, x + dot_r, h // 2 + dot_r)

    def _draw_waveform_seekbar(self, w=None, h=None, x=None):
        """
        Render waveform seekbar. Two paths:
          • numpy available: pre-rendered pixel arrays composited per frame,
            pushed to canvas via PhotoImage.put() row strings. One canvas op.
          • numpy unavailable: falls back to original create_line loop.
        """
        pts = self._waveform_data
        if not pts:
            return
        cv  = self.prog_cv
        W   = w or cv.winfo_width()
        H   = h or (cv.winfo_height() or 32)
        if W < 4 or H < 2:
            return
        if x is None:
            x = getattr(self, "_prog_r_cur", 0.0) * W

        split_x = max(0, min(W - 1, int(x)))

        # ── Try fast numpy path ───────────────────────────────────────────
        try:
            import numpy as _np_wf
            import base64 as _b64

            # Rebuild pixel arrays if size changed or not built yet
            cached_size = getattr(self, "_wf_cached_size", None)
            arrays_ok   = (getattr(self, "_wf_arr_played",   None) is not None and
                           getattr(self, "_wf_arr_unplayed", None) is not None)
            if cached_size != (W, H) or not arrays_ok:
                self._wf_build_images(W, H)

            # If build failed (e.g. no numpy), fall through to slow path
            if (getattr(self, "_wf_arr_played", None) is None or
                    getattr(self, "_wf_arr_unplayed", None) is None):
                raise RuntimeError("arrays not built")

            # Composite: copy unplayed, paint played slice on left
            frame = self._wf_arr_unplayed.copy()
            if split_x > 0:
                frame[:, :split_x] = self._wf_arr_played[:, :split_x]

            # Cue markers as coloured pixel columns
            dur = self.engine.duration
            if dur > 0 and self.current_idx >= 0:
                cues = self._bookmarks.get(self.current_idx, [])
                cue_rgb = [(232,85,85),(85,180,232),(85,232,122),
                           (232,196,85),(196,85,232),(232,122,85)]
                for ci, (sec, _lbl) in enumerate(cues):
                    cx2 = max(0, min(W - 1, int((sec / dur) * W)))
                    frame[:, cx2] = cue_rgb[ci % len(cue_rgb)]

            # Playhead — bright vertical glow line + dot
            ph_x = max(0, min(W - 1, split_x))
            # Glow line: two columns wide, gradient brightness
            for px_off, brightness in [(-1, 120), (0, 255), (1, 120)]:
                col_x = max(0, min(W - 1, ph_x + px_off))
                frame[:, col_x] = brightness

            # Push to PhotoImage using put() with base64-encoded PPM
            # PhotoImage.put() accepts a base64-encoded PPM via the 'data' arg
            # on creation, but for updates we use the put(data, to=) method
            # which accepts a Tcl image data string.
            # Fastest supported method: create with data= initially, then
            # replace via configure(data=) — requires base64 PPM each frame.
            header = f"P6\n{W} {H}\n255\n".encode()
            b64    = _b64.b64encode(header + frame.tobytes()).decode("ascii")

            # Use PhotoImage(data=) on first call, then reconfigure
            if (not hasattr(self, "_wf_photo") or self._wf_photo is None or
                    getattr(self, "_wf_photo_size", None) != (W, H)):
                self._wf_photo = tk.PhotoImage(data=b64)
                self._wf_photo_size = (W, H)
                # Remove old canvas image if size changed
                if hasattr(self, "_wf_canvas_img") and self._wf_canvas_img:
                    try:
                        cv.delete(self._wf_canvas_img)
                    except Exception:
                        pass
                self._wf_canvas_img = cv.create_image(0, 0, anchor="nw",
                                                       image=self._wf_photo)
            else:
                self._wf_photo.configure(data=b64)

            cv.tag_raise(self._wf_canvas_img)

            # Playhead dot — larger, easier to grab
            cy    = H // 2
            dot_r = 6 if getattr(self, "_prog_hover", False) or self.seeking else 4
            cv.delete("prog_dot_item")
            cv.create_oval(split_x - dot_r, cy - dot_r,
                           split_x + dot_r, cy + dot_r,
                           fill=C["white"], outline=C["glow"],
                           tags="prog_dot_item")
            return

        except Exception:
            pass

        # ── Fallback: original create_line path (no numpy) ────────────────
        cv.delete("all")
        # Recreate the persistent items that delete("all") wiped
        self.prog_fill = cv.create_rectangle(0, 0, split_x, H,
                                              fill=C["glow"], outline="")
        N  = len(pts)
        cy = H // 2
        for i, mag in enumerate(pts):
            px    = int(i / N * W)
            bar_h = max(2, int(mag * (H * 0.88)))
            if px <= split_x:
                bv = int(0xcc + mag * (0xff - 0xcc))
            else:
                bv = int(0x18 + mag * (0x38 - 0x18))
            cv.create_line(px, cy - bar_h // 2, px, cy + bar_h // 2,
                           fill=f"#{bv:02x}{bv:02x}{bv:02x}", width=1)
        dot_r = 5 if getattr(self, "_prog_hover", False) or self.seeking else 3
        self.prog_dot = cv.create_oval(split_x - dot_r, cy - dot_r,
                                        split_x + dot_r, cy + dot_r,
                                        fill=C["white"], outline=C["glow"])

    def _wf_build_images(self, W: int, H: int):
        """Pre-render played and unplayed waveform pixel arrays. Called once per canvas size."""
        try:
            import numpy as _np_wf
            pts = self._waveform_data
            if not pts:
                return
            cy = H // 2

            played   = _np_wf.zeros((H, W, 3), dtype=_np_wf.uint8)
            unplayed = _np_wf.zeros((H, W, 3), dtype=_np_wf.uint8)

            # Interpolate peak values to canvas width
            peaks_w = _np_wf.interp(
                _np_wf.arange(W),
                _np_wf.linspace(0, W - 1, len(pts)),
                _np_wf.array(pts, dtype=_np_wf.float32),
            ).astype(_np_wf.float32)

            bar_heights = _np_wf.maximum(2, (peaks_w * cy * 0.88).astype(int))

            for xi in range(W):
                bh   = int(bar_heights[xi])
                mag  = float(peaks_w[xi])
                y0   = max(0, cy - bh)
                y1   = min(H, cy + bh)
                bv_p = int(0xcc + mag * (0xff - 0xcc))   # played:   bright white  cc→ff
                bv_u = int(0x18 + mag * (0x38 - 0x18))   # unplayed: very dim       18→38
                played  [y0:y1, xi] = bv_p
                unplayed[y0:y1, xi] = bv_u

            self._wf_arr_played   = played
            self._wf_arr_unplayed = unplayed
            self._wf_cached_size  = (W, H)
            self._wf_photo        = None   # force recreation at new size
            self._wf_canvas_img   = None
        except Exception:
            self._wf_arr_played   = None
            self._wf_arr_unplayed = None

    # ── VOLUME ────────────────────────────
    VOL_W = 152
    VOL_OFF = 14
    VOL_CY = 32
    VOL_TICKS = 8

    def _vol_x_to_vol(self, x):
        return max(0.0, min(1.0, (x - self.VOL_OFF) / self.VOL_W))

    def _vol_hover(self, entering):
        if self._vol_hover_job:
            self.root.after_cancel(self._vol_hover_job)
            self._vol_hover_job = None
        self._vol_animate_hover(1.0 if entering else 0.0)

    def _vol_animate_hover(self, target):
        diff = target - self._vol_glow
        if abs(diff) < 0.02:
            self._vol_glow = target
            self._upd_vol()
            return
        self._vol_glow += diff * 0.22
        self._upd_vol()
        self._vol_hover_job = self.root.after(
            16 if HW_ACCEL else 50, lambda: self._vol_animate_hover(target)
        )

    def _vol_press(self, e):
        self._vol_dragging = True
        vol = self._vol_x_to_vol(e.x)
        self.engine.set_volume(vol)
        self._upd_vol()
        self._sp_vol_debounce(int(vol * 100))

    def _vol_drag(self, e):
        vol = self._vol_x_to_vol(e.x)
        self.engine.set_volume(vol)
        self._upd_vol()
        self._sp_vol_debounce(int(vol * 100))

    def _vol_release(self, e):
        self._vol_dragging = False
        if self._sp_mode:
            if hasattr(self, "_sp_vol_job") and self._sp_vol_job:
                self.root.after_cancel(self._sp_vol_job)
                self._sp_vol_job = None
            pct = int(self.engine.volume * 100)
            threading.Thread(
                target=lambda: self.sp_api.volume(pct), daemon=True
            ).start()

    def _vol_scroll(self, e):
        delta = 0.05 if e.delta > 0 else -0.05
        self.engine.set_volume(self.engine.volume + delta)
        self._upd_vol()
        self._sp_vol_debounce(int(self.engine.volume * 100))

    def _sp_vol_debounce(self, pct):
        if not self._sp_mode:
            return
        if hasattr(self, "_sp_vol_job") and self._sp_vol_job:
            self.root.after_cancel(self._sp_vol_job)
        self._sp_vol_job = self.root.after(
            250,
            lambda p=pct: threading.Thread(
                target=lambda: self.sp_api.volume(p), daemon=True
            ).start(),
        )

    def _set_vol(self, x):
        """Kept for keyboard shortcuts (Up/Down arrows)."""
        vol = max(0.0, min(1.0, x / self.VOL_W))
        self.engine.set_volume(vol)
        self._upd_vol()
        self._sp_vol_debounce(int(vol * 100))

    def _upd_vol(self):
        cv = self.vol_cv
        cv.delete("all")
        W = self.VOL_W
        off = self.VOL_OFF
        cy = self.VOL_CY
        vol = self.engine.volume
        g = self._vol_glow if hasattr(self, "_vol_glow") else 0.0

        track_h = 3 + int(g * 3)
        ty1 = cy - track_h // 2
        ty2 = cy + track_h // 2 + track_h % 2

        # background track
        tr_br = 28 + int(g * 14)
        cv.create_rectangle(
            off,
            ty1,
            off + W,
            ty2,
            fill=f"#{tr_br:02x}{tr_br:02x}{tr_br:02x}",
            outline="",
        )

        # filled portion
        fill_x = off + int(vol * W)
        if fill_x > off:
            fb = 130 + int(g * 125)
            fb = min(255, fb)
            cv.create_rectangle(
                off, ty1, fill_x, ty2, fill=f"#{fb:02x}{fb:02x}{fb:02x}", outline=""
            )
            hb = min(255, fb + 70)
            cv.create_line(
                off, ty1, fill_x, ty1, fill=f"#{hb:02x}{hb:02x}{hb:02x}", width=1
            )

        # segment tick marks
        for i in range(1, self.VOL_TICKS):
            tx = off + int(i / self.VOL_TICKS * W)
            filled = tx <= fill_x
            tb = 52 if filled else 40
            cv.create_line(
                tx,
                cy - track_h - 2,
                tx,
                cy + track_h + 2,
                fill=f"#{tb:02x}{tb:02x}{tb:02x}",
                width=1,
            )

        # scrubber dot
        dot_r = 4 + int(g * 3)
        db = 190 + int(g * 65)
        db = min(255, db)
        cv.create_oval(
            fill_x - dot_r,
            cy - dot_r,
            fill_x + dot_r,
            cy + dot_r,
            fill=f"#{db:02x}{db:02x}{db:02x}",
            outline="",
        )
        if dot_r >= 5:
            cv.create_oval(
                fill_x - 2, cy - 2, fill_x + 2, cy + 2, fill="#ffffff", outline=""
            )

        # corner bracket accents
        bk = 45 + int(g * 65)
        bc = f"#{bk:02x}{bk:02x}{bk:02x}"
        for sx, dx in [(off - 4, 5), (off + W + 4, -5)]:
            for sy, dy in [(ty1 - 3, 5), (ty2 + 3, -5)]:
                cv.create_line(sx, sy, sx + dx, sy, fill=bc)
                cv.create_line(sx, sy, sx, sy + dy, fill=bc)

        # VOL label + percentage
        lbl_br = 75 + int(g * 85)
        lc = f"#{lbl_br:02x}{lbl_br:02x}{lbl_br:02x}"
        cv.create_text(
            off,
            cy - 15,
            text="VOL",
            anchor="w",
            font=("Courier New", 9, "bold"),
            fill=lc,
        )
        cv.create_text(
            off + W,
            cy - 15,
            text=f"{int(vol * 100):>3}%",
            anchor="e",
            font=("Courier New", 9, "bold"),
            fill=lc,
        )

    # ── RIGHT CLICK MENU ──────────────────
    def _on_rclick(self, event):
        cy = self.track_list.canvasy(event.y)
        row = self._tl_row_at(cy)
        if row < 0 or row >= len(self._display_indices):
            return
        lib_idx = self._display_indices[row]
        m = tk.Menu(
            self.root,
            bg=C["panel"],
            fg=C["white"],
            font=FMS,
            relief="flat",
            activebackground=C["select2"],
            activeforeground=C["white"],
            tearoff=0,
        )
        m.add_command(label="▶  Play Now", command=lambda: self._play_single(lib_idx))
        m.add_command(
            label="+  Add to Queue", command=lambda: self._add_to_queue(lib_idx)
        )
        m.add_separator()
        m.add_command(
            label="✎  Edit Tags", command=lambda: self._open_tag_editor(lib_idx)
        )
        m.add_command(
            label="🖼  Set Cover Image", command=lambda: self._set_track_art(lib_idx)
        )
        m.add_command(
            label="✕  Clear Cover Image", command=lambda: self._clear_track_art(lib_idx)
        )
        m.add_separator()
        m.add_command(
            label="♦  Add to Playlist…", command=lambda: self._add_to_pl_dialog(lib_idx)
        )
        if self.view == "playlist":
            m.add_command(
                label="↗  Export Playlist M3U",
                command=lambda: self._export_playlist_m3u(self.active_playlist),
            )
            m.add_command(
                label="[X]  Remove from Playlist",
                command=lambda: self._rm_from_pl(lib_idx),
            )
        m.add_separator()
        m.add_command(
            label="[X]  Remove from Library", command=lambda: self._rm_from_lib(lib_idx)
        )
        m.post(event.x_root, event.y_root)

    def _play_single(self, lib_idx):
        self.queue = [lib_idx]
        self.queue_pos = 0
        self._play_item(0)

    def _add_to_queue(self, lib_idx):
        self._manual_queue.append(lib_idx)
        # If nothing is playing yet, start it immediately
        if self.queue_pos < 0 and not self.engine.is_playing:
            self.queue = list(self._manual_queue)
            self.queue_pos = 0
            self._play_item(0)
        self._set_status("QUEUED")
        if self.view == "queue":
            self._refresh_queue()

    def _rm_from_pl(self, lib_idx):
        if self.active_playlist:
            pl = self.playlists[self.active_playlist]
            if lib_idx in pl:
                pl.remove(lib_idx)
            self._save()
            self._refresh_tracks()

    def _rm_from_lib(self, lib_idx):
        if lib_idx < len(self.library):
            was_playing_this = self.current_idx == lib_idx
            self.library.pop(lib_idx)
            # Remap playlist indices
            for n in self.playlists:
                self.playlists[n] = [
                    i if i < lib_idx else i - 1
                    for i in self.playlists[n]
                    if i != lib_idx
                ]
            # Remap queue indices and fix queue_pos
            old_queue_pos = self.queue_pos
            self.queue = [
                i if i < lib_idx else i - 1 for i in self.queue if i != lib_idx
            ]
            # If removed track was at or before queue_pos, shift pos back
            if old_queue_pos >= len(self.queue):
                self.queue_pos = max(-1, len(self.queue) - 1)
            if self.current_idx == lib_idx:
                self.current_idx = -1
                if was_playing_this:
                    self.engine.stop()
                    self.engine.is_playing = False
                    self.btn_play.config(text="▶")
                    self.wavevis.set_active(False)
                    self._set_logo_playing(False)
                    self.now_title.config(text="NO TRACK")
                    self.now_artist.config(text="")
                    self.now_album.config(text="")
                    self.status_lbl.config(text="[ IDLE ]")
                    self._draw_prog(0)
            elif self.current_idx > lib_idx:
                self.current_idx -= 1
            self._save()
            self._tracks_dirty = True
            self._refresh_tracks()

    # ── TRACK COVER ART ───────────────────
    def _set_track_art(self, lib_idx):
        if lib_idx >= len(self.library):
            return
        path = filedialog.askopenfilename(
            title="Select Cover Image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.library[lib_idx]["art_path"] = path
            self._save()
            self._set_status("COVER SET")

    def _clear_track_art(self, lib_idx):
        if lib_idx >= len(self.library):
            return
        self.library[lib_idx].pop("art_path", None)
        self._save()
        self._set_status("COVER CLEARED")

    # ── LYRICS VIEW ───────────────────────
    def _build_lyrics_view(self):
        self.lyrics_frame = tk.Frame(self.content, bg=C["bg"])

        hdr = tk.Frame(self.lyrics_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(hdr, text="LYRICS", font=FMX, fg=C["white"], bg=C["bg"]).pack(
            side="left"
        )
        self._lyrics_src_lbl = tk.Label(
            hdr, text="", font=FMS, fg=C["white3"], bg=C["bg"]
        )
        self._lyrics_src_lbl.pack(side="left", padx=12)
        self._lyrics_sync_badge = tk.Label(
            hdr, text="", font=FMS, fg=C["white3"], bg=C["bg"]
        )
        self._lyrics_sync_badge.pack(side="right", padx=8)

        tk.Frame(self.lyrics_frame, bg=C["border"], height=1).pack(
            fill="x", padx=20, pady=(8, 0)
        )

        self._lyrics_track_lbl = tk.Label(
            self.lyrics_frame,
            text="— NO TRACK —",
            font=("Courier New", 10, "bold"),
            fg=C["white2"],
            bg=C["bg"],
            anchor="w",
        )
        self._lyrics_track_lbl.pack(fill="x", padx=24, pady=(10, 0))

        lf = tk.Frame(self.lyrics_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=0, pady=8)
        self._lyrics_sb = tk.Scrollbar(
            lf, bg=C["panel"], troughcolor=C["bg"], width=6, bd=0, highlightthickness=0
        )
        self._lyrics_sb.pack(side="right", fill="y")
        self._lyrics_cv = tk.Canvas(
            lf, bg=C["bg"], highlightthickness=0, yscrollcommand=self._lyrics_sb.set
        )
        self._lyrics_cv.pack(side="left", fill="both", expand=True)
        self._lyrics_sb.config(command=self._lyrics_cv.yview)
        self._lyrics_inner = tk.Frame(self._lyrics_cv, bg=C["bg"])
        self._lyrics_win = self._lyrics_cv.create_window(
            0, 0, anchor="nw", window=self._lyrics_inner
        )
        self._lyrics_inner.bind("<Configure>", self._on_lyrics_inner_resize)
        self._lyrics_cv.bind("<Configure>", self._on_lyrics_cv_resize)
        self._lyrics_cv.bind(
            "<MouseWheel>",
            lambda e: self._lyrics_cv.yview_scroll(
                -1 * (1 if e.delta > 0 else -1), "units"
            ),
        )

    def _on_lyrics_inner_resize(self, e):
        self._lyrics_cv.configure(scrollregion=self._lyrics_cv.bbox("all"))

    def _on_lyrics_cv_resize(self, e):
        self._lyrics_cv.itemconfig(self._lyrics_win, width=e.width)

    def _refresh_lyrics_view(self):
        title = self.now_title.cget("text").replace("…", "").strip()
        artist = self.now_artist.cget("text").strip()
        if not title or title == "— NO TRACK —":
            self._set_lyrics_lines(["— Play a track to see lyrics —"], synced=False)
            return
        self._lyrics_track_lbl.config(text=f"{artist}  //  {title}")
        # Use the canonical key stored at track-start — avoids truncation mismatch
        key = self._current_lyrics_key or (
            artist.lower().strip(),
            title.lower().strip(),
        )
        cached = self._lyrics_cache.get(key, "MISSING")
        if cached == "MISSING":
            self._set_lyrics_lines(["[ Searching lyrics… ]"], synced=False)
            self._fetch_lyrics(artist, title)
        elif cached is None:
            # In-flight — clear marker and re-kick so we don't spin forever
            self._set_lyrics_lines(["[ Searching lyrics… ]"], synced=False)
            del self._lyrics_cache[key]
            self._fetch_lyrics(artist, title)
        else:
            synced = self._synced_cache.get(key)
            source = self._source_cache.get(key, "")
            if synced:
                self._load_synced_lyrics(synced)
            else:
                self._set_lyrics_lines(cached.splitlines(), synced=False)
            self._lyrics_src_lbl.config(text=f"[ {source} ]" if source else "")

    def _set_lyrics_lines(self, lines, synced=False):
        """Rebuild inner frame with one Label per line."""
        self._stop_lyrics_sync()
        for w in self._lyrics_inner.winfo_children():
            w.destroy()
        self._lyrics_lines = []
        self._lyrics_active_line = -1
        font_normal = ("Courier New", 12)
        font_active = ("Courier New", 13, "bold")
        tk.Frame(self._lyrics_inner, bg=C["bg"], height=18).pack()
        for line in lines:
            text = line.strip()
            if not text:
                tk.Frame(self._lyrics_inner, bg=C["bg"], height=10).pack()
                self._lyrics_lines.append(None)
                continue
            lbl = tk.Label(
                self._lyrics_inner,
                text=text,
                font=font_normal,
                fg=C["white3"],
                bg=C["bg"],
                anchor="center",
                justify="center",
                wraplength=580,
                cursor="arrow",
                pady=5,
            )
            lbl.pack(fill="x", padx=40)
            lbl._font_normal = font_normal
            lbl._font_active = font_active
            self._lyrics_lines.append(lbl)
        tk.Frame(self._lyrics_inner, bg=C["bg"], height=60).pack()
        self._lyrics_cv.yview_moveto(0)
        if synced:
            self._lyrics_sync_badge.config(text="[ ◈ SYNCED ]", fg=C["white3"])
        else:
            self._lyrics_sync_badge.config(text="[ STATIC ]", fg=C["white3"])

    def _load_synced_lyrics(self, synced_lines):
        """synced_lines: list of (ms, text). Build labels, attach timestamps, start ticker."""
        lines = [text for _, text in synced_lines]
        self._set_lyrics_lines(lines, synced=True)
        timed = []
        slot_i = 0
        for ms, text in synced_lines:
            text = text.strip()
            while slot_i < len(self._lyrics_lines):
                slot = self._lyrics_lines[slot_i]
                slot_i += 1
                if slot is not None:
                    timed.append((ms, slot))
                    break
        self._lyrics_timed = timed
        self._lyrics_active_line = -1
        self._start_lyrics_sync()

    # ── Universal position helper ─────────────────────────────────────────────
    def _get_pos_ms(self):
        """Return current playback position in milliseconds for any source."""
        try:
            if self._sp_mode and self._sp_dur_ms > 0:
                return self._sp_pos_ms
            return int(self.engine._pos_cache * 1000)
        except Exception:
            return 0

    def _start_lyrics_sync(self):
        self._stop_lyrics_sync()
        self._lyrics_sync_tick()

    def _stop_lyrics_sync(self):
        if self._lyrics_sync_job:
            try:
                self.root.after_cancel(self._lyrics_sync_job)
            except:
                pass
        self._lyrics_sync_job = None
        self._lyrics_timed = []

    def _lyrics_sync_tick(self):
        if self.view != "lyrics":
            self._lyrics_sync_job = self.root.after(200, self._lyrics_sync_tick)
            return
        timed = getattr(self, "_lyrics_timed", [])
        if not timed:
            return
        pos_ms = self._get_pos_ms()

        # Find the last line whose timestamp is <= current position
        active = -1
        for i, (ms, _) in enumerate(timed):
            if ms <= pos_ms:
                active = i
            else:
                break

        # Always repaint — catches paused-at-start and seek jumps
        if active != self._lyrics_active_line:
            self._lyrics_active_line = active
            for i, (ms, lbl) in enumerate(timed):
                dist = i - active  # positive = upcoming, negative = past
                if i == active:
                    lbl.config(fg=C["glow"], font=lbl._font_active)
                elif dist == 1:  # next line
                    lbl.config(fg=C["white3"], font=lbl._font_normal)
                elif dist == 2:
                    lbl.config(fg="#555555", font=lbl._font_normal)
                elif dist == -1:  # just-passed line
                    lbl.config(fg="#444444", font=lbl._font_normal)
                else:
                    lbl.config(fg="#222222", font=lbl._font_normal)
            if 0 <= active < len(timed):
                self._scroll_to_lyric_line(active)

        self._lyrics_sync_job = self.root.after(80, self._lyrics_sync_tick)

    def _scroll_to_lyric_line(self, idx):
        """Scroll so the active line is centred vertically in the canvas."""
        try:
            _, lbl = self._lyrics_timed[idx]
            lbl.update_idletasks()
            # Walk up widget tree to accumulate y offset relative to canvas
            y = 0
            w = lbl
            while w != self._lyrics_cv and w is not None:
                y += w.winfo_y()
                w = w.master
            lbl_h = lbl.winfo_height()
            cv_h = self._lyrics_cv.winfo_height()
            inner_h = self._lyrics_inner.winfo_height()
            if inner_h <= cv_h or cv_h < 1:
                return
            # Centre the line in the viewport
            target = (y + lbl_h / 2 - cv_h / 2) / inner_h
            target = max(0.0, min(1.0, target))
            self._lyrics_cv.yview_moveto(target)
        except Exception:
            pass

    def _fetch_lyrics(self, artist, title):
        if not artist or not title:
            return
        key = (artist.lower().strip(), title.lower().strip())
        if key in self._lyrics_cache:
            return
        self._lyrics_cache[key] = None  # in-flight

        def _parse_lrc(lrc_text):
            # Matches [mm:ss.xx] or [mm:ss.xxx]
            pattern = re.compile(r"\[(\d+):(\d+)[\.:](\d+)\](.*)")
            lines = []
            for raw in lrc_text.splitlines():
                m = pattern.match(raw.strip())
                if m:
                    mins = int(m.group(1))
                    secs = int(m.group(2))
                    frac = m.group(3)
                    # 2-digit = hundredths (×10 to get ms), 3-digit = ms already
                    frac_ms = int(frac) * 10 if len(frac) == 2 else int(frac)
                    ms = (mins * 60 + secs) * 1000 + frac_ms
                    text = m.group(4).strip()
                    if text:
                        lines.append((ms, text))
            return sorted(lines, key=lambda x: x[0])

        def _worker():
            plain = ""
            synced = None
            source = ""

            # Source 1: lrclib.net — prefers synced LRC
            try:
                url = (
                    "https://lrclib.net/api/search?artist_name={}&track_name={}".format(
                        urllib.parse.quote(artist), urllib.parse.quote(title)
                    )
                )
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "OternosPlayer/1.0",
                        "Accept": "application/json",
                    },
                )
                with urllib.request.urlopen(req, timeout=8) as r:
                    results = json.loads(r.read().decode())
                if results:
                    best = results[0]
                    plain_text = best.get("plainLyrics", "").strip()
                    synced_lrc = best.get("syncedLyrics", "").strip()
                    if synced_lrc:
                        parsed = _parse_lrc(synced_lrc)
                        if parsed:
                            synced = parsed
                            plain = plain_text or "\n".join(t for _, t in parsed)
                            source = "lrclib.net"
                    elif plain_text:
                        plain = plain_text
                        source = "lrclib.net"
            except Exception:
                pass

            # Source 2: Musixmatch plain fallback
            if not plain:
                try:
                    q = urllib.parse.quote(f"{artist} {title}")
                    url = f"https://api.musixmatch.com/ws/1.1/track.search?q={q}&page_size=1&page=1&s_track_rating=desc&apikey=b6de7a5a69bef03d45e9f5ccabeaa7c5"
                    req = urllib.request.Request(
                        url, headers={"User-Agent": "OternosPlayer/1.0"}
                    )
                    with urllib.request.urlopen(req, timeout=8) as r:
                        data = json.loads(r.read().decode())
                    items = (
                        data.get("message", {}).get("body", {}).get("track_list", [])
                    )
                    if items:
                        tid = items[0]["track"]["track_id"]
                        url2 = f"https://api.musixmatch.com/ws/1.1/track.lyrics.get?track_id={tid}&apikey=b6de7a5a69bef03d45e9f5ccabeaa7c5"
                        with urllib.request.urlopen(
                            urllib.request.Request(
                                url2, headers={"User-Agent": "OternosPlayer/1.0"}
                            ),
                            timeout=8,
                        ) as r2:
                            d2 = json.loads(r2.read().decode())
                        body = (
                            d2.get("message", {})
                            .get("body", {})
                            .get("lyrics", {})
                            .get("lyrics_body", "")
                            .strip()
                        )
                        if body and "****" not in body:
                            plain = body
                            source = "musixmatch"
                except Exception:
                    pass

            # Source 3: lyrics.ovh
            if not plain:
                try:
                    url = "https://api.lyrics.ovh/v1/{}/{}".format(
                        urllib.parse.quote(artist), urllib.parse.quote(title)
                    )
                    req = urllib.request.Request(
                        url, headers={"User-Agent": "OternosPlayer/1.0"}
                    )
                    with urllib.request.urlopen(req, timeout=6) as r:
                        data = json.loads(r.read().decode())
                    candidate = data.get("lyrics", "").strip()
                    if candidate:
                        plain = candidate
                        source = "lyrics.ovh"
                except Exception:
                    pass

            if not plain:
                plain = "[ No lyrics found ]"
                source = ""

            self._lyrics_cache[key] = plain
            self._synced_cache[key] = synced
            self._source_cache[key] = source
            self.root.after(
                0, lambda: self._on_lyrics_fetched(artist, title, plain, synced, source)
            )

        threading.Thread(target=_worker, daemon=True).start()

    def _on_lyrics_fetched(self, artist, title, plain, synced, source=""):
        # Match against the canonical key set at track-start — immune to label truncation
        fetched_key = (artist.lower().strip(), title.lower().strip())
        if self._current_lyrics_key and fetched_key != self._current_lyrics_key:
            return  # stale result from a previous track
        if not self._current_lyrics_key:
            # Fallback: compare against live labels (no track set yet)
            cur_title = self.now_title.cget("text").replace("…", "").strip().lower()
            cur_artist = self.now_artist.cget("text").strip().lower()
            ta = artist.lower().strip()
            tt = title.lower().strip()
            title_match = (
                cur_title in tt
                or tt.startswith(cur_title)
                or cur_title.startswith(tt[:20])
            )
            artist_match = cur_artist in ta or ta in cur_artist or not cur_artist
            if not (title_match or artist_match):
                return
        try:
            self._lyrics_src_lbl.config(text=f"[ {source} ]" if source else "")
        except Exception:
            pass
        try:
            self._lyrics_track_lbl.config(
                text=f"{artist}  //  {title}" if artist else title
            )
        except Exception:
            pass
        # Update player bar badge
        has_real = plain and plain != "[ No lyrics found ]"
        if synced:
            self._set_lyrics_badge("synced", source)
        elif has_real:
            self._set_lyrics_badge("plain", source)
        else:
            self._set_lyrics_badge("none")
        # Update main lyrics panel
        if self.view == "lyrics":
            if synced:
                self._load_synced_lyrics(synced)
            else:
                self._set_lyrics_lines(plain.splitlines(), synced=False)
        # Update popup window if open
        popup = getattr(self, "_lyric_popup", None)
        if popup:
            try:
                if popup.winfo_exists():
                    try:
                        self._lp_track_lbl.config(
                            text=f"{artist}  //  {title}" if artist else title
                        )
                    except Exception:
                        pass
                    try:
                        self._lp_badge.config(text=f"[ {source} ]" if source else "")
                    except Exception:
                        pass
                    if synced:
                        self._lp_load_synced(synced)
                    else:
                        self._lp_set_lines(plain.splitlines(), synced=False)
            except Exception:
                pass

    def _show_lyrics(self, text, source):
        """Compat shim for older call sites."""
        self._lyrics_src_lbl.config(text=f"[ {source} ]" if source else "")
        self._set_lyrics_lines(text.splitlines() if text else [], synced=False)

    # ── SLEEP TIMER ───────────────────────
    def _open_sleep_timer(self):
        win = tk.Toplevel(self.root)
        content, _close = self._popup_setup(win, "SYS::SLEEP TIMER", w=320, h=260)

        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(12, 0))

        # Countdown display
        self._sleep_disp = tk.Label(
            content,
            text=self._sleep_display(),
            font=("Courier New", 28, "bold"),
            fg=C["glow"],
            bg=C["bg"],
        )
        self._sleep_disp.pack(pady=(12, 8))

        # Presets
        presets = tk.Frame(content, bg=C["bg"])
        presets.pack()
        for mins in [15, 30, 45, 60, 90]:
            b = tk.Label(
                presets,
                text=f"{mins}m",
                font=FM,
                fg=C["white3"],
                bg=C["panel"],
                cursor="hand2",
                padx=8,
                pady=4,
            )
            b.pack(side="left", padx=3)
            b.bind("<Button-1>", lambda e, m=mins: self._set_sleep(m, win))
            b.bind("<Enter>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white3"], C["white"], duration_ms=60))
            b.bind("<Leave>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white"], C["white3"], duration_ms=60))

        # Cancel button
        btn_frame = tk.Frame(content, bg=C["bg"])
        btn_frame.pack(pady=14)
        cancel_b = tk.Label(
            btn_frame,
            text="CANCEL",
            font=FM,
            fg=C["white3"],
            bg=C["bg"],
            cursor="hand2",
        )
        cancel_b.pack(side="left", padx=8)
        cancel_b.bind("<Button-1>", lambda e: self._cancel_sleep(win))
        cancel_b.bind("<Enter>", lambda e: ColorAnim.run(self.root, cancel_b, "fg", C["white3"], C["red"], duration_ms=60))
        cancel_b.bind("<Leave>", lambda e: ColorAnim.run(self.root, cancel_b, "fg", C["red"], C["white3"], duration_ms=60))

        # Live update the display every second
        def _tick():
            if not win.winfo_exists():
                return
            self._sleep_disp.config(text=self._sleep_display())
            win.after(1000, _tick)

        _tick()

    def _sleep_display(self):
        if self._sleep_end_time is None:
            return "OFF"
        remaining = max(0, self._sleep_end_time - time.time())
        m = int(remaining // 60)
        s = int(remaining % 60)
        return f"{m:02d}:{s:02d}"

    def _set_sleep(self, minutes, win=None):
        if self._sleep_job:
            self.root.after_cancel(self._sleep_job)
        self._sleep_minutes = minutes
        self._sleep_end_time = time.time() + minutes * 60
        self._poll_sleep()
        self._set_status(f"SLEEP {minutes}m")
        if win and win.winfo_exists():
            win.destroy()

    def _cancel_sleep(self, win=None):
        if self._sleep_job:
            self.root.after_cancel(self._sleep_job)
            self._sleep_job = None
        self._sleep_end_time = None
        self._sleep_minutes = 0
        self._set_status("SLEEP OFF")
        if win and win.winfo_exists():
            win.destroy()

    def _poll_sleep(self):
        if self._sleep_end_time is None:
            return
        remaining = self._sleep_end_time - time.time()
        # Update status label with countdown
        if remaining > 0:
            m = int(remaining // 60)
            s = int(remaining % 60)
            self.status_lbl.config(text=f"⏾ {m:02d}:{s:02d}")
            self._sleep_job = self.root.after(1000, self._poll_sleep)
        else:
            # Time's up — fade volume to zero then stop
            self._sleep_end_time = None
            self._sleep_job = None
            self._sleep_fade_stop()

    def _sleep_fade_stop(self, vol=None):
        """Gradually fade volume to 0 then stop playback."""
        if vol is None:
            vol = self.settings.get("volume", 80)
        if vol > 0:
            new_vol = max(0, vol - 4)
            self.engine.set_volume(new_vol)
            self.root.after(120, lambda: self._sleep_fade_stop(new_vol))
        else:
            self.engine.pause()
            self.btn_play.config(text="▶")
            self.wavevis.set_active(False)
            self._set_logo_playing(False)
            self.status_lbl.config(text="SLEEP zzz")
            # Restore volume for next time
            self.engine.set_volume(self.settings.get("volume", 80))

    # ── MINI PLAYER ───────────────────────
    def _toggle_mini_player(self):
        if self._mini_win and self._mini_win.winfo_exists():
            self._mini_win.destroy()
            self._mini_win = None
            self.root.deiconify()
        else:
            self._open_mini_player()

    def _open_mini_player(self):
        self.root.withdraw()
        W, H = 420, 116
        # Position bottom-right of screen
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        gx, gy = sw - W - 24, sh - H - 60

        win = tk.Toplevel()
        win.title("OTERNOS")
        win.geometry(f"{W}x{H}+{gx}+{gy}")
        win.configure(bg=C["bg"])
        win.resizable(False, False)
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        win.wm_attributes("-alpha", 0.96)
        self._mini_win = win
        self._popup_fadein(win, duration_ms=100, start=0.0, end=0.96)
        self._mini_topmost = True
        self._mini_prog_r = 0.0  # smooth progress ratio
        self._mini_drag_x = None
        self._mini_seeking = False

        try:
            win.iconphoto(False, self._icon_img)
        except:
            pass

        # ── drag (only from non-interactive areas) ──
        def _drag_start(e):
            win._mx = e.x_root - win.winfo_x()
            win._my = e.y_root - win.winfo_y()

        def _drag_move(e):
            nx = e.x_root - win._mx
            ny = e.y_root - win._my
            # Snap to screen edges within 20px
            if abs(nx) < 20:
                nx = 0
            if abs(ny) < 20:
                ny = 0
            if abs(nx - (sw - W)) < 20:
                nx = sw - W
            if abs(ny - (sh - H - 48)) < 20:
                ny = sh - H - 48
            win.geometry(f"+{nx}+{ny}")

        # ── outer border glow frame — FFT-reactive ──
        self._mini_border_frame = tk.Frame(win, bg=C["border"], padx=1, pady=1)
        self._mini_border_frame.pack(fill="both", expand=True)
        inner = tk.Frame(self._mini_border_frame, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        # ── top strip: art + info + controls ──
        top = tk.Frame(inner, bg=C["bg"])
        top.pack(fill="x", padx=0, pady=0)
        top.bind("<ButtonPress-1>", _drag_start)
        top.bind("<B1-Motion>", _drag_move)

        # Album art (54x54)
        self._mini_art_cv = tk.Canvas(
            top, bg=C["panel2"], width=54, height=54, highlightthickness=0
        )
        self._mini_art_cv.pack(side="left", padx=(8, 0), pady=8)
        self._mini_art_photo = None
        self._mini_draw_art()

        # Info column
        info = tk.Frame(top, bg=C["bg"])
        info.pack(side="left", fill="both", expand=True, padx=10, pady=(10, 4))
        info.bind("<ButtonPress-1>", _drag_start)
        info.bind("<B1-Motion>", _drag_move)

        self._mini_title = tk.Label(
            info,
            text="— NO TRACK —",
            font=("Courier New", 9, "bold"),
            fg=C["white"],
            bg=C["bg"],
            anchor="w",
            cursor="hand2",
        )
        self._mini_title.pack(fill="x")
        self._mini_title.bind("<Double-Button-1>", lambda e: self._toggle_mini_player())

        self._mini_artist = tk.Label(
            info,
            text="",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["bg"],
            anchor="w",
        )
        self._mini_artist.pack(fill="x")
        self._mini_artist.bind("<ButtonPress-1>", _drag_start)
        self._mini_artist.bind("<B1-Motion>", _drag_move)

        # Time row
        trow = tk.Frame(info, bg=C["bg"])
        trow.pack(fill="x", pady=(2, 0))
        self._mini_cur = tk.Label(
            trow, text="0:00", font=("Courier New", 7), fg=C["white3"], bg=C["bg"]
        )
        self._mini_cur.pack(side="left")
        self._mini_cur_hex = tk.Label(
            trow, text="0x0000", font=("Courier New", 5), fg=C["white3"], bg=C["bg"]
        )
        self._mini_cur_hex.pack(side="left", padx=(4, 0))
        self._mini_tot = tk.Label(
            trow, text="0:00", font=("Courier New", 7), fg=C["white3"], bg=C["bg"]
        )
        self._mini_tot.pack(side="right")

        # Controls column
        ctrl = tk.Frame(top, bg=C["bg"])
        ctrl.pack(side="right", padx=(0, 8), pady=8)

        def _mbtn(text, cmd, sz=12):
            b = tk.Label(
                ctrl,
                text=text,
                font=("Courier New", sz),
                fg=C["white3"],
                bg=C["bg"],
                cursor="hand2",
                padx=5,
            )
            b.pack(side="left")
            b.bind("<Button-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.config(fg=C["white"]))
            b.bind("<Leave>", lambda e: b.config(fg=C["white3"]))
            return b

        # Shuffle
        self._mini_shuf_btn = _mbtn("⇌", self._toggle_shuffle, sz=10)
        _mbtn("⏮", self._prev)
        self._mini_play_btn = _mbtn("▶", self._toggle_play, sz=14)
        _mbtn("⏭", self._next)
        # Repeat
        self._mini_rep_btn = _mbtn("↺", self._toggle_repeat, sz=10)

        # Window controls (top-right)
        wctrl = tk.Frame(top, bg=C["bg"])
        wctrl.pack(side="right", anchor="n", pady=4)

        pin_b = tk.Label(
            wctrl,
            text="📌",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["bg"],
            cursor="hand2",
        )
        pin_b.pack()
        pin_b.bind("<Button-1>", lambda e: self._mini_toggle_topmost(pin_b))
        pin_b.bind("<Enter>", lambda e: pin_b.config(fg=C["white"]))
        pin_b.bind("<Leave>", lambda e: pin_b.config(fg=C["white3"]))

        close_b = tk.Label(
            wctrl,
            text="✕",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["bg"],
            cursor="hand2",
        )
        close_b.pack()
        close_b.bind("<Button-1>", lambda e: self._toggle_mini_player())
        close_b.bind("<Enter>", lambda e: close_b.config(fg=C["white"]))
        close_b.bind("<Leave>", lambda e: close_b.config(fg=C["white3"]))

        # ── seekable progress bar ──
        prog_frame = tk.Frame(inner, bg=C["bg"])
        prog_frame.pack(fill="x", padx=0, pady=0, side="bottom")

        self._mini_prog_cv = tk.Canvas(
            prog_frame, bg=C["border"], height=5, highlightthickness=0, cursor="hand2"
        )
        self._mini_prog_cv.pack(fill="x")
        self._mini_prog_fill = self._mini_prog_cv.create_rectangle(
            0, 0, 0, 5, fill=C["white"], outline=""
        )
        self._mini_prog_dot = self._mini_prog_cv.create_oval(
            -4, -2, 4, 7, fill=C["glow"], outline="", state="hidden"
        )

        def _prog_hover(entering):
            self._mini_prog_cv.itemconfig(
                self._mini_prog_dot, state="normal" if entering else "hidden"
            )

        def _prog_seek(e):
            self._mini_seeking = True
            w = max(1, self._mini_prog_cv.winfo_width())
            r = max(0.0, min(1.0, e.x / w))
            if self._sp_mode:
                ms = int(r * self._sp_dur_ms)
                threading.Thread(
                    target=lambda: self.sp_api.seek(ms), daemon=True
                ).start()
            elif self.engine.duration > 0:
                self.engine.seek(r * self.engine.duration)
            self._mini_prog_r = r
            self._mini_seeking = False

        def _prog_move(e):
            w = max(1, self._mini_prog_cv.winfo_width())
            r = max(0.0, min(1.0, e.x / w))
            # Drag dot preview
            x = r * w
            self._mini_prog_cv.coords(self._mini_prog_dot, x - 4, -2, x + 4, 7)

        self._mini_prog_cv.bind("<Enter>", lambda e: _prog_hover(True))
        self._mini_prog_cv.bind("<Leave>", lambda e: _prog_hover(False))
        self._mini_prog_cv.bind("<ButtonRelease-1>", _prog_seek)
        self._mini_prog_cv.bind("<B1-Motion>", _prog_move)

        # ── volume scroll on whole window ──
        def _scroll_vol(e):
            delta = 0.04 if e.delta > 0 else -0.04
            self.engine.set_volume(self.engine.volume + delta)

        win.bind("<MouseWheel>", _scroll_vol)

        # ── keyboard shortcuts ──
        win.bind("<space>", lambda e: self._toggle_play())
        win.bind("<Right>", lambda e: self._next())
        win.bind("<Left>", lambda e: self._prev())
        win.bind("<Escape>", lambda e: self._toggle_mini_player())

        # ── right-click context menu ──
        def _ctx(e):
            menu = tk.Menu(
                win,
                bg=C["panel"],
                fg=C["white"],
                activebackground=C["select2"],
                activeforeground=C["white"],
                font=FM,
                tearoff=0,
                bd=0,
                relief="flat",
            )
            menu.add_command(label="Expand player", command=self._toggle_mini_player)
            menu.add_separator()
            menu.add_command(
                label="Add to queue", command=lambda: self._add_current_to_queue()
            )
            menu.add_separator()
            topmost_lbl = "✓ Always on top" if self._mini_topmost else "  Always on top"
            menu.add_command(
                label=topmost_lbl, command=lambda: self._mini_toggle_topmost(pin_b)
            )
            menu.tk_popup(e.x_root, e.y_root)

        win.bind("<Button-3>", _ctx)

        self._mini_update()
        self._mini_tick()

    def _mini_draw_art(self):
        """Draw album art or placeholder into the mini art canvas."""
        cv = self._mini_art_cv
        cv.delete("all")
        # Try to reuse main art photo
        if self._art_photo:
            try:
                cv.create_image(27, 27, image=self._art_photo, anchor="center")
                return
            except:
                pass
        # Placeholder — geometric pattern
        cv.create_rectangle(0, 0, 54, 54, fill=C["panel2"], outline="")
        for i in range(3):
            r = 8 + i * 7
            cv.create_oval(
                27 - r, 27 - r, 27 + r, 27 + r, outline=C["border2"], fill="", width=1
            )
        cv.create_oval(24, 24, 30, 30, fill=C["white3"], outline="")

    def _mini_toggle_topmost(self, pin_btn=None):
        self._mini_topmost = not self._mini_topmost
        self._mini_win.wm_attributes("-topmost", self._mini_topmost)
        if pin_btn:
            pin_btn.config(fg=C["white"] if self._mini_topmost else C["white3"])

    def _add_current_to_queue(self):
        if self.current_idx >= 0:
            self._add_to_queue(self.current_idx)

    def _mini_update(self):
        if not self._mini_win or not self._mini_win.winfo_exists():
            return
        title = self.now_title.cget("text")
        artist = self.now_artist.cget("text")
        self._mini_title.config(text=title[:38] if len(title) > 38 else title)
        self._mini_artist.config(text=artist[:42] if len(artist) > 42 else artist)
        playing = self.engine.is_playing or self._sp_playing
        self._mini_play_btn.config(text="⏸" if playing else "▶")
        # Shuffle / repeat state colors
        self._mini_shuf_btn.config(fg=C["white"] if self.shuffle else C["white3"])
        rep_icon = {"off": "↺", "all": "↺", "one": "↻"}[self.repeat_mode]
        self._mini_rep_btn.config(
            text=rep_icon, fg=C["white"] if self.repeat_mode != "off" else C["white3"]
        )
        # Album art sync
        self._mini_draw_art()

    def _mini_tick(self):
        if not self._mini_win or not self._mini_win.winfo_exists():
            return
        try:
            # Smooth progress
            if self._mini_seeking:
                r = self._mini_prog_r
            elif self._sp_mode and self._sp_dur_ms > 0:
                r = min(1.0, self._sp_pos_ms / self._sp_dur_ms)
                cur = self._sp_pos_ms / 1000
                tot = self._sp_dur_ms / 1000
            elif self.engine.duration > 0:
                pos = self.engine._pos_cache
                dur = self.engine.duration
                r = min(1.0, pos / dur)
                cur = pos
                tot = dur
            else:
                r = 0.0
                cur = 0
                tot = 0

            # Lerp progress bar smoothly
            self._mini_prog_r += (r - self._mini_prog_r) * 0.18
            w = max(1, self._mini_prog_cv.winfo_width())
            px = self._mini_prog_r * w
            self._mini_prog_cv.coords(self._mini_prog_fill, 0, 0, px, 5)

            # Update time labels
            try:
                self._mini_cur.config(text=self._fmt(cur))
                self._mini_tot.config(text=self._fmt(tot))
                self._mini_cur_hex.config(text=f"0x{int(cur):04X}")
            except:
                pass

            # FFT-reactive border color
            try:
                fft = getattr(self, "_fft_bars", None)
                playing = self.engine.is_playing or self._sp_playing
                if fft and playing:
                    bass = min(1.0, sum(fft[:6]) / 6 * 4.0)
                    bv = int(0x1f + (0xe8 - 0x1f) * bass)
                    self._mini_border_frame.config(bg=f"#{bv:02x}{bv:02x}{bv:02x}")
                else:
                    self._mini_border_frame.config(bg=C["border"])
            except:
                pass

        except:
            pass

        self._mini_update()
        self._mini_win.after(50, self._mini_tick)  # 20fps — smooth enough, light

    # ── HISTORY ───────────────────────────
    def _history_add(self, track, source="library"):
        entry = {
            "title": track.get("title", ""),
            "artist": track.get("artist", ""),
            "album": track.get("album", ""),
            "source": source,
            "ts": int(time.time()),
        }
        # Avoid duplicate consecutive entries (same title AND source)
        if (
            self._history
            and self._history[-1].get("title") == entry["title"]
            and self._history[-1].get("source", "library")
            == entry.get("source", "library")
        ):
            return
        self._history.append(entry)
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max :]
        self._save()
        if self.view == "history":
            self._refresh_history_view()

    def _build_history_view(self):
        self.history_frame = tk.Frame(self.content, bg=C["bg"])
        hdr = tk.Frame(self.history_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(16, 0))
        tk.Label(hdr, text="RECENTLY PLAYED", font=FMX, fg=C["white"], bg=C["bg"]).pack(
            side="left"
        )
        clr = tk.Label(
            hdr, text="[ PURGE LOG ]", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2"
        )
        clr.pack(side="right")
        clr.bind("<Button-1>", lambda e: self._clear_history())
        clr.bind("<Enter>", lambda e: clr.config(fg=C["white"]))
        clr.bind("<Leave>", lambda e: clr.config(fg=C["white3"]))

        # Source filter buttons
        flt = tk.Frame(self.history_frame, bg=C["bg"])
        flt.pack(fill="x", padx=20, pady=(6, 0))
        tk.Label(flt, text="FILTER:", font=FMS, fg=C["white3"], bg=C["bg"]).pack(
            side="left"
        )
        self._hist_filter = tk.StringVar(value="all")
        for _lbl, _key in [
            ("ALL", "all"),
            ("LIBRARY", "library"),
            ("SPOTIFY", "spotify"),
            ("YOUTUBE", "youtube"),
            ("SOUNDCLOUD", "soundcloud"),
        ]:
            _b = tk.Label(
                flt,
                text=_lbl,
                font=FMS,
                fg=C["white"] if _key == "all" else C["white3"],
                bg=C["bg"],
                cursor="hand2",
                padx=8,
            )
            _b.pack(side="left")

            def _on_click(e, k=_key, btn=_b, f=flt):
                self._hist_filter.set(k)
                for child in f.winfo_children()[1:]:
                    child.config(fg=C["white3"])
                btn.config(fg=C["white"])
                self._refresh_history_view()

            _b.bind("<Button-1>", _on_click)

        tk.Frame(self.history_frame, bg=C["border"], height=1).pack(
            fill="x", padx=20, pady=(8, 0)
        )

        lf = tk.Frame(self.history_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=0, pady=0)
        sb = tk.Scrollbar(
            lf, bg=C["panel"], troughcolor=C["bg"], width=6, bd=0, highlightthickness=0
        )
        sb.pack(side="right", fill="y")
        self._hist_cv = tk.Canvas(
            lf, bg=C["bg"], highlightthickness=0, yscrollcommand=sb.set
        )
        self._hist_cv.pack(side="left", fill="both", expand=True)
        sb.config(command=self._hist_cv.yview)
        self._hist_inner = tk.Frame(self._hist_cv, bg=C["bg"])
        self._hist_cv.create_window(0, 0, anchor="nw", window=self._hist_inner)
        self._hist_inner.bind(
            "<Configure>",
            lambda e: self._hist_cv.configure(scrollregion=self._hist_cv.bbox("all")),
        )
        self._hist_cv.bind(
            "<MouseWheel>",
            lambda e: self._hist_cv.yview_scroll(
                int(-1 * (e.delta / 120)) * 3, "units"
            ),
        )
        self._hist_inner.bind(
            "<MouseWheel>",
            lambda e: self._hist_cv.yview_scroll(
                int(-1 * (e.delta / 120)) * 3, "units"
            ),
        )

    def _refresh_history_view(self):
        for w in self._hist_inner.winfo_children():
            w.destroy()
        filt = getattr(self, "_hist_filter", None)
        filt = filt.get() if filt else "all"
        entries = list(reversed(self._history))
        if filt != "all":
            entries = [e for e in entries if e.get("source", "library") == filt]
        if not entries:
            tk.Label(
                self._hist_inner,
                text="No history yet — play some tracks.",
                font=FM,
                fg=C["white3"],
                bg=C["bg"],
            ).pack(padx=24, pady=20)
            return
        src_colors = {
            "library":   C["white3"],
            "spotify":   "#1db954",
            "youtube":   "#ff0000",
            "soundcloud":"#ff5500",
            "deezer":    "#a238ff",
            "archive":   "#4a9eff",
            "bandcamp":  "#1da0c3",
        }
        for i, e in enumerate(entries):
            bg = C["select"] if i % 2 == 0 else C["bg"]
            row = tk.Frame(self._hist_inner, bg=bg, cursor="hand2")
            row.pack(fill="x")
            ts_str = time.strftime("%H:%M:%S", time.localtime(e.get("ts", 0)))
            src = e.get("source", "library")
            src_col = src_colors.get(src, C["white3"])
            src_badge = {
                "library": "SRC::LIB", "spotify": "SRC::SPT",
                "youtube": "SRC::YT", "soundcloud": "SRC::SC",
                "deezer": "SRC::DZ", "archive": "SRC::IA",
                "bandcamp": "SRC::BC",
            }.get(src, "SRC::???")
            # hex track ID
            tk.Label(row, text=f"0x{i:04X}", font=("Courier New", 6),
                     fg=C["white3"], bg=bg, width=7, anchor="w"
                     ).pack(side="left", padx=(10, 0), pady=5)
            tk.Label(row, text=f"[{ts_str}]", font=("Courier New", 7),
                     fg=C["white3"], bg=bg, width=11, anchor="w"
                     ).pack(side="left")
            tk.Label(row, text=src_badge, font=("Courier New", 8, "bold"),
                     fg=src_col, bg=bg, width=9, anchor="w"
                     ).pack(side="left")
            tk.Label(row, text=e.get("title", "")[:36], font=FM,
                     fg=C["white"], bg=bg, anchor="w"
                     ).pack(side="left", padx=6)
            tk.Label(row, text=e.get("artist", "")[:24], font=FMS,
                     fg=C["white3"], bg=bg, anchor="w"
                     ).pack(side="left")
            for w in (row,) + tuple(row.winfo_children()):
                w.bind("<Enter>", lambda ev, r=row: r.config(bg=C["select2"]))
                w.bind("<Leave>", lambda ev, r=row, b=bg: r.config(bg=b))

    def _clear_history(self):
        self._history = []
        self._refresh_history_view()
        self._save()

    # ── LAST.FM ───────────────────────────
    def _schedule_scrobble(self):
        if self._scrobble_job:
            self.root.after_cancel(self._scrobble_job)

        # Poll every 30s to check if we should scrobble
        def _check():
            if self._scrobbler:
                self._scrobbler.track_maybe_scrobble()
            self._scrobble_job = self.root.after(30000, _check)

        self._scrobble_job = self.root.after(30000, _check)

    def _open_lastfm_auth(self):
        """Open Last.fm auth flow in browser."""
        sk = self.settings.get("lastfm_session_key", "")
        if sk:
            from tkinter import messagebox

            messagebox.showinfo(
                "Last.fm",
                "Already connected.\nTo disconnect, clear the session key in Settings.",
                parent=self.root,
            )
            return
        key = self.settings.get("lastfm_api_key", "").strip()
        sec = self.settings.get("lastfm_api_secret", "").strip()
        if not key or not sec:
            from tkinter import messagebox

            messagebox.showwarning(
                "Last.fm",
                "Enter your API key and secret in Settings first.",
                parent=self.root,
            )
            return
        scr = LastFmScrobbler(api_key=key, api_secret=sec)
        token = scr.get_token()
        if not token:
            from tkinter import messagebox

            messagebox.showerror(
                "Last.fm", "Could not get token — check API key.", parent=self.root
            )
            return
        webbrowser.open(scr.get_auth_url(token))

        # Poll for session key
        def _poll_session(attempts=0):
            if attempts > 30:
                return
            sk2 = scr.get_session(token)
            if sk2:
                self.settings["lastfm_session_key"] = sk2
                self._scrobbler.session_key = sk2
                self._save()
                self._set_status("LASTFM OK")
            else:
                self.root.after(3000, lambda: _poll_session(attempts + 1))

        self.root.after(3000, _poll_session)

    # ── DISCORD ───────────────────────────
    def _discord_connect(self):
        if not self.settings.get("discord_enabled", False):
            return
        ok = self._discord.connect()
        self._discord_enabled = ok

    # ── CROSSFADE ─────────────────────────
    def _start_crossfade(self, seconds, on_done):
        if self._xfade_job:
            self.root.after_cancel(self._xfade_job)
            self._xfade_job = None
        target_vol = self.engine.volume
        self._xfade_target_vol = target_vol
        self._xfade_fading_in = False
        step_ms = 40
        out_steps = max(8, int(seconds * 1000 / step_ms))
        in_steps = out_steps

        def _fade_out(n=0):
            if not self.engine.is_playing and n > 2:
                _do_load()
                return
            self.engine.set_volume(max(0.0, target_vol * (1.0 - n / out_steps)))
            if n < out_steps:
                self._xfade_job = self.root.after(step_ms, lambda: _fade_out(n + 1))
            else:
                _do_load()

        def _do_load():
            self.engine._volume = 0.0
            self._xfade_fading_in = True
            self._xfade_loading = True
            on_done()
            self._xfade_loading = False
            self.root.after(step_ms * 2, _fade_in)

        def _fade_in(n=0):
            if not self._xfade_fading_in:
                return
            self.engine.set_volume(
                min(self._xfade_target_vol, self._xfade_target_vol * (n + 1) / in_steps)
            )
            if n < in_steps - 1:
                self._xfade_job = self.root.after(step_ms, lambda: _fade_in(n + 1))
            else:
                self.engine.set_volume(self._xfade_target_vol)
                self._xfade_fading_in = False
                self._xfade_job = None

        _fade_out()

    # ── FOLDER WATCHER ────────────────────
    def _on_watcher_new_file(self, path):
        """Called from watcher thread when a new audio file appears."""

        def _add():
            # Check not already in library
            existing = {t["path"] for t in self.library}
            if path not in existing:
                meta = self.engine.get_metadata(path)
                meta["path"] = path
                self.library.append(meta)
                self._save()
                self._refresh_tracks()
                self._set_status("NEW TRACK")

        self.root.after(0, _add)

    def _open_watch_dirs(self):
        dirs = self.settings.get("watch_dirs", [])
        win = tk.Toplevel(self.root)
        content, _close = self._popup_setup(win, "SYS::WATCH FOLDERS", w=460, h=320)

        tk.Label(content, text="AUTO-SCAN FOLDERS", font=FMX, fg=C["white"], bg=C["bg"]).pack(pady=(14, 4), padx=20, anchor="w")
        tk.Label(content, text="New audio files in these folders are added automatically.",
                 font=FMS, fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=20, pady=8)

        lf = tk.Frame(content, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=20)
        self._watch_listbox = tk.Listbox(
            lf,
            bg=C["panel"],
            fg=C["white"],
            font=FM,
            selectbackground=C["select2"],
            selectforeground=C["white"],
            bd=0,
            highlightthickness=1,
            highlightbackground=C["border"],
            activestyle="none",
        )
        self._watch_listbox.pack(fill="both", expand=True)
        for d in dirs:
            self._watch_listbox.insert("end", d)

        bf = tk.Frame(content, bg=C["bg"])
        bf.pack(fill="x", padx=20, pady=10)

        def _add_dir():
            d = filedialog.askdirectory(parent=win)
            if d and d not in dirs:
                dirs.append(d)
                self._watch_listbox.insert("end", d)
                self.settings["watch_dirs"] = dirs
                self._watcher.watch(d)
                self._save()

        def _rem_dir():
            sel = self._watch_listbox.curselection()
            if sel:
                d = self._watch_listbox.get(sel[0])
                dirs.remove(d)
                self._watch_listbox.delete(sel[0])
                self.settings["watch_dirs"] = dirs
                self._save()

        for txt, cmd in [("+ Add Folder", _add_dir), ("− Remove", _rem_dir)]:
            b = tk.Label(
                bf,
                text=txt,
                font=FM,
                fg=C["white3"],
                bg=C["panel"],
                cursor="hand2",
                padx=10,
                pady=4,
            )
            b.pack(side="left", padx=(0, 6))
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white3"], C["white"], duration_ms=60))
            b.bind("<Leave>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white"], C["white3"], duration_ms=60))

    # ── WAVEFORM SEEKBAR ──────────────────
    def _load_waveform(self, path):
        """Load audio waveform in background for the seekbar."""
        self._waveform_data = None
        self._waveform_last_px = -1  # force full redraw when new waveform arrives
        _load_path = path  # capture for race-condition check

        def _worker():
            try:
                if not SCIPY_AVAILABLE:
                    return
                import numpy as _np_w

                ext = str(path).lower().rsplit(".", 1)[-1]
                pcm = None
                # WAV: use stdlib wave (fast, no extra deps)
                if ext == "wav":
                    import wave

                    with wave.open(str(path), "rb") as wf:
                        n_ch = wf.getnchannels()
                        rate = wf.getframerate()
                        n = wf.getnframes()
                        if n > rate * 600:
                            return  # skip files > 10 min
                        raw = wf.readframes(n)
                    pcm = _np_w.frombuffer(raw, dtype=_np_w.int16).astype(_np_w.float32)
                    if n_ch == 2:
                        pcm = pcm.reshape(-1, 2).mean(axis=1)
                    pcm /= 32768.0
                # MP3 / FLAC / OGG / M4A: use soundfile (already a dep via scipy)
                elif ext in ("mp3", "flac", "ogg", "m4a", "aac", "wma", "opus"):
                    try:
                        import soundfile as _sf_w

                        data, rate = _sf_w.read(
                            str(path), dtype="float32", always_2d=True
                        )
                        if len(data) > rate * 600:
                            return  # skip > 10 min
                        pcm = data.mean(axis=1)
                    except Exception:
                        return
                else:
                    return
                if pcm is None or len(pcm) < 2:
                    return
                # Race check — if track changed while decoding, discard
                if self._current_play_path != _load_path:
                    return
                # Downsample to 600 envelope points — vectorised, no Python loop
                buckets = 600
                trim    = (len(pcm) // buckets) * buckets
                if trim < buckets:
                    trim = len(pcm)
                    buckets = max(1, trim)
                mat   = _np_w.abs(pcm[:trim]).reshape(buckets, -1)
                # Blend peak + RMS for a waveform that shows both transients
                # and sustained energy (pure peak looks spiky, pure RMS too flat)
                peak_vals = mat.max(axis=1)
                rms_vals  = _np_w.sqrt((mat ** 2).mean(axis=1))
                blended   = peak_vals * 0.6 + rms_vals * 0.4
                # Normalise so the loudest point fills the bar
                max_val = blended.max()
                if max_val > 0:
                    blended /= max_val
                peaks = blended.tolist()
                if self._current_play_path != _load_path:
                    return
                self._waveform_data = peaks
                self.root.after(0, self._draw_waveform_seekbar)
            except Exception:
                pass

        threading.Thread(target=_worker, daemon=True).start()

    # ── TAG EDITOR ────────────────────────
    def _open_tag_editor(self, lib_idx):
        if lib_idx < 0 or lib_idx >= len(self.library):
            return
        track = self.library[lib_idx]
        win = tk.Toplevel(self.root)
        content, _close = self._popup_setup(win, "SYS::EDIT TAGS", w=420, h=300)

        tk.Label(content, text="EDIT TAGS", font=FMX, fg=C["white"], bg=C["bg"]).pack(
            pady=(14, 2), padx=20, anchor="w"
        )
        tk.Label(content, text=Path(track["path"]).name[:52], font=FMS, fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8, 12))

        fields = {}
        for label, key in [
            ("Title", "title"),
            ("Artist", "artist"),
            ("Album", "album"),
        ]:
            row = tk.Frame(content, bg=C["bg"])
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=f"{label:<8}", font=FM, fg=C["white3"], bg=C["bg"], width=8, anchor="w").pack(side="left")
            var = tk.StringVar(value=track.get(key, ""))
            e = tk.Entry(row, textvariable=var, font=FM, bg=C["panel"], fg=C["white"],
                         insertbackground=C["white"], relief="flat", bd=0,
                         highlightthickness=1, highlightbackground=C["border"])
            e.pack(side="left", fill="x", expand=True, ipady=4)
            fields[key] = var

        def _save_tags():
            for key, var in fields.items():
                track[key] = var.get().strip()
                self.library[lib_idx][key] = track[key]
            if MUTAGEN_AVAILABLE:
                try:
                    from mutagen.id3 import ID3, TIT2, TPE1, TALB
                    try:
                        tags = ID3(track["path"])
                    except:
                        tags = ID3()
                    tags[TIT2.__name__] = TIT2(encoding=3, text=track["title"])
                    tags[TPE1.__name__] = TPE1(encoding=3, text=track["artist"])
                    tags[TALB.__name__] = TALB(encoding=3, text=track["album"])
                    tags.save(track["path"])
                except Exception:
                    pass
            self._save()
            self._refresh_tracks()
            self._popup_fadeout(win)

        bf = tk.Frame(content, bg=C["bg"])
        bf.pack(pady=14)
        for txt, cmd in [("SAVE", _save_tags), ("CANCEL", lambda: self._popup_fadeout(win))]:
            b = tk.Label(bf, text=txt, font=FM, fg=C["white3"], bg=C["panel"],
                         cursor="hand2", padx=10, pady=5)
            b.pack(side="left", padx=6)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white3"], C["white"], duration_ms=60))
            b.bind("<Leave>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white"], C["white3"], duration_ms=60))

    # ── SMART PLAYLISTS ───────────────────
    def _open_smart_playlist(self):
        win = tk.Toplevel(self.root)
        content, _close = self._popup_setup(win, "SYS::SMART PLAYLIST", w=460, h=380)

        tk.Label(content, text="SMART PLAYLIST", font=FMX, fg=C["white"], bg=C["bg"]).pack(pady=(14, 4), padx=20, anchor="w")
        tk.Label(content, text="Auto-fills based on rules applied to your library.", font=FMS, fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8, 12))

        # Name
        nf = tk.Frame(content, bg=C["bg"])
        nf.pack(fill="x", padx=20, pady=4)
        tk.Label(nf, text="Name    ", font=FM, fg=C["white3"], bg=C["bg"]).pack(side="left")
        name_var = tk.StringVar(value="Smart Mix")
        tk.Entry(
            nf,
            textvariable=name_var,
            font=FM,
            bg=C["panel"],
            fg=C["white"],
            insertbackground=C["white"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=C["border"],
        ).pack(side="left", fill="x", expand=True, ipady=4)

        # Rule
        rf = tk.Frame(content, bg=C["bg"])
        rf.pack(fill="x", padx=20, pady=8)
        tk.Label(rf, text="Rule    ", font=FM, fg=C["white3"], bg=C["bg"]).pack(side="left")
        field_var = tk.StringVar(value="artist")
        op_var = tk.StringVar(value="contains")
        val_var = tk.StringVar()
        tk.OptionMenu(rf, field_var, "artist", "title", "album").pack(side="left")
        tk.OptionMenu(rf, op_var, "contains", "starts with", "ends with").pack(side="left", padx=4)
        tk.Entry(rf, textvariable=val_var, font=FM, bg=C["panel"], fg=C["white"],
                 insertbackground=C["white"], relief="flat", bd=0,
                 highlightthickness=1, highlightbackground=C["border"], width=18).pack(side="left", ipady=4)

        # Limit
        lf2 = tk.Frame(content, bg=C["bg"])
        lf2.pack(fill="x", padx=20, pady=4)
        tk.Label(lf2, text="Limit   ", font=FM, fg=C["white3"], bg=C["bg"]).pack(side="left")
        limit_var = tk.IntVar(value=25)
        tk.Spinbox(lf2, from_=5, to=500, textvariable=limit_var, font=FM,
                   bg=C["panel"], fg=C["white"], width=6,
                   buttonbackground=C["border"], relief="flat").pack(side="left")
        tk.Label(lf2, text=" tracks", font=FM, fg=C["white3"], bg=C["bg"]).pack(side="left")

        # Sort
        sf2 = tk.Frame(content, bg=C["bg"])
        sf2.pack(fill="x", padx=20, pady=4)
        tk.Label(sf2, text="Sort by ", font=FM, fg=C["white3"], bg=C["bg"]).pack(side="left")
        sort_var = tk.StringVar(value="title")
        tk.OptionMenu(sf2, sort_var, "title", "artist", "album", "random").pack(side="left")

        def _create():
            name = name_var.get().strip()
            field = field_var.get()
            op = op_var.get()
            val = val_var.get().strip().lower()
            limit = limit_var.get()
            sort = sort_var.get()
            if not name or not val:
                return
            matches = []
            for i, t in enumerate(self.library):
                fv = t.get(field, "").lower()
                hit = (
                    (op == "contains" and val in fv)
                    or (op == "starts with" and fv.startswith(val))
                    or (op == "ends with" and fv.endswith(val))
                )
                if hit:
                    matches.append(i)
            if sort == "random":
                random.shuffle(matches)
            elif sort in ("title", "artist", "album"):
                matches.sort(key=lambda i: self.library[i].get(sort, "").lower())
            matches = matches[:limit]
            self.playlists[name] = matches
            self._refresh_pl_sidebar()
            self._save()
            self._set_status(f"SMART: {len(matches)} TRACKS")
            self._popup_fadeout(win)

        bf = tk.Frame(content, bg=C["bg"])
        bf.pack(pady=14)
        for txt, cmd in [("CREATE", _create), ("CANCEL", lambda: self._popup_fadeout(win))]:
            b = tk.Label(bf, text=txt, font=FM, fg=C["white3"], bg=C["panel"],
                         cursor="hand2", padx=10, pady=5)
            b.pack(side="left", padx=6)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white3"], C["white"], duration_ms=60))
            b.bind("<Leave>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white"], C["white3"], duration_ms=60))

    # ── DUPLICATE DETECTOR ────────────────
    def _open_duplicate_detector(self):
        # Group by (title.lower, artist.lower)
        from collections import defaultdict

        groups = defaultdict(list)
        for i, t in enumerate(self.library):
            key = (
                t.get("title", "").lower().strip(),
                t.get("artist", "").lower().strip(),
            )
            groups[key].append(i)
        dupes = {k: v for k, v in groups.items() if len(v) > 1}

        win = tk.Toplevel(self.root)
        content, _close = self._popup_setup(win, "SYS::DUPLICATE DETECTOR", w=560, h=400)

        tk.Label(content, text="DUPLICATE TRACKS", font=FMX, fg=C["white"], bg=C["bg"]).pack(pady=(14, 4), padx=20, anchor="w")
        count_txt = (f"{len(dupes)} duplicate group(s) found" if dupes else "No duplicates found.")
        tk.Label(content, text=count_txt, font=FMS, fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8, 0))

        lf = tk.Frame(content, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=10, pady=8)
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"], width=6, bd=0, highlightthickness=0)
        sb.pack(side="right", fill="y")
        lb = tk.Listbox(lf, bg=C["bg"], fg=C["white"], font=FM, selectbackground=C["select2"],
                        bd=0, highlightthickness=0, activestyle="none", yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.config(command=lb.yview)

        to_remove = []
        for (title, artist), idxs in dupes.items():
            lb.insert("end", f"  {title[:36]}  —  {artist[:24]}")
            for i, idx in enumerate(idxs):
                p = Path(self.library[idx]["path"])
                label = f"    {'[KEEP] ' if i == 0 else '[DUPE] '}{p.name[:50]}"
                lb.insert("end", label)
                if i > 0:
                    to_remove.append(idx)
            lb.insert("end", "")

        def _remove_dupes():
            keep = set(range(len(self.library))) - set(to_remove)
            self.library = [self.library[i] for i in sorted(keep)]
            self._save()
            self._refresh_tracks()
            self._popup_fadeout(win)
            self._set_status(f"REMOVED {len(to_remove)}")

        bf = tk.Frame(content, bg=C["bg"])
        bf.pack(pady=8)
        if to_remove:
            b = tk.Label(bf, text=f"REMOVE {len(to_remove)} DUPES", font=FM, fg=C["white3"],
                         bg=C["panel"], cursor="hand2", padx=10, pady=5)
            b.pack(side="left", padx=6)
            b.bind("<Button-1>", lambda e: _remove_dupes())
            b.bind("<Enter>", lambda e: ColorAnim.run(self.root, b, "fg", C["white3"], C["white"], duration_ms=60))
            b.bind("<Leave>", lambda e: ColorAnim.run(self.root, b, "fg", C["white"], C["white3"], duration_ms=60))
        cl2 = tk.Label(bf, text="CLOSE", font=FM, fg=C["white3"], bg=C["panel"],
                       cursor="hand2", padx=10, pady=5)
        cl2.pack(side="left", padx=6)
        cl2.bind("<Button-1>", lambda e: self._popup_fadeout(win))
        cl2.bind("<Enter>", lambda e: ColorAnim.run(self.root, cl2, "fg", C["white3"], C["white"], duration_ms=60))
        cl2.bind("<Leave>", lambda e: ColorAnim.run(self.root, cl2, "fg", C["white"], C["white3"], duration_ms=60))

    # ── EXPORT PLAYLIST ───────────────────
    def _export_playlist_m3u(self, name=None):
        tracks = []
        if name and name in self.playlists:
            tracks = [
                self.library[i] for i in self.playlists[name] if i < len(self.library)
            ]
        elif self.active_playlist and self.active_playlist in self.playlists:
            tracks = [
                self.library[i]
                for i in self.playlists[self.active_playlist]
                if i < len(self.library)
            ]
        else:
            tracks = self.library

        out = filedialog.asksaveasfilename(
            defaultextension=".m3u",
            filetypes=[("M3U Playlist", "*.m3u"), ("All files", "*")],
            initialfile=(name or "oternos_export") + ".m3u",
            parent=self.root,
        )
        if not out:
            return
        try:
            lines = ["#EXTM3U"]
            for t in tracks:
                dur = int(t.get("duration", 0))
                lines.append(
                    f"#EXTINF:{dur},{t.get('artist', '')} - {t.get('title', '')}"
                )
                lines.append(t["path"])
            Path(out).write_text("\n".join(lines), encoding="utf-8")
            self._set_status("EXPORTED")
        except Exception:
            self._set_status("EXPORT ERR")

    # ── NEW VISUALIZER MODES ──────────────
    def _viz_spectrum(self, cv, W, H, t, playing, bars):
        """Classic mirrored spectrum analyser."""
        _cx, cy = W / 2, H / 2
        n = len(bars)
        bw = W / n
        for i, b in enumerate(bars):
            amp = b
            h2 = max(2, amp * H * 0.85)
            br = min(255, int(60 + amp * 195))
            col = f"#{br:02x}{br:02x}{br:02x}"
            x = i * bw
            # Mirrored top + bottom
            cv.create_rectangle(
                x + 1, cy - h2 / 2, x + bw - 1, cy + h2 / 2, fill=col, outline=""
            )
        # Centre line
        cv.create_line(0, cy, W, cy, fill=C["border"], width=1)

    def _viz_oscilloscope(self, cv, W, H, t, playing, bars):
        """Smooth oscilloscope waveform drawn as a connected line."""
        cy = H / 2
        n = len(bars)
        points = []
        for i, b in enumerate(bars):
            x = i / (n - 1) * W
            # Alternate positive/negative for waveform feel
            sign = math.sin(i * 0.65 + t * 0.08)
            y = cy + sign * b * cy * 0.85
            points.append(x)
            points.append(y)
        if len(points) >= 4:
            br = min(255, int(80 + self._viz_glow * 175))
            col = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_line(points, fill=col, width=2, smooth=True)
        # Scan line
        scan_x = t % (W or 1)
        cv.create_line(scan_x, 0, scan_x, H, fill=C["border"], width=1)

    def _viz_particles(self, cv, W, H, t, playing, bars):
        """Particles that explode outward on beat."""
        _cx, _cy = W / 2, H / 2
        energy = sum(bars[:8]) / 8
        # Update particle positions
        for p in self._viz_grid_particles:
            speed = 0.008 + energy * 0.025
            p[0] += p[2] * speed
            p[1] += p[3] * speed
            # Bounce off edges
            if p[0] < 0 or p[0] > 1:
                p[2] *= -1
            if p[1] < 0 or p[1] > 1:
                p[3] *= -1
            p[0] = max(0, min(1, p[0]))
            p[1] = max(0, min(1, p[1]))
        # Draw particles
        for i, p in enumerate(self._viz_grid_particles):
            x, y = p[0] * W, p[1] * H
            # Size pulses with beat
            sz = 2 + energy * 6 + math.sin(t * 0.04 + i * 0.5) * 1.5
            br = min(255, int(50 + energy * 200))
            col = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_oval(x - sz, y - sz, x + sz, y + sz, fill=col, outline="")
        # Connect nearby particles
        pts = self._viz_grid_particles
        thresh = 0.18
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                dist = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
                if dist < thresh:
                    alpha = int((1 - dist / thresh) * 60)
                    col = f"#{alpha:02x}{alpha:02x}{alpha:02x}"
                    cv.create_line(
                        pts[i][0] * W,
                        pts[i][1] * H,
                        pts[j][0] * W,
                        pts[j][1] * H,
                        fill=col,
                        width=1,
                    )

    # ══════════════════════════════════════
    #  MODE: GLITCH
    #  Corrupted scanlines, block tears, CRT noise, and a fragmenting waveform.
    #  Idle = slow drift; playing = hard cuts, colour bleed, heavy block glitches.
    # ══════════════════════════════════════
    def _viz_glitch(self, cv, W, H, t, playing, bars):
        energy = sum(bars[:8]) / 8
        glow   = self._viz_glow
        iW, iH = int(W), int(H)   # range() and randint() require ints

        # ── seeded randomness so glitches are repeatable per-frame ──
        rng = random.Random(t * 7 + int(energy * 1000))

        # ── CRT scanlines ──
        step = 4 if playing else 8
        for y in range(0, iH, step):
            br = rng.randint(8, 22) if playing else rng.randint(4, 12)
            col = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_line(0, y, iW, y, fill=col, width=1)

        # ── horizontal block tears ──
        n_tears = int(2 + energy * 10) if playing else 1
        for _ in range(n_tears):
            ty   = rng.randint(0, iH)
            th   = rng.randint(2, max(3, int(12 * energy)))
            tx   = rng.randint(-60, 60)
            br   = rng.randint(40, min(255, int(80 + energy * 175)))
            col  = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_rectangle(tx, ty, iW + tx, ty + th, fill=col, outline="")

        # ── corrupted data columns ──
        n_cols = int(3 + energy * 8) if playing else 2
        for _ in range(n_cols):
            cx2  = rng.randint(0, iW)
            cw   = rng.randint(1, max(2, int(8 * energy)))
            cy2  = rng.randint(0, iH)
            ch2  = rng.randint(4, max(5, int(iH * 0.35 * energy)))
            br   = rng.randint(30, min(255, int(60 + energy * 195)))
            col  = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_rectangle(cx2, cy2, cx2 + cw, cy2 + ch2, fill=col, outline="")

        # ── waveform that glitches/tears on beats ──
        cy_mid = iH / 2
        pts = []
        for i, b in enumerate(bars):
            x      = i / (len(bars) - 1) * iW
            jitter = int(20 * energy)
            shift  = rng.randint(-jitter, jitter) if (playing and jitter > 0) else 0
            sign   = math.sin(i * 0.9 + t * 0.06)
            y      = cy_mid + sign * b * cy_mid * 0.7 + shift
            pts.extend([x, y])
        if len(pts) >= 4:
            br  = min(255, int(100 + glow * 155))
            col = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_line(pts, fill=col, width=2, smooth=True)

        # ── glitch text labels ──
        chars = "01XOR#@%&!"
        if playing:
            for _ in range(int(3 + energy * 6)):
                gx = rng.randint(0, max(1, iW - 20))
                gy = rng.randint(0, max(1, iH - 12))
                gc = rng.choice(chars)
                br = rng.randint(50, min(255, int(80 + energy * 175)))
                col = f"#{br:02x}{br:02x}{br:02x}"
                cv.create_text(gx, gy, text=gc, fill=col, font=("Courier New", 8))

        # ── bright centre flash on hard beat ──
        if playing and energy > 0.75:
            flash = int((energy - 0.75) / 0.25 * 180)
            fc    = min(255, flash)
            col   = f"#{fc:02x}{fc:02x}{fc:02x}"
            cv.create_rectangle(0, 0, iW, iH, fill=col, outline="", stipple="gray25")

        # ── corner brackets ──
        bsz  = 18
        hbr  = min(255, int(60 + glow * 120))
        bcol = C["border2"] if not playing else f"#{hbr:02x}{hbr:02x}{hbr:02x}"
        for ox, oy, dx, dy in [(0,0,1,1),(iW,0,-1,1),(0,iH,1,-1),(iW,iH,-1,-1)]:
            cv.create_line(ox, oy, ox + dx*bsz, oy,    fill=bcol, width=1)
            cv.create_line(ox, oy, ox,           oy + dy*bsz, fill=bcol, width=1)

    # ══════════════════════════════════════
    #  MODE: CIPHER
    #  Falling encrypted-data columns (monochrome Matrix rain).
    #  Each column has independent speed and phase.
    #  Playing = fast/bright; idle = slow/dim.
    # ══════════════════════════════════════
    def _viz_cipher(self, cv, W, H, t, playing, bars):
        # ── init persistent column state ──
        if not hasattr(self, "_cipher_cols"):
            n = 36
            rng = random.Random(42)
            self._cipher_cols = [
                {
                    "x":     rng.uniform(0, 1),          # normalised x
                    "y":     rng.uniform(-2, 0),          # normalised y (can start above screen)
                    "speed": rng.uniform(0.004, 0.014),
                    "len":   rng.randint(6, 18),
                    "phase": rng.uniform(0, 100),
                    "chars": [rng.randint(0, 15) for _ in range(20)],
                }
                for _ in range(n)
            ]

        energy  = sum(bars[:8]) / 8
        glow    = self._viz_glow
        fsize   = max(8, int(W / 38))
        fh      = fsize + 4
        charset = "01アイウエオカキクケコサシスセソタチツテトナニヌネノ#@%&"

        for col_data in self._cipher_cols:
            spd   = col_data["speed"] * (1.0 + energy * 2.5) if playing else col_data["speed"] * 0.35
            col_data["y"] += spd
            if col_data["y"] > 1.2:
                # reset to top with slight x drift
                col_data["y"]   = random.uniform(-0.5, -0.05)
                col_data["x"]   = random.uniform(0, 1)
                col_data["len"] = random.randint(6, 18)

            cx2 = int(col_data["x"] * W)
            cy_base = col_data["y"] * H

            for row in range(col_data["len"]):
                cy2 = cy_base - row * fh
                if cy2 < -fh or cy2 > H + fh:
                    continue

                # fade: head = brightest, tail fades to black
                frac = 1.0 - (row / col_data["len"])
                if row == 0:
                    # head glyph — white/bright
                    br = min(255, int(180 + glow * 75)) if playing else 120
                else:
                    base_br = int(55 + glow * 80) if playing else 28
                    br = max(10, int(base_br * frac))

                char_idx = (col_data["chars"][row % len(col_data["chars"])] + int(t * 0.7 + row)) % len(charset)
                ch  = charset[char_idx]
                col_hex = f"#{br:02x}{br:02x}{br:02x}"
                cv.create_text(
                    cx2, int(cy2),
                    text=ch,
                    fill=col_hex,
                    font=("Courier New", fsize, "bold"),
                    anchor="n",
                )

        # ── horizontal scan rule at mid-screen ──
        scan_y = H * 0.5 + math.sin(t * 0.02) * H * 0.3
        sbr    = int(30 + glow * 40) if playing else 18
        cv.create_line(0, scan_y, W, scan_y, fill=f"#{sbr:02x}{sbr:02x}{sbr:02x}", width=1)

        # ── bottom bar: spectrum underlay ──
        bw = W / len(bars)
        for i, b in enumerate(bars):
            hh  = max(2, b * H * 0.12)
            br  = min(255, int(25 + b * 90))
            col_hex = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_rectangle(i * bw, H - hh, i * bw + bw - 1, H, fill=col_hex, outline="")

    # ══════════════════════════════════════
    #  MODE: ARASAKA
    #  Corporate targeting reticle —
    #  nested rings, rotating data-arc segments,
    #  radial tick grid, and a centre lock crosshair.
    # ══════════════════════════════════════
    def _viz_arasaka(self, cv, W, H, t, playing, bars):
        cx, cy = W / 2, H / 2
        R      = min(W, H) * 0.40
        glow   = self._viz_glow
        energy = sum(bars[:8]) / 8

        # ── radial grid lines (targeting overlay) ──
        n_spokes = 24
        for i in range(n_spokes):
            a   = i / n_spokes * math.pi * 2
            br  = 18 if not playing else int(20 + glow * 18)
            col = f"#{br:02x}{br:02x}{br:02x}"
            cv.create_line(cx, cy, cx + R * 1.25 * math.cos(a), cy + R * 1.25 * math.sin(a),
                           fill=col, width=1)

        # ── concentric rings with alternating brightness ──
        for ri in range(6):
            frac = (ri + 1) / 6
            r    = R * frac
            br   = int(22 + 20 * (1 - frac)) if not playing else int(35 + 55 * (1 - frac) + glow * 40 * (1 - frac))
            br   = min(255, br)
            lw   = 2 if ri == 2 else 1
            cv.create_oval(cx - r, cy - r, cx + r, cy + r,
                           outline=f"#{br:02x}{br:02x}{br:02x}", fill="", width=lw)

        # ── rotating data-arc segments (outer ring, driven by bars) ──
        n_segs = 48
        arc_r  = R * 1.08
        arc_w  = R * 0.14
        rot    = t * 0.008 * (1.8 if playing else 0.4)
        for i in range(n_segs):
            a_start = (i / n_segs) * 360 + math.degrees(rot)
            a_ext   = (360 / n_segs) * 0.72      # slight gap between segments
            h_val   = bars[i % len(bars)]
            if playing:
                br = int(40 + h_val * 215)
            else:
                br = int(18 + h_val * 45)
            br  = min(255, br)
            col = f"#{br:02x}{br:02x}{br:02x}"
            lw  = max(1, int(1 + h_val * 3))
            # draw as arc on outer ring
            r1 = arc_r
            r2 = arc_r + arc_w * h_val
            # approximate arc with line from inner to outer radius at mid-angle
            a_mid = math.radians(a_start + a_ext / 2)
            x1 = cx + r1 * math.cos(a_mid)
            y1 = cy + r1 * math.sin(a_mid)
            x2 = cx + r2 * math.cos(a_mid)
            y2 = cy + r2 * math.sin(a_mid)
            cv.create_line(x1, y1, x2, y2, fill=col, width=lw)

        # ── counter-rotating inner hex ──
        hex_r = R * 0.38
        rot2  = -t * 0.006 * (1.5 if playing else 0.3)
        hpts  = []
        for i in range(6):
            a = i / 6 * math.pi * 2 + rot2
            hpts.extend([cx + hex_r * math.cos(a), cy + hex_r * math.sin(a)])
        hbr = int(70 + glow * 80) if playing else 38
        hbr = min(255, hbr)
        cv.create_polygon(hpts, outline=f"#{hbr:02x}{hbr:02x}{hbr:02x}", fill="", width=1)

        # ── tick marks on the main ring ──
        for i in range(72):
            a      = i / 72 * math.pi * 2 + math.radians(t * 0.5 * (1 if playing else 0.15))
            long   = i % 6 == 0
            r_in   = R * (0.90 if long else 0.94)
            r_out  = R
            br     = int(80 + glow * 60) if (long and playing) else (40 if long else 22)
            br     = min(255, br)
            cv.create_line(cx + r_in * math.cos(a),  cy + r_in * math.sin(a),
                           cx + r_out * math.cos(a), cy + r_out * math.sin(a),
                           fill=f"#{br:02x}{br:02x}{br:02x}", width=(2 if long else 1))

        # ── lock crosshair ──
        ch_r  = R * 0.50
        gap   = R * 0.08
        ch_br = int(110 + glow * 100) if playing else 55
        ch_br = min(255, ch_br)
        ch_col = f"#{ch_br:02x}{ch_br:02x}{ch_br:02x}"
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            cv.create_line(cx + dx * gap, cy + dy * gap,
                           cx + dx * ch_r, cy + dy * ch_r,
                           fill=ch_col, width=1)

        # ── corner HUD text blocks ──
        hud_br  = int(35 + glow * 45) if playing else 22
        hud_col = f"#{hud_br:02x}{hud_br:02x}{hud_br:02x}"
        hud_items = [
            (12,  12,  "nw", "ARASAKA CORP"),
            (W-12, 12,  "ne", f"EN:{int(energy*100):03d}"),
            (12,  H-12, "sw", f"T:{t:06d}"),
            (W-12, H-12,"se", "LOCKED"),
        ]
        for hx, hy, anc, txt in hud_items:
            cv.create_text(hx, hy, text=txt, fill=hud_col,
                           font=("Courier New", 8), anchor=anc)

        # ── centre pulse ──
        pr  = 3 + glow * 7 if playing else 3
        pbr = int(180 + glow * 75) if playing else 70
        pbr = min(255, pbr)
        cv.create_oval(cx - pr, cy - pr, cx + pr, cy + pr,
                       fill=f"#{pbr:02x}{pbr:02x}{pbr:02x}", outline="")

    # ══════════════════════════════════════
    #  MIKU VIZ: TWIN TAILS
    #  Two massive swaying tail arcs + spectrum ring + floating notes
    # ══════════════════════════════════════
    def _viz_miku_tails(self, cv, W, H, t, playing, bars):
        cx = W / 2
        bass = sum(bars[:8]) / 8 if bars else 0
        sum(bars) / len(bars) if bars else 0

        # ── Head centred at top-third ──
        hcy = H * 0.28
        hr = min(W, H) * 0.058

        # ── Subtle spectrum bars at very bottom ──
        n = len(bars)
        bw = W / n
        bar_max = H * 0.08
        for i, h in enumerate(bars):
            bh = max(1, h * bar_max)
            x = i * bw
            if (i / n) < 0.5:
                v = int(8 + h * 55)
                col = f"#{v // 6:02x}{min(255, v + 40):02x}{min(255, v + 36):02x}"
            else:
                v = int(7 + h * 50)
                col = f"#{min(255, v + 55):02x}{v // 6:02x}{min(255, v + 44):02x}"
            cv.create_rectangle(
                x, H * 0.92 - bh, x + bw - 1, H * 0.92, fill=col, outline=""
            )

        # ── Twin tails using explicit bezier interpolation ──
        # Control points are defined in canvas coordinates so we can
        # see exactly what shape they make:
        #   P0 = bun (start, beside head)
        #   P1 = control 1 (pull slightly OUT and a bit down)
        #   P2 = control 2 (pull far DOWN and slightly back in)
        #   P3 = tip (end, hanging low)
        # This guarantees the tail goes DOWN with a gentle outward lean.

        sway_l = math.sin(t * 0.026) * (W * 0.018 + bass * W * 0.025)
        sway_r = math.sin(t * 0.021 + 1.1) * (W * 0.016 + bass * W * 0.022)

        bun_x_off = hr * 0.70  # buns sit left/right of head centre
        bun_y = hcy - hr * 0.4

        def _bezier4(p0, p1, p2, p3, segs=48):
            """Cubic bezier curve through 4 control points."""
            pts = []
            for i in range(segs):
                t2 = i / (segs - 1)
                mt = 1 - t2
                x = (
                    mt**3 * p0[0]
                    + 3 * mt**2 * t2 * p1[0]
                    + 3 * mt * t2**2 * p2[0]
                    + t2**3 * p3[0]
                )
                y = (
                    mt**3 * p0[1]
                    + 3 * mt**2 * t2 * p1[1]
                    + 3 * mt * t2**2 * p2[1]
                    + t2**3 * p3[1]
                )
                pts.extend([x, y])
            return pts

        def _draw_tail(bun_x, sign, sway, c_dark, c_bright):
            # P0: bun position
            p0 = (bun_x, bun_y)
            # P1: pull outward a little, barely down yet
            p1 = (bun_x + sign * W * 0.10 + sway * 0.3, bun_y + H * 0.08)
            # P2: now mostly down, still leaning out slightly
            p2 = (bun_x + sign * W * 0.14 + sway * 0.7, bun_y + H * 0.40)
            # P3: tip — hanging at ~75% of canvas height
            p3 = (bun_x + sign * W * 0.08 + sway, bun_y + H * 0.58)

            pts = _bezier4(p0, p1, p2, p3)
            if len(pts) >= 4:
                cv.create_line(pts, fill=c_dark, width=8, smooth=True, capstyle="round")
                cv.create_line(
                    pts, fill=c_bright, width=3, smooth=True, capstyle="round"
                )

        _draw_tail(cx - bun_x_off, -1, sway_l, "#093830", "#39c5bb")
        _draw_tail(cx + bun_x_off, +1, sway_r, "#093830", "#4dd8d0")

        # ── Head drawn on top of tail bases ──
        hv = int(70 + bass * 110)
        cv.create_oval(
            cx - hr,
            hcy - hr,
            cx + hr,
            hcy + hr,
            fill=C["bg"],
            outline=f"#{hv // 6:02x}{min(255, hv):02x}{min(255, hv - 3):02x}",
            width=2,
        )

        # ── ♪ inside head ──
        nv = int(90 + bass * 140)
        cv.create_text(
            cx,
            hcy,
            text="♪",
            font=("Consolas", max(8, int(hr * 0.95))),
            fill=f"#{nv // 6:02x}{min(255, nv):02x}{min(255, nv - 3):02x}",
            anchor="center",
        )

        # ── Bun circles ──
        br2 = hr * 0.32
        for bx in (cx - bun_x_off, cx + bun_x_off):
            cv.create_oval(
                bx - br2,
                bun_y - br2,
                bx + br2,
                bun_y + br2,
                fill=C["bg"],
                outline=f"#{hv // 6:02x}{min(255, hv):02x}{min(255, hv - 3):02x}",
                width=1,
            )

        # ── Floating ♪ notes ──
        if not hasattr(self, "_mt_notes"):
            self._mt_notes = []
        if bass > 0.38 and t % max(1, int(16 - bass * 10)) == 0:
            import random as _r

            self._mt_notes.append(
                {
                    "x": cx + _r.uniform(-W * 0.40, W * 0.40),
                    "y": H * 0.80,
                    "vy": _r.uniform(1.0, 2.2) + bass * 1.0,
                    "age": 0,
                    "sym": _r.choice(["♪", "♫", "♬", "✦"]),
                    "pink": _r.random() > 0.5,
                }
            )
        dead = []
        for n_ in self._mt_notes:
            n_["y"] -= n_["vy"]
            n_["age"] += 1
            life = n_["age"] / 60
            if life > 1 or n_["y"] < 0:
                dead.append(n_)
                continue
            alpha = int((1 - life) * 200)
            if n_["pink"]:
                nc = f"#{min(255, alpha + 55):02x}{alpha // 5:02x}{min(255, alpha + 44):02x}"
            else:
                nc = f"#{alpha // 6:02x}{min(255, alpha + 28):02x}{min(255, alpha + 22):02x}"
            cv.create_text(
                n_["x"],
                n_["y"],
                text=n_["sym"],
                font=("Consolas", max(8, int(11 - life * 3))),
                fill=nc,
                anchor="center",
            )
        for d in dead:
            self._mt_notes.remove(d)

    # ══════════════════════════════════════
    #  MIKU VIZ: SAKURA
    #  Cherry blossom storm + soft wave + name glow
    # ══════════════════════════════════════
    def _viz_miku_sakura(self, cv, W, H, t, playing, bars):
        bass = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0

        # Soft gradient backdrop — horizontal teal-to-dark strips
        strips = 8
        for i in range(strips):
            y1 = H * i / strips
            y2 = H * (i + 1) / strips
            frac = i / (strips - 1)
            gv = int(4 + frac * 12 + bass * 10)
            cv.create_rectangle(
                0,
                y1,
                W,
                y2,
                fill=f"#{gv:02x}{min(255, gv * 4):02x}{min(255, gv * 4 - 2):02x}",
                outline="",
            )

        # Gentle sine wave across centre
        pts = []
        steps = 80
        amp = H * (0.06 + energy * 0.12)
        for i in range(steps + 1):
            x = W * i / steps
            y = H / 2 + amp * math.sin(t * 0.035 + x * 0.018)
            pts.extend([x, y])
        if len(pts) >= 4:
            wv = int(20 + energy * 50)
            cv.create_line(
                pts,
                fill=f"#{wv // 4:02x}{min(255, wv + 20):02x}{min(255, wv + 15):02x}",
                width=2,
                smooth=True,
            )

        # Petal shower
        if not hasattr(self, "_sk_petals"):
            import random as _r

            self._sk_petals = [
                {
                    "x": _r.uniform(0, W),
                    "y": _r.uniform(-H, H),
                    "vx": _r.uniform(-0.6, 0.6),
                    "vy": _r.uniform(0.5, 1.8),
                    "a": _r.uniform(0, math.pi * 2),
                    "va": _r.uniform(-0.05, 0.05),
                    "sz": _r.uniform(3, 8),
                    "pink": _r.random() > 0.4,
                }
                for _ in range(30 + int(energy * 20))
            ]
        for p in self._sk_petals:
            p["x"] += p["vx"] + math.sin(t * 0.018) * 0.5 + bass * 0.4
            p["y"] += p["vy"] + bass * 0.6
            p["a"] += p["va"]
            if p["y"] > H + 12:
                import random as _r

                p["x"] = _r.uniform(0, W)
                p["y"] = -10
            pts = []
            for i in range(4):
                a2 = p["a"] + i * math.pi / 2
                pts += [
                    p["x"] + p["sz"] * math.cos(a2),
                    p["y"] + p["sz"] * 0.55 * math.sin(a2),
                ]
            pv = int(18 + energy * 55)
            if p["pink"]:
                col = f"#{min(255, pv + 90):02x}{pv // 3:02x}{min(255, pv + 75):02x}"
            else:
                col = f"#{pv // 4:02x}{min(255, pv + 45):02x}{min(255, pv + 40):02x}"
            cv.create_polygon(pts, fill=col, outline="")

        # "初音ミク" glow text
        tv = int(40 + bass * 120)
        cv.create_text(
            W / 2,
            H * 0.22,
            text="初音ミク",
            font=("Yu Gothic UI", max(14, int(min(W, H) * 0.055)))
            if self._font_exists("Yu Gothic UI")
            else ("Consolas", max(12, int(min(W, H) * 0.048))),
            fill=f"#{tv // 5:02x}{min(255, tv + 20):02x}{min(255, tv + 15):02x}",
            anchor="center",
        )
        cv.create_text(
            W / 2,
            H * 0.78,
            text="HATSUNE MIKU",
            font=("Consolas", max(8, int(min(W, H) * 0.028))),
            fill=f"#{tv // 8:02x}{min(255, tv // 2):02x}{min(255, tv // 2 - 3):02x}",
            anchor="center",
        )

    # ══════════════════════════════════════
    #  MIKU VIZ: STARFALL
    #  Falling ✦ stars + twin-tail silhouette + beat flash
    # ══════════════════════════════════════
    def _viz_miku_starfall(self, cv, W, H, t, playing, bars):
        bass = sum(bars[:8]) / 8 if bars else 0
        sum(bars) / len(bars) if bars else 0
        cx, cy = W / 2, H / 2

        # Beat flash background
        if bass > 0.6:
            fv = int(bass * 18)
            cv.create_rectangle(
                0,
                0,
                W,
                H,
                fill=f"#{fv // 4:02x}{min(255, fv * 3):02x}{min(255, fv * 3 - 3):02x}",
            )

        # Falling stars
        if not hasattr(self, "_sf_stars"):
            import random as _r

            self._sf_stars = [
                {
                    "x": _r.uniform(0, W),
                    "y": _r.uniform(-H, H),
                    "vy": _r.uniform(1.0, 3.5),
                    "sym": _r.choice(["✦", "✧", "★", "♪", "✦"]),
                    "sz": _r.randint(7, 14),
                    "pink": _r.random() > 0.5,
                    "twinkle_phase": _r.uniform(0, math.pi * 2),
                }
                for _ in range(40)
            ]
        for s in self._sf_stars:
            s["y"] += s["vy"] * (1 + bass * 1.8)
            if s["y"] > H + 20:
                import random as _r

                s["x"] = _r.uniform(0, W)
                s["y"] = -15
                s["sym"] = _r.choice(["✦", "✧", "★", "♪", "✦"])
            twinkle = math.sin(t * 0.08 + s["twinkle_phase"]) * 0.5 + 0.5
            sv = int(18 + twinkle * 80 + bass * 60)
            if s["pink"]:
                col = f"#{min(255, sv + 80):02x}{sv // 3:02x}{min(255, sv + 65):02x}"
            else:
                col = f"#{sv // 4:02x}{min(255, sv + 30):02x}{min(255, sv + 25):02x}"
            cv.create_text(
                s["x"],
                s["y"],
                text=s["sym"],
                font=("Consolas", s["sz"]),
                fill=col,
                anchor="center",
            )

        # Miku silhouette twin tails (simple outline, faint)
        sway = math.sin(t * 0.028) * (0.15 + bass * 0.22)
        tl = min(W, H) * 0.38

        def _outline_tail(bx, by, sign, sw, col):
            pts = []
            for i in range(30):
                frac = i / 29
                a = math.pi * (0.55 + sign * 0.78 * frac**0.7) + sw * frac**0.7
                r = tl * frac
                pts.extend([bx + r * math.cos(a) * sign, by + r * math.sin(a) * 1.1])
            if len(pts) >= 4:
                cv.create_line(pts, fill=col, width=2, smooth=True, capstyle="round")

        ov = int(16 + bass * 40)
        tc = f"#{ov // 4:02x}{min(255, ov + 20):02x}{min(255, ov + 16):02x}"
        _outline_tail(cx - W * 0.06, cy - H * 0.05, -1, sway, tc)
        _outline_tail(cx + W * 0.06, cy - H * 0.05, +1, -sway, tc)

        # ── Centre ♪ pulse dot ──
        cr = 5 + bass * 14
        cpv = int(45 + bass * 145)
        cv.create_oval(
            cx - cr,
            H * 0.25 - cr,
            cx + cr,
            H * 0.25 + cr,
            fill=f"#{cpv // 5:02x}{min(255, cpv):02x}{min(255, cpv - 4):02x}",
            outline="",
        )

    # ══════════════════════════════════════
    #  MIKU VIZ: RIBBON
    #  Flowing teal/pink ribbons that dance with the music
    # ══════════════════════════════════════
    def _viz_miku_ribbon(self, cv, W, H, t, playing, bars):
        bass = sum(bars[:8]) / 8 if bars else 0
        mid = sum(bars[8:24]) / 16 if len(bars) >= 24 else 0
        treble = sum(bars[32:]) / 16 if len(bars) >= 48 else 0
        energy = (bass + mid + treble) / 3

        # Multiple ribbon paths weaving across the screen
        ribbon_defs = [
            # (y_centre_frac, speed, amp_frac, freq, color_mode, width)
            (0.35, 0.028, 0.18, 0.016, "teal", 4),
            (0.50, 0.022, 0.22, 0.012, "pink", 4),
            (0.65, 0.032, 0.16, 0.020, "teal", 3),
            (0.42, 0.018, 0.12, 0.009, "dim", 2),
            (0.58, 0.024, 0.14, 0.011, "dim", 2),
        ]
        for yf, spd, ampf, freq, mode, lw in ribbon_defs:
            cy_r = H * yf
            amp = H * (ampf + energy * ampf * 1.5)
            pts = []
            steps = 100
            for i in range(steps + 1):
                x = W * i / steps
                phase = t * spd + x * freq
                y = (
                    cy_r
                    + amp * math.sin(phase)
                    + (bass * H * 0.06 * math.sin(phase * 2))
                )
                pts.extend([x, y])
            if len(pts) < 4:
                continue
            # color
            frac = math.sin(t * spd * 2) * 0.5 + 0.5
            if mode == "teal":
                v = int(20 + frac * 60 + energy * 80)
                col = f"#{v // 5:02x}{min(255, v + 25):02x}{min(255, v + 20):02x}"
            elif mode == "pink":
                v = int(15 + frac * 55 + energy * 70)
                col = f"#{min(255, v + 75):02x}{v // 4:02x}{min(255, v + 60):02x}"
            else:
                v = int(10 + frac * 25)
                col = f"#{v // 4:02x}{min(255, v + 15):02x}{min(255, v + 12):02x}"
            cv.create_line(pts, fill=col, width=lw, smooth=True)

        # Sparkle dots on ribbon peaks
        if t % 3 == 0:
            import random as _r

            for _ in range(int(2 + energy * 5)):
                sx = _r.uniform(0, W)
                sy = H / 2 + _r.uniform(-H * 0.25, H * 0.25)
                sr = _r.uniform(1.5, 3.5 + energy * 3)
                sv = int(30 + energy * 120)
                if _r.random() > 0.5:
                    sc = f"#{min(255, sv + 60):02x}{sv // 4:02x}{min(255, sv + 48):02x}"
                else:
                    sc = f"#{sv // 5:02x}{min(255, sv + 22):02x}{min(255, sv + 18):02x}"
                cv.create_oval(sx - sr, sy - sr, sx + sr, sy + sr, fill=sc, outline="")

        # "VOCALOID" label at bottom
        lv = int(14 + energy * 35)
        cv.create_text(
            W / 2,
            H * 0.90,
            text="V O C A L O I D",
            font=("Consolas", max(8, int(min(W, H) * 0.022))),
            fill=f"#{lv // 5:02x}{min(255, lv + 12):02x}{min(255, lv + 10):02x}",
            anchor="center",
        )

    # ══════════════════════════════════════
    #  MIKU VIZ: WAVEFORM
    #  Twin mirrored waveforms + teal/pink fill + beat pulse ring
    # ══════════════════════════════════════
    def _viz_miku_wave(self, cv, W, H, t, playing, bars):
        bass = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0
        cx, cy = W / 2, H / 2

        # Centre line
        lv = int(8 + energy * 20)
        cv.create_line(
            0,
            cy,
            W,
            cy,
            fill=f"#{lv // 4:02x}{min(255, lv * 3):02x}{min(255, lv * 3 - 2):02x}",
            width=1,
        )

        # Upper waveform (teal) — bars mapped to wave shape
        n = len(bars)
        upper = []
        lower = []
        for i in range(n):
            x = W * i / (n - 1)
            h = bars[i] * H * 0.40
            upper.extend([x, cy - h])
            lower.extend([x, cy + h])

        # Fill between centre and upper
        if len(upper) >= 4:
            fill_pts_top = [0, cy] + upper + [W, cy]
            tv = int(12 + energy * 45)
            cv.create_polygon(
                fill_pts_top,
                fill=f"#{tv // 5:02x}{min(255, tv + 20):02x}{min(255, tv + 16):02x}",
                outline="",
            )
            cv.create_line(upper, fill="#39c5bb", width=2, smooth=True)

        # Fill between centre and lower (pink)
        if len(lower) >= 4:
            fill_pts_bot = [0, cy] + lower + [W, cy]
            pv = int(10 + energy * 40)
            cv.create_polygon(
                fill_pts_bot,
                fill=f"#{min(255, pv + 50):02x}{pv // 4:02x}{min(255, pv + 40):02x}",
                outline="",
            )
            cv.create_line(lower, fill="#ff6eb4", width=2, smooth=True)

        # Beat pulse ring at centre
        pr = min(W, H) * (0.05 + bass * 0.18)
        pv = int(40 + bass * 160)
        cv.create_oval(
            cx - pr,
            cy - pr,
            cx + pr,
            cy + pr,
            outline=f"#{pv // 5:02x}{min(255, pv + 15):02x}{min(255, pv + 10):02x}",
            fill="",
            width=2,
        )
        if bass > 0.3:
            pr2 = pr * 1.6
            pv2 = int(pv * 0.4)
            cv.create_oval(
                cx - pr2,
                cy - pr2,
                cx + pr2,
                cy + pr2,
                outline=f"#{min(255, pv2 + 30):02x}{pv2 // 4:02x}{min(255, pv2 + 24):02x}",
                fill="",
                width=1,
            )

        # Scrolling note strip at top
        note_syms = "♪ ♫ ✦ ♩ ♬ ✧ ♪ ♫ ✦"
        nv = int(12 + energy * 30)
        cv.create_text(
            ((W // 2 + t * 2) % (W + 100)) - 50,
            H * 0.06,
            text=note_syms,
            font=("Consolas", max(7, int(min(W, H) * 0.022))),
            fill=f"#{nv // 5:02x}{min(255, nv + 15):02x}{min(255, nv + 12):02x}",
            anchor="center",
        )

    # ── HOTKEY CUSTOMISER ─────────────────
    def _open_hotkey_editor(self):
        win = tk.Toplevel(self.root)
        content, _close = self._popup_setup(win, "SYS::HOTKEYS", w=400, h=320)

        tk.Label(content, text="HOTKEY CUSTOMISER", font=FMX, fg=C["white"], bg=C["bg"]).pack(pady=(14, 4), padx=20, anchor="w")
        tk.Label(content, text="Press a key combo to assign. Global media keys always active.",
                 font=FMS, fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8, 12))

        actions = [
            ("Play / Pause", "play_pause"),
            ("Next track", "next"),
            ("Previous", "prev"),
            ("Volume up", "vol_up"),
            ("Volume down", "vol_down"),
        ]
        hk = self.settings.get("hotkeys", {})
        vars_ = {}
        for label, key in actions:
            row = tk.Frame(content, bg=C["bg"])
            row.pack(fill="x", padx=20, pady=3)
            tk.Label(row, text=f"{label:<18}", font=FM, fg=C["white3"], bg=C["bg"],
                     width=18, anchor="w").pack(side="left")
            var = tk.StringVar(value=hk.get(key, ""))
            e = tk.Entry(row, textvariable=var, font=FM, bg=C["panel"], fg=C["white"],
                         insertbackground=C["white"], relief="flat", bd=0,
                         highlightthickness=1, highlightbackground=C["border"], width=16)
            e.pack(side="left", ipady=4)
            vars_[key] = var

            def _capture(event, v=var):
                parts = []
                if event.state & 0x4: parts.append("Ctrl")
                if event.state & 0x1: parts.append("Shift")
                if event.state & 0x8: parts.append("Alt")
                parts.append(event.keysym)
                v.set("+".join(parts))
                return "break"
            e.bind("<KeyPress>", _capture)

        def _save_hk():
            for key, var in vars_.items():
                hk[key] = var.get()
            self.settings["hotkeys"] = hk
            self._save()
            self._apply_custom_hotkeys()
            self._popup_fadeout(win)

        bf = tk.Frame(content, bg=C["bg"])
        bf.pack(pady=14)
        for txt, cmd in [("SAVE", _save_hk), ("CANCEL", lambda: self._popup_fadeout(win))]:
            b = tk.Label(bf, text=txt, font=FM, fg=C["white3"], bg=C["panel"],
                         cursor="hand2", padx=10, pady=5)
            b.pack(side="left", padx=6)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white3"], C["white"], duration_ms=60))
            b.bind("<Leave>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white"], C["white3"], duration_ms=60))

    # ══════════════════════════════════════
    #  SPECTRUM ANALYZER (player bar strip)
    # ══════════════════════════════════════
    def _apply_custom_hotkeys(self):
        """Bind custom keyboard shortcuts from settings to root window."""
        hk = self.settings.get("hotkeys", {})
        action_map = {
            "play_pause": lambda: self._toggle_play(),
            "next":       lambda: self._next(),
            "prev":       lambda: self._prev(),
            "vol_up":     lambda: (self.engine.set_volume(min(1.0, self.engine.volume + 0.1)), self._upd_vol()),
            "vol_down":   lambda: (self.engine.set_volume(max(0.0, self.engine.volume - 0.1)), self._upd_vol()),
        }
        def _guard(fn):
            def _inner(e):
                fw = self.root.focus_get()
                if fw and fw.winfo_class() in ("Entry", "Text", "TEntry"):
                    return
                fn()
            return _inner
        for action, combo in hk.items():
            if not combo or action not in action_map:
                continue
            try:
                # Convert "Ctrl+Space" -> "<Control-space>"
                parts = combo.split("+")
                key = parts[-1]
                mods = parts[:-1]
                tk_combo = ""
                for m in mods:
                    tk_combo += f"{m}-"
                tk_combo = f"<{tk_combo}{key}>"
                self.root.bind(tk_combo, _guard(action_map[action]))
            except Exception:
                pass



    # ══════════════════════════════════════
    #  REPLAY GAIN / LOUDNESS NORMALIZATION
    # ══════════════════════════════════════
    def _measure_loudness(self, path, lib_idx=None):
        """
        Measure integrated loudness (RMS-based, roughly EBU R128 inspired).
        Stores gain_db in the library entry so tracks play at matched volume.
        Runs in background — call from _import_batch or on first play.
        """
        def _worker():
            gain_db = 0.0
            try:
                if SCIPY_AVAILABLE:
                    import numpy as _np
                    import soundfile as _sf2

                    data, sr = _sf2.read(path, dtype="float32", always_2d=True)
                    mono = data.mean(axis=1)

                    # Integrated RMS over the whole track (ignore silence)
                    # Target: -18 dBFS RMS (roughly -14 LUFS, broadcast standard)
                    TARGET_RMS = 0.1259  # 10^(-18/20)
                    rms = float(_np.sqrt(_np.mean(mono ** 2)))
                    if rms > 1e-6:
                        import math
                        gain_db = round(20.0 * math.log10(TARGET_RMS / rms), 2)
                        # Cap at ±15 dB to prevent extreme volume jumps
                        gain_db = max(-15.0, min(15.0, gain_db))

            except Exception:
                pass

            # Store in library
            if lib_idx is not None and 0 <= lib_idx < len(self.library):
                self.library[lib_idx]["gain_db"] = gain_db
            else:
                for t in self.library:
                    if t.get("path") == path:
                        t["gain_db"] = gain_db
                        break

        import threading as _th
        _th.Thread(target=_worker, daemon=True).start()


    def _seekbar_rclick(self, event):
        """Right-click on seekbar — add cue point or jump to existing one."""
        w = self.prog_cv.winfo_width() or 1
        dur = self.engine.duration
        if dur <= 0 or self.current_idx < 0:
            return
        r = max(0.0, min(1.0, event.x / w))
        pos_s = r * dur
        idx = self.current_idx

        # Check if click is near an existing cue (within 6px)
        cues = self._bookmarks.get(idx, [])
        for ci, (sec, label) in enumerate(cues):
            cue_x = int((sec / dur) * w)
            if abs(event.x - cue_x) <= 6:
                # Near existing cue — show context menu
                m = tk.Menu(self.root, tearoff=0,
                            bg=C["panel"], fg=C["white"], font=FMS,
                            relief="flat", bd=0,
                            activebackground=C["select2"],
                            activeforeground=C["white"])
                m.add_command(
                    label=f"▶  Jump to cue {ci+1}: {self._fmt(sec)}",
                    command=lambda s=sec: self.engine.seek(s)
                )
                m.add_command(
                    label=f"✎  Rename cue {ci+1}",
                    command=lambda i=ci: self._rename_cue(idx, i)
                )
                m.add_separator()
                m.add_command(
                    label=f"✕  Delete cue {ci+1}",
                    command=lambda i=ci: self._delete_cue(idx, i)
                )
                try:
                    m.tk_popup(event.x_root, event.y_root)
                finally:
                    m.grab_release()
                return

        # No existing cue nearby — add new one
        m = tk.Menu(self.root, tearoff=0,
                    bg=C["panel"], fg=C["white"], font=FMS,
                    relief="flat", bd=0,
                    activebackground=C["select2"],
                    activeforeground=C["white"])
        m.add_command(
            label=f"◈  Add cue point at {self._fmt(pos_s)}",
            command=lambda p=pos_s: self._add_cue_at(idx, p)
        )
        if cues:
            m.add_separator()
            m.add_command(
                label="✕  Clear all cues for this track",
                command=lambda: self._clear_cues(idx)
            )
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _add_cue_at(self, lib_idx, pos_s):
        """Add a numbered cue point at pos_s seconds."""
        cues = self._bookmarks.setdefault(lib_idx, [])
        n = len(cues) + 1
        label = f"CUE {n}"
        cues.append((pos_s, label))
        # Keep sorted by position
        cues.sort(key=lambda c: c[0])
        self._save()
        self._set_status(f"CUE {n} @ {self._fmt(pos_s)}")
        # Redraw seekbar immediately
        self._draw_waveform_seekbar()

    def _delete_cue(self, lib_idx, cue_idx):
        """Remove a cue point by index."""
        cues = self._bookmarks.get(lib_idx, [])
        if 0 <= cue_idx < len(cues):
            cues.pop(cue_idx)
            self._save()
            self._draw_waveform_seekbar()

    def _clear_cues(self, lib_idx):
        """Remove all cue points for a track."""
        self._bookmarks[lib_idx] = []
        self._save()
        self._draw_waveform_seekbar()

    def _rename_cue(self, lib_idx, cue_idx):
        """Rename a cue point via a simple dialog."""
        cues = self._bookmarks.get(lib_idx, [])
        if 0 <= cue_idx < len(cues):
            sec, old_label = cues[cue_idx]
            new_label = simpledialog.askstring(
                "Rename Cue",
                f"Name for cue at {self._fmt(sec)}:",
                initialvalue=old_label,
                parent=self.root,
            )
            if new_label and new_label.strip():
                cues[cue_idx] = (sec, new_label.strip())
                self._save()
                self._draw_waveform_seekbar()

    def _apply_replay_gain(self, gain_db):
        """
        Apply replay gain by scaling the engine volume.
        Stores original volume and restores it when normalization is off.
        """
        if not self.settings.get("normalize"):
            return
        import math
        linear = 10.0 ** (gain_db / 20.0)
        adjusted = max(0.0, min(1.0, self.engine.volume * linear))
        self.engine.set_volume(adjusted)

    # ══════════════════════════════════════
    #  BPM DETECTION + MOOD CLASSIFICATION
    # ══════════════════════════════════════
    def _analyse_track(self, path, lib_idx=None):
        """
        Background analysis: BPM detection + mood classification.
        Stores results in _bpm_cache and _mood_cache, saves to library entry.
        Pure-Python — works without librosa. Uses energy-envelope autocorrelation.
        """
        if path in self._bpm_cache:
            return  # already done

        def _worker():
            bpm = 0.0
            mood = ""
            try:
                if SCIPY_AVAILABLE:
                    import numpy as _np
                    import soundfile as _sf2

                    data, sr = _sf2.read(path, dtype="float32", always_2d=True)
                    mono = data.mean(axis=1)

                    # ── BPM via energy-envelope autocorrelation ──────────────
                    # Downsample to ~100 Hz envelope for speed
                    hop = max(1, sr // 100)
                    frames = len(mono) // hop
                    envelope = _np.array([
                        float(_np.abs(mono[i*hop:(i+1)*hop]).mean())
                        for i in range(frames)
                    ])
                    # Bandpass-ish: diff to emphasise onsets
                    onset = _np.diff(envelope.clip(0))
                    onset = _np.maximum(onset, 0)

                    # Autocorrelation over the range 40–220 BPM
                    fps = sr / hop
                    lo = int(60.0 / 220 * fps)
                    hi = int(60.0 / 40  * fps)
                    hi = min(hi, len(onset) // 2)
                    if hi > lo:
                        ac = _np.correlate(onset, onset, mode="full")
                        ac = ac[len(ac)//2:]
                        ac_range = ac[lo:hi]
                        peak_lag = int(_np.argmax(ac_range)) + lo
                        bpm = round(fps * 60.0 / peak_lag, 1) if peak_lag > 0 else 0.0
                        # Sanity: octave correction
                        if bpm > 200: bpm /= 2
                        if bpm < 40:  bpm *= 2
                        bpm = round(bpm, 1)

                    # ── Mood from spectral + energy features ─────────────────
                    # Spectral centroid proxy: mean freq of first 4 s
                    chunk = min(len(mono), sr * 4)
                    mag = _np.abs(_np.fft.rfft(mono[:chunk] * _np.hanning(chunk)))
                    freqs = _np.fft.rfftfreq(chunk, d=1.0/sr)
                    centroid = float(_np.sum(freqs * mag) / (_np.sum(mag) + 1e-9))
                    rms = float(_np.sqrt(_np.mean(mono**2)))

                    # Simple but effective mood rules
                    if bpm >= 128 and centroid > 3000 and rms > 0.06:
                        mood = "⚡ EUPHORIC"
                    elif bpm >= 110 and rms > 0.05:
                        mood = "🔥 ENERGETIC"
                    elif bpm >= 90 and centroid > 2000:
                        mood = "✦ UPBEAT"
                    elif bpm < 80 and centroid < 2500 and rms < 0.04:
                        mood = "💤 MELLOW"
                    elif bpm < 90 and rms < 0.05:
                        mood = "🌙 CHILL"
                    else:
                        mood = "◈ BALANCED"

                elif MUTAGEN_AVAILABLE:
                    # Fallback: use BPM tag if present (e.g. DJ software writes it)
                    try:
                        from mutagen import File as _MF3
                        f = _MF3(path, easy=True)
                        if f:
                            bpm_tag = f.get("bpm", f.get("tbpm", ["0"]))[0]
                            bpm = float(str(bpm_tag).strip() or 0)
                    except Exception:
                        pass

            except Exception:
                pass

            # Store in caches and library entry
            self._bpm_cache[path] = bpm
            self._mood_cache[path] = mood
            if lib_idx is not None and 0 <= lib_idx < len(self.library):
                self.library[lib_idx]["bpm"]  = bpm
                self.library[lib_idx]["mood"] = mood
            elif path in [t.get("path") for t in self.library]:
                for t in self.library:
                    if t.get("path") == path:
                        t["bpm"]  = bpm
                        t["mood"] = mood
                        break
            # Update context sidebar live if this is the playing track
            self.root.after(0, lambda: self._on_analysis_done(path, bpm, mood))

        import threading as _th
        _th.Thread(target=_worker, daemon=True).start()

    def _on_analysis_done(self, path, bpm, mood):
        """Called on main thread when BPM/mood analysis finishes for a track."""
        # Update context sidebar if it's the current track
        if self.current_idx >= 0 and self.current_idx < len(self.library):
            if self.library[self.current_idx].get("path") == path:
                self._update_context_sidebar(self.library[self.current_idx])
        # Update track list to show BPM badge
        if self.view in ("library", "playlist"):
            self._tl_update_highlight()

    def _spec_tick(self):
        """Update the RMS norm meter from FFT data."""
        try:
            playing = self.engine.is_playing or self._sp_playing
            fft = getattr(self, "_fft_bars", None)
            if fft and playing:
                rms = min(1.0, sum(fft[:32]) / 32 * 3.5)
                peak = min(1.0, max(fft[:32]) * 2.8)
                self._norm_meter.update(rms, peak)
                # FFT-reactive playerbar top border pulse
                bass = min(1.0, sum(fft[:6]) / 6 * 4.0)
                br = int(0x2e + (0xe8 - 0x2e) * bass)
                col = f"#{br:02x}{br:02x}{br:02x}"
                self._pb_border_cv.config(bg=col)
                # [04] FFT-reactive active tab underline width
                try:
                    active_key = getattr(self, "_active_tab_key", self.view)
                    btn = self.tab_btns.get(active_key)
                    if btn:
                        tab_w = btn._frame.winfo_width()
                        pulse_w = max(4, int(tab_w * (0.3 + bass * 0.7)))
                        btn._glow_bar.config(width=pulse_w, bg=C["glow"])
                except Exception:
                    pass
                # Library column header brightness pulse
                try:
                    if hasattr(self, "_col_header_frame") and self.view in ("library", "playlist"):
                        energy_mid = min(1.0, sum(fft[8:16]) / 8 * 4.0)
                        hv = int(0x1f + energy_mid * (0x3a - 0x1f))
                        self._col_header_frame.config(bg=f"#{hv:02x}{hv:02x}{hv:02x}")
                        for lbl in self._col_header_frame.winfo_children():
                            lbl.config(bg=f"#{hv:02x}{hv:02x}{hv:02x}")
                except Exception:
                    pass
                # [08] Sidebar VU meter stripe
                try:
                    sv = self._sidebar_vu_cv
                    sv.delete("all")
                    sv_h = sv.winfo_height() or 200
                    n_bands = 8
                    band_h = sv_h // n_bands
                    for bi in range(n_bands):
                        mag = min(1.0, fft[bi * 2] * 5.0)
                        fill_h = int(band_h * mag)
                        y0 = sv_h - bi * band_h - fill_h
                        y1 = sv_h - bi * band_h
                        bv = int(0x28 + mag * (0xe8 - 0x28))
                        sv.create_rectangle(0, y0, 3, y1,
                            fill=f"#{bv:02x}{bv:02x}{bv:02x}", outline="")
                except Exception:
                    pass
                # NOW PLAYING header label bass pulse
                try:
                    bv_lbl = int(0x42 + bass * (0xcc - 0x42))
                    self._now_playing_hdr_lbl.config(fg=f"#{bv_lbl:02x}{bv_lbl:02x}{bv_lbl:02x}")
                except Exception:
                    pass

                # ── Cyberui widget energy feeds ───────────────────────────
                energy = min(1.0, sum(fft[:32]) / 32 * 3.5)
                try:
                    if hasattr(self, "_circuit"):
                        self._circuit.set_energy(energy)
                except Exception:
                    pass
                try:
                    if hasattr(self, "_radar"):
                        self._radar.set_energy(energy)
                except Exception:
                    pass
                try:
                    if hasattr(self, "_plasma"):
                        self._plasma.set_energy(energy)
                except Exception:
                    pass
                try:
                    if hasattr(self, "_freq_ring"):
                        self._freq_ring.update_bars(fft[:48] if len(fft) >= 48 else fft)
                except Exception:
                    pass
                try:
                    if hasattr(self, "_waveform_scope"):
                        self._waveform_scope.update_bars(fft[:64] if len(fft) >= 64 else fft)
                except Exception:
                    pass
                try:
                    if hasattr(self, "_lib_spectrum") and self.view in ("library","playlist"):
                        self._lib_spectrum.update_bars(fft[:48] if len(fft) >= 48 else fft)
                except Exception:
                    pass
                try:
                    if hasattr(self, "_signal_meter"):
                        self._signal_meter.update_from_bars(fft)
                except Exception:
                    pass
                try:
                    if hasattr(self, "_holo_frame"):
                        self._holo_frame.set_energy(energy)
                except Exception:
                    pass
                try:
                    if hasattr(self, "_glyph_wall"):
                        self._glyph_wall.set_energy(energy * 0.4)
                except Exception:
                    pass
                try:
                    if hasattr(self, "_node_graph"):
                        self._node_graph.set_energy(energy)
                except Exception:
                    pass
                # Store energy for AIDJ mood analyser
                self._norm_rms = energy
            else:
                self._norm_meter.update(0, None)
                self._pb_border_cv.config(bg=C["border2"])
                # Reset tab glow bar width
                try:
                    active_key = getattr(self, "_active_tab_key", self.view)
                    btn = self.tab_btns.get(active_key)
                    if btn:
                        btn._glow_bar.config(width=btn._frame.winfo_width(), bg=C["glow"])
                except Exception:
                    pass
                # Reset sidebar VU
                try:
                    self._sidebar_vu_cv.delete("all")
                except Exception:
                    pass
        except Exception:
            pass
        self.root.after(60 if HW_ACCEL else 400, self._spec_tick)

    # ══════════════════════════════════════
    #  PLAYBACK SPEED
    # ══════════════════════════════════════
    SPEED_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]

    def _cycle_speed(self):
        steps = self.SPEED_STEPS
        idx = steps.index(self._playback_speed) if self._playback_speed in steps else 2
        self._playback_speed = steps[(idx + 1) % len(steps)]
        self._speed_lbl.config(text=f"{self._playback_speed}×")

        src = self._active_source

        if src == "spotify":
            self._playback_speed = 1.0
            self._speed_lbl.config(text="1.0×")
            self._set_status("SPEED: N/A FOR SPOTIFY")
            return

        if not SCIPY_AVAILABLE:
            self._playback_speed = 1.0
            self._speed_lbl.config(text="1.0×")
            self._set_status("SPEED: NEEDS SCIPY+SOUNDFILE")
            return

        # Use engine._path as truth — if something is loaded, apply speed
        if not self.engine._path:
            self._set_status(
                f"SPEED QUEUED: {self._playback_speed}×"
                if self._playback_speed != 1.0
                else "SPEED: NORMAL"
            )
            return

        self._set_status("PROCESSING…")
        self._speed_processing = True
        speed = self._playback_speed

        def _done():
            self._speed_processing = False
            self.root.after(
                0,
                lambda: self._set_status(
                    f"SPEED {speed}×" if speed != 1.0 else "SPEED NORMAL"
                ),
            )

        def _err(msg):
            self._speed_processing = False
            print(f"[speed] error: {msg}")
            self._playback_speed = 1.0
            self.root.after(0, lambda: self._speed_lbl.config(text="1.0×"))
            self.root.after(0, lambda: self._set_status("SPEED ERROR"))

        self.engine.set_speed(speed, on_done=_done, on_error=_err)

    def _apply_playback_speed(self):
        """Delegate to engine.set_speed (legacy call path)."""
        self.engine.set_speed(
            self._playback_speed,
            on_done=lambda: self.root.after(
                0,
                lambda: self._set_status(
                    f"SPEED {self._playback_speed}×"
                    if self._playback_speed != 1.0
                    else "SPEED NORMAL"
                ),
            ),
            on_error=lambda msg: self.root.after(
                0, lambda: self._set_status("SPEED ERROR")
            ),
        )

    # ══════════════════════════════════════
    #  A-B LOOP
    # ══════════════════════════════════════
    def _ab_set_a(self):
        pos = (
            self.engine.get_position() if not self._sp_mode else self._sp_pos_ms / 1000
        )
        self._ab_a = pos
        self._ab_active = bool(self._ab_a is not None and self._ab_b is not None)
        self._ab_lbl.config(text=f"{self._fmt(self._ab_a)}–?")
        self._set_status(f"A: {self._fmt(self._ab_a)}")

    def _ab_set_b(self):
        pos = (
            self.engine.get_position() if not self._sp_mode else self._sp_pos_ms / 1000
        )
        if self._ab_a is not None and pos > self._ab_a:
            self._ab_b = pos
            self._ab_active = True
            self._ab_lbl.config(text=f"{self._fmt(self._ab_a)}–{self._fmt(self._ab_b)}")
            self._set_status("A-B LOOP ON")
        else:
            self._set_status("SET A FIRST")

    def _ab_clear(self):
        self._ab_a = self._ab_b = None
        self._ab_active = False
        self._ab_lbl.config(text="—")
        self._set_status("A-B CLEAR")

    def _ab_check(self):
        """Called from _poll. Loops back to A when position passes B."""
        if not self._ab_active or self._ab_b is None:
            return
        if self._sp_mode:
            pos = self._sp_pos_ms / 1000
        else:
            pos = self.engine.get_position()
        if pos >= self._ab_b:
            if self._sp_mode:
                ms = int(self._ab_a * 1000)
                threading.Thread(
                    target=lambda: self.sp_api.seek(ms), daemon=True
                ).start()
            else:
                self.engine.seek(self._ab_a)

    # ══════════════════════════════════════
    #  BOOKMARKS
    # ══════════════════════════════════════
    def _add_bookmark(self):
        if self.current_idx < 0 or not self.engine.is_playing:
            self._set_status("NO TRACK PLAYING")
            return
        pos = (
            self.engine.get_position() if not self._sp_mode else self._sp_pos_ms / 1000
        )
        label = self._fmt(pos)
        bk = self._bookmarks.setdefault(self.current_idx, [])
        bk.append((pos, label))
        self._save()
        self._set_status(f"BKM @ {label}")

    def _open_bookmarks(self):
        idx = self.current_idx
        bk = self._bookmarks.get(idx, [])
        win = tk.Toplevel(self.root)
        content, _close = self._popup_setup(win, "SYS::BOOKMARKS", w=340, h=300)

        title = self.library[idx]["title"] if 0 <= idx < len(self.library) else "—"
        tk.Label(content, text="BOOKMARKS", font=FMX, fg=C["white"], bg=C["bg"]).pack(pady=(12, 2), padx=20, anchor="w")
        tk.Label(content, text=title[:40], font=FMS, fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=20, pady=8)

        lf = tk.Frame(content, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=16)
        if not bk:
            tk.Label(lf, text="No bookmarks for this track.", font=FM, fg=C["white3"], bg=C["bg"]).pack(pady=12)
        else:
            for i, (sec, lbl) in enumerate(bk):
                row = tk.Frame(lf, bg=C["bg"], cursor="hand2")
                row.pack(fill="x", pady=2)
                tk.Label(row, text=f"⊹ {lbl}", font=FM, fg=C["white"], bg=C["bg"], anchor="w").pack(side="left", padx=6)

                def _seek_bk(s=sec):
                    self.engine.seek(s)
                    self._popup_fadeout(win)

                def _del_bk(ii=i):
                    self._bookmarks[idx].pop(ii)
                    self._save()
                    self._popup_fadeout(win)
                    self.root.after(120, self._open_bookmarks)

                go = tk.Label(row, text="GO", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2")
                go.pack(side="right", padx=4)
                go.bind("<Button-1>", lambda e, f=_seek_bk: f())
                go.bind("<Enter>", lambda e, w=go: ColorAnim.run(self.root, w, "fg", C["white3"], C["white"], duration_ms=60))
                go.bind("<Leave>", lambda e, w=go: ColorAnim.run(self.root, w, "fg", C["white"], C["white3"], duration_ms=60))
                dl = tk.Label(row, text="×", font=FMS, fg=C["white3"], bg=C["bg"], cursor="hand2")
                dl.pack(side="right", padx=2)
                dl.bind("<Button-1>", lambda e, f=_del_bk: f())
                dl.bind("<Enter>", lambda e, w=dl: ColorAnim.run(self.root, w, "fg", C["white3"], C["red"], duration_ms=60))
                dl.bind("<Leave>", lambda e, w=dl: ColorAnim.run(self.root, w, "fg", C["red"], C["white3"], duration_ms=60))

        cl2 = tk.Label(content, text="CLOSE", font=FM, fg=C["white3"], bg=C["panel"], cursor="hand2", padx=10, pady=5)
        cl2.pack(pady=10)
        cl2.bind("<Button-1>", lambda e: self._popup_fadeout(win))
        cl2.bind("<Enter>", lambda e: ColorAnim.run(self.root, cl2, "fg", C["white3"], C["white"], duration_ms=60))
        cl2.bind("<Leave>", lambda e: ColorAnim.run(self.root, cl2, "fg", C["white"], C["white3"], duration_ms=60))

    # ══════════════════════════════════════
    #  GAPLESS PLAYBACK
    # ══════════════════════════════════════
    def _gapless_preload(self):
        """Start pre-loading the next track 5s before end."""
        if self._sp_mode or not self.queue:
            return
        next_pos = self.queue_pos + 1
        if self.repeat_mode == "all" and next_pos >= len(self.queue):
            next_pos = 0
        if next_pos < 0 or next_pos >= len(self.queue):
            return
        lib_idx = self.queue[next_pos]
        if lib_idx >= len(self.library):
            return
        path = self.library[lib_idx]["path"]

        # Pre-open the file in a background thread so it's cached by OS
        def _preload():
            try:
                with open(path, "rb") as f:
                    f.read(65536)  # read first 64KB to warm FS cache
            except Exception:
                pass

        threading.Thread(target=_preload, daemon=True).start()

    # ══════════════════════════════════════
    #  TRACK RECOMMENDATIONS
    # ══════════════════════════════════════
    def _open_recommendations(self):
        rec = TrackRecommender(self.library, self._history)
        idxs = rec.recommend(30)

        win = tk.Toplevel(self.root)
        content, _close = self._popup_setup(win, "SYS::RECOMMENDATIONS", w=500, h=440)

        tk.Label(content, text="RECOMMENDED FOR YOU", font=FMX, fg=C["white"], bg=C["bg"]).pack(pady=(14, 4), padx=20, anchor="w")
        tk.Label(content, text="Based on your listening history", font=FMS, fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(8, 0))

        lf = tk.Frame(content, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=0, pady=6)
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"], width=6, bd=0, highlightthickness=0)
        sb.pack(side="right", fill="y")
        lb = tk.Listbox(lf, bg=C["bg"], fg=C["white"], font=FM, selectbackground=C["select2"],
                        bd=0, highlightthickness=0, activestyle="none", yscrollcommand=sb.set)
        lb.pack(side="left", fill="both", expand=True)
        sb.config(command=lb.yview)

        for i in idxs:
            t = self.library[i]
            lb.insert("end", f"  {t.get('title', '')[:36]:<38} {t.get('artist', '')[:24]}")

        bf = tk.Frame(content, bg=C["bg"])
        bf.pack(pady=10)

        def _play_all():
            if idxs:
                self.queue = list(idxs)
                self.queue_pos = 0
                self._play_item(0)
                self._popup_fadeout(win)

        def _play_sel():
            sel = lb.curselection()
            if sel:
                i = idxs[sel[0]]
                self.queue = [i]
                self.queue_pos = 0
                self._play_item(0, force=True)
                self._popup_fadeout(win)

        def _add_all():
            self.queue.extend(idxs)
            self._set_status(f"+{len(idxs)} QUEUED")
            self._popup_fadeout(win)

        for txt, cmd in [("PLAY ALL", _play_all), ("PLAY SEL", _play_sel), ("ADD TO QUEUE", _add_all)]:
            b = tk.Label(bf, text=txt, font=FM, fg=C["white3"], bg=C["panel"],
                         cursor="hand2", padx=8, pady=5)
            b.pack(side="left", padx=4)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white3"], C["white"], duration_ms=60))
            b.bind("<Leave>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white"], C["white3"], duration_ms=60))

    def _open_neural_graph(self):
        """Neural listening map — force-directed graph of artist co-plays."""
        win = tk.Toplevel(self.root)
        content, _close = self._popup_setup(win, "SYS::NEURAL MAP", w=620, h=540)

        tk.Label(content, text="NEURAL LISTENING MAP", font=FMX,
                 fg=C["white"], bg=C["bg"]).pack(pady=(10, 0), padx=20, anchor="w")
        tk.Label(content, text="artist nodes  ·  edge = consecutive plays  ·  size = play count",
                 font=("Courier New", 8), fg=C["white3"], bg=C["bg"]).pack(padx=20, anchor="w")
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(6, 0))

        cv = tk.Canvas(content, bg=C["bg"], highlightthickness=0)
        cv.pack(fill="both", expand=True, padx=0, pady=0)

        def _build():
            # --- collect artist play counts and adjacency ---
            play_counts = {}
            adj = {}
            hist = self._history
            for i, e in enumerate(hist):
                a = e.get("artist", "").strip()
                if not a or a == "Unknown":
                    continue
                play_counts[a] = play_counts.get(a, 0) + 1
                if i > 0:
                    b = hist[i - 1].get("artist", "").strip()
                    if b and b != a and b != "Unknown":
                        key = tuple(sorted([a, b]))
                        adj[key] = adj.get(key, 0) + 1

            if not play_counts:
                cv.create_text(310, 230, text="[ NO HISTORY YET — PLAY SOME TRACKS ]",
                               font=FM, fill=C["white3"], anchor="center")
                return

            # keep top 30 artists by play count
            artists = sorted(play_counts, key=lambda x: -play_counts[x])[:30]
            artist_set = set(artists)
            adj = {k: v for k, v in adj.items() if k[0] in artist_set and k[1] in artist_set}

            W = cv.winfo_width() or 580
            H = cv.winfo_height() or 460
            import random as _r
            import math as _m

            # random initial positions
            pos = {a: [_r.uniform(W * 0.15, W * 0.85),
                        _r.uniform(H * 0.15, H * 0.85)] for a in artists}

            # force-directed layout — 80 iterations
            for _ in range(80):
                force = {a: [0.0, 0.0] for a in artists}
                # repulsion between all pairs
                for i, a in enumerate(artists):
                    for b in artists[i + 1:]:
                        dx = pos[a][0] - pos[b][0]
                        dy = pos[a][1] - pos[b][1]
                        dist = max(1.0, _m.hypot(dx, dy))
                        rep = 2200.0 / (dist * dist)
                        force[a][0] += rep * dx / dist
                        force[a][1] += rep * dy / dist
                        force[b][0] -= rep * dx / dist
                        force[b][1] -= rep * dy / dist
                # attraction along edges
                for (a, b), weight in adj.items():
                    dx = pos[b][0] - pos[a][0]
                    dy = pos[b][1] - pos[a][1]
                    dist = max(1.0, _m.hypot(dx, dy))
                    att = dist * 0.04 * (1 + weight * 0.5)
                    force[a][0] += att * dx / dist
                    force[a][1] += att * dy / dist
                    force[b][0] -= att * dx / dist
                    force[b][1] -= att * dy / dist
                # apply + clamp to canvas
                for a in artists:
                    pos[a][0] = max(40, min(W - 40, pos[a][0] + force[a][0] * 0.12))
                    pos[a][1] = max(30, min(H - 30, pos[a][1] + force[a][1] * 0.12))

            # --- draw edges ---
            max_edge = max(adj.values()) if adj else 1
            for (a, b), weight in adj.items():
                bv = int(0x18 + (weight / max_edge) * 0x30)
                cv.create_line(pos[a][0], pos[a][1], pos[b][0], pos[b][1],
                               fill=f"#{bv:02x}{bv:02x}{bv:02x}", width=1)

            # --- draw nodes ---
            max_plays = max(play_counts[a] for a in artists)
            for a in artists:
                x, y = pos[a]
                r = 4 + int((play_counts[a] / max_plays) * 14)
                bv = int(0x44 + (play_counts[a] / max_plays) * (0xe8 - 0x44))
                col = f"#{bv:02x}{bv:02x}{bv:02x}"
                cv.create_oval(x - r, y - r, x + r, y + r,
                               fill=col, outline=C["border2"], width=1)
                label = a[:14] + "…" if len(a) > 14 else a
                cv.create_text(x, y + r + 7, text=label,
                               font=("Courier New", 6), fill=C["white3"], anchor="n")

            # --- legend ---
            cv.create_text(W - 10, H - 10,
                text=f"[ {len(artists)} ARTISTS  ·  {len(adj)} CONNECTIONS ]",
                font=("Courier New", 6), fill=C["white3"], anchor="se")

        cv.bind("<Configure>", lambda e: (cv.delete("all"), _build()))
        win.after(250, lambda: (cv.delete("all"), _build()))

    # ══════════════════════════════════════
    #  THEME / COLOR EDITOR
    # ══════════════════════════════════════
    def _open_theme_editor(self):
        win = tk.Toplevel(self.root)
        win.title("OTERNOS // THEMES")
        win.configure(bg=C["bg"])
        win.geometry("620x680")
        win.resizable(True, True)
        win.minsize(500, 500)
        win.transient(self.root)
        self._popup_fadein(win)

        # ── Header ────────────────────────────────────────────────
        hdr = tk.Frame(win, bg=C["panel"], height=44)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Frame(hdr, bg=C["border2"], height=1).pack(side="bottom", fill="x")
        tk.Label(hdr, text="◈ THEME STUDIO", font=FML, fg=C["white"], bg=C["panel"]).pack(side="left", padx=18, pady=10)
        cl = tk.Label(hdr, text="[ ✕ ]", font=("Courier New", 11), fg=C["white3"], bg=C["panel"], cursor="hand2", padx=14)
        cl.pack(side="right")
        cl.bind("<Button-1>", lambda e: self._popup_fadeout(win))
        cl.bind("<Enter>", lambda e: ColorAnim.run(self.root, cl, "fg", C["white3"], C["red"], duration_ms=60))
        cl.bind("<Leave>", lambda e: ColorAnim.run(self.root, cl, "fg", C["red"], C["white3"], duration_ms=60))

        # ── Tab bar ───────────────────────────────────────────────
        tab_bar = tk.Frame(win, bg=C["panel"])
        tab_bar.pack(fill="x")
        tk.Frame(win, bg=C["border"], height=1).pack(fill="x")
        _tab_btns = {}
        _tab_frames = {}
        _active_tab = tk.StringVar(value="presets")

        body_host = tk.Frame(win, bg=C["bg"])
        body_host.pack(fill="both", expand=True)

        def _switch_tab(name):
            _active_tab.set(name)
            for k, f in _tab_frames.items():
                f.pack_forget()
            _tab_frames[name].pack(fill="both", expand=True)
            for k, b in _tab_btns.items():
                b.config(fg=C["white"] if k == name else C["white3"], bg=C["panel"])

        def _make_tab(key, label):
            b = tk.Label(
                tab_bar,
                text=label,
                font=("Courier New", 7, "bold"),
                fg=C["white3"],
                bg=C["panel"],
                cursor="hand2",
                padx=14,
                pady=9,
            )
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: _switch_tab(k))
            b.bind("<Enter>", lambda e, w=b, k=key: w.config(fg=C["white"]))
            b.bind(
                "<Leave>",
                lambda e, w=b, k=key: w.config(
                    fg=C["white"] if _active_tab.get() == k else C["white3"]
                ),
            )
            _tab_btns[key] = b
            f = tk.Frame(body_host, bg=C["bg"])
            _tab_frames[key] = f
            return f

        # ══════════════════════════════════════════════════════════
        #  TAB 1 — PRESETS
        # ══════════════════════════════════════════════════════════
        pf = _make_tab("presets", "PRESETS")

        tk.Label(
            pf,
            text="SELECT A PRESET THEME",
            font=("Courier New", 7),
            fg=C["white3"],
            bg=C["bg"],
        ).pack(anchor="w", padx=20, pady=(16, 8))
        tk.Frame(pf, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(0, 12))

        grid = tk.Frame(pf, bg=C["bg"])
        grid.pack(padx=20, fill="x")

        def _do_apply_preset(c, n):
            C.update(c)
            C["panel2"] = C["panel"]
            self.settings["active_theme"] = n
            self._rebuild_ui_colors()
            self._save()
            self._set_status(f"Theme: {n}")

        col = 0
        row_f = None
        for name, colors in self._theme_presets.items():
            if col % 4 == 0:
                row_f = tk.Frame(grid, bg=C["bg"])
                row_f.pack(fill="x", pady=4)
            col += 1
            card = tk.Frame(
                row_f,
                bg=colors["bg"],
                width=120,
                height=80,
                cursor="hand2",
                highlightthickness=1,
                highlightbackground=colors["border2"],
            )
            card.pack(side="left", padx=4)
            card.pack_propagate(False)
            # Mini UI mock inside card
            mock_panel = tk.Frame(card, bg=colors["panel"], height=18)
            mock_panel.pack(fill="x")
            tk.Label(
                mock_panel,
                text=name,
                font=("Courier New", 6, "bold"),
                fg=colors["glow"],
                bg=colors["panel"],
            ).pack(side="left", padx=4)
            mock_body = tk.Frame(card, bg=colors["bg"])
            mock_body.pack(fill="both", expand=True, padx=4, pady=2)
            for txt, fg in [
                ("▬▬▬▬▬▬▬", colors["white2"]),
                ("▬▬▬▬▬", colors["white3"]),
                ("▬▬▬▬▬▬", colors["white3"]),
            ]:
                tk.Label(
                    mock_body, text=txt, font=("Courier New", 5), fg=fg, bg=colors["bg"]
                ).pack(anchor="w")
            mock_bar = tk.Frame(card, bg=colors["panel"], height=12)
            mock_bar.pack(fill="x")
            tk.Label(
                mock_bar,
                text="▶",
                font=("Courier New", 5),
                fg=colors["glow"],
                bg=colors["panel"],
            ).pack(side="left", padx=3)

            def _bind_card(w, c=colors, n=name):
                w.bind("<Button-1>", lambda e, c=c, n=n: _do_apply_preset(c, n))
                w.bind(
                    "<Enter>",
                    lambda e, w=w: (
                        w.config(highlightbackground=colors["glow"])
                        if hasattr(w, "config")
                        else None
                    ),
                )
                for ch in w.winfo_children():
                    _bind_card(ch, c, n)

            card.bind("<Button-1>", lambda e, c=colors, n=name: _do_apply_preset(c, n))
            for ch in card.winfo_children():
                for w in [ch] + list(ch.winfo_children()):
                    w.bind(
                        "<Button-1>", lambda e, c=colors, n=name: _do_apply_preset(c, n)
                    )

        # Active indicator
        tk.Frame(pf, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(16, 6))
        active_lbl = tk.Label(
            pf,
            text=f"Active: {self.settings.get('active_theme', 'VOID')}",
            font=("Courier New", 7),
            fg=C["white3"],
            bg=C["bg"],
        )
        active_lbl.pack(anchor="w", padx=20)

        # ══════════════════════════════════════════════════════════
        #  TAB 2 — COLORS  (full token editor)
        # ══════════════════════════════════════════════════════════
        cf = _make_tab("colors", "COLORS")

        c_outer = tk.Frame(cf, bg=C["bg"])
        c_outer.pack(fill="both", expand=True)
        c_sb = tk.Scrollbar(
            c_outer,
            orient="vertical",
            bg=C["panel"],
            troughcolor=C["bg"],
            width=6,
            relief="flat",
            bd=0,
        )
        c_sb.pack(side="right", fill="y")
        c_cv = tk.Canvas(
            c_outer, bg=C["bg"], highlightthickness=0, yscrollcommand=c_sb.set
        )
        c_cv.pack(side="left", fill="both", expand=True)
        c_sb.config(command=c_cv.yview)
        c_inner = tk.Frame(c_cv, bg=C["bg"])
        c_win = c_cv.create_window(0, 0, anchor="nw", window=c_inner)
        c_inner.bind(
            "<Configure>", lambda e: c_cv.configure(scrollregion=c_cv.bbox("all"))
        )
        c_cv.bind("<Configure>", lambda e: c_cv.itemconfig(c_win, width=e.width))

        def _c_scroll(e):
            c_cv.yview_scroll(int(-1 * (e.delta / 120)) * 3, "units")

        c_cv.bind("<MouseWheel>", _c_scroll)
        c_inner.bind("<MouseWheel>", _c_scroll)

        ALL_TOKENS = [
            (
                "BACKGROUNDS",
                [
                    ("bg", "Main background"),
                    ("panel", "Panel / sidebar"),
                    ("select", "Selection bg"),
                    ("select2", "Deep selection"),
                ],
            ),
            (
                "BORDERS",
                [
                    ("border", "Border (dim)"),
                    ("border2", "Border (bright)"),
                ],
            ),
            (
                "TEXT",
                [
                    ("white", "Primary text"),
                    ("white2", "Secondary text"),
                    ("white3", "Muted text"),
                    ("glow", "Accent / hover"),
                ],
            ),
            (
                "ACCENTS",
                [
                    ("red", "Error / warning"),
                ],
            ),
        ]

        self._theme_vars = {}

        def _make_color_entry(parent, key, label):
            rf = tk.Frame(parent, bg=C["bg"])
            rf.pack(fill="x", padx=20, pady=2)
            # Swatch
            sw = tk.Frame(
                rf,
                bg=C.get(key, "#000000"),
                width=18,
                height=18,
                highlightthickness=1,
                highlightbackground=C["border"],
            )
            sw.pack(side="left", padx=(0, 8))
            sw.pack_propagate(False)
            # Label
            tk.Label(
                rf,
                text=f"{label:<20}",
                font=("Courier New", 8),
                fg=C["white2"],
                bg=C["bg"],
                width=20,
                anchor="w",
            ).pack(side="left")
            # Entry
            var = tk.StringVar(value=C.get(key, "#000000"))
            self._theme_vars[key] = var
            ent = tk.Entry(
                rf,
                textvariable=var,
                font=("Courier New", 8),
                bg=C["panel"],
                fg=C["white"],
                insertbackground=C["white"],
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=C["border2"],
                width=9,
            )
            ent.pack(side="left", ipady=3)

            # Color picker button
            def _pick(k=key, v=var, s=sw):
                try:
                    from tkinter import colorchooser

                    result = colorchooser.askcolor(color=v.get(), title=f"Pick {k}")
                    if result and result[1]:
                        v.set(result[1])
                        try:
                            s.config(bg=result[1])
                        except:
                            pass
                except Exception:
                    pass

            pick_btn = tk.Label(
                rf,
                text="⬛",
                font=("Courier New", 9),
                fg=C["white3"],
                bg=C["bg"],
                cursor="hand2",
            )
            pick_btn.pack(side="left", padx=4)
            pick_btn.bind("<Button-1>", lambda e, f=_pick: f())

            # Live swatch update
            def _upd(v=var, s=sw):
                try:
                    s.config(bg=v.get() if v.get().startswith("#") else C["bg"])
                except:
                    pass

            var.trace_add("write", lambda *a, f=_upd: f())
            # Bind scroll to canvas
            for w in (rf, sw, ent, pick_btn):
                w.bind("<MouseWheel>", _c_scroll)

        for section_name, tokens in ALL_TOKENS:
            sf = tk.Frame(c_inner, bg=C["bg"])
            sf.pack(fill="x", pady=(14, 2))
            tk.Label(
                sf,
                text=section_name,
                font=("Courier New", 8, "bold"),
                fg=C["white3"],
                bg=C["bg"],
            ).pack(anchor="w", padx=20)
            tk.Frame(c_inner, bg=C["border2"], height=1).pack(
                fill="x", padx=20, pady=(2, 4)
            )
            sf.bind("<MouseWheel>", _c_scroll)
            for key, label in tokens:
                _make_color_entry(c_inner, key, label)

        tk.Frame(c_inner, bg=C["bg"], height=16).pack()

        def _apply_colors():
            for key, var in self._theme_vars.items():
                try:
                    val = var.get().strip()
                    if val and not val.startswith("#"):
                        val = "#" + val
                    if val:
                        C[key] = val
                except Exception:
                    pass
            C["panel2"] = C["panel"]
            self._rebuild_ui_colors()
            self._save()
            self._set_status("Colors applied")

        c_foot = tk.Frame(cf, bg=C["panel"])
        c_foot.pack(fill="x", side="bottom")
        tk.Frame(c_foot, bg=C["border"], height=1).pack(fill="x")
        for txt, cmd in [
            ("[ APPLY ]", _apply_colors),
            (
                "[ RESET ]",
                lambda: _do_apply_preset(self._theme_presets["VOID"], "VOID"),
            ),
        ]:
            b = tk.Label(
                c_foot,
                text=txt,
                font=FM,
                fg=C["white3"],
                bg=C["panel"],
                cursor="hand2",
                padx=10,
                pady=8,
            )
            b.pack(side="left", padx=8)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=C["white3"]))

        # ══════════════════════════════════════════════════════════
        #  TAB 3 — TYPOGRAPHY
        # ══════════════════════════════════════════════════════════
        tf = _make_tab("type", "TYPOGRAPHY")

        tk.Label(
            tf,
            text="FONT SETTINGS",
            font=("Courier New", 7),
            fg=C["white3"],
            bg=C["bg"],
        ).pack(anchor="w", padx=20, pady=(16, 8))
        tk.Frame(tf, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(0, 12))

        font_families = [
            "Courier New",
            "Consolas",
            "Lucida Console",
            "Terminal",
            "Fixedsys",
            "OCR A Extended",
        ]
        font_var = tk.StringVar(value="Courier New")
        size_var = tk.IntVar(value=9)

        def _font_row(label, options, var, width=20):
            r = tk.Frame(tf, bg=C["bg"])
            r.pack(fill="x", padx=20, pady=5)
            tk.Label(
                r,
                text=label,
                font=("Courier New", 8),
                fg=C["white2"],
                bg=C["bg"],
                width=18,
                anchor="w",
            ).pack(side="left")
            lbl = tk.Label(
                r,
                text=f"[ {var.get()} ]",
                font=("Courier New", 8),
                fg=C["white"],
                bg=C["panel"],
                cursor="hand2",
                padx=8,
                pady=3,
            )
            lbl.pack(side="left")

            def _cycle(e=None):
                if isinstance(options[0], str):
                    idx = options.index(var.get()) if var.get() in options else 0
                    var.set(options[(idx + 1) % len(options)])
                else:
                    idx = options.index(var.get()) if var.get() in options else 0
                    var.set(options[(idx + 1) % len(options)])
                lbl.config(text=f"[ {var.get()} ]")

            lbl.bind("<Button-1>", _cycle)
            return var

        _font_row("Font family", font_families, font_var)
        _font_row("Base size", [7, 8, 9, 10, 11, 12], size_var)

        tk.Frame(tf, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(16, 8))

        # Preview box
        prev_f = tk.Frame(
            tf, bg=C["panel"], highlightthickness=1, highlightbackground=C["border2"]
        )
        prev_f.pack(fill="x", padx=20, pady=4)
        prev_lbl = tk.Label(
            prev_f,
            text="OTERNOS  //  NOW PLAYING\nTrack Title  --  Artist Name\n0:00 ----------- 3:45",
            font=(font_var.get(), size_var.get()),
            fg=C["white"],
            bg=C["panel"],
            justify="left",
            padx=12,
            pady=10,
        )
        prev_lbl.pack(anchor="w")

        def _apply_font():
            fam = font_var.get()
            sz = int(size_var.get())
            global FM, FMS, FML, FMX
            FM = (fam, sz)
            FMS = (fam, sz - 1)
            FML = (fam, sz + 1, "bold")
            FMX = (fam, sz + 4, "bold")
            prev_lbl.config(font=(fam, sz))
            self.settings["font_family"] = fam
            self.settings["font_size"] = sz
            self._save()
            self._set_status(f"Font: {fam} {sz}pt")

        t_foot = tk.Frame(tf, bg=C["panel"])
        t_foot.pack(fill="x", side="bottom")
        tk.Frame(t_foot, bg=C["border"], height=1).pack(fill="x")
        ap = tk.Label(
            t_foot,
            text="[ APPLY FONT ]",
            font=FM,
            fg=C["white3"],
            bg=C["panel"],
            cursor="hand2",
            padx=10,
            pady=8,
        )
        ap.pack(side="left", padx=8)
        ap.bind("<Button-1>", lambda e: _apply_font())
        ap.bind("<Enter>", lambda e: ap.config(fg=C["white"]))
        ap.bind("<Leave>", lambda e: ap.config(fg=C["white3"]))

        # ══════════════════════════════════════════════════════════
        #  TAB 4 — EXPORT / IMPORT
        # ══════════════════════════════════════════════════════════
        ef = _make_tab("export", "EXPORT")

        tk.Label(
            ef,
            text="SAVE & SHARE THEMES",
            font=("Courier New", 7),
            fg=C["white3"],
            bg=C["bg"],
        ).pack(anchor="w", padx=20, pady=(16, 8))
        tk.Frame(ef, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(0, 12))

        # Export current theme as hex string
        import json as _json

        def _export():
            data = {
                k: C[k]
                for k in (
                    "bg",
                    "panel",
                    "border",
                    "border2",
                    "white",
                    "white2",
                    "white3",
                    "glow",
                    "select",
                    "select2",
                    "red",
                )
            }
            txt = _json.dumps(data, separators=(",", ":"))
            export_var.set(txt)

        def _import():
            try:
                txt = export_var.get().strip()
                data = _json.loads(txt)
                C.update(data)
                C["panel2"] = C["panel"]
                self._rebuild_ui_colors()
                self._save()
                self._set_status("Theme imported")
            except Exception as ex:
                self._set_status(f"Import failed: {ex}")

        tk.Label(
            ef,
            text="Theme JSON  (copy to share, paste to import):",
            font=("Courier New", 7),
            fg=C["white2"],
            bg=C["bg"],
        ).pack(anchor="w", padx=20)
        export_var = tk.StringVar()
        _export()
        txt_box = tk.Entry(
            ef,
            textvariable=export_var,
            font=("Courier New", 7),
            bg=C["panel"],
            fg=C["white"],
            insertbackground=C["white"],
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=C["border2"],
        )
        txt_box.pack(fill="x", padx=20, pady=6, ipady=4)

        e_foot = tk.Frame(ef, bg=C["panel"])
        e_foot.pack(fill="x", side="bottom")
        tk.Frame(e_foot, bg=C["border"], height=1).pack(fill="x")
        for txt, cmd in [("[ EXPORT ]", _export), ("[ IMPORT ]", _import)]:
            b = tk.Label(
                e_foot,
                text=txt,
                font=FM,
                fg=C["white3"],
                bg=C["panel"],
                cursor="hand2",
                padx=10,
                pady=8,
            )
            b.pack(side="left", padx=8)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, w=b: w.config(fg=C["white"]))
            b.bind("<Leave>", lambda e, w=b: w.config(fg=C["white3"]))

        # ── Start on presets tab ──────────────────────────────────
        _switch_tab("presets")

    def _apply_theme_preset(self, name):
        colors = self._theme_presets.get(name)
        if colors:
            C.update(colors)
            C["panel2"] = C["panel"]
            self._rebuild_ui_colors()

    def _rebuild_ui_colors(self):
        """
        Remap every widget color to the new palette.
        If switching away from Miku, restore cybercore widgets first.
        If switching to Miku, apply Miku-specific overrides after.
        The two themes never bleed into each other.
        """
        active = self.settings.get("active_theme", "").upper()
        going_to_miku = active == "MIKU"
        going_to_nerv = active == "NERV"
        going_to_angel = active == "ANGEL"

        # Always destroy baroque frame first — recreated by _apply_angel_theme if needed
        try:
            if getattr(self, "_baroque_frame", None):
                self._baroque_frame.destroy()
                self._baroque_frame = None
        except Exception:
            pass
        try:
            for w in list(self.root.winfo_children()):
                if w.__class__.__name__ == "BaroqueStrip":
                    try:
                        w.destroy()
                    except Exception:
                        pass
        except Exception:
            pass

        self._restore_cybercore()

        ALL_TOKENS = (
            "bg",
            "panel",
            "panel2",
            "border",
            "border2",
            "white",
            "white2",
            "white3",
            "glow",
            "select",
            "select2",
            "red",
        )

        _all_theme_colors = set()
        _all_theme_panel = set()
        for preset in self._theme_presets.values():
            for tok in ALL_TOKENS:
                v = preset.get(tok, "")
                if v:
                    _all_theme_colors.add(v.lower())
            for tok in ("panel", "panel2"):
                v = preset.get(tok, "")
                if v:
                    _all_theme_panel.add(v.lower())
        _all_theme_panel.add(C["panel2"].lower())
        _cur_panel = {C["panel"].lower(), C["panel2"].lower()}

        def _recolor(w):
            try:
                # Skip baroque corner canvases — they manage their own bg
                if w.__class__.__name__ == "BaroqueCorner":
                    return
                cls = w.winfo_class()
                if cls in ("Frame", "Labelframe", "Canvas"):
                    cur_bg = w.cget("bg").lower()
                    if cur_bg in _cur_panel:
                        w.config(bg=C["panel"])
                    elif cur_bg in _all_theme_colors:
                        w.config(bg=C["bg"])
                    if cls == "Canvas":
                        w.config(highlightbackground=C["border"])
                elif cls == "Label":
                    cur_bg = w.cget("bg").lower()
                    cur_fg = w.cget("fg").lower()
                    new_bg = (
                        C["panel"]
                        if cur_bg in _cur_panel
                        else C["bg"]
                        if cur_bg in _all_theme_colors
                        else None
                    )
                    # Map any theme fg color to the closest semantic equivalent
                    new_fg = None
                    if cur_fg in _all_theme_colors:
                        # Find which token this color was closest to across all themes
                        # Default to white — _update_tabs / hover will correct specific widgets
                        new_fg = C["white"]
                        for preset in self._theme_presets.values():
                            if cur_fg == preset.get("white", "").lower():
                                new_fg = C["white"]
                                break
                            elif cur_fg == preset.get("white2", "").lower():
                                new_fg = C["white2"]
                                break
                            elif cur_fg == preset.get("white3", "").lower():
                                new_fg = C["white3"]
                                break
                            elif cur_fg == preset.get("glow", "").lower():
                                new_fg = C["white2"]
                                break  # reset glow → neutral after theme swap
                    cfg = {}
                    if new_bg is not None:
                        cfg["bg"] = new_bg
                    if new_fg is not None:
                        cfg["fg"] = new_fg
                    if cfg:
                        w.config(**cfg)
                elif cls == "Entry":
                    w.config(
                        bg=C["panel"],
                        fg=C["white"],
                        insertbackground=C["glow"],
                        highlightbackground=C["border2"],
                    )
                elif cls == "Text":
                    w.config(
                        bg=C["panel"],
                        fg=C["white"],
                        insertbackground=C["glow"],
                        selectbackground=C["select2"],
                        highlightbackground=C["border"],
                    )
                elif cls == "Listbox":
                    w.config(
                        bg=C["bg"],
                        fg=C["white"],
                        selectbackground=C["select2"],
                        selectforeground=C["glow"],
                        highlightthickness=0,
                    )
                elif cls == "Scrollbar":
                    w.config(
                        bg=C["panel"],
                        troughcolor=C["bg"],
                        activebackground=C["border2"],
                    )
                elif cls == "Scale":
                    w.config(
                        bg=C["bg"],
                        fg=C["white"],
                        troughcolor=C["panel"],
                        activebackground=C["glow"],
                    )
                elif cls == "Button":
                    w.config(
                        bg=C["panel"],
                        fg=C["white"],
                        activebackground=C["select2"],
                        activeforeground=C["glow"],
                        highlightbackground=C["border"],
                    )
            except Exception:
                pass
            for child in w.winfo_children():
                _recolor(child)

        self.root.configure(bg=C["bg"])
        _recolor(self.root)

        for w in self.root.winfo_children():
            if w.winfo_class() == "Toplevel":
                try:
                    w.configure(bg=C["bg"])
                    _recolor(w)
                except Exception:
                    pass

        if going_to_miku:
            self.root.after(50, self._apply_miku_theme)
        elif going_to_nerv:
            self.root.after(50, self._apply_nerv_theme)
        elif active == "NIER":
            self.root.after(50, self._apply_nier_theme)
        elif going_to_angel:
            self.root.after(50, self._apply_angel_theme)

        # Refresh canvas-drawn views so row colors use the new palette
        self.root.after(60, self._post_theme_refresh)

        self._set_status("THEME APPLIED")

    def _post_theme_refresh(self):
        """Redraw all canvas-based views after a theme change."""
        try:
            if hasattr(self, "track_list"):
                self._refresh_tracks()
            if hasattr(self, "_update_tabs"):
                self._update_tabs()
            # Redraw progress bar colors
            if hasattr(self, "prog_fill"):
                self.prog_cv.itemconfig(self.prog_fill, fill=C["glow"])
            if hasattr(self, "prog_dot"):
                self.prog_cv.itemconfig(
                    self.prog_dot, fill=C["white"], outline=C["glow"]
                )
            # Redraw vol canvas
            if hasattr(self, "_upd_vol"):
                self._upd_vol()
            # Sidebar accent bars — walk and recolor
            if hasattr(self, "_side_frame"):
                for f in self._side_frame.winfo_children():
                    for child in f.winfo_children():
                        if child.winfo_class() == "Frame" and child.winfo_width() <= 4:
                            child.config(bg=C["border"])
        except Exception:
            pass

    # ══════════════════════════════════════
    #  RESTORE CYBERCORE — undo any Miku overrides
    # ══════════════════════════════════════
    def _restore_cybercore(self):
        """
        Called when switching away from Miku back to any cybercore theme.
        Restores all Miku-swapped widgets back to their original cybercore versions.
        Does NOT touch colors — _rebuild_ui_colors handles that afterward.
        """
        global FM, FMS, FML, FMX

        # ── Restore Courier New fonts ──
        FM = ("Courier New", 9)
        FMS = ("Courier New", 8)
        FML = ("Courier New", 10, "bold")
        FMX = ("Courier New", 13, "bold")

        # ── Sidebar logo: swap MikuLogo/NierLogo → OternosLogo ──
        try:
            if isinstance(self._sidebar_logo, (MikuLogo, NierLogo)):
                parent = self._sidebar_logo.master
                self._sidebar_logo.destroy()
                self._sidebar_logo = OternosLogo(parent, size=52, bg=C["panel"])
                self._sidebar_logo.pack(side="left", padx=(14, 8))
                self._sidebar_logo.is_playing = getattr(self.engine, "playing", False)
        except Exception:
            pass

        # ── Sidebar wordmark ──
        try:
            for w in self._side_frame.winfo_children():
                for child in w.winfo_children() if hasattr(w, "winfo_children") else []:
                    if isinstance(child, tk.Label):
                        t = child.cget("text")
                        if t in ("初音ミク", "NERV", "YoRHa", "✦ ANGEL ✦", "✦ Angel ✦"):
                            child.config(
                                text="OTERNOS",
                                font=("Courier New", 8, "bold"),
                                fg=C["white"],
                            )
                        elif any(
                            x in str(t)
                            for x in (
                                "VOCALOID",
                                "God's In His Heaven",
                                "MAGI v",
                                "No. 2",
                                "Celestial",
                                "✧ ascend",
                                "she ascends",
                            )
                        ):
                            child.config(
                                text="SYS v1.0", font=("Courier New", 7), fg=C["white3"]
                            )
        except Exception:
            pass

        # ── Topbar wordmark ──
        try:
            for w in self.root.winfo_children():
                if w.winfo_class() == "Frame":
                    for child in w.winfo_children():
                        if isinstance(child, tk.Label):
                            t = str(child.cget("text"))
                            if (
                                "M I K U" in t
                                or "N E R V" in t
                                or "Y O R H A" in t
                                or "A N G E L" in t
                                or "Angel.exe" in t
                                or "✦ Angel.exe ✦" in t
                            ):
                                child.config(
                                    text="O T E R N O S",
                                    font=("Courier New", 9, "bold"),
                                    fg=C["white3"],
                                )
                                break
                    break
        except Exception:
            pass

        # ── Tab bar: restore ──
        try:
            for key, btn in self.tab_btns.items():
                btn.config(font=("Courier New", 7, "bold"))
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind("<Enter>", lambda e, w=btn: w.config(fg=C["white"]))
                btn.bind(
                    "<Leave>",
                    lambda e, w=btn, k=key: w.config(
                        fg=C["glow"] if k == getattr(self, "view", "") else C["white3"]
                    ),
                )
        except Exception:
            pass

        # ── Now-playing labels: restore Courier New ──
        try:
            self.now_title.config(font=("Courier New", 9, "bold"))
            self.now_artist.config(font=("Courier New", 8))
            self.now_album.config(font=("Courier New", 7))
        except Exception:
            pass

        # ── Progress bar: restore ──
        try:
            self.prog_cv.config(bg=C["bg"])
            self.prog_cv.itemconfig(self.prog_fill, fill=C["white2"])
            self.prog_cv.itemconfig(self.prog_dot, fill=C["white"])
        except Exception:
            pass

        # ── Player control buttons: restore Courier New + white hover ──
        try:
            for btn in (
                self.btn_shuf,
                self.btn_prev,
                self.btn_play,
                self.btn_next,
                self.btn_repeat,
            ):
                sz = 16 if btn is self.btn_play else 12
                btn.config(font=("Courier New", sz), fg=C["white3"])
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind(
                    "<Enter>",
                    lambda e, w=btn: ColorAnim.run(
                        self.root, w, "fg", C["white3"], C["white"], duration_ms=40
                    ),
                )
                btn.bind(
                    "<Leave>",
                    lambda e, w=btn: ColorAnim.run(
                        self.root, w, "fg", C["white"], C["white3"], duration_ms=40
                    ),
                )
        except Exception:
            pass

        # ── DataTicker: swap MikuTicker/AngelTicker → DataTicker ──
        try:
            if (
                hasattr(self, "_ticker")
                and isinstance(self._ticker, (MikuTicker, AngelTicker))
                and self._ticker.winfo_exists()
            ):
                parent = self._ticker.master
                self._ticker.destroy()
                self._ticker = DataTicker(parent, width=900, height=10, bg=C["panel"])
                self._ticker.pack(fill="x")
        except Exception:
            pass

        # ── CornerBrackets: swap MikuCornerDeco → CornerBrackets ──
        try:
            hdr = self.lib_frame.winfo_children()[0]
            for child in list(hdr.winfo_children()):
                if isinstance(child, MikuCornerDeco):
                    child.destroy()
                    brackets = CornerBrackets(hdr, size=28, bg=C["bg"])
                    brackets.pack(side="left", padx=(0, 6))
                    break
        except Exception:
            pass

        # ── Track list: restore Courier New ──
        try:
            self.track_list.config(font=("Courier New", 9))
        except Exception:
            pass

        # ── Sidebar section labels: restore Courier New ──
        try:
            _script_fonts = (
                "Edwardian Script ITC",
                "Kunstler Script",
                "French Script MT",
                "Monotype Corsiva",
                "Lucida Calligraphy",
                "Segoe Script",
                "Lucida Handwriting",
                "Palatino Linotype",
                "Book Antiqua",
                "Garamond",
                "Perpetua",
                "Georgia",
                "Times New Roman",
            )

            def _restore_side_fonts(w):
                if isinstance(w, tk.Label):
                    try:
                        f = w.cget("font")
                        fs = str(f)
                        if "Consolas" in fs or any(sf in fs for sf in _script_fonts):
                            sz = 8
                            try:
                                parts = self.root.tk.splitlist(f)
                                sz = int(parts[1]) if len(parts) > 1 else 8
                            except Exception:
                                pass
                            w.config(font=("Courier New", sz))
                    except Exception:
                        pass
                for ch in w.winfo_children() if hasattr(w, "winfo_children") else []:
                    _restore_side_fonts(ch)

            _restore_side_fonts(self._side_frame)
        except Exception:
            pass

        try:
            self._sidebar_status_lbl.config(font=("Courier New", 8))
        except Exception:
            pass

        # ── Restore viz bar ──
        try:
            self._viz_mf_miku.pack_forget()
            self._viz_mf_nerv.pack_forget()
            self._viz_mf_nier.pack_forget()
            if hasattr(self, "_viz_mf_angel"):
                self._viz_mf_angel.pack_forget()
            self._viz_mf_cyber.pack(side="right")
            if getattr(self, "_viz_mode", "").startswith(
                ("miku", "nerv_", "nier_", "angel_")
            ):
                self._set_viz_mode("hexcore")
        except Exception:
            pass

        # ── Restore viz info bar fonts ──
        try:
            self.viz_track_lbl.config(font=("Courier New", 8), fg=C["white2"])
            self.viz_pos_lbl.config(font=("Courier New", 8), fg=C["white3"])
            self.viz_mode_lbl.config(font=("Courier New", 8), fg=C["white3"])
        except Exception:
            pass

        # ── Strip theme prefixes ──
        try:
            cur = self.now_title.cget("text")
            if cur and cur.startswith("♪  "):
                self.now_title.config(text=cur[3:])
            elif cur and cur.startswith("[NERV] "):
                self.now_title.config(text=cur[7:])
            elif cur and cur.startswith("// "):
                self.now_title.config(text=cur[3:])
            elif cur and cur.startswith("✦ "):
                self.now_title.config(text=cur[2:])
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════
    #  NieR:Automata THEME — YoRHa terminal aesthetic
    # ══════════════════════════════════════════════════════════
    def _apply_nier_theme(self):
        """
        Full NieR:Automata override. Aged parchment + gold on near-black.
        Monospaced serif terminal feel. YoRHa sigil replaces logo.
        """
        global FM, FMS, FML, FMX
        _nf = next(
            (
                f
                for f in ("Consolas", "Lucida Console", "Courier New")
                if self._font_exists(f)
            ),
            "Courier New",
        )
        FM = (_nf, 9)
        FMS = (_nf, 8)
        FML = (_nf, 10, "bold")
        FMX = (_nf, 13, "bold")

        GOLD = "#c8b878"
        DGOLD = "#504838"
        CREAM = "#e8e4d0"

        # ── Sidebar logo → NierLogo ──
        try:
            if not isinstance(self._sidebar_logo, NierLogo):
                parent = self._sidebar_logo.master
                self._sidebar_logo.destroy()
                self._sidebar_logo = NierLogo(parent, size=52, bg=C["panel"])
                self._sidebar_logo.pack(side="left", padx=(14, 8))
                self._sidebar_logo.is_playing = getattr(self.engine, "playing", False)
        except Exception:
            pass

        # ── Sidebar wordmark ──
        try:
            for w in self._side_frame.winfo_children():
                for child in w.winfo_children() if hasattr(w, "winfo_children") else []:
                    if isinstance(child, tk.Label):
                        t = child.cget("text")
                        if t == "OTERNOS":
                            child.config(text="YoRHa", font=(_nf, 8, "bold"), fg=GOLD)
                        elif "SYS v" in str(t):
                            child.config(text="No. 2 Type B", font=(_nf, 6), fg=DGOLD)
        except Exception:
            pass

        # ── Topbar wordmark ──
        try:
            for w in self.root.winfo_children():
                if w.winfo_class() == "Frame":
                    for child in w.winfo_children():
                        if isinstance(child, tk.Label) and "OTERNOS" in str(
                            child.cget("text")
                        ):
                            child.config(
                                text="Y O R H A", font=(_nf, 9, "bold"), fg=GOLD
                            )
                            break
                    break
        except Exception:
            pass

        # ── Tab bar ──
        try:
            for key, btn in self.tab_btns.items():
                is_active = key == getattr(self, "view", "")
                btn.config(font=(_nf, 7, "bold"), fg=GOLD if is_active else DGOLD)
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind("<Enter>", lambda e, w=btn: w.config(fg=CREAM))
                btn.bind(
                    "<Leave>",
                    lambda e, w=btn, k=key: w.config(
                        fg=GOLD if k == getattr(self, "view", "") else DGOLD
                    ),
                )
        except Exception:
            pass

        # ── Now-playing labels ──
        try:
            self.now_title.config(font=(_nf, 9, "bold"), fg=CREAM)
            self.now_artist.config(font=(_nf, 8), fg=GOLD)
            self.now_album.config(font=(_nf, 7), fg=DGOLD)
            cur = self.now_title.cget("text")
            if cur and not cur.startswith("// "):
                self.now_title.config(text="// " + cur)
        except Exception:
            pass

        # ── Progress bar: gold fill, cream dot ──
        try:
            self.prog_cv.config(bg="#1e1c12")
            self.prog_cv.itemconfig(self.prog_fill, fill=GOLD)
            self.prog_cv.itemconfig(self.prog_dot, fill=CREAM, outline=GOLD)
        except Exception:
            pass

        # ── Player controls: gold hover ──
        try:
            for btn in (
                self.btn_shuf,
                self.btn_prev,
                self.btn_play,
                self.btn_next,
                self.btn_repeat,
            ):
                sz = 16 if btn is self.btn_play else 12
                btn.config(font=(_nf, sz), fg=DGOLD)
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind(
                    "<Enter>",
                    lambda e, w=btn: ColorAnim.run(
                        self.root, w, "fg", DGOLD, GOLD, duration_ms=60
                    ),
                )
                btn.bind(
                    "<Leave>",
                    lambda e, w=btn: ColorAnim.run(
                        self.root, w, "fg", GOLD, DGOLD, duration_ms=60
                    ),
                )
        except Exception:
            pass

        # ── Switch viz button bar: hide cyber/miku/nerv, show nier ──
        try:
            self._viz_mf_cyber.pack_forget()
            self._viz_mf_miku.pack_forget()
            self._viz_mf_nerv.pack_forget()
            self._viz_mf_nier.pack(side="right")
            for mode, btn in self._viz_mode_btns.items():
                if mode.startswith("nier_"):
                    btn.config(font=(_nf, 8, "bold"), bg=C["bg"])
            self._set_viz_mode("nier_yorha")
        except Exception:
            pass

        # ── Viz info labels ──
        try:
            self.viz_track_lbl.config(font=(_nf, 8), fg=CREAM)
            self.viz_pos_lbl.config(font=(_nf, 8), fg=DGOLD)
            self.viz_mode_lbl.config(font=(_nf, 8), fg=GOLD)
        except Exception:
            pass

        # ── Sidebar section dividers → gold ──
        try:

            def _gold_dividers(w):
                if w.winfo_class() == "Frame":
                    try:
                        if w.cget("bg").lower() in (
                            C["border2"].lower(),
                            C["border"].lower(),
                        ):
                            w.config(bg=DGOLD)
                    except Exception:
                        pass
                for ch in w.winfo_children() if hasattr(w, "winfo_children") else []:
                    _gold_dividers(ch)

            _gold_dividers(self._side_frame)
        except Exception:
            pass

        try:
            self._sidebar_status_lbl.config(font=(_nf, 6), fg=DGOLD)
        except Exception:
            pass

    # ── NieR Visualizer 1: YoRHa — hexagonal sigil + spectrum ──
    def _viz_nier_yorha(self, cv, W, H, t, playing, bars):
        import math as _m

        bass = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0

        # Scanline texture
        for yy in range(0, H, 4):
            cv.create_line(0, yy, W, yy, fill="#111108", width=1)

        cx, cy = W / 2, H / 2
        ang = t * 0.006

        # Outer slow hex
        r_out = min(W, H) * (0.38 + bass * 0.06)
        gv = int(140 + bass * 80)
        pts = []
        for k in range(6):
            a = ang + k * _m.pi / 3
            pts += [cx + r_out * _m.cos(a), cy + r_out * _m.sin(a)]
        cv.create_polygon(
            pts,
            outline=f"#{gv:02x}{int(gv * 0.9):02x}{int(gv * 0.55):02x}",
            fill="",
            width=1,
        )

        # Middle hex counter
        r_mid = min(W, H) * (0.25 + energy * 0.04)
        mv = int(100 + energy * 80)
        pts2 = []
        for k in range(6):
            a = -ang * 1.3 + k * _m.pi / 3
            pts2 += [cx + r_mid * _m.cos(a), cy + r_mid * _m.sin(a)]
        cv.create_polygon(
            pts2,
            outline=f"#{mv:02x}{int(mv * 0.9):02x}{int(mv * 0.5):02x}",
            fill="",
            width=1,
        )

        # Cross
        arm = min(W, H) * 0.32 * (0.9 + bass * 0.1)
        lv = int(110 + energy * 90)
        lc = f"#{lv:02x}{int(lv * 0.88):02x}{int(lv * 0.5):02x}"
        cv.create_line(cx - arm, cy, cx + arm, cy, fill=lc, width=1)
        cv.create_line(cx, cy - arm, cx, cy + arm, fill=lc, width=1)

        # Core
        cr = min(W, H) * (0.04 + bass * 0.03)
        cv2 = int(180 + bass * 70)
        cv.create_oval(
            cx - cr,
            cy - cr,
            cx + cr,
            cy + cr,
            fill=f"#{cv2:02x}{int(cv2 * 0.9):02x}{int(cv2 * 0.55):02x}",
            outline="",
        )

        # Spectrum bars — small, around outer ring base
        n = len(bars)
        if n:
            bw = (W - 80) / n
            for i, h in enumerate(bars):
                bh = max(1, h * (H * 0.18))
                bx = 40 + i * bw
                fv = int(60 + h * 140)
                cv.create_rectangle(
                    bx,
                    H - 20 - bh,
                    bx + bw - 1,
                    H - 20,
                    fill=f"#{fv:02x}{int(fv * 0.88):02x}{int(fv * 0.5):02x}",
                    outline="",
                )

        # Corner data
        dv = int(60 + energy * 80)
        dc = f"#{dv:02x}{int(dv * 0.85):02x}{int(dv * 0.45):02x}"
        unit_text = ["No. 2 Type B", "No. 9 Type S", "YoRHa Unit", "Bunker Comm"]
        cv.create_text(
            8,
            8,
            text=f"[ {unit_text[(t // 200) % 4]} ]",
            font=("Consolas", max(6, int(W * 0.013))),
            fill=dc,
            anchor="nw",
        )
        cv.create_text(
            W - 8,
            8,
            text=f"// {int(energy * 100):03d} //",
            font=("Consolas", max(6, int(W * 0.013))),
            fill=dc,
            anchor="ne",
        )
        cv.create_text(
            W - 8,
            H - 8,
            text="Glory to Mankind",
            font=("Consolas", max(6, int(W * 0.012))),
            fill=dc,
            anchor="se",
        )

    # ── NieR Visualizer 2: Machine — network of nodes + pulses ──
    def _viz_nier_machine(self, cv, W, H, t, playing, bars):
        import math as _m

        bass = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0

        for yy in range(0, H, 4):
            cv.create_line(0, yy, W, yy, fill="#111108", width=1)

        # Node grid
        cols, rows = 8, 5
        nodes = []
        for r in range(rows):
            for c in range(cols):
                nx = W * (0.1 + 0.8 * c / (cols - 1))
                ny = H * (0.15 + 0.7 * r / (rows - 1))
                nodes.append((nx, ny))

        # Edges — connect nearby nodes, pulsing brightness
        for i, (x1, y1) in enumerate(nodes):
            for j, (x2, y2) in enumerate(nodes):
                if j <= i:
                    continue
                dist = _m.hypot(x2 - x1, y2 - y1)
                if dist > W * 0.22:
                    continue
                bar_idx = min(len(bars) - 1, (i + j) % max(len(bars), 1)) if bars else 0
                pulse = bars[bar_idx] if bars else 0
                ev = int(25 + pulse * 70)
                cv.create_line(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=f"#{ev:02x}{int(ev * 0.88):02x}{int(ev * 0.5):02x}",
                    width=1,
                )

        # Nodes — radius pulses with bass
        for i, (nx, ny) in enumerate(nodes):
            bar_idx = min(len(bars) - 1, i % max(len(bars), 1)) if bars else 0
            amp = bars[bar_idx] if bars else 0
            nr = 3 + amp * 7 + bass * 4
            nv = int(80 + amp * 160)
            cv.create_oval(
                nx - nr,
                ny - nr,
                nx + nr,
                ny + nr,
                fill=f"#{nv:02x}{int(nv * 0.88):02x}{int(nv * 0.5):02x}",
                outline="",
            )

        # Travelling pulse dot along random edge based on t
        if len(nodes) > 1:
            edge_t = (t % 120) / 120.0
            n1 = nodes[(t // 120) % len(nodes)]
            n2 = nodes[(t // 120 + 3) % len(nodes)]
            px = n1[0] + (n2[0] - n1[0]) * edge_t
            py = n1[1] + (n2[1] - n1[1]) * edge_t
            pv = int(200 + bass * 55)
            pr = 5 + bass * 6
            cv.create_oval(
                px - pr,
                py - pr,
                px + pr,
                py + pr,
                fill=f"#{pv:02x}{int(pv * 0.9):02x}{int(pv * 0.55):02x}",
                outline="",
            )

        dv = int(55 + energy * 70)
        dc = f"#{dv:02x}{int(dv * 0.85):02x}{int(dv * 0.45):02x}"
        labels = ["CONNECTED", "TRANSMITTING", "SEARCHING", "NETWORK OK"]
        cv.create_text(
            W // 2,
            H - 12,
            text=f"// MACHINE NETWORK — {labels[(t // 150) % 4]} //",
            font=("Consolas", max(6, int(W * 0.013))),
            fill=dc,
            anchor="center",
        )

    # ── NieR Visualizer 3: Ruins — waveform + falling glyph rain ──
    def _viz_nier_ruins(self, cv, W, H, t, playing, bars):
        import random as _random

        sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0

        for yy in range(0, H, 4):
            cv.create_line(0, yy, W, yy, fill="#111108", width=1)

        # Falling glyph columns — use per-column isolated RNG, never touch global state
        GLYPHS = "01アイウエオカキ⬡⬢◈◉▸▹░▒▓"
        cols = 16
        cw = W / cols
        for ci in range(cols):
            rng = _random.Random(ci * 137 + t // 8)
            gy = (t * (1.0 + ci * 0.07)) % (H + 40) - 20
            gv = int(40 + rng.random() * 60)
            gc = f"#{gv:02x}{int(gv * 0.88):02x}{int(gv * 0.5):02x}"
            cv.create_text(
                ci * cw + cw / 2,
                gy,
                text=rng.choice(GLYPHS),
                font=("Consolas", max(7, int(cw * 0.55))),
                fill=gc,
                anchor="center",
            )
            # Trail
            for trail in range(1, 4):
                ty = gy - trail * 18
                tv = int(gv * (1 - trail * 0.25))
                tc = f"#{tv:02x}{int(tv * 0.88):02x}{int(tv * 0.5):02x}"
                rng_trail = _random.Random(ci * 137 + (t // 8) - trail)
                cv.create_text(
                    ci * cw + cw / 2,
                    ty,
                    text=rng_trail.choice(GLYPHS),
                    font=("Consolas", max(6, int(cw * 0.45))),
                    fill=tc,
                    anchor="center",
                )

        # Waveform overlay
        if bars:
            n = len(bars)
            cy = H // 2
            pts = []
            for i, h in enumerate(bars):
                x = (i / n) * W
                y = cy - h * H * 0.28
                pts.extend([x, y])
            if len(pts) >= 4:
                wv = int(120 + energy * 100)
                cv.create_line(
                    pts,
                    fill=f"#{wv:02x}{int(wv * 0.9):02x}{int(wv * 0.55):02x}",
                    width=2,
                    smooth=True,
                )
            # Mirror
            pts2 = []
            for i, h in enumerate(bars):
                x = (i / n) * W
                y = cy + h * H * 0.28
                pts2.extend([x, y])
            if len(pts2) >= 4:
                wv2 = int(70 + energy * 60)
                cv.create_line(
                    pts2,
                    fill=f"#{wv2:02x}{int(wv2 * 0.9):02x}{int(wv2 * 0.55):02x}",
                    width=1,
                    smooth=True,
                )

        # Status line
        dv = int(60 + energy * 70)
        dc = f"#{dv:02x}{int(dv * 0.85):02x}{int(dv * 0.45):02x}"
        msgs = [
            "SYSTEM FAILURE",
            "OBJECTIVE UNKNOWN",
            "SEARCHING FOR PURPOSE",
            "DATA CORRUPTED",
            "...",
        ]
        cv.create_text(
            W // 2,
            H - 12,
            text=f"[ {msgs[(t // 180) % len(msgs)]} ]",
            font=("Consolas", max(6, int(W * 0.013))),
            fill=dc,
            anchor="center",
        )

    # ══════════════════════════════════════════════════════════
    #  ANGEL THEME — ethereal angelcore / void blush overhaul
    # ══════════════════════════════════════════════════════════
    def _apply_angel_theme(self):
        """
        Full angel theme pass. Runs AFTER _rebuild_ui_colors has applied
        the ANGEL palette. Soft blush + white, gothic cursive fonts,
        feather dividers, angelic wordmarks, blush hover glows.
        """
        global FM, FMS, FML, FMX

        BLUSH = "#d4449a"
        ROSE = "#e8789c"
        LILAC = "#b07aa0"
        INK = "#1a0e18"
        DIM = "#c090b0"
        BGWHITE = "#fdf6fb"

        # ── Pick best gothic cursive font available on Windows ──
        _script = next(
            (
                f
                for f in (
                    "Edwardian Script ITC",
                    "Kunstler Script",
                    "French Script MT",
                    "Monotype Corsiva",
                    "Lucida Calligraphy",
                    "Segoe Script",
                    "Lucida Handwriting",
                    "Palatino Linotype",
                    "Book Antiqua",
                    "Courier New",
                )
                if self._font_exists(f)
            ),
            "Courier New",
        )

        _serif = next(
            (
                f
                for f in (
                    "Palatino Linotype",
                    "Book Antiqua",
                    "Garamond",
                    "Perpetua",
                    "Georgia",
                    "Times New Roman",
                    "Courier New",
                )
                if self._font_exists(f)
            ),
            "Courier New",
        )

        # Override global font tokens with script + serif
        FM = (_script, 9)
        FMS = (_script, 8)
        FML = (_script, 11, "bold")
        FMX = (_script, 14, "bold")

        # ── Sidebar wordmark → cursive angelic ──
        try:
            for w in self._side_frame.winfo_children():
                for child in w.winfo_children() if hasattr(w, "winfo_children") else []:
                    if isinstance(child, tk.Label):
                        t = child.cget("text")
                        if t == "OTERNOS":
                            child.config(
                                text="✦ Angel ✦", font=(_script, 11, "bold"), fg=BLUSH
                            )
                        elif "SYS v" in str(t):
                            child.config(
                                text="she ascends ✧", font=(_script, 7), fg=DIM
                            )
        except Exception:
            pass

        # ── Topbar wordmark ──
        try:
            for w in self.root.winfo_children():
                if w.winfo_class() == "Frame":
                    for child in w.winfo_children():
                        if isinstance(child, tk.Label) and "OTERNOS" in str(
                            child.cget("text")
                        ):
                            child.config(
                                text="✦ Angel.exe ✦",
                                font=(_script, 12, "bold"),
                                fg=BLUSH,
                            )
                            break
                    break
        except Exception:
            pass

        # ── Tab bar — script font, blush active ──
        try:
            for key, btn in self.tab_btns.items():
                is_active = key == getattr(self, "view", "")
                btn.config(font=(_script, 8, "bold"), fg=BLUSH if is_active else LILAC)
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind("<Enter>", lambda e, w=btn: w.config(fg=INK))
                btn.bind(
                    "<Leave>",
                    lambda e, w=btn, k=key: w.config(
                        fg=BLUSH if k == getattr(self, "view", "") else LILAC
                    ),
                )
        except Exception:
            pass

        # ── Now-playing labels — script title, serif artist ──
        try:
            self.now_title.config(font=(_script, 12, "bold"), fg=INK)
            self.now_artist.config(font=(_script, 9), fg=BLUSH)
            self.now_album.config(font=(_serif, 7, "italic"), fg=LILAC)
            cur = self.now_title.cget("text")
            if cur and not cur.startswith("✦ "):
                self.now_title.config(text="✦ " + cur)
        except Exception:
            pass

        # ── Progress bar — blush fill, rose dot ──
        try:
            self.prog_cv.config(bg="#f0d8e8")
            self.prog_cv.itemconfig(self.prog_fill, fill=BLUSH)
            self.prog_cv.itemconfig(self.prog_dot, fill=BGWHITE, outline=BLUSH)
        except Exception:
            pass

        # ── Player control buttons — blush hover anim ──
        try:
            for btn in (
                self.btn_shuf,
                self.btn_prev,
                self.btn_play,
                self.btn_next,
                self.btn_repeat,
            ):
                sz = 18 if btn is self.btn_play else 13
                btn.config(font=(_script, sz), fg=ROSE)
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind(
                    "<Enter>",
                    lambda e, w=btn: ColorAnim.run(
                        self.root, w, "fg", ROSE, BLUSH, duration_ms=60
                    ),
                )
                btn.bind(
                    "<Leave>",
                    lambda e, w=btn: ColorAnim.run(
                        self.root, w, "fg", BLUSH, ROSE, duration_ms=60
                    ),
                )
        except Exception:
            pass

        # ── All sidebar labels → script font ──
        try:

            def _angel_fonts(w):
                if isinstance(w, tk.Label):
                    try:
                        f = w.cget("font")
                        if "Courier" in str(f) or "Consolas" in str(f):
                            sz = 8
                            try:
                                parts = self.root.tk.splitlist(f)
                                sz = int(parts[1]) if len(parts) > 1 else 8
                            except Exception:
                                pass
                            w.config(font=(_script, sz))
                    except Exception:
                        pass
                for ch in w.winfo_children() if hasattr(w, "winfo_children") else []:
                    _angel_fonts(ch)

            _angel_fonts(self._side_frame)
        except Exception:
            pass

        # ── Sidebar status label ──
        try:
            self._sidebar_status_lbl.config(font=(_script, 7), fg=DIM)
        except Exception:
            pass

        # ── Sidebar section dividers → rose pink ──
        try:

            def _rose_dividers(w):
                if w.winfo_class() == "Frame":
                    try:
                        bg = w.cget("bg").lower()
                        if bg in (C["border2"].lower(), C["border"].lower()):
                            w.config(bg=ROSE)
                    except Exception:
                        pass
                for ch in w.winfo_children() if hasattr(w, "winfo_children") else []:
                    _rose_dividers(ch)

            _rose_dividers(self._side_frame)
        except Exception:
            pass

        # ── DataTicker → AngelTicker (soft rose scrolling text) ──
        try:
            if (
                hasattr(self, "_ticker")
                and not isinstance(self._ticker, AngelTicker)
                and self._ticker.winfo_exists()
            ):
                parent = self._ticker.master
                self._ticker.destroy()
                self._ticker = AngelTicker(parent, width=900, height=10, bg=C["panel"])
                self._ticker.pack(fill="x")
        except Exception:
            pass

        # ── Switch to angel viz frame ──
        try:
            self._viz_mf_cyber.pack_forget()
            self._viz_mf_miku.pack_forget()
            self._viz_mf_nerv.pack_forget()
            self._viz_mf_nier.pack_forget()
            self._viz_mf_angel.pack(side="right")
            for mode, btn in self._viz_mode_btns.items():
                if mode.startswith("angel_"):
                    btn.config(bg=C["bg"], font=(_script, 8, "bold"))
            self._set_viz_mode("angel_feathers")
        except Exception:
            pass

        # ── Viz info labels — script font ──
        try:
            self.viz_track_lbl.config(font=(_script, 9), fg=INK)
            self.viz_pos_lbl.config(font=(_script, 8), fg=LILAC)
            self.viz_mode_lbl.config(font=(_script, 9, "bold"), fg=BLUSH)
        except Exception:
            pass

        # ── Baroque frame overlay — 4 corner canvases ──
        try:
            # Already destroyed by _rebuild_ui_colors — just create fresh
            self._baroque_frame = BaroqueFrame(self.root, bg=C["panel"])
        except Exception:
            pass

    # ── ANGEL Viz 1: Feathers — falling feather particles ──
    def _viz_angel_feathers(self, cv, W, H, t, playing, bars):
        import math as _m
        import random as _rng

        bass = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0

        # Soft white/blush background gradient
        steps = 12
        for i in range(steps):
            y0 = H * i // steps
            y1 = H * (i + 1) // steps
            fade = i / steps
            r = int(253 - fade * 8)
            g = int(246 - fade * 20)
            b = int(251 - fade * 10)
            cv.create_rectangle(
                0, y0, W, y1, fill=f"#{r:02x}{g:02x}{b:02x}", outline=""
            )

        # Soft radial glow at centre — aurora bloom
        cx, cy = W / 2, H * 0.42
        glow_r = min(W, H) * (0.35 + bass * 0.15)
        for ring in range(8, 0, -1):
            rr = glow_r * ring / 8
            alpha_v = int(8 + (8 - ring) * 4 + bass * 20)
            alpha_v = min(alpha_v, 60)
            rv = int(240 + bass * 15)
            gv = int(180 + bass * 30)
            bv = int(210 + bass * 30)
            col = f"#{min(rv, 255):02x}{min(gv, 255):02x}{min(bv, 255):02x}"
            try:
                cv.create_oval(
                    cx - rr, cy - rr, cx + rr, cy + rr, outline=col, width=1, fill=""
                )
            except Exception:
                pass

        # Halo ring at top
        halo_y = H * 0.18
        halo_rx = min(W, H) * (0.12 + bass * 0.03)
        halo_ry = halo_rx * 0.22
        hv = int(160 + bass * 55)
        halo_col = f"#{min(hv + 60, 255):02x}{int(hv * 0.4):02x}{int(hv * 0.7):02x}"
        cv.create_oval(
            cx - halo_rx,
            halo_y - halo_ry,
            cx + halo_rx,
            halo_y + halo_ry,
            outline=halo_col,
            width=2,
            fill="",
        )
        cv.create_oval(
            cx - halo_rx * 1.06,
            halo_y - halo_ry * 1.4,
            cx + halo_rx * 1.06,
            halo_y + halo_ry * 1.4,
            outline=f"#{int(hv * 0.3):02x}{int(hv * 0.2):02x}{int(hv * 0.3):02x}",
            width=1,
            fill="",
        )

        # Falling feathers
        FEATHER_COLS = 18
        for col_i in range(FEATHER_COLS):
            rng = _rng.Random(col_i * 919 + t // 6)
            speed = 0.8 + col_i * 0.13 + rng.random() * 0.5
            fy = (t * speed * 0.55 + col_i * (H / FEATHER_COLS) * 1.3) % (H + 80) - 40
            fx = W * (0.04 + (col_i / FEATHER_COLS) * 0.92)
            # Gentle sway
            sway = _m.sin(t * 0.018 + col_i * 1.3) * 18
            fx += sway

            # Feather brightness — tied to nearby bar
            bar_i = (
                min(len(bars) - 1, int(col_i / FEATHER_COLS * len(bars))) if bars else 0
            )
            amp = bars[bar_i] if bars else 0.3
            bv2 = int(180 + amp * 75)
            gv2 = int(80 + amp * 60)
            feath_col = f"#{min(bv2, 255):02x}{min(gv2, 255):02x}{int(bv2 * 0.85):02x}"
            feath_dim = (
                f"#{int(bv2 * 0.7):02x}{int(gv2 * 0.6):02x}{int(bv2 * 0.65):02x}"
            )

            # Draw feather as a tapered oval + central quill line
            fl = 22 + amp * 12  # feather length
            fw = 7 + amp * 4  # feather width
            angle = _m.sin(t * 0.02 + col_i) * 0.3  # slight rotation
            cos_a = _m.cos(angle)
            sin_a = _m.sin(angle)
            # Tip and base
            tip_x = fx + cos_a * fl * 0.5
            tip_y = fy - sin_a * fl * 0.5
            base_x = fx - cos_a * fl * 0.5
            base_y = fy + sin_a * fl * 0.5
            # Side points (perpendicular)
            perp_x = -sin_a * fw * 0.5
            perp_y = cos_a * fw * 0.5
            pts = [
                tip_x,
                tip_y,
                fx + perp_x * 0.7,
                fy + perp_y * 0.7,
                base_x,
                base_y,
                fx - perp_x * 0.7,
                fy - perp_y * 0.7,
            ]
            try:
                cv.create_polygon(
                    pts, fill=feath_dim, outline=feath_col, width=1, smooth=True
                )
                # Central quill
                cv.create_line(tip_x, tip_y, base_x, base_y, fill=feath_col, width=1)
                # Barbs — tiny lines branching off quill
                for barb in range(4):
                    tb = 0.2 + barb * 0.2
                    bx = tip_x + (base_x - tip_x) * tb
                    by = tip_y + (base_y - tip_y) * tb
                    bl = fw * (0.9 - barb * 0.15)
                    cv.create_line(
                        bx,
                        by,
                        bx + perp_x * bl,
                        by + perp_y * bl,
                        fill=feath_dim,
                        width=1,
                    )
                    cv.create_line(
                        bx,
                        by,
                        bx - perp_x * bl,
                        by - perp_y * bl,
                        fill=feath_dim,
                        width=1,
                    )
            except Exception:
                pass

        # Floating sparkle dots
        for si in range(20):
            rng2 = _rng.Random(si * 337 + t // 12)
            sx = W * rng2.random()
            sy = H * rng2.random()
            pulse = _m.sin(t * 0.04 + si * 0.8) * 0.5 + 0.5
            sv = int(180 + pulse * 75)
            sr = 1 + pulse * 2
            scol = f"#{min(sv, 255):02x}{int(sv * 0.4):02x}{int(sv * 0.75):02x}"
            cv.create_oval(sx - sr, sy - sr, sx + sr, sy + sr, fill=scol, outline="")

        # Bottom spectrum — soft blush bars
        if bars:
            n = len(bars)
            bw = W / n
            for i, h in enumerate(bars):
                bh = max(1, h * H * 0.15)
                bx = i * bw
                fv3 = int(180 + h * 75)
                gv3 = int(60 + h * 60)
                bcol = f"#{min(fv3, 255):02x}{min(gv3, 255):02x}{int(fv3 * 0.85):02x}"
                cv.create_rectangle(bx, H - bh, bx + bw - 1, H, fill=bcol, outline="")

        # Corner text
        ev = int(100 + energy * 80)
        ec = f"#{min(ev + 80, 255):02x}{int(ev * 0.3):02x}{int(ev * 0.7):02x}"
        msgs = ["✦ ascending ✦", "✧ holy static ✧", "✦ pure signal ✦", "✧ void angel ✧"]
        cv.create_text(
            W // 2,
            H - 14,
            text=msgs[(t // 160) % len(msgs)],
            font=("Courier New", max(6, int(W * 0.013))),
            fill=ec,
            anchor="center",
        )
        cv.create_text(
            8,
            8,
            text="SOUL: ████ 100%",
            font=("Courier New", max(6, int(W * 0.013))),
            fill=ec,
            anchor="nw",
        )
        cv.create_text(
            W - 8,
            8,
            text=f"WINGS: {int(energy * 100):03d}Hz",
            font=("Courier New", max(6, int(W * 0.013))),
            fill=ec,
            anchor="ne",
        )

    # ── ANGEL Viz 2: Halo — rotating sacred geometry + spectrum ──
    def _viz_angel_halo(self, cv, W, H, t, playing, bars):
        import math as _m

        bass = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0
        cx, cy = W / 2, H / 2

        # Soft white bg
        cv.create_rectangle(0, 0, W, H, fill="#fdf6fb", outline="")

        ang = t * 0.007

        # Outer halo ellipse (tilted perspective)
        halo_rx = min(W, H) * (0.40 + bass * 0.06)
        halo_ry = halo_rx * 0.20
        hv = int(80 + bass * 90)
        halo_c = f"#{min(hv + 100, 255):02x}{int(hv * 0.3):02x}{int(hv * 0.75):02x}"
        cv.create_oval(
            cx - halo_rx,
            cy * 0.48 - halo_ry,
            cx + halo_rx,
            cy * 0.48 + halo_ry,
            outline=halo_c,
            width=3,
            fill="",
        )
        # Inner glow halo
        halo_rx2 = halo_rx * 0.88
        cv.create_oval(
            cx - halo_rx2,
            cy * 0.48 - halo_ry * 0.7,
            cx + halo_rx2,
            cy * 0.48 + halo_ry * 0.7,
            outline=f"#{int(hv * 0.4):02x}{int(hv * 0.2):02x}{int(hv * 0.35):02x}",
            width=1,
            fill="",
        )

        # Rotating 8-pointed star sigil
        star_r_out = min(W, H) * (0.28 + bass * 0.06)
        star_r_in = star_r_out * 0.42
        pts = []
        for k in range(16):
            r = star_r_out if k % 2 == 0 else star_r_in
            a = ang + k * _m.pi / 8
            pts += [cx + r * _m.cos(a), cy + r * _m.sin(a)]
        sv = int(80 + bass * 100)
        star_c = f"#{min(sv + 100, 255):02x}{int(sv * 0.25):02x}{int(sv * 0.7):02x}"
        cv.create_polygon(pts, outline=star_c, fill="", width=1)

        # Inner rotating cross
        cross_r = star_r_in * 0.85
        for arm in range(4):
            a = -ang * 1.5 + arm * _m.pi / 2
            cv.create_line(
                cx,
                cy,
                cx + cross_r * _m.cos(a),
                cy + cross_r * _m.sin(a),
                fill=f"#{int(sv * 0.6):02x}{int(sv * 0.3):02x}{int(sv * 0.55):02x}",
                width=1,
            )

        # Orbiting feather dots
        for oi in range(12):
            oa = ang * 1.8 + oi * _m.pi / 6
            bar_i = min(len(bars) - 1, oi % max(len(bars), 1)) if bars else 0
            amp = bars[bar_i] if bars else 0.3
            orb_r = star_r_out * (1.15 + amp * 0.12)
            ox = cx + orb_r * _m.cos(oa)
            oy = cy + orb_r * _m.sin(oa)
            ov = int(120 + amp * 135)
            oc = f"#{min(ov + 60, 255):02x}{int(ov * 0.2):02x}{int(ov * 0.65):02x}"
            dot_r = 2 + amp * 4
            cv.create_oval(
                ox - dot_r, oy - dot_r, ox + dot_r, oy + dot_r, fill=oc, outline=""
            )

        # Core glow
        core_r = min(W, H) * (0.045 + bass * 0.035)
        cv2 = int(160 + bass * 55)
        cv.create_oval(
            cx - core_r,
            cy - core_r,
            cx + core_r,
            cy + core_r,
            fill=f"#{min(cv2 + 60, 255):02x}{int(cv2 * 0.25):02x}{int(cv2 * 0.75):02x}",
            outline="",
        )

        # Spectrum — circular, around the sigil
        if bars:
            n = len(bars)
            for i, h in enumerate(bars):
                a = (i / n) * _m.pi * 2 - _m.pi / 2
                r_inner = star_r_out * 1.30
                r_outer = r_inner + h * min(W, H) * 0.15
                bv = int(100 + h * 155)
                bcol = (
                    f"#{min(bv + 60, 255):02x}{int(bv * 0.2):02x}{int(bv * 0.65):02x}"
                )
                x0 = cx + r_inner * _m.cos(a)
                y0 = cy + r_inner * _m.sin(a)
                x1 = cx + r_outer * _m.cos(a)
                y1 = cy + r_outer * _m.sin(a)
                cv.create_line(x0, y0, x1, y1, fill=bcol, width=2)

        ev = int(80 + energy * 80)
        ec = f"#{min(ev + 80, 255):02x}{int(ev * 0.25):02x}{int(ev * 0.65):02x}"
        cv.create_text(
            W // 2,
            H - 14,
            text="✦ HALO SIGNAL ✦",
            font=("Courier New", max(6, int(W * 0.013))),
            fill=ec,
            anchor="center",
        )
        cv.create_text(
            8,
            8,
            text=f"SANCTITY: {int(energy * 100):03d}%",
            font=("Courier New", max(6, int(W * 0.013))),
            fill=ec,
            anchor="nw",
        )

    # ── ANGEL Viz 3: Wings — sweeping wing arcs + feather bars ──
    def _viz_angel_wings(self, cv, W, H, t, playing, bars):
        import math as _m

        bass = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0
        cx, cy = W / 2, H * 0.52

        # Soft white bg
        cv.create_rectangle(0, 0, W, H, fill="#fdf6fb", outline="")

        # Ambient bottom glow
        glow_steps = 10
        for gi in range(glow_steps, 0, -1):
            gw = W * gi / glow_steps
            gh = H * 0.25 * gi / glow_steps
            gv = int(220 + bass * 25)
            gv2a = int(160 + bass * 50)
            cv.create_oval(
                cx - gw / 2,
                H - gh,
                cx + gw / 2,
                H + gh,
                fill=f"#{min(gv, 255):02x}{min(gv2a, 255):02x}{int(gv * 0.95):02x}",
                outline="",
            )

        # Wing sweep — each wing is multiple arcs (primary, secondary, covert feathers)
        flap_ang = _m.sin(t * 0.025) * 0.22 * (1 + bass * 0.6)  # flap with beat
        wing_span = min(W, H) * (0.38 + bass * 0.05)

        for side in (-1, 1):  # left=-1, right=1
            # Primary feathers — big sweeping arcs
            for fi in range(9):
                ratio = fi / 8
                # Angle spread for each feather
                base_ang = (
                    side * (_m.pi * 0.10 + ratio * _m.pi * 0.52) + flap_ang * side
                )
                tip_ang = base_ang + side * _m.pi * 0.09
                feather_len = wing_span * (0.95 - ratio * 0.28)

                fx_root = cx + side * wing_span * 0.05
                fy_root = cy - min(W, H) * 0.02
                fx_mid = fx_root + _m.cos(base_ang) * feather_len * 0.55
                fy_mid = fy_root + _m.sin(base_ang) * feather_len * 0.55
                fx_tip = fx_root + _m.cos(tip_ang) * feather_len
                fy_tip = fy_root + _m.sin(tip_ang) * feather_len

                bar_i = min(len(bars) - 1, int(ratio * len(bars) * 0.9)) if bars else 0
                amp = bars[bar_i] if bars else 0.3
                fv = int(120 + amp * 135)
                fv2 = int(80 + amp * 100)
                fcol = (
                    f"#{min(fv + 60, 255):02x}{int(fv * 0.2):02x}{int(fv * 0.65):02x}"
                )
                fcol2 = f"#{int(fv2 + 80):02x}{int(fv2 * 0.25):02x}{int(fv2 * 0.7):02x}"
                width = max(1, int(3 - ratio * 1.5) + int(amp * 2))
                try:
                    cv.create_line(
                        fx_root,
                        fy_root,
                        fx_mid,
                        fy_mid,
                        fx_tip,
                        fy_tip,
                        fill=fcol,
                        width=width,
                        smooth=True,
                    )
                    # Feather edge barb line
                    barb_dx = (fy_tip - fy_mid) * 0.12 * side
                    barb_dy = -(fx_tip - fx_mid) * 0.12 * side
                    cv.create_line(
                        fx_mid,
                        fy_mid,
                        fx_mid + barb_dx,
                        fy_mid + barb_dy,
                        fill=fcol2,
                        width=1,
                    )
                except Exception:
                    pass

            # Secondary covert feathers — smaller, above primary row
            for si in range(6):
                ratio2 = si / 5
                cov_ang = (
                    side * (_m.pi * 0.08 + ratio2 * _m.pi * 0.38)
                    + flap_ang * side * 0.7
                )
                cov_len = wing_span * (0.42 - ratio2 * 0.12)
                cx2 = cx + side * wing_span * 0.04
                cy2 = cy - min(W, H) * 0.06
                cx2_tip = cx2 + _m.cos(cov_ang) * cov_len
                cy2_tip = cy2 + _m.sin(cov_ang) * cov_len
                bar_i2 = (
                    min(len(bars) - 1, int(ratio2 * len(bars) * 0.5)) if bars else 0
                )
                amp2 = bars[bar_i2] if bars else 0.2
                cv3 = int(100 + amp2 * 110)
                ccol = (
                    f"#{min(cv3 + 80, 255):02x}{int(cv3 * 0.2):02x}{int(cv3 * 0.6):02x}"
                )
                try:
                    cv.create_line(cx2, cy2, cx2_tip, cy2_tip, fill=ccol, width=1)
                except Exception:
                    pass

        # Central body glow — soft blush core
        core_r = min(W, H) * (0.04 + bass * 0.025)
        cv2v = int(160 + bass * 75)
        cv.create_oval(
            cx - core_r,
            cy - core_r,
            cx + core_r,
            cy + core_r,
            fill=f"#{min(cv2v + 60, 255):02x}{int(cv2v * 0.25):02x}{int(cv2v * 0.75):02x}",
            outline="",
        )

        # Floating particles drifting up from centre
        import random as _rng2

        for pi in range(14):
            rng3 = _rng2.Random(pi * 773 + t // 10)
            px = cx + (rng3.random() - 0.5) * W * 0.5
            py_base = cy + rng3.random() * H * 0.3
            py = (py_base - t * (0.4 + rng3.random() * 0.4)) % H
            pv = int(150 + rng3.random() * 105)
            pr = 1 + rng3.random() * 2
            pcol = f"#{min(pv + 50, 255):02x}{int(pv * 0.2):02x}{int(pv * 0.65):02x}"
            cv.create_oval(px - pr, py - pr, px + pr, py + pr, fill=pcol, outline="")

        ev = int(80 + energy * 80)
        ec = f"#{min(ev + 80, 255):02x}{int(ev * 0.25):02x}{int(ev * 0.65):02x}"
        wing_msgs = [
            "✦ wings unfold ✦",
            "✧ take flight ✧",
            "✦ beyond the void ✦",
            "✧ she ascends ✧",
        ]
        cv.create_text(
            W // 2,
            H - 14,
            text=wing_msgs[(t // 170) % 4],
            font=("Courier New", max(6, int(W * 0.013))),
            fill=ec,
            anchor="center",
        )
        cv.create_text(
            8,
            8,
            text=f"WINGSPAN: {int(bass * 100 + bass * W * 0.01):03d}",
            font=("Courier New", max(6, int(W * 0.013))),
            fill=ec,
            anchor="nw",
        )
        cv.create_text(
            W - 8,
            8,
            text="ALT: ∞",
            font=("Courier New", max(6, int(W * 0.013))),
            fill=ec,
            anchor="ne",
        )

    # ══════════════════════════════════════
    #  MIKU THEME — independent full override
    # ══════════════════════════════════════
    def _apply_miku_theme(self):
        """
        Fully independent Miku theme pass. Runs AFTER _rebuild_ui_colors
        has already applied the Miku color palette. Swaps every cybercore
        widget for its Miku equivalent without touching any cybercore state.
        """
        global FM, FMS, FML, FMX
        # Pick the softest available font on Windows for Miku
        _miku_body = next(
            (
                f
                for f in (
                    "Yu Gothic UI",
                    "Meiryo UI",
                    "Microsoft YaHei UI",
                    "Segoe UI",
                    "Consolas",
                )
                if self._font_exists(f)
            ),
            "Consolas",
        )
        FM = (_miku_body, 9)
        FMS = (_miku_body, 8)
        FML = (_miku_body, 10, "bold")
        FMX = (_miku_body, 13, "bold")

        # ── Sidebar logo → MikuLogo ──
        try:
            if not isinstance(self._sidebar_logo, MikuLogo):
                parent = self._sidebar_logo.master
                self._sidebar_logo.destroy()
                self._sidebar_logo = MikuLogo(parent, size=52, bg=C["panel"])
                self._sidebar_logo.pack(side="left", padx=(14, 8))
                self._sidebar_logo.is_playing = getattr(self.engine, "playing", False)
        except Exception:
            pass

        # ── Sidebar wordmark ──
        try:
            for w in self._side_frame.winfo_children():
                for child in w.winfo_children() if hasattr(w, "winfo_children") else []:
                    if isinstance(child, tk.Label):
                        t = child.cget("text")
                        if t == "OTERNOS":
                            child.config(
                                text="初音ミク",
                                font=("Consolas", 8, "bold"),
                                fg=C["glow"],
                            )
                        elif "SYS v" in str(t):
                            child.config(
                                text="VOCALOID ♪", font=("Consolas", 6), fg=C["white3"]
                            )
        except Exception:
            pass

        # ── Topbar wordmark ──
        try:
            for w in self.root.winfo_children():
                if w.winfo_class() == "Frame":
                    for child in w.winfo_children():
                        if isinstance(child, tk.Label) and "OTERNOS" in str(
                            child.cget("text")
                        ):
                            child.config(
                                text="✦ M I K U  P L A Y E R ✦",
                                font=("Consolas", 9, "bold"),
                                fg=C["glow"],
                            )
                            break
                    break
        except Exception:
            pass

        # ── Tab bar ──
        try:
            for key, btn in self.tab_btns.items():
                is_active = key == getattr(self, "view", "")
                btn.config(
                    font=("Consolas", 7, "bold"),
                    fg=C["glow"] if is_active else C["white3"],
                )
        except Exception:
            pass

        # ── Now-playing labels ──
        try:
            self.now_title.config(font=("Consolas", 9, "bold"), fg=C["white"])
            self.now_artist.config(font=("Consolas", 8), fg=C["glow"])
            self.now_album.config(font=("Consolas", 7), fg=C["white3"])
        except Exception:
            pass

        # ── Progress bar: teal fill, pink dot ──
        try:
            self.prog_cv.config(bg=C["border"])
            self.prog_cv.itemconfig(self.prog_fill, fill=C["glow"])
            self.prog_cv.itemconfig(self.prog_dot, fill=C["red"])
        except Exception:
            pass

        # ── Player controls: pink hover ──
        try:
            for btn in (
                self.btn_shuf,
                self.btn_prev,
                self.btn_play,
                self.btn_next,
                self.btn_repeat,
            ):
                sz = 16 if btn is self.btn_play else 12
                btn.config(font=("Consolas", sz), fg=C["white2"])
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind(
                    "<Enter>",
                    lambda e, w=btn: ColorAnim.run(
                        self.root, w, "fg", C["white2"], C["red"], duration_ms=60
                    ),
                )
                btn.bind(
                    "<Leave>",
                    lambda e, w=btn: ColorAnim.run(
                        self.root, w, "fg", C["red"], C["white2"], duration_ms=60
                    ),
                )
        except Exception:
            pass

        # ── DataTicker → MikuTicker ──
        try:
            if (
                hasattr(self, "_ticker")
                and not isinstance(self._ticker, MikuTicker)
                and self._ticker.winfo_exists()
            ):
                parent = self._ticker.master
                self._ticker.destroy()
                self._ticker = MikuTicker(parent, width=900, height=10, bg=C["panel"])
                self._ticker.pack(fill="x")
        except Exception:
            pass

        # ── CornerBrackets → MikuCornerDeco ──
        try:
            hdr = self.lib_frame.winfo_children()[0]
            for child in list(hdr.winfo_children()):
                if isinstance(child, CornerBrackets):
                    child.destroy()
                    MikuCornerDeco(hdr, size=28, bg=C["bg"]).pack(
                        side="left", padx=(0, 6)
                    )
                    break
        except Exception:
            pass

        # ── Track list ──
        try:
            self.track_list.config(
                font=("Consolas", 9),
                fg=C["white2"],
                selectbackground=C["select2"],
                selectforeground=C["glow"],
            )
        except Exception:
            pass

        # ── Sidebar labels → Consolas ──
        try:

            def _miku_fonts(w):
                if isinstance(w, tk.Label):
                    try:
                        f = w.cget("font")
                        if "Courier" in str(f):
                            sz = 8
                            try:
                                parts = self.root.tk.splitlist(f)
                                sz = int(parts[1]) if len(parts) > 1 else 8
                            except Exception:
                                pass
                            w.config(font=("Consolas", sz))
                    except Exception:
                        pass
                for ch in w.winfo_children() if hasattr(w, "winfo_children") else []:
                    _miku_fonts(ch)

            _miku_fonts(self._side_frame)
        except Exception:
            pass

        try:
            self._sidebar_status_lbl.config(font=("Consolas", 6), fg=C["white3"])
        except Exception:
            pass

        # ── Switch viz button bar: hide cybercore, show miku ──
        try:
            self._viz_mf_cyber.pack_forget()
            self._viz_mf_miku.pack(side="right")
            # Restyle miku buttons with current palette
            miku_font = (
                ("Yu Gothic UI", 8, "bold")
                if self._font_exists("Yu Gothic UI")
                else ("Consolas", 8, "bold")
            )
            for mode, btn in self._viz_mode_btns.items():
                if mode.startswith("miku"):
                    btn.config(font=miku_font, bg=C["bg"])
            self._set_viz_mode("miku_tails")
        except Exception:
            pass

        # ── Viz info bar: teal Consolas text ──
        try:
            miku_font_sm = (
                ("Yu Gothic UI", 8)
                if self._font_exists("Yu Gothic UI")
                else ("Consolas", 8)
            )
            self.viz_track_lbl.config(font=miku_font_sm, fg=C["glow"])
            self.viz_pos_lbl.config(font=miku_font_sm, fg=C["white3"])
            self.viz_mode_lbl.config(font=miku_font_sm, fg=C["white2"])
        except Exception:
            pass

        # ── Now-playing: prefix track title with ♪ ──
        try:
            cur = self.now_title.cget("text")
            if cur and not cur.startswith("♪"):
                self.now_title.config(text="♪  " + cur)
        except Exception:
            pass

        # ── Sidebar section dividers: teal instead of dim white ──
        try:

            def _teal_dividers(w):
                if w.winfo_class() == "Frame":
                    try:
                        if w.cget("bg").lower() in (
                            C["border2"].lower(),
                            C["border"].lower(),
                        ):
                            w.config(bg=C["glow"])
                    except Exception:
                        pass
                for ch in w.winfo_children() if hasattr(w, "winfo_children") else []:
                    _teal_dividers(ch)

            _teal_dividers(self._side_frame)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════
    #  NERV THEME
    # ═══════════════════════════════════════════════════
    def _apply_nerv_theme(self):
        global FM, FMS, FML, FMX
        _nf = next(
            (
                f
                for f in ("Consolas", "Lucida Console", "Courier New")
                if self._font_exists(f)
            ),
            "Courier New",
        )
        FM = (_nf, 9)
        FMS = (_nf, 8)
        FML = (_nf, 10, "bold")
        FMX = (_nf, 13, "bold")
        RED = "#ff0000"
        DKRED = "#660000"
        WHITE = "#f0f0f0"
        try:
            for w in self.root.winfo_children():
                if w.winfo_class() == "Frame":
                    for ch in w.winfo_children():
                        if hasattr(ch, "cget") and "OTERNOS" in str(ch.cget("text")):
                            ch.config(text="N E R V", font=(_nf, 11, "bold"), fg=RED)
                            break
                    break
        except Exception:
            pass
        try:
            for w in self._side_frame.winfo_children():
                for ch in w.winfo_children() if hasattr(w, "winfo_children") else []:
                    if isinstance(ch, tk.Label):
                        t = ch.cget("text")
                        if t == "OTERNOS":
                            ch.config(text="NERV", font=(_nf, 8, "bold"), fg=RED)
                        elif "SYS v" in str(t):
                            ch.config(
                                text="God's In His Heaven", font=(_nf, 6), fg=DKRED
                            )
        except Exception:
            pass
        try:
            for key, btn in self.tab_btns.items():
                btn.config(
                    font=(_nf, 7, "bold"),
                    fg=RED if key == getattr(self, "view", "") else DKRED,
                )
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind("<Enter>", lambda e, w=btn: w.config(fg=RED))
                btn.bind(
                    "<Leave>",
                    lambda e, w=btn, k=key: w.config(
                        fg=RED if k == getattr(self, "view", "") else DKRED
                    ),
                )
        except Exception:
            pass
        try:
            self.now_title.config(font=(_nf, 9, "bold"), fg=WHITE)
            self.now_artist.config(font=(_nf, 8), fg=RED)
            self.now_album.config(font=(_nf, 7), fg=DKRED)
            cur = self.now_title.cget("text")
            if cur and not cur.startswith("[NERV]"):
                self.now_title.config(text="[NERV] " + cur)
        except Exception:
            pass
        try:
            self.prog_cv.config(bg="#0a0000")
            self.prog_cv.itemconfig(self.prog_fill, fill=RED)
            self.prog_cv.itemconfig(self.prog_dot, fill=WHITE)
        except Exception:
            pass
        try:
            for btn in (
                self.btn_shuf,
                self.btn_prev,
                self.btn_play,
                self.btn_next,
                self.btn_repeat,
            ):
                sz = 16 if btn is self.btn_play else 12
                btn.config(font=(_nf, sz), fg=DKRED)
                btn.unbind("<Enter>")
                btn.unbind("<Leave>")
                btn.bind(
                    "<Enter>",
                    lambda e, w=btn: ColorAnim.run(
                        self.root, w, "fg", DKRED, RED, duration_ms=60
                    ),
                )
                btn.bind(
                    "<Leave>",
                    lambda e, w=btn: ColorAnim.run(
                        self.root, w, "fg", RED, DKRED, duration_ms=60
                    ),
                )
        except Exception:
            pass
        try:
            self.track_list.config(
                font=(_nf, 9),
                fg=WHITE,
                selectbackground="#3a0000",
                selectforeground=RED,
            )
        except Exception:
            pass
        try:
            self._viz_mf_cyber.pack_forget()
            self._viz_mf_miku.pack_forget()
            self._viz_mf_nerv.pack(side="right")
            for mode, btn in self._viz_mode_btns.items():
                if mode.startswith("nerv_"):
                    btn.config(font=(_nf, 8, "bold"), bg=C["bg"])
            self._set_viz_mode("nerv_magi")
        except Exception:
            pass
        try:
            self.viz_track_lbl.config(font=(_nf, 8), fg=WHITE)
            self.viz_pos_lbl.config(font=(_nf, 8), fg=DKRED)
            self.viz_mode_lbl.config(font=(_nf, 8), fg=RED)
        except Exception:
            pass

    def _viz_nerv_magi(self, cv, W, H, t, playing, bars):
        import math as _m

        bass = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0
        for fx, fy, fr, fl in [
            (0.06, 0.18, 0.09, True),
            (0.88, 0.09, 0.08, False),
            (0.72, 0.06, 0.07, False),
            (0.04, 0.55, 0.07, False),
            (0.30, 0.85, 0.08, True),
        ]:
            pts = []
            for k in range(6):
                a = k * _m.pi / 3
                pts.extend(
                    [
                        fx * W + fr * min(W, H) * _m.cos(a),
                        fy * H + fr * min(W, H) * _m.sin(a),
                    ]
                )
            bv = int(50 + bass * 140)
            cv.create_polygon(
                pts,
                outline=f"#{bv:02x}0000",
                fill=f"#{bv:02x}0000" if fl else "",
                width=2,
            )
        col_w = W // 3
        for ci, (lbl, seg) in enumerate(
            zip(
                ["MELCHIOR", "BALTHASAR", "CASPER"], [bars[:16], bars[16:32], bars[32:]]
            )
        ):
            seg = seg or [0]
            avg = sum(seg) / len(seg)
            cx0 = ci * col_w
            bv = int(40 + avg * 160)
            hv = int(130 + avg * 120)
            cv.create_rectangle(
                cx0 + 4,
                32,
                cx0 + col_w - 6,
                H - 12,
                outline=f"#{bv:02x}0000",
                fill="",
                width=1,
            )
            cv.create_text(
                cx0 + col_w // 2,
                22,
                text=f"[ {lbl} ]",
                font=("Consolas", max(7, int(W * 0.016))),
                fill=f"#{hv:02x}0000",
                anchor="center",
            )
            n = len(seg)
            bw_ = (col_w - 20) / max(n, 1)
            for i, h in enumerate(seg):
                bh = max(2, h * (H - 80))
                bx = cx0 + 10 + i * bw_
                fv = int(55 + h * 195)
                cv.create_rectangle(
                    bx,
                    H - 30 - bh,
                    bx + bw_ - 1,
                    H - 30,
                    fill=f"#{fv:02x}0000",
                    outline="",
                )
        er = min(W, H) * (0.042 + bass * 0.05)
        ev = int(120 + bass * 130)
        cv.create_oval(
            W // 2 - er,
            H // 2 - er,
            W // 2 + er,
            H // 2 + er,
            outline=f"#{ev:02x}0000",
            fill="",
            width=2,
        )
        cv.create_text(
            W // 2,
            H // 2,
            text="NERV",
            font=("Consolas", max(8, int(er * 0.85))),
            fill=f"#{ev:02x}0000",
            anchor="center",
        )
        msgs = [
            "God's In His Heaven",
            "All's Right With The World",
            "MAGI ONLINE",
            "ANGEL DETECTED",
            "PATTERN: BLUE",
            "SYNC RATE: 400%",
        ]
        mv = int(80 + energy * 100)
        cv.create_text(
            W // 2,
            H * 0.94,
            text=f"// {msgs[(t // 140) % len(msgs)]} //",
            font=("Consolas", max(7, int(W * 0.014))),
            fill=f"#{mv:02x}0000",
            anchor="center",
        )

    def _viz_nerv_angel(self, cv, W, H, t, playing, bars):
        import math as _m

        bass = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0
        cx, cy = W / 2, H / 2
        ang = t * 0.008
        max_r = min(W, H) * 0.44
        for fx, fy, fr, fl in [
            (0.07, 0.12, 0.09, True),
            (0.86, 0.08, 0.08, False),
            (0.06, 0.78, 0.07, False),
            (0.88, 0.80, 0.09, True),
        ]:
            pts = []
            for k in range(6):
                a = ang * 0.25 + k * _m.pi / 3
                pts.extend(
                    [
                        fx * W + fr * min(W, H) * _m.cos(a),
                        fy * H + fr * min(W, H) * _m.sin(a),
                    ]
                )
            bv = int(35 + bass * 90)
            cv.create_polygon(
                pts,
                outline=f"#{bv:02x}0000",
                fill=f"#{bv // 2:02x}0000" if fl else "",
                width=2,
            )
        for ring in range(1, 6):
            frac = ring / 5
            amp = bars[min(len(bars) - 1, int(frac * len(bars)))] if bars else 0
            r = max_r * frac * (0.9 + amp * 0.22)
            rv = int(55 + amp * 200)
            pts = []
            for k in range(6):
                a = ang + k * _m.pi / 3
                pts.extend([cx + r * _m.cos(a), cy + r * _m.sin(a)])
            pts.extend(pts[:2])
            cv.create_line(
                pts, fill=f"#{rv:02x}0000", width=max(1, int(3.5 - ring * 0.5))
            )
        cr = min(W, H) * (0.05 + bass * 0.07)
        fv = int(160 + bass * 90)
        pts = []
        for k in range(6):
            a = ang * 2 + k * _m.pi / 3
            pts.extend([cx + cr * _m.cos(a), cy + cr * _m.sin(a)])
        cv.create_polygon(
            pts, fill=f"#{fv:02x}0000", outline=f"#{min(255, fv + 60):02x}0000", width=2
        )
        cv2 = int(50 + energy * 80)
        for tx, ty, anch, lbl in [
            (8, 8, "nw", "PATTERN: BLUE"),
            (W - 8, 8, "ne", "ANGEL CLASS: ?"),
            (8, H - 8, "sw", "A.T. LVL: MAX"),
            (W - 8, H - 8, "se", "NEUTRALIZE"),
        ]:
            cv.create_text(
                tx,
                ty,
                text=lbl,
                font=("Consolas", max(6, int(W * 0.012))),
                fill=f"#{cv2:02x}0000",
                anchor=anch,
            )

    def _viz_nerv_eva(self, cv, W, H, t, playing, bars):
        import math as _m

        bass = sum(bars[:8]) / 8 if bars else 0
        energy = sum(bars) / len(bars) if bars else 0
        for fx, fy, fr in [
            (0.10, 0.18, 0.07),
            (0.87, 0.14, 0.08),
            (0.09, 0.82, 0.06),
            (0.88, 0.78, 0.07),
        ]:
            pts = []
            for k in range(6):
                a = k * _m.pi / 3
                pts.extend(
                    [
                        fx * W + fr * min(W, H) * _m.cos(a),
                        fy * H + fr * min(W, H) * _m.sin(a),
                    ]
                )
            bv = int(18 + bass * 30)
            cv.create_polygon(pts, outline=f"#{bv:02x}0000", fill="", width=1)
        hv = int(130 + energy * 120)
        cv.create_text(
            W // 2,
            14,
            text="EVA-01  //  UNIT STATUS  //  NERV HQ",
            font=("Consolas", max(7, int(W * 0.016))),
            fill=f"#{hv:02x}0000",
            anchor="center",
        )
        cv.create_line(10, 26, W - 10, 26, fill=f"#{hv // 2:02x}0000", width=1)
        sync = min(1.0, energy * 1.4 + bass * 0.4)
        sy_top = 36
        sy_bot = H - 60
        sy_h = sy_bot - sy_top
        sx0 = 16
        sx1 = 48
        cv.create_rectangle(
            sx0, sy_top, sx1, sy_bot, outline="#550000", fill="", width=1
        )
        sv = int(80 + sync * 170)
        cv.create_rectangle(
            sx0 + 2,
            sy_bot - int(sync * sy_h),
            sx1 - 2,
            sy_bot - 2,
            fill=f"#{sv:02x}0000",
            outline="",
        )
        cv.create_text(
            (sx0 + sx1) // 2,
            sy_top - 8,
            text="SYNC",
            font=("Consolas", max(6, int(W * 0.012))),
            fill="#660000",
            anchor="center",
        )
        cv.create_text(
            (sx0 + sx1) // 2,
            sy_bot + 8,
            text=f"{int(sync * 400)}%",
            font=("Consolas", max(6, int(W * 0.013))),
            fill=f"#{sv:02x}0000",
            anchor="center",
        )
        batt = max(0.0, 1.0 - (t % 600) / 600.0) if playing else 1.0
        bx0 = W - 50
        bx1 = W - 18
        cv.create_rectangle(
            bx0, sy_top, bx1, sy_bot, outline="#550000", fill="", width=1
        )
        bv2 = int(200 * batt)
        cv.create_rectangle(
            bx0 + 2,
            sy_bot - int(batt * sy_h),
            bx1 - 2,
            sy_bot - 2,
            fill=f"#{bv2:02x}0000",
            outline="",
        )
        cv.create_text(
            (bx0 + bx1) // 2,
            sy_top - 8,
            text="PWR",
            font=("Consolas", max(6, int(W * 0.012))),
            fill="#660000",
            anchor="center",
        )
        cv.create_text(
            (bx0 + bx1) // 2,
            sy_bot + 8,
            text=f"{int(batt * 100)}%",
            font=("Consolas", max(6, int(W * 0.013))),
            fill=f"#{bv2:02x}0000",
            anchor="center",
        )
        n = len(bars)
        bw_ = (W - 120) / max(n, 1)
        for i, h in enumerate(bars):
            bh = max(1, h * (H - 100) * 0.68)
            fv = int(50 + h * 200)
            cv.create_rectangle(
                60 + i * bw_,
                H - 60 - bh,
                60 + (i + 1) * bw_ - 1,
                H - 60,
                fill=f"#{fv:02x}0000",
                outline="",
            )
        for si, line in enumerate(
            [
                "PILOT: IKARI SHINJI",
                f"A.T. FIELD: {'ACTIVE' if bass > 0.3 else 'STANDBY'}",
                f"THREAT: {'CRITICAL' if energy > 0.7 else 'NOMINAL'}",
                f"CORE TEMP: {int(20 + energy * 80)}°C",
            ]
        ):
            lv = int(55 + energy * 90)
            hot = any(x in line for x in ("CRITICAL", "ACTIVE"))
            cv.create_text(
                W // 2,
                H - 52 + si * 13,
                text=line,
                font=("Consolas", max(6, int(W * 0.013))),
                fill=f"#{min(255, lv + 60):02x}0000" if hot else f"#{lv:02x}0000",
                anchor="center",
            )
        if bass > 0.6 and (t // 8) % 2 == 0:
            cv.create_rectangle(
                0,
                0,
                W,
                H,
                outline=f"#{min(255, int(bass * 200) + 60):02x}0000",
                fill="",
                width=3,
            )
            cv.create_text(
                W // 2,
                H // 2 - 20,
                text="⚠  ANGEL ALERT  ⚠",
                font=("Consolas", max(10, int(W * 0.025))),
                fill="#ff0000",
                anchor="center",
            )

    # ══════════════════════════════════════
    #  COMMAND PALETTE
    # ══════════════════════════════════════

    # ══════════════════════════════════════════════════════
    #  AUTO-PLAYLIST FROM SEED TRACK
    # ══════════════════════════════════════════════════════
    def _open_auto_playlist(self):
        idx = self.current_idx
        if idx < 0 or idx >= len(self.library):
            self._set_status("PLAY A TRACK FIRST")
            return
        seed = self.library[idx]
        win = tk.Toplevel(self.root)
        content, _close = self._popup_setup(win, "SYS::AUTO-PLAYLIST", w=520, h=460)

        tk.Label(content, text="AUTO-PLAYLIST", font=FMX, fg=C["white"], bg=C["bg"]).pack(pady=(12, 2), anchor="w", padx=20)
        tk.Label(content, text=f"Seed: {seed['title']} — {seed.get('artist', '')}", font=FMS, fg=C["glow"], bg=C["bg"]).pack(anchor="w", padx=20)
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=20, pady=6)
        lf = tk.Frame(content, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=12, pady=4)
        sb = tk.Scrollbar(lf, bg=C["panel"], troughcolor=C["bg"], activebackground=C["border2"], width=8)
        sb.pack(side="right", fill="y")
        lb = tk.Listbox(lf, bg=C["bg"], fg=C["white2"], font=FM, selectbackground=C["select"],
                        relief="flat", bd=0, highlightthickness=0, yscrollcommand=sb.set)
        lb.pack(fill="both", expand=True)
        sb.config(command=lb.yview)
        seed_path = seed["path"]
        seed_bpm = self._bpm_cache.get(seed_path, 0)
        seed_mood = self._mood_cache.get(seed_path, "")
        scored = []
        for i, t in enumerate(self.library):
            if i == idx:
                continue
            p = t.get("path", "")
            bpm = self._bpm_cache.get(p, 0)
            mood = self._mood_cache.get(p, "")
            score = 0
            if seed_bpm and bpm:
                score += max(0, 30 - abs(bpm - seed_bpm))
            if mood and mood == seed_mood:
                score += 25
            score += min(10, sum(1 for e in self._history if e.get("title") == t.get("title", "")) * 2)
            score -= self._skip_counts.get(p, 0) * 8
            scored.append((score, i, t))
        scored.sort(key=lambda x: -x[0])
        result_indices = [i for _, i, _ in scored[:30]]
        for _, _, t in scored[:30]:
            lb.insert("end", f"  {t['title'][:42]}  —  {t.get('artist', '')[:22]}")

        def _load():
            self.queue = [idx] + result_indices
            self.queue_pos = 0
            self._play_item(0)
            self._set_status(f"AUTO-PLAYLIST: {len(result_indices) + 1} TRACKS")
            self._popup_fadeout(win)

        play_btn = tk.Label(content, text="▶  PLAY THIS PLAYLIST", font=FM, fg=C["white3"],
                            bg=C["panel"], cursor="hand2", pady=6)
        play_btn.pack(padx=20, pady=8, fill="x")
        play_btn.bind("<Button-1>", lambda e: _load())
        play_btn.bind("<Enter>", lambda e: ColorAnim.run(self.root, play_btn, "fg", C["white3"], C["white"], duration_ms=60))
        play_btn.bind("<Leave>", lambda e: ColorAnim.run(self.root, play_btn, "fg", C["white"], C["white3"], duration_ms=60))

    # ══════════════════════════════════════════════════════
    #  FLOW MODE
    # ══════════════════════════════════════════════════════
    def _toggle_flow_mode(self):
        self._flow_mode = not self._flow_mode
        self._set_status("🌊 FLOW MODE ON" if self._flow_mode else "🌊 FLOW MODE OFF")

    def _flow_enqueue(self, current_track):
        if len(self.queue) - self.queue_pos > 3:
            return
        path = current_track.get("path", "")
        cur_bpm = self._bpm_cache.get(path, 0)
        cur_mood = self._mood_cache.get(path, "")
        in_queue = set(self.queue)
        scored = []
        for i, t in enumerate(self.library):
            if i in in_queue:
                continue
            p = t.get("path", "")
            bpm = self._bpm_cache.get(p, 0)
            mood = self._mood_cache.get(p, "")
            score = 0
            if cur_bpm and bpm:
                score += max(0, 20 - abs(bpm - cur_bpm))
            if mood == cur_mood:
                score += 20
            score += random.randint(0, 8) - self._skip_counts.get(p, 0) * 8
            scored.append((score, i))
        scored.sort(key=lambda x: -x[0])
        adds = [i for _, i in scored[:3]]
        self.queue.extend(adds)
        if adds:
            self._set_status(f"FLOW: +{len(adds)} QUEUED")

    # ══════════════════════════════════════════════════════
    #  SMART SKIP
    # ══════════════════════════════════════════════════════
    def _toggle_smart_skip(self):
        self._smart_skip_on = not self._smart_skip_on
        self._set_status(
            "⚡ SMART SKIP ON" if self._smart_skip_on else "⚡ SMART SKIP OFF"
        )

    # ══════════════════════════════════════════════════════
    #  VOICE COMMANDS
    # ══════════════════════════════════════════════════════
    def _toggle_voice_control(self):
        self._voice_on = not self._voice_on
        if self._voice_on:
            self._set_status("🎙 VOICE ON")
            self._start_voice_thread()
        else:
            self._set_status("🎙 VOICE OFF")

    def _start_voice_thread(self):
        def _listen():
            try:
                import subprocess

                ps = (
                    "Add-Type -AssemblyName System.Speech;"
                    "$r=New-Object System.Speech.Recognition.SpeechRecognitionEngine;"
                    "$r.SetInputToDefaultAudioDevice();"
                    "$c=New-Object System.Speech.Recognition.Choices;"
                    '@("skip","next","previous","pause","play","louder","softer","shuffle","stop","ambient","repeat","flow mode") | ForEach-Object { $c.Add($_) };'
                    "$g=New-Object System.Speech.Recognition.GrammarBuilder($c);"
                    "$gr=New-Object System.Speech.Recognition.Grammar($g);"
                    "$r.LoadGrammar($gr);"
                    "while($true){try{$res=$r.Recognize([timespan]::FromSeconds(5));if($res){Write-Output $res.Text}}catch{}}"
                )
                proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command", ps],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    creationflags=0x08000000,
                )
                while self._voice_on:
                    line = (
                        proc.stdout.readline().decode(errors="ignore").strip().lower()
                    )
                    if line:
                        self.root.after(0, lambda l=line: self._handle_voice(l))
                proc.terminate()
            except Exception:
                self.root.after(0, lambda: self._set_status("🎙 VOICE: UNAVAILABLE"))

        threading.Thread(target=_listen, daemon=True).start()

    def _handle_voice(self, cmd):
        self._set_status(f"🎙 {cmd.upper()}")
        if cmd in ("skip", "next"):
            self._next()
        elif cmd == "previous":
            self._prev()
        elif cmd in ("pause", "play"):
            self._toggle_play()
        elif cmd == "louder":
            self.volume = min(1.0, self.volume + 0.1)
            self._upd_vol()
        elif cmd == "softer":
            self.volume = max(0.0, self.volume - 0.1)
            self._upd_vol()
        elif cmd == "shuffle":
            self._toggle_shuffle()
        elif cmd == "stop":
            self.engine.stop()
        elif cmd == "ambient":
            self._open_ambient_mode()
        elif cmd == "repeat":
            self._toggle_repeat()
        elif "flow" in cmd:
            self._toggle_flow_mode()

    # ══════════════════════════════════════════════════════
    #  MINI LYRICS TICKER
    # ══════════════════════════════════════════════════════
    def _start_lyric_ticker(self):
        """Reset the lyric ticker state. The actual tick is driven by _poll →
        _sync_lyric_ticker every 100ms, so no job scheduling needed here."""
        if self._lyric_ticker_job:
            try:
                self.root.after_cancel(self._lyric_ticker_job)
            except:
                pass
        self._lyric_ticker_job = None
        # Clear the ticker text so it doesn't show stale lyrics from the previous track
        try:
            self.lyric_ticker_lbl.config(text="")
        except:
            pass

    def _sync_lyric_ticker(self):
        if not hasattr(self, "lyric_ticker_lbl"):
            return
        # Use live now-playing labels so ticker works for library, YT, SC, and Spotify
        title = self.now_title.cget("text").replace("…", "").strip()
        artist = self.now_artist.cget("text").strip()
        if not title or title == "— NO TRACK —":
            try:
                self.lyric_ticker_lbl.config(text="")
            except:
                pass
            return
        key = (artist.lower().strip(), title.lower().strip())
        synced = self._synced_cache.get(key)
        if not synced:
            try:
                self.lyric_ticker_lbl.config(text="")
            except:
                pass
            return
        pos_ms = self._get_pos_ms()
        cur_line = ""
        for ms, text in synced:
            if ms <= pos_ms:
                cur_line = text
            else:
                break
        try:
            self.lyric_ticker_lbl.config(text=f"♪  {cur_line}" if cur_line else "")
        except:
            pass

    # ══════════════════════════════════════════════════════
    #  AMBIENT MODE
    # ══════════════════════════════════════════════════════
    def _open_ambient_mode(self):
        if self._ambient_win and self._ambient_win.winfo_exists():
            self._ambient_win.destroy()
            self._ambient_win = None
            return
        win = tk.Toplevel(self.root)
        win.title("AMBIENT")
        win.configure(bg="#000000")
        win.attributes("-fullscreen", True)
        win.wm_attributes("-topmost", True)
        self._ambient_win = win
        cv = tk.Canvas(win, bg="#000000", highlightthickness=0)
        cv.pack(fill="both", expand=True)
        win.bind(
            "<Escape>", lambda e: (win.destroy(), setattr(self, "_ambient_win", None))
        )
        cv.bind(
            "<Button-1>", lambda e: (win.destroy(), setattr(self, "_ambient_win", None))
        )
        self._ambient_cv = cv
        self._ambient_t = 0

        # Pre-generate static noise field for CRT texture (reused every frame)
        self._ambient_noise = []
        import random as _rnd

        for _ in range(320):
            self._ambient_noise.append(
                (
                    _rnd.randint(0, 1920),
                    _rnd.randint(0, 1080),
                    _rnd.randint(1, 3),
                    _rnd.uniform(0.01, 0.06),
                )
            )

        # Pre-generate floating hex glyph positions
        self._ambient_glyphs = []
        HEX_CHARS = "0123456789ABCDEF◈◉○●□■▪▫▸▹△▽◇◆"
        for _ in range(55):
            self._ambient_glyphs.append(
                {
                    "x": _rnd.uniform(0.02, 0.98),
                    "y": _rnd.uniform(0.05, 0.92),
                    "char": _rnd.choice(HEX_CHARS),
                    "speed": _rnd.uniform(0.00008, 0.00025),
                    "phase": _rnd.uniform(0, math.pi * 2),
                    "size": _rnd.choice([7, 8, 9, 10]),
                }
            )

        self._ambient_tick()

    def _ambient_tick(self):
        if not (self._ambient_win and self._ambient_win.winfo_exists()):
            return
        cv = self._ambient_cv
        cv.delete("all")
        W = cv.winfo_width() or 1920
        H = cv.winfo_height() or 1080
        t = self._ambient_t

        # ── Background void ──────────────────────────────────────────────────
        cv.configure(bg="#000000")

        # ── CRT scanlines (every 3px, very subtle) ───────────────────────────
        for yy in range(0, H, 3):
            cv.create_line(0, yy, W, yy, fill="#060606", width=1)

        # ── Floating hex glyphs — drift vertically, fade in/out ──────────────
        for g in self._ambient_glyphs:
            gy = (g["y"] + t * g["speed"]) % 1.0
            alpha_t = math.sin(t * 0.012 + g["phase"])
            # Map to brightness: 0.02–0.10 range (very dim)
            bright = int((0.06 + 0.04 * alpha_t) * 255)
            col = f"#{bright:02x}{bright:02x}{bright:02x}"
            cv.create_text(
                int(g["x"] * W),
                int(gy * H),
                text=g["char"],
                font=("Courier New", g["size"]),
                fill=col,
                anchor="center",
            )

        # ── Subtle vignette border ────────────────────────────────────────────
        vpad = 60
        for i in range(6):
            alpha = int(18 - i * 2)
            col = f"#{alpha:02x}{alpha:02x}{alpha:02x}"
            cv.create_rectangle(
                i * vpad // 6,
                i * vpad // 6,
                W - i * vpad // 6,
                H - i * vpad // 6,
                outline=col,
                fill="",
                width=vpad // 6,
            )

        # ── Track info ───────────────────────────────────────────────────────
        idx = self.current_idx
        if 0 <= idx < len(self.library):
            tr = self.library[idx]
            title = tr.get("title", "")
            artist = tr.get("artist", "")
        elif self._sp_mode:
            title = self.now_title.cget("text")
            artist = self.now_artist.cget("text")
            tr = {}
        else:
            title = "OTERNOS  P L A Y E R"
            artist = ""
            tr = {}

        # Breathing scale on title
        breath = 1.0 + 0.018 * math.sin(t * 0.025)
        title_fs = max(28, int(W * 0.034 * breath))
        artist_fs = max(14, int(title_fs * 0.46))

        # ── System prefix line ───────────────────────────────────────────────
        cv.create_text(
            W // 2,
            H * 0.36,
            text="[ OTERNOS  //  AMBIENT ]",
            font=("Courier New", 9),
            fill="#1e1e1e",
            anchor="center",
        )

        # ── Thin horizontal rule above title ─────────────────────────────────
        rule_y = H * 0.415
        rule_w = min(W * 0.55, 700)
        cv.create_line(
            W // 2 - rule_w // 2,
            rule_y,
            W // 2 + rule_w // 2,
            rule_y,
            fill="#1c1c1c",
            width=1,
        )
        cv.create_line(
            W // 2 - rule_w // 2,
            rule_y + 3,
            W // 2 + rule_w // 2,
            rule_y + 3,
            fill="#0e0e0e",
            width=1,
        )

        # ── Title — white glow with dim shadow ───────────────────────────────
        # Shadow
        cv.create_text(
            W // 2 + 2,
            H * 0.47 + 2,
            text=title[:52],
            font=("Courier New", title_fs, "bold"),
            fill="#0a0a0a",
            anchor="center",
        )
        # Main text
        cv.create_text(
            W // 2,
            H * 0.47,
            text=title[:52],
            font=("Courier New", title_fs, "bold"),
            fill="#e8e8e8",
            anchor="center",
        )

        # ── Artist — dimmer, tracked spacing ─────────────────────────────────
        if artist:
            spaced = "  ".join(artist.upper()[:36])
            cv.create_text(
                W // 2,
                H * 0.47 + title_fs + 22,
                text=spaced,
                font=("Courier New", artist_fs),
                fill="#383838",
                anchor="center",
            )

        # ── Thin rule below artist ────────────────────────────────────────────
        below_rule_y = H * 0.47 + title_fs + 22 + artist_fs + 14
        cv.create_line(
            W // 2 - rule_w // 2,
            below_rule_y,
            W // 2 + rule_w // 2,
            below_rule_y,
            fill="#141414",
            width=1,
        )

        # ── Synced lyric line ─────────────────────────────────────────────────
        key = (
            tr.get("artist", "").lower().strip(),
            tr.get("title", "").lower().strip(),
        )
        synced = self._synced_cache.get(key)
        if synced and (self.engine.is_playing or self._sp_playing):
            if self._sp_mode and self._sp_dur_ms > 0:
                pos_ms = self._sp_pos_ms
            else:
                pos_ms = int(self.engine.get_position() * 1000)
            cur_line = ""
            for ms, line in synced:
                if ms <= pos_ms:
                    cur_line = line
                else:
                    break
            if cur_line:
                lyric_y = below_rule_y + 38
                cv.create_text(
                    W // 2,
                    lyric_y,
                    text=cur_line[:80],
                    font=("Courier New", max(13, int(W * 0.016))),
                    fill="#2a2a2a",
                    anchor="center",
                )

        # ── Progress bar — slim, monochrome, Signalis-style ──────────────────
        if self._sp_mode and self._sp_dur_ms > 0:
            dur = self._sp_dur_ms / 1000.0
            pos = self._sp_pos_ms / 1000.0
        else:
            dur = self.engine.duration
            pos = (
                self.engine.get_position()
                if self.engine.is_playing
                else getattr(self.engine, "_pos_cache", 0)
            )
        r_prog = min(1.0, pos / dur) if dur > 0 else 0

        bar_w = W * 0.52
        bar_x = (W - bar_w) / 2
        bar_y = H - 54
        # Track bg
        cv.create_rectangle(
            bar_x, bar_y, bar_x + bar_w, bar_y + 2, fill="#111111", outline=""
        )
        # Fill — white, no color
        if r_prog > 0:
            cv.create_rectangle(
                bar_x,
                bar_y,
                bar_x + bar_w * r_prog,
                bar_y + 2,
                fill="#2e2e2e",
                outline="",
            )
        # Playhead dot
        px = bar_x + bar_w * r_prog
        cv.create_rectangle(
            px - 3, bar_y - 2, px + 3, bar_y + 4, fill="#484848", outline=""
        )

        # Time readout
        def _fmt(s):
            m, s2 = divmod(int(max(0, s)), 60)
            return f"{m}:{s2:02d}"

        cv.create_text(
            bar_x - 10,
            bar_y + 1,
            text=_fmt(pos),
            font=("Courier New", 8),
            fill="#1e1e1e",
            anchor="e",
        )
        cv.create_text(
            bar_x + bar_w + 10,
            bar_y + 1,
            text=_fmt(dur),
            font=("Courier New", 8),
            fill="#1e1e1e",
            anchor="w",
        )

        # ── Clock — bottom right, very dim ───────────────────────────────────
        import time as _ti

        cv.create_text(
            W - 32,
            H - 22,
            text=_ti.strftime("%H:%M"),
            font=("Courier New", 11),
            fill="#1a1a1a",
            anchor="se",
        )

        # ── System status string — bottom left ───────────────────────────────
        playing_sym = "▶" if (self.engine.is_playing or self._sp_playing) else "⏸"
        cv.create_text(
            32,
            H - 22,
            text=f"{playing_sym}  SYS::AMBIENT  //  ESC to exit",
            font=("Courier New", 8),
            fill="#161616",
            anchor="sw",
        )

        self._ambient_t += 1
        cv.after(50, self._ambient_tick)

    # ══════════════════════════════════════════════════════
    #  CONTEXT-AWARE SIDEBAR
    # ══════════════════════════════════════════════════════
    def _update_context_sidebar(self, track):
        if not hasattr(self, "_ctx_frame"):
            return
        for w in self._ctx_frame.winfo_children():
            w.destroy()
        if not track:
            return
        tk.Label(
            self._ctx_frame,
            text="NOW PLAYING",
            font=("Courier New", 8),
            fg=C["white3"],
            bg=C["panel"],
        ).pack(anchor="w", padx=8, pady=(4, 0))
        path = track.get("path", "")
        bpm = self._bpm_cache.get(path, 0)
        mood = self._mood_cache.get(path, "")
        skips = self._skip_counts.get(path, 0)
        gain_db = track.get("gain_db", None)
        gain_str = f"GAIN: {gain_db:+.1f}dB" if gain_db is not None else ""
        for text, val in [
            (f"◈ {int(bpm)} BPM" if bpm else "◈ analyzing…", C["glow"]),
            (mood if mood else "", C["white2"]),
            (gain_str, C["white3"]),
            (f"⏭ skipped {skips}×" if skips else "", C["white3"]),
        ]:
            if text:
                tk.Label(
                    self._ctx_frame,
                    text=f"  {text}",
                    font=("Courier New", 7),
                    fg=val,
                    bg=C["panel"],
                ).pack(anchor="w", padx=8)
        artist = track.get("artist", "").lower()
        similar = [
            t
            for t in self.library
            if t.get("artist", "").lower() == artist
            and t.get("title", "") != track.get("title", "")
        ][:4]
        if similar:
            tk.Label(
                self._ctx_frame,
                text="MORE BY ARTIST",
                font=("Courier New", 8),
                fg=C["white3"],
                bg=C["panel"],
            ).pack(anchor="w", padx=8, pady=(6, 0))
            for st in similar:
                lbl = tk.Label(
                    self._ctx_frame,
                    text=f"  {st['title'][:22]}",
                    font=("Courier New", 7),
                    fg=C["white3"],
                    bg=C["panel"],
                    cursor="hand2",
                    anchor="w",
                )
                lbl.pack(fill="x")

                def _ps(e, t=st):
                    i = next((j for j, x in enumerate(self.library) if x is t), -1)
                    if i >= 0:
                        self.queue = [i]
                        self.queue_pos = 0
                        self._play_item(0)

                lbl.bind("<Button-1>", _ps)
                lbl.bind("<Enter>", lambda e, w=lbl: w.config(fg=C["white"]))
                lbl.bind("<Leave>", lambda e, w=lbl: w.config(fg=C["white3"]))

    # ══════════════════════════════════════════════════════
    #  SMART FOLDERS
    # ══════════════════════════════════════════════════════
    def _open_smart_folders(self):
        win = tk.Toplevel(self.root)
        content, _close = self._popup_setup(win, "SYS::SMART FOLDERS", w=640, h=540)

        tk.Label(content, text="SMART FOLDERS", font=FMX, fg=C["white"], bg=C["bg"]).pack(pady=(12, 4), anchor="w", padx=20)
        tk.Label(content, text="Auto-populated folders based on rules", font=FMS, fg=C["white3"], bg=C["bg"]).pack(anchor="w", padx=20)
        tk.Frame(content, bg=C["border"], height=1).pack(fill="x", padx=20, pady=6)
        folders = [
            ("⚡ High Energy", lambda t: self._mood_cache.get(t.get("path", ""), "") in ("⚡ EUPHORIC", "🔥 ENERGETIC")),
            ("🌙 Late Night",  lambda t: self._mood_cache.get(t.get("path", ""), "") in ("🌙 CHILL", "💤 MELLOW")),
            ("🔥 Fast >130 BPM", lambda t: self._bpm_cache.get(t.get("path", ""), 0) > 130),
            ("💤 Slow <80 BPM",  lambda t: 0 < self._bpm_cache.get(t.get("path", ""), 0) < 80),
            ("⭐ Most Played",   lambda t: sum(1 for e in self._history if e.get("title") == t.get("title", "")) >= 3),
            ("⏭ Never Skipped", lambda t: self._skip_counts.get(t.get("path", ""), 0) == 0 and t.get("duration", 0) > 60),
            ("🆕 Recently Added", lambda t: self.library.index(t) >= max(0, len(self.library) - 50)),
        ]
        nb = tk.Frame(content, bg=C["bg"])
        nb.pack(fill="x", padx=20, pady=(0, 4))
        ca = tk.Frame(content, bg=C["bg"])
        ca.pack(fill="both", expand=True, padx=12, pady=4)

        def _show(name, rule):
            for w in ca.winfo_children():
                w.destroy()
            matches = [t for t in self.library if rule(t)]
            tk.Label(ca, text=f"{name}  ({len(matches)} tracks)", font=FM, fg=C["glow"], bg=C["bg"]).pack(anchor="w", padx=8, pady=(4, 2))
            lf2 = tk.Frame(ca, bg=C["bg"])
            lf2.pack(fill="both", expand=True)
            sb2 = tk.Scrollbar(lf2, bg=C["panel"], troughcolor=C["bg"], width=8)
            sb2.pack(side="right", fill="y")
            lb2 = tk.Listbox(lf2, bg=C["bg"], fg=C["white2"], font=FM, selectbackground=C["select"],
                             relief="flat", bd=0, highlightthickness=0, yscrollcommand=sb2.set)
            lb2.pack(fill="both", expand=True)
            sb2.config(command=lb2.yview)
            idxs = []
            for t in matches:
                lb2.insert("end", f"  {t['title'][:42]}  —  {t.get('artist', '')[:22]}")
                try:
                    idxs.append(self.library.index(t))
                except:
                    pass

            def _pa():
                if idxs:
                    self.queue = list(idxs)
                    self.queue_pos = 0
                    self._play_item(0)
                    self._set_status(f"PLAYING: {name}")

            pb = tk.Label(ca, text=f"▶  PLAY ALL ({len(matches)})", font=FM, fg=C["white3"],
                          bg=C["panel"], cursor="hand2", pady=4)
            pb.pack(padx=8, pady=6, fill="x")
            pb.bind("<Button-1>", lambda e: _pa())
            pb.bind("<Enter>", lambda e: ColorAnim.run(self.root, pb, "fg", C["white3"], C["white"], duration_ms=60))
            pb.bind("<Leave>", lambda e: ColorAnim.run(self.root, pb, "fg", C["white"], C["white3"], duration_ms=60))

        for name, rule in folders:
            b = tk.Label(nb, text=name, font=FMS, fg=C["white3"], bg=C["panel"],
                         cursor="hand2", padx=6, pady=3)
            b.pack(side="left", padx=2, pady=2)
            b.bind("<Button-1>", lambda e, n=name, r=rule: _show(n, r))
            b.bind("<Enter>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white3"], C["white"], duration_ms=60))
            b.bind("<Leave>", lambda e, w=b: ColorAnim.run(self.root, w, "fg", C["white"], C["white3"], duration_ms=60))
        if folders:
            _show(*folders[0])

    def _open_palette(self):
        if self._palette_win and self._palette_win.winfo_exists():
            self._palette_win.focus()
            return

        win = tk.Toplevel(self.root)
        win.title("")
        win.configure(bg=C["bg"])
        win.overrideredirect(True)
        win.wm_attributes("-topmost", True)
        # Centre over main window
        rw = self.root.winfo_width()
        rh = self.root.winfo_height()
        rx = self.root.winfo_x()
        ry = self.root.winfo_y()
        pw, ph = 480, 340
        win.geometry(f"{pw}x{ph}+{rx + rw // 2 - pw // 2}+{ry + rh // 4}")
        self._palette_win = win
        self._popup_fadein(win, duration_ms=80)
        outer = tk.Frame(win, bg=C["glow"], padx=1, pady=1)
        outer.pack(fill="both", expand=True)
        inner = tk.Frame(outer, bg=C["bg"])
        inner.pack(fill="both", expand=True)

        # Search input
        tk.Label(
            inner, text="⌨  COMMAND PALETTE", font=FMS, fg=C["white3"], bg=C["bg"]
        ).pack(anchor="w", padx=14, pady=(10, 4))
        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=0)

        search_var = tk.StringVar()
        entry = tk.Entry(
            inner,
            textvariable=search_var,
            font=FML,
            bg=C["panel"],
            fg=C["white"],
            insertbackground=C["glow"],
            relief="flat",
            bd=0,
            highlightthickness=0,
        )
        entry.pack(fill="x", padx=16, pady=(10, 6), ipady=6)
        entry.focus_set()

        # Results list
        results_frame = tk.Frame(inner, bg=C["bg"])
        results_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Build command registry
        COMMANDS = [
            ("▶ Play / Pause", self._toggle_play),
            ("⏭ Next track", self._next),
            ("⏮ Previous track", self._prev),
            ("◈ All Tracks", lambda: self._switch_view("library")),
            ("◈ Queue", lambda: self._switch_view("queue")),
            ("◈ Visualizer", lambda: self._switch_view("visualizer")),
            ("◈ Lyrics", lambda: self._switch_view("lyrics")),
            ("◈ History", lambda: self._switch_view("history")),
            ("◈ Spotify", lambda: self._switch_view("spotify")),
            ("◈ YouTube", lambda: self._switch_view("youtube")),
            ("⊡ Mini Player", self._toggle_mini_player),
            ("⏾ Sleep Timer", self._open_sleep_timer),
            ("✎ Edit Tags", lambda: self._open_tag_editor(self.current_idx)),
            ("⊹ Add Bookmark", self._add_bookmark),
            ("⊗ View Bookmarks", self._open_bookmarks),
            ("⇌ Toggle Shuffle", self._toggle_shuffle),
            ("↺ Toggle Repeat", self._toggle_repeat),
            ("⊞ Find Duplicates", self._open_duplicate_detector),
            ("↗ Export M3U", self._export_playlist_m3u),
            ("◫ Smart Playlist", self._open_smart_playlist),
            ("⧗ Watch Folders", self._open_watch_dirs),
            ("★ Recommendations", self._open_recommendations),
            ("🎨 Theme Editor", self._open_theme_editor),
            ("⌨ Hotkeys", self._open_hotkey_editor),
            ("⚙ Settings", self._open_settings),
            ("A-B Set A", self._ab_set_a),
            ("A-B Set B", self._ab_set_b),
            ("A-B Clear", self._ab_clear),
            ("Speed cycle", self._cycle_speed),
            ("🎙 Voice Control", self._toggle_voice_control),
            ("🌊 Flow Mode", self._toggle_flow_mode),
            ("⚡ Smart Skip", self._toggle_smart_skip),
            ("🌌 Ambient Mode", self._open_ambient_mode),
            ("🎵 Auto-Playlist", self._open_auto_playlist),
            ("📁 Smart Folders", self._open_smart_folders),
        ]
        # Add playlist entries dynamically
        for pl_name in list(self.playlists.keys())[:20]:
            name = pl_name
            COMMANDS.append(
                (f"♦ Playlist: {name}", lambda n=name: self._load_playlist(n))
            )

        _selected = [0]

        def _refresh(q=""):
            for w in results_frame.winfo_children():
                w.destroy()
            result_btns.clear()
            _selected[0] = 0
            q = q.lower().strip()
            shown = [(lbl, cmd) for lbl, cmd in COMMANDS if not q or q in lbl.lower()][:12]
            for i, (lbl, cmd) in enumerate(shown):
                bg = C["select2"] if i == _selected[0] else C["bg"]
                row = tk.Frame(results_frame, bg=bg, cursor="hand2")
                row.pack(fill="x")
                tk.Label(
                    row, text=lbl, font=FM, fg=C["white"], bg=bg,
                    anchor="w", padx=16, pady=5,
                ).pack(fill="x")

                def _run(c=cmd):
                    self._popup_fadeout(win)
                    self._palette_win = None
                    self.root.after(90, c)

                for w in (row,) + tuple(row.winfo_children()):
                    w.bind("<Button-1>", lambda e, f=_run: f())
                    w.bind("<Enter>", lambda e, r=row, idx=i: _highlight(idx))
                    w.bind("<Leave>", lambda e, r=row, b=bg, idx=i: None)
                result_btns.append((row, cmd))

        def _highlight(idx):
            _selected[0] = idx
            for j, (row, _) in enumerate(result_btns):
                row.config(bg=C["select2"] if j == idx else C["bg"])
                for child in row.winfo_children():
                    child.config(bg=C["select2"] if j == idx else C["bg"])

        search_var.trace_add("write", lambda *a: _refresh(search_var.get()))
        _refresh()

        def _close_palette():
            self._popup_fadeout(win)
            self._palette_win = None

        def _key(e):
            if e.keysym == "Escape":
                _close_palette()
            elif e.keysym == "Return" and result_btns:
                _, cmd = result_btns[_selected[0]]
                _close_palette()
                cmd()
            elif e.keysym == "Down":
                _highlight(min(_selected[0] + 1, len(result_btns) - 1))
            elif e.keysym == "Up":
                _highlight(max(_selected[0] - 1, 0))

        entry.bind("<KeyPress>", _key)

        def _on_focus_out(e):
            win.after(150, lambda: _close_palette() if win.winfo_exists() else None)

        win.bind("<FocusOut>", _on_focus_out)

    # ══════════════════════════════════════
    #  ALBUM VIEW
    # ══════════════════════════════════════
    def _build_album_view(self):
        self.album_frame = tk.Frame(self.content, bg=C["bg"])

        hdr = tk.Frame(self.album_frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(16, 0))
        self._alb_hdr_lbl = tk.Label(
            hdr, text="ALBUMS", font=FMX, fg=C["white"], bg=C["bg"]
        )
        self._alb_hdr_lbl.pack(side="left")
        self._alb_back_btn = tk.Label(
            hdr, text="← BACK", font=FM, fg=C["white3"], bg=C["bg"], cursor="hand2"
        )
        self._alb_back_btn.pack(side="left", padx=(16, 0))
        self._alb_back_btn.pack_forget()
        self._alb_back_btn.bind("<Button-1>", lambda e: self._alb_show_grid())
        self._alb_back_btn.bind(
            "<Enter>", lambda e: self._alb_back_btn.config(fg=C["white"])
        )
        self._alb_back_btn.bind(
            "<Leave>", lambda e: self._alb_back_btn.config(fg=C["white3"])
        )

        tk.Frame(self.album_frame, bg=C["border"], height=1).pack(
            fill="x", padx=20, pady=(8, 0)
        )

        lf = tk.Frame(self.album_frame, bg=C["bg"])
        lf.pack(fill="both", expand=True)
        sb = tk.Scrollbar(
            lf, bg=C["panel"], troughcolor=C["bg"], width=6, bd=0, highlightthickness=0
        )
        sb.pack(side="right", fill="y")
        self._alb_cv = tk.Canvas(
            lf, bg=C["bg"], highlightthickness=0, yscrollcommand=sb.set
        )
        self._alb_cv.pack(side="left", fill="both", expand=True)
        sb.config(command=self._alb_cv.yview)
        self._alb_inner = tk.Frame(self._alb_cv, bg=C["bg"])
        self._alb_win = self._alb_cv.create_window(
            0, 0, anchor="nw", window=self._alb_inner
        )
        self._alb_inner.bind(
            "<Configure>",
            lambda e: self._alb_cv.configure(scrollregion=self._alb_cv.bbox("all")),
        )
        self._alb_cv.bind(
            "<Configure>",
            lambda e: self._alb_cv.itemconfig(self._alb_win, width=e.width),
        )
        self._alb_cv.bind(
            "<MouseWheel>",
            lambda e: self._alb_cv.yview_scroll(-3 if e.delta > 0 else 3, "units"),
        )
        self._alb_ctx = tk.Menu(
            self.root,
            tearoff=0,
            bg=C["panel"],
            fg=C["white"],
            activebackground=C["select"],
            activeforeground=C["glow"],
            font=FM,
            bd=0,
        )

    def _refresh_album_view(self):
        for w in self._alb_inner.winfo_children():
            w.destroy()
        self._alb_show_grid()

    def _alb_show_grid(self):
        for w in self._alb_inner.winfo_children():
            w.destroy()
        self._alb_hdr_lbl.config(text="ALBUMS")
        self._alb_back_btn.pack_forget()

        from collections import defaultdict

        albums = defaultdict(list)
        for i, t in enumerate(self.library):
            al = t.get("album", "") or "Unknown Album"
            albums[al].append(i)

        if not albums:
            tk.Label(
                self._alb_inner,
                text="No albums in library.",
                font=FM,
                fg=C["white3"],
                bg=C["bg"],
            ).pack(pady=40)
            return

        COLS = 4
        CELL_W = 152
        CELL_H = 182

        def _sort_key(item):
            name = item[0]
            meta = getattr(self, "_album_meta", {}).get(name, {})
            return (0 if meta.get("fav") else 1, name.lower())

        row_frame = None
        for col_idx, (album_name, idxs) in enumerate(
            sorted(albums.items(), key=_sort_key)
        ):
            if col_idx % COLS == 0:
                row_frame = tk.Frame(self._alb_inner, bg=C["bg"])
                row_frame.pack(fill="x", padx=16, pady=4)

            meta = getattr(self, "_album_meta", {}).get(album_name, {})
            is_fav = meta.get("fav", False)

            cell = tk.Frame(
                row_frame, bg=C["panel2"], width=CELL_W, height=CELL_H, cursor="hand2"
            )
            cell.pack(side="left", padx=4)
            cell.pack_propagate(False)

            art_cv = tk.Canvas(
                cell,
                bg=C["panel"],
                width=CELL_W,
                height=104,
                highlightthickness=0,
                cursor="hand2",
            )
            art_cv.pack()
            self._draw_album_art_async(art_cv, idxs, CELL_W, 104, album_name)

            fav_row = tk.Frame(cell, bg=C["panel2"])
            fav_row.pack(fill="x", padx=6, pady=(3, 0))
            heart = tk.Label(
                fav_row,
                text="♥" if is_fav else "♡",
                font=("Courier New", 9),
                fg="#cc3333" if is_fav else C["white3"],
                bg=C["panel2"],
                cursor="hand2",
            )
            heart.pack(side="right")

            lbl = tk.Label(
                cell,
                text=album_name[:22],
                font=FMS,
                fg=C["white"],
                bg=C["panel2"],
                wraplength=CELL_W - 8,
                justify="left",
                anchor="w",
            )
            lbl.pack(fill="x", padx=6, pady=(1, 0))

            artist = self.library[idxs[0]].get("artist", "") if idxs else ""
            tk.Label(
                cell,
                text=f"{artist[:20]}\n{len(idxs)} track{'s' if len(idxs) != 1 else ''}",
                font=("Courier New", 7),
                fg=C["white3"],
                bg=C["panel2"],
                anchor="w",
            ).pack(fill="x", padx=6)

            def _open(e, n=album_name, ix=idxs):
                self._alb_open_album(n, ix)

            def _toggle_fav(e, n=album_name):
                m = getattr(self, "_album_meta", {})
                if n not in m:
                    m[n] = {}
                m[n]["fav"] = not m[n].get("fav", False)
                self._album_meta = m
                self._save()
                self._alb_show_grid()

            def _ctx(e, n=album_name, ix=idxs):
                self._alb_show_context(e, n, ix)

            heart.bind("<Button-1>", _toggle_fav)
            art_cv.bind("<Button-1>", _open)
            for w in (cell, lbl) + tuple(cell.winfo_children()):
                w.bind("<Double-Button-1>", _open)
                w.bind("<Button-3>", _ctx)
                w.bind("<Enter>", lambda e, c=cell: c.config(bg=C["select2"]))
                w.bind("<Leave>", lambda e, c=cell: c.config(bg=C["panel2"]))

    def _alb_open_album(self, album_name, idxs):
        for w in self._alb_inner.winfo_children():
            w.destroy()
        self._alb_hdr_lbl.config(text=f"ALBUMS  //  {album_name.upper()}")
        self._alb_back_btn.pack(side="left", padx=(16, 0))

        hdr = tk.Frame(self._alb_inner, bg=C["bg"])
        hdr.pack(fill="x", padx=16, pady=(8, 4))
        for txt, wd in [("#", 3), ("TITLE", 30), ("ARTIST", 20), ("TIME", 6)]:
            tk.Label(
                hdr,
                text=txt,
                font=("Courier New", 8, "bold"),
                fg=C["white3"],
                bg=C["bg"],
                width=wd,
                anchor="w",
            ).pack(side="left")
        tk.Frame(self._alb_inner, bg=C["border"], height=1).pack(
            fill="x", padx=16, pady=(0, 4)
        )

        for pos, idx in enumerate(idxs):
            t = self.library[idx]
            title = t.get("title", "Unknown")
            artist = t.get("artist", "")
            dur = t.get("duration", 0)
            dur_str = f"{int(dur) // 60}:{int(dur) % 60:02d}" if dur else "--:--"
            row = tk.Frame(
                self._alb_inner,
                bg=C["panel"] if pos % 2 == 0 else C["panel2"],
                cursor="hand2",
            )
            row.pack(fill="x", padx=16, pady=1)
            tk.Label(
                row,
                text=f"{pos + 1:>3}",
                font=FM,
                fg=C["white3"],
                bg=row["bg"],
                width=3,
                anchor="w",
            ).pack(side="left", padx=(6, 0))
            tk.Label(
                row,
                text=title[:36],
                font=FM,
                fg=C["white"],
                bg=row["bg"],
                width=30,
                anchor="w",
            ).pack(side="left", padx=4)
            tk.Label(
                row,
                text=artist[:22],
                font=FM,
                fg=C["white2"],
                bg=row["bg"],
                width=20,
                anchor="w",
            ).pack(side="left")
            tk.Label(
                row,
                text=dur_str,
                font=FM,
                fg=C["white3"],
                bg=row["bg"],
                width=6,
                anchor="w",
            ).pack(side="left")

            def _play(e, i=idx, il=idxs, p=pos):
                self.queue = list(il)
                self.queue_pos = p
                self._play_item(i)

            row.bind("<Double-Button-1>", _play)
            row.bind("<Enter>", lambda e, r=row: r.config(bg=C["select"]))
            row.bind(
                "<Leave>",
                lambda e, r=row, p=pos: r.config(
                    bg=C["panel"] if p % 2 == 0 else C["panel2"]
                ),
            )
            for child in row.winfo_children():
                child.bind("<Double-Button-1>", _play)

        btn_row = tk.Frame(self._alb_inner, bg=C["bg"])
        btn_row.pack(fill="x", padx=16, pady=12)

        def _play_all():
            self.queue = list(idxs)
            self.queue_pos = 0
            self._play_item(idxs[0])

        def _shuffle_all():
            import random

            s = list(idxs)
            random.shuffle(s)
            self.queue = s
            self.queue_pos = 0
            self._play_item(s[0])

        for txt, cmd in [("▶  PLAY ALL", _play_all), ("⇄  SHUFFLE", _shuffle_all)]:
            b = tk.Label(
                btn_row,
                text=txt,
                font=FM,
                fg=C["white"],
                bg=C["panel2"],
                padx=12,
                pady=4,
                cursor="hand2",
            )
            b.pack(side="left", padx=4)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>", lambda e, btn=b: btn.config(bg=C["select2"]))
            b.bind("<Leave>", lambda e, btn=b: btn.config(bg=C["panel2"]))

    def _alb_show_context(self, event, album_name, idxs):
        m = self._alb_ctx
        m.delete(0, "end")
        meta = getattr(self, "_album_meta", {}).get(album_name, {})
        is_fav = meta.get("fav", False)
        m.add_command(
            label="▶  Play Album",
            command=lambda: [
                setattr(self, "queue", list(idxs)),
                setattr(self, "queue_pos", 0),
                self._play_item(idxs[0]),
            ],
        )
        m.add_separator()
        m.add_command(
            label="♥  Remove Favorite" if is_fav else "♡  Add to Favorites",
            command=lambda: self._alb_toggle_fav(album_name),
        )
        m.add_separator()
        m.add_command(
            label="✎  Rename Album", command=lambda: self._alb_rename(album_name, idxs)
        )
        m.add_command(
            label="🖼  Set Art from File",
            command=lambda: self._alb_set_art_file(album_name),
        )
        m.add_command(
            label="🔗  Set Art from URL",
            command=lambda: self._alb_set_art_url(album_name),
        )
        m.add_command(
            label="✕  Clear Custom Art", command=lambda: self._alb_clear_art(album_name)
        )
        m.add_separator()
        m.add_command(
            label=f"  {len(idxs)} tracks · {album_name[:28]}", state="disabled"
        )
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _alb_toggle_fav(self, album_name):
        if not hasattr(self, "_album_meta"):
            self._album_meta = {}
        if album_name not in self._album_meta:
            self._album_meta[album_name] = {}
        self._album_meta[album_name]["fav"] = not self._album_meta[album_name].get(
            "fav", False
        )
        self._save()
        self._alb_show_grid()

    def _alb_rename(self, old_name, idxs):
        new_name = simpledialog.askstring(
            "Rename Album",
            f"New name for '{old_name}':",
            initialvalue=old_name,
            parent=self.root,
        )
        if not new_name or new_name == old_name:
            return
        for idx in idxs:
            self.library[idx]["album"] = new_name
        if hasattr(self, "_album_meta") and old_name in self._album_meta:
            self._album_meta[new_name] = self._album_meta.pop(old_name)
        self._save()
        self._alb_show_grid()

    def _alb_set_art_file(self, album_name):
        from tkinter import filedialog

        path = filedialog.askopenfilename(
            title="Select Album Art",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.gif *.webp"), ("All", "*.*")],
            parent=self.root,
        )
        if not path:
            return
        if not hasattr(self, "_album_meta"):
            self._album_meta = {}
        if album_name not in self._album_meta:
            self._album_meta[album_name] = {}
        self._album_meta[album_name]["art_path"] = path
        self._album_meta[album_name].pop("art_url", None)
        self._save()
        self._alb_show_grid()

    def _alb_set_art_url(self, album_name):
        url = simpledialog.askstring(
            "Set Art from URL", "Enter image URL:", parent=self.root
        )
        if not url:
            return
        if not hasattr(self, "_album_meta"):
            self._album_meta = {}
        if album_name not in self._album_meta:
            self._album_meta[album_name] = {}
        self._album_meta[album_name]["art_url"] = url
        self._album_meta[album_name].pop("art_path", None)
        self._save()
        self._alb_show_grid()

    def _alb_clear_art(self, album_name):
        if hasattr(self, "_album_meta") and album_name in self._album_meta:
            self._album_meta[album_name].pop("art_path", None)
            self._album_meta[album_name].pop("art_url", None)
        self._save()
        self._alb_show_grid()

    def _draw_album_art_async(self, cv, idxs, w, h, album_name=""):
        cv.delete("all")
        meta = getattr(self, "_album_meta", {}).get(album_name, {})
        art_path = meta.get("art_path")
        art_url = meta.get("art_url")

        def _draw_placeholder():
            import random as _r

            seed = hash(album_name or str(idxs[:2])) % 10000
            rng = _r.Random(seed)
            for _ in range(8):
                x1 = rng.randint(-10, w)
                y1 = rng.randint(-10, h)
                x2 = x1 + rng.randint(20, 80)
                y2 = y1 + rng.randint(20, 60)
                br = rng.randint(18, 48)
                cv.create_rectangle(
                    x1, y1, x2, y2, fill=f"#{br:02x}{br:02x}{br:02x}", outline=""
                )
            for _ in range(4):
                x = rng.randint(0, w)
                y = rng.randint(0, h)
                r = rng.randint(12, 35)
                br = rng.randint(25, 55)
                cv.create_oval(
                    x - r,
                    y - r,
                    x + r,
                    y + r,
                    fill=f"#{br:02x}{br:02x}{br:02x}",
                    outline="",
                )
            initial = (album_name[:1] or "?").upper()
            cv.create_text(
                w // 2,
                h // 2,
                text=initial,
                font=("Courier New", 36, "bold"),
                fill=C["white3"],
            )

        if art_path or art_url:

            def _load():
                try:
                    from PIL import Image, ImageTk
                    import io
                    import urllib.request

                    if art_path:
                        img = Image.open(art_path)
                    else:
                        with urllib.request.urlopen(art_url, timeout=6) as r:
                            img = Image.open(io.BytesIO(r.read()))
                    img = img.convert("RGB").resize((w, h), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)

                    def _show():
                        try:
                            cv.delete("all")
                            cv.create_image(0, 0, anchor="nw", image=photo)
                            cv._photo = photo
                        except Exception:
                            pass

                    self.root.after(0, _show)
                except Exception:
                    self.root.after(0, _draw_placeholder)

            import threading

            threading.Thread(target=_load, daemon=True).start()
        else:
            _draw_placeholder()

    def _refresh_pl_sidebar(self):
        for w in self.pl_sidebar.winfo_children():
            w.destroy()
        for name, idxs in self.playlists.items():
            # Mosaic swatch (16×16 colored dot derived from playlist hash)
            h = abs(hash(name)) % 200 + 55
            dot_col = f"#{h:02x}{h:02x}{h:02x}"

            f = tk.Frame(self.pl_sidebar, bg=C["panel"], cursor="hand2")
            f.pack(fill="x")

            # Small colored dot
            dot = tk.Canvas(f, bg=C["panel"], width=8, height=8, highlightthickness=0)
            dot.pack(side="left", padx=(14, 4), pady=6)
            dot.create_oval(0, 0, 8, 8, fill=dot_col, outline="")

            l = tk.Label(
                f,
                text=f"{name[:18]}  [{len(idxs)}]",
                font=FMS,
                fg=C["white2"],
                bg=C["panel"],
                anchor="w",
                pady=5,
            )
            l.pack(side="left", fill="x", expand=True, padx=(0, 14))

            def _enter(e, fr=f, lb=l):
                ColorAnim.run(
                    self.root, lb, "fg", C["white2"], C["white"], duration_ms=50
                )
                ColorAnim.run(
                    self.root, lb, "bg", C["panel"], C["select2"], duration_ms=50
                )
                ColorAnim.run(
                    self.root, fr, "bg", C["panel"], C["select2"], duration_ms=50
                )

            def _leave(e, fr=f, lb=l):
                ColorAnim.run(
                    self.root, lb, "fg", C["white"], C["white2"], duration_ms=50
                )
                ColorAnim.run(
                    self.root, lb, "bg", C["select2"], C["panel"], duration_ms=50
                )
                ColorAnim.run(
                    self.root, fr, "bg", C["select2"], C["panel"], duration_ms=50
                )

            def _load(n=name):
                self._load_playlist(n)

            for w in (f, l, dot):
                w.bind("<Button-1>", lambda e, c=_load: c())
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)
                if hasattr(self, "_side_scroll_fn"):
                    w.bind("<MouseWheel>", self._side_scroll_fn)

    # ── POLL LOOP ─────────────────────────
    def _poll(self):
        if getattr(self, "_closing", False):
            return
        if self._sp_mode:
            if not self.seeking and self._sp_dur_ms > 0:
                r = min(1.0, self._sp_pos_ms / self._sp_dur_ms)
                self._draw_prog(r)
                pos_s = int(self._sp_pos_ms / 1000)
                dur_s = int(self._sp_dur_ms / 1000)
                self.lbl_cur.config(text=self._fmt(pos_s))
                self.lbl_tot.config(text=self._fmt(dur_s))
                try:
                    self.lbl_cur_hex.config(text=f"0x{pos_s:04X}")
                    self.lbl_tot_hex.config(text=f"0x{dur_s:04X}")
                except Exception:
                    pass
            if self._sp_playing:
                self._sp_pos_ms += 100
        elif (self.engine.is_playing or self.engine.is_paused) and not self.seeking:
            pos = self.engine.get_position()
            dur = self.engine.duration

            # Seek settle guard — for a few ticks after a seek completes,
            # engine.get_position() may still return the pre-seek value.
            # Clamp to the committed seek target so the bar doesn't snap back.
            settle_ticks = getattr(self, "_seek_settle_ticks", 0)
            if settle_ticks > 0:
                self._seek_settle_ticks -= 1
                settle_r = getattr(self, "_seek_settle_r", None)
                if settle_r is not None and dur > 0:
                    settled_pos = settle_r * dur
                    # Only override if engine position looks stale (behind target)
                    if pos < settled_pos - 1.0:
                        pos = settled_pos
                        self._prog_r_cur = settle_r
            self.lbl_cur.config(text=self._fmt(pos))
            try:
                self.lbl_cur_hex.config(text=f"0x{int(pos):04X}")
            except Exception:
                pass
            # Update lbl_tot whenever duration becomes known (async read may have just finished)
            if dur > 0:
                cur_tot = self.lbl_tot.cget("text")
                expected = self._fmt(dur)
                if cur_tot != expected:
                    self.lbl_tot.config(text=expected)
                    try:
                        self.lbl_tot_hex.config(text=f"0x{int(dur):04X}")
                    except Exception:
                        pass
                self._draw_prog(min(1.0, pos / dur))
                if self.engine.is_playing and dur - pos < 5.0:
                    self._gapless_preload()
            else:
                try:
                    import pygame as _pg

                    raw = _pg.mixer.music.get_pos() / 1000.0
                    if raw > 0:
                        self._draw_prog(min(1.0, raw / 240.0))
                except Exception:
                    pass
            if (
                not self.engine.is_paused
                and self.engine.is_done()
                and not getattr(self, "_speed_processing", False)
            ):
                self.engine.is_playing = False
                self.wavevis.set_active(False)
                self.btn_play.config(text="▶")
                self.status_lbl.config(text="[ IDLE ]")
                self._waveform_data = None
                self._art_static_noise()  # [07] TV static on track end
                src = self._active_source
                if self.repeat_mode == "one":
                    # Repeat the current track regardless of source
                    if src == "soundcloud" and getattr(self, "_sc_current_track", None):
                        t = self._sc_current_track
                        threading.Thread(
                            target=lambda: self._sc_stream(t), daemon=True
                        ).start()
                    elif src == "youtube" and getattr(self, "_yt_current_track", None):
                        t = self._yt_current_track
                        threading.Thread(
                            target=lambda: self._yt_stream(t), daemon=True
                        ).start()
                    elif self.queue_pos >= 0:
                        self._play_item(self.queue_pos)
                elif src in ("soundcloud", "youtube", "deezer", "archive", "bandcamp"):
                    if src == "soundcloud":
                        pass  # handled exclusively by _watch_end thread in _sc_stream
                    elif self.repeat_mode == "all":
                        if src == "soundcloud" and getattr(self, "_sc_current_track", None):
                            t = self._sc_current_track
                            threading.Thread(target=lambda: self._sc_stream(t), daemon=True).start()
                        elif src == "youtube" and getattr(self, "_yt_current_track", None):
                            t = self._yt_current_track
                            threading.Thread(target=lambda: self._yt_stream(t), daemon=True).start()
                        elif src == "deezer" and getattr(self, "_dz_current_track", None):
                            t = self._dz_current_track
                            threading.Thread(target=lambda: self._dz_stream(t), daemon=True).start()
                    else:
                        self._active_source = "none"
                        self._set_source_badge("none")
                elif self.repeat_mode == "all" or self.queue_pos < len(self.queue) - 1:
                    # Let AIDJ handle track advance if a session is active
                    if getattr(self, 'aidj', None) and self.aidj._active:
                        self.aidj.on_track_end()
                    else:
                        self._next()
                else:
                    # Queue exhausted — check if AIDJ should take over
                    if getattr(self, 'aidj', None) and self.aidj._active:
                        self.aidj.on_track_end()
                    else:
                        # Release the source lock so Spotify/etc can take over
                        self._active_source = "none"
                        self._set_source_badge("none")
        # Lyric ticker sync
        self._sync_lyric_ticker()
        # A-B loop check
        self._ab_check()
        self.root.after(80 if HW_ACCEL else 200, self._poll)

    def _fmt(self, s):
        s = max(0, int(s))
        return f"{s // 60}:{s % 60:02d}"

    # ── AIDJ VIEW ─────────────────────────
    def _build_aidj_view(self):
        """Build the AI DJ tab panel."""
        self.aidj_frame = self._aidj_view.build(self.content)

    # ── NETSTREAM VIEW ────────────────────
    def _build_netstream_view(self):
        """Build the Local Network Streaming tab panel."""
        self.netstream_frame = self._netstream_view.build(self.content)

    # ── FX VIEW ───────────────────────────
    def _build_fx_view(self):
        """Build the Playback Manipulation FX tab panel."""
        self.fx_frame = self._audiofx_view.build(self.content)

    # ── HELP VIEW ─────────────────────────
    def _build_help_view(self):
        self.help_frame = tk.Frame(self.content, bg=C["bg"])
        top = tk.Frame(self.help_frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="HELP", font=FMX, fg=C["white"], bg=C["bg"]).pack(
            side="left"
        )
        tk.Label(
            top, text="how to use oternos player", font=FMS, fg=C["white3"], bg=C["bg"]
        ).pack(side="left", padx=12)
        tk.Frame(self.help_frame, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        outer = tk.Frame(self.help_frame, bg=C["bg"])
        outer.pack(fill="both", expand=True, padx=20, pady=(8, 8))
        sb = tk.Scrollbar(
            outer, bg=C["panel"], troughcolor=C["bg"], width=6, relief="flat", bd=0
        )
        sb.pack(side="right", fill="y")
        cv = tk.Canvas(outer, bg=C["bg"], highlightthickness=0, yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True)
        sb.config(command=cv.yview)
        self._help_cv = cv  # store direct reference for scroll routing
        inner = tk.Frame(cv, bg=C["bg"])
        win = cv.create_window(0, 0, anchor="nw", window=inner)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfig(win, width=e.width))

        def _help_scroll(e):
            cv.yview_scroll(int(-1 * (e.delta / 120)) * 3, "units")

        cv.bind("<MouseWheel>", _help_scroll)
        inner.bind("<MouseWheel>", _help_scroll)

        # Bind to all children recursively after they're created
        def _bind_all(w):
            w.bind("<MouseWheel>", _help_scroll)
            for child in w.winfo_children():
                _bind_all(child)

        self.help_frame.bind("<Configure>", lambda e: _bind_all(inner))

        def _sec(t):
            tk.Label(
                inner,
                text=t,
                font=("Courier New", 10, "bold"),
                fg=C["white"],
                bg=C["bg"],
            ).pack(anchor="w", pady=(18, 2))
            tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", pady=(0, 6))

        def _sub(t):
            tk.Label(
                inner,
                text="  " + t,
                font=("Courier New", 9, "bold"),
                fg=C["white2"],
                bg=C["bg"],
            ).pack(anchor="w", pady=(10, 2))

        def _dot(t):
            row = tk.Frame(inner, bg=C["bg"])
            row.pack(fill="x", pady=1)
            tk.Label(
                row,
                text="  ·",
                font=FM,
                fg=C["white3"],
                bg=C["bg"],
                width=3,
                anchor="w",
            ).pack(side="left", padx=(8, 0))
            tk.Label(
                row,
                text=t,
                font=FMS,
                fg=C["white2"],
                bg=C["bg"],
                anchor="w",
                wraplength=660,
                justify="left",
            ).pack(side="left", fill="x", expand=True)
            row.bind(
                "<MouseWheel>",
                lambda e: cv.yview_scroll(int(-1 * (e.delta / 120)) * 3, "units"),
            )

        _sec("GETTING STARTED")
        _sub("Adding Music")
        _dot("Click 'Add Files' in the sidebar to add MP3, WAV, FLAC, or M4A files.")
        _dot(
            "Click 'Add Folder' to scan an entire folder and add all audio files at once."
        )
        _dot(
            "Your library saves automatically — tracks stay next time you open the app."
        )
        _sub("Playing a Track")
        _dot("Double-click any track in the Library to start playing it.")
        _dot("Press SPACE to play/pause at any time.")
        _dot("Use the ▶ button at the bottom center to play/pause.")

        _sec("PLAYBACK CONTROLS")
        _sub("Buttons")
        _dot("▶ / ⏸  —  Play or pause the current track.")
        _dot("⏮  —  Previous track (or restart if past 3 seconds).")
        _dot("⏭  —  Skip to next track.")
        _dot("⇌  —  Toggle shuffle — plays tracks in random order.")
        _dot("↺  —  Toggle repeat: off → repeat all → repeat one.")
        _sub("Progress Bar")
        _dot("Click anywhere on the bar to jump to that position.")
        _dot("Click and drag to scrub through the track.")
        _sub("Volume")
        _dot("Click the volume bar on the right to set volume.")
        _dot("Scroll the mouse wheel over the volume bar to adjust.")
        _sub("Keyboard Shortcuts")
        _dot("SPACE — Play / Pause")
        _dot("LEFT / RIGHT ARROW — Previous / Next track")
        _dot("CTRL + LEFT / RIGHT — Seek back / forward 10 seconds")
        _dot("UP / DOWN ARROW — Volume up / down")

        _sec("LIBRARY")
        _sub("Managing Tracks")
        _dot(
            "Right-click any track to Play, Add to Queue, Add to Playlist, Edit Tags, or Remove."
        )
        _dot(
            "Click a column header (TITLE, ARTIST, ALBUM, TIME) to sort by that field. Click again to reverse order."
        )
        _dot("Search also filters by album name.")
        _sub("Tag Editor")
        _dot("Right-click a track → Edit Tags to change title, artist, and album.")
        _dot("Changes are saved directly to the file.")

        _sec("PLAYLISTS")
        _sub("Creating a Playlist")
        _dot("Click '+ New Playlist' in the sidebar, type a name, press Enter.")
        _sub("Adding Tracks")
        _dot("Right-click a track in the Library → Add to Playlist → select playlist.")
        _sub("Managing")
        _dot("Click a playlist name in the sidebar to open it.")
        _dot("Right-click tracks inside to remove them or reorder by dragging.")

        _sec("QUEUE")
        _dot("Right-click any track → Add to Queue to add it to the play queue.")
        _dot("Click the QUEUE tab to see and manage upcoming tracks.")
        _dot("Drag tracks up or down in the queue to reorder them.")
        _dot("Tracks play in queue order after the current track finishes.")

        _sec("VISUALIZER")
        _dot("Click the VISUALIZER tab — it animates automatically when music plays.")
        _dot("Change the visualizer style in Settings (⚙ top right).")

        _sec("LYRICS")
        _dot("Click the LYRICS tab while a track is playing.")
        _dot(
            "Lyrics are fetched automatically from the internet based on title and artist."
        )
        _dot("If not found automatically, you can paste them in manually.")

        _sec("HISTORY")
        _dot("The HISTORY tab shows every track you have played with timestamps.")
        _dot("Click any entry to play that track again.")

        _sec("ALBUMS")
        _dot("The ALBUMS tab groups your library by album automatically.")
        _dot("Click an album to see all its tracks.")

        _sec("SIDEBAR TOOLS")
        _sub("Sleep Timer")
        _dot("Set a timer — the player stops automatically when it runs out.")
        _sub("Mini Player")
        _dot("Compact view showing just controls and track info.")
        _sub("Watch Folders")
        _dot(
            "Set folders to monitor — new audio files appear in your library instantly."
        )
        _sub("Smart Playlist")
        _dot("Create a playlist based on rules (artist, duration, date added, etc).")
        _dot("Updates automatically as your library changes.")
        _sub("Find Dupes")
        _dot("Scans your library for duplicate tracks and shows them side by side.")
        _sub("Export M3U")
        _dot(
            "Save your current playlist as an M3U file for use in other media players."
        )
        _sub("Hotkeys")
        _dot("View and customize global keyboard shortcuts for playback control.")
        _sub("Recommend")
        _dot("Get track suggestions based on your listening history.")
        _sub("Themes")
        _dot("Change the color scheme — pick a preset or build a custom theme.")
        _sub("Bookmarks")
        _dot("Save a position in a track to resume at that exact point later.")

        _sec("STREAMING")
        _sub("Spotify")
        _dot(
            "Click SPOTIFY tab → connect your account to browse and play your playlists."
        )
        _dot("Requires a Spotify Premium account for full playback control.")
        _sub("SoundCloud")
        _dot("Click SOUNDCLOUD tab to search and stream SoundCloud tracks.")
        _dot("No account required to search. Log in to access your liked tracks.")
        _sub("YouTube")
        _dot("Click YOUTUBE tab → search for any song → double-click to play.")
        _dot("Requires yt-dlp: run  pip install yt-dlp  in your terminal.")
        _dot("Played tracks are cached locally so they load instantly next time.")

        _sec("SETTINGS  (⚙)")
        _sub("EQ / Equalizer")
        _dot(
            "Boost or cut frequency bands with presets: Bass Boost, Treble, Rock, Classical, and more."
        )
        _dot("Select 'flat' to disable EQ processing.")
        _sub("Last.fm")
        _dot(
            "Enter your Last.fm API key to enable automatic scrobbling of every track you play."
        )
        _sub("Audio Device")
        _dot("Select which output device to use for audio playback.")

        tk.Frame(inner, bg=C["bg"], height=20).pack()
