"""
aidj.py — OTERNOS PLAYER
AI DJ — intelligent auto-mix, spoken commentary, mood-aware transitions,
and Claude-powered set narration.

Features:
  • AIDJEngine      — orchestrates transitions, crossfade timing, queue building
  • MoodAnalyser    — lightweight BPM+RMS mood classifier (no model needed)
  • DJCommentator   — generates and TTS-speaks DJ commentary via system TTS
  • AIDJView        — the tkinter UI panel (mounted inside VoidPlayer)

Integration points in player.py (see INTEGRATION NOTES at bottom of file):
  • import AIDJEngine, AIDJView from .aidj
  • add `self.aidj = AIDJEngine(self)` in VoidPlayer.__init__
  • add `self._build_aidj_view()` call in _build_deferred_views
  • add ("AIDJ", "aidj") to the _tabs list in _build_topbar
  • add aidj_frame to _switch_view pack/forget lists
  • wire `elif view == "aidj": self.aidj_frame.pack(…); self.aidj.on_view_shown()`
"""

from __future__ import annotations

import sys
import os
import json
import math
import random
import threading
import time
from pathlib import Path
from typing import Optional, Callable, List, Dict

# ── tkinter / constants import (relative when in package, absolute when frozen) ──
try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    tk = None  # type: ignore

if getattr(sys, "frozen", False):
    from oternos.constants import C, FM, FMS, FML, FMX, HW_ACCEL
    from oternos.animation import ColorAnim
    from oternos.diagnostics import log_exception, get_logger
else:
    try:
        from .constants import C, FM, FMS, FML, FMX, HW_ACCEL
        from .animation import ColorAnim
        from .diagnostics import log_exception, get_logger
    except ImportError:
        # Fallback stubs for standalone testing
        C = {"bg": "#050505", "panel": "#0c0c0c", "border": "#1f1f1f",
             "border2": "#2e2e2e", "white": "#e8e8e8", "white2": "#9a9a9a",
             "white3": "#424242", "glow": "#ffffff", "select": "#1e1e1e",
             "select2": "#242424", "red": "#cc2222"}
        FM = ("Courier New", 9)
        FMS = ("Courier New", 8)
        FML = ("Courier New", 10, "bold")
        FMX = ("Courier New", 13, "bold")
        HW_ACCEL = True
        class ColorAnim:
            @classmethod
            def run(cls, *a, **kw): pass
        def log_exception(ctx, exc): pass
        def get_logger(): import logging; return logging.getLogger("aidj")


# ─────────────────────────────────────────────────────────────────────────────
#  MOOD ANALYSER  — BPM + RMS → mood tag + energy score
# ─────────────────────────────────────────────────────────────────────────────
class MoodAnalyser:
    """
    Lightweight, no-model mood classifier.

    Inputs:  bpm (float), rms (float 0-1), optional genre tag (str)
    Outputs: mood label, energy (0-1), valence (0-1), recommended_transition

    Mood palette:
        VOID / DARK / CHILL / FLOW / RISE / PEAK / DROP / EUPHORIC
    """

    MOODS = {
        "VOID":     dict(energy=(0.0, 0.2), bpm=(0, 80),   valence=0.1),
        "DARK":     dict(energy=(0.1, 0.4), bpm=(60, 110),  valence=0.2),
        "CHILL":    dict(energy=(0.2, 0.45), bpm=(70, 110), valence=0.5),
        "FLOW":     dict(energy=(0.3, 0.6), bpm=(90, 130),  valence=0.55),
        "RISE":     dict(energy=(0.5, 0.75), bpm=(115, 145), valence=0.65),
        "PEAK":     dict(energy=(0.65, 0.9), bpm=(130, 175), valence=0.75),
        "DROP":     dict(energy=(0.7, 1.0), bpm=(125, 180), valence=0.8),
        "EUPHORIC": dict(energy=(0.75, 1.0), bpm=(140, 200), valence=0.9),
    }

    TRANSITION_MAP = {
        # (from_mood, to_mood) → technique
        ("VOID",  "CHILL"):   "fade_long",
        ("VOID",  "DARK"):    "fade_medium",
        ("CHILL", "FLOW"):    "crossfade",
        ("CHILL", "RISE"):    "crossfade",
        ("FLOW",  "RISE"):    "beatmatch",
        ("FLOW",  "PEAK"):    "beatmatch",
        ("RISE",  "PEAK"):    "cut",
        ("RISE",  "DROP"):    "cut",
        ("PEAK",  "DROP"):    "cut",
        ("PEAK",  "CHILL"):   "fade_long",
        ("DROP",  "EUPHORIC"):"cut",
        ("EUPHORIC","PEAK"):  "beatmatch",
        ("DARK",  "VOID"):    "fade_long",
    }

    @classmethod
    def analyse(cls, bpm: float, rms: float, genre: str = "") -> Dict:
        bpm = max(30.0, min(300.0, float(bpm or 120)))
        rms = max(0.0,  min(1.0,   float(rms or 0.3)))
        energy = rms * 0.6 + min(1.0, (bpm - 60) / 140) * 0.4

        best_mood = "FLOW"
        best_score = -1.0
        for mood, spec in cls.MOODS.items():
            el, eh = spec["energy"]
            bl, bh = spec["bpm"]
            score = 0.0
            # energy match
            if el <= energy <= eh:
                score += 1.0 - abs(energy - (el + eh) / 2) / ((eh - el) / 2 + 0.001)
            else:
                score -= min(abs(energy - el), abs(energy - eh)) * 2
            # bpm match
            if bl <= bpm <= bh:
                score += 0.5
            else:
                score -= min(abs(bpm - bl), abs(bpm - bh)) / 100
            if score > best_score:
                best_score = score
                best_mood = mood

        valence = cls.MOODS[best_mood]["valence"]
        # genre modifiers
        g = genre.lower()
        if any(w in g for w in ("classical", "ambient", "sleep")):
            valence = max(0.1, valence - 0.2)
            energy = max(0.0, energy - 0.15)
        if any(w in g for w in ("punk", "metal", "industrial")):
            energy = min(1.0, energy + 0.15)

        return {
            "mood":      best_mood,
            "energy":    round(energy, 3),
            "valence":   round(valence, 3),
            "bpm":       bpm,
            "rms":       rms,
        }

    @classmethod
    def transition_style(cls, from_mood: str, to_mood: str) -> str:
        key = (from_mood, to_mood)
        if key in cls.TRANSITION_MAP:
            return cls.TRANSITION_MAP[key]
        # energy-based fallback
        fe = cls.MOODS.get(from_mood, {}).get("energy", (0.5, 0.5))
        te = cls.MOODS.get(to_mood,   {}).get("energy", (0.5, 0.5))
        fe_mid = (fe[0] + fe[1]) / 2
        te_mid = (te[0] + te[1]) / 2
        delta = abs(te_mid - fe_mid)
        if delta < 0.15:
            return "beatmatch"
        if te_mid > fe_mid:
            return "cut" if delta > 0.35 else "crossfade"
        return "fade_long" if delta > 0.35 else "fade_medium"


# ─────────────────────────────────────────────────────────────────────────────
#  DJ COMMENTATOR  — text commentary + optional TTS
# ─────────────────────────────────────────────────────────────────────────────
class DJCommentator:
    """
    Generates DJ-style transition commentary.
    If Windows SAPI TTS is available (pyttsx3 or win32com), speaks it aloud.
    Otherwise emits text only.
    """

    _INTROS = [
        "Alright, this next one is {title} — {mood} vibes incoming.",
        "Dropping into {title} now. Energy at {energy}.",
        "Here we go — {title} by {artist}.",
        "Transition locked. {mood} sector. Rolling {title}.",
        "Next track: {title}. {bpm} BPM. Strap in.",
        "Set continues with {title} — {artist}. {mood}.",
        "[{mood}] {title} — {bpm} BPM — going live.",
        "Smoothing into {title}. Crossfade complete.",
        "Vibe shift. {title} — by {artist}.",
        "Queue says {title}. Energy {energy_pct}%. Let's run it.",
    ]

    _MOOD_PHRASES = {
        "VOID":     "descending into the void",
        "DARK":     "shadows incoming",
        "CHILL":    "easing the tension",
        "FLOW":     "keeping the flow",
        "RISE":     "building up",
        "PEAK":     "at peak intensity",
        "DROP":     "brace for the drop",
        "EUPHORIC": "full euphoria mode",
    }

    def __init__(self, volume: float = 0.7):
        self._tts = None
        self._tts_lock = threading.Lock()
        self._volume = volume
        self._enabled = False
        threading.Thread(target=self._init_tts, daemon=True).start()

    def _init_tts(self):
        try:
            import pyttsx3
            eng = pyttsx3.init()
            eng.setProperty("rate", 175)
            eng.setProperty("volume", self._volume)
            # prefer a darker/deeper voice if available
            voices = eng.getProperty("voices")
            for v in voices:
                if any(w in v.name.lower() for w in ("david", "mark", "zira")):
                    eng.setProperty("voice", v.id)
                    break
            self._tts = eng
            self._enabled = True
        except Exception:
            pass

    def generate_text(self, track: Dict, mood_data: Dict,
                      transition_style: str = "crossfade") -> str:
        title  = (track.get("title",  "Unknown") or "Unknown")[:40]
        artist = (track.get("artist", "")        or "")[:30]
        bpm    = int(mood_data.get("bpm", 120))
        mood   = mood_data.get("mood", "FLOW")
        energy = mood_data.get("energy", 0.5)

        tmpl = random.choice(self._INTROS)
        phrase = self._MOOD_PHRASES.get(mood, mood.lower())
        text = tmpl.format(
            title=title,
            artist=artist if artist else "unknown artist",
            bpm=bpm,
            mood=phrase,
            energy=f"{energy:.2f}",
            energy_pct=int(energy * 100),
        )
        return text

    def speak(self, text: str):
        if not self._enabled or not self._tts:
            return
        def _do():
            with self._tts_lock:
                try:
                    self._tts.say(text)
                    self._tts.runAndWait()
                except Exception as e:
                    log_exception("dj_tts", e)
        threading.Thread(target=_do, daemon=True).start()

    def set_volume(self, vol: float):
        self._volume = max(0.0, min(1.0, vol))
        if self._tts:
            try:
                self._tts.setProperty("volume", self._volume)
            except Exception:
                pass

    def set_enabled(self, v: bool):
        self._enabled = bool(v) and (self._tts is not None)


# ─────────────────────────────────────────────────────────────────────────────
#  AI DJ ENGINE
# ─────────────────────────────────────────────────────────────────────────────
class AIDJEngine:
    """
    Orchestrates the AI DJ session.

    API (called by VoidPlayer):
        start_session(mode)     — start auto-DJ
        stop_session()          — stop auto-DJ
        on_track_end()          — called when a track finishes (hook into _play_next)
        on_track_start(track)   — called when a new track starts
        build_queue(n)          — fills DJ queue with n tracks
        get_session_stats()     — returns dict of stats for UI
        set_mode(mode)          — 'smart' | 'energy_ramp' | 'mood_lock' | 'random'
        set_commentary(bool)    — enable/disable spoken commentary
        set_crossfade_sec(sec)  — override crossfade duration for DJ mode

    Modes:
        smart        — energy-aware, avoids repeats, mood-compatible next track
        energy_ramp  — gradually increases energy over the set
        mood_lock    — locks to a chosen mood and stays there
        random       — shuffled but commentary still works
    """

    MODES = ["smart", "energy_ramp", "mood_lock", "random"]

    def __init__(self, player):
        self.player = player            # VoidPlayer instance
        self._active  = False
        self._mode    = "smart"
        self._mood_lock = "FLOW"
        self._session_start: Optional[float] = None
        self._tracks_played: List[Dict] = []
        self._dj_queue: List[int] = []  # library indices
        self._recent_indices: List[int] = []
        self._energy_target = 0.5
        self._energy_ramp_rate = 0.05   # per track
        self._crossfade_override: Optional[int] = None
        self._commentary = DJCommentator()
        self._commentary_enabled = False
        self._last_mood: Optional[Dict] = None
        self._log: List[str] = []
        self._on_log_update: Optional[Callable] = None   # set by AIDJView
        self._logger = get_logger()

    # ── session control ───────────────────────────────────────────────────────
    def start_session(self, mode: str = "smart"):
        self._active = True
        self._mode   = mode if mode in self.MODES else "smart"
        self._session_start = time.time()
        self._tracks_played.clear()
        self._recent_indices.clear()
        self._energy_target  = 0.3   # start low, ramp up
        self._dj_queue.clear()
        self._append_log(f"[AIDJ] Session started — mode: {self._mode.upper()}")
        self.build_queue(8)
        # If player is idle, kick off first track
        if not self.player.engine.is_playing and self._dj_queue:
            self._play_next_dj()

    def stop_session(self):
        self._active = False
        self._append_log("[AIDJ] Session ended.")

    def on_track_end(self):
        """Hook: call this from player._play_next or poll loop when track ends."""
        if not self._active:
            return
        # Refill queue if low
        if len(self._dj_queue) < 3:
            self.build_queue(6)
        self._play_next_dj()

    def on_track_start(self, track: Dict):
        """Hook: call when a track begins playing."""
        if not self._active:
            return
        bpm  = float(track.get("bpm")  or self.player._bpm_cache.get(track.get("path",""), 0) or 120)
        rms  = float(self.player._norm_rms or 0.3)
        genre = track.get("genre", "")
        mood_data = MoodAnalyser.analyse(bpm, rms, genre)
        self._last_mood = mood_data
        self._tracks_played.append({**track, "_mood": mood_data})

        # Energy ramp
        if self._mode == "energy_ramp":
            self._energy_target = min(1.0, self._energy_target + self._energy_ramp_rate)

        # Commentary
        if self._commentary_enabled:
            prev_mood = (self._tracks_played[-2].get("_mood", {}).get("mood")
                         if len(self._tracks_played) >= 2 else None)
            transition = (MoodAnalyser.transition_style(prev_mood, mood_data["mood"])
                          if prev_mood else "fade_medium")
            text = self._commentary.generate_text(track, mood_data, transition)
            self._append_log(f"[DJ] {text}")
            self._commentary.speak(text)
        else:
            self._append_log(
                f"[AIDJ] Now: {track.get('title','?')[:36]} "
                f"| {mood_data['mood']} | {int(mood_data['bpm'])}BPM "
                f"| E:{int(mood_data['energy']*100)}%"
            )

    # ── queue builder ─────────────────────────────────────────────────────────
    def build_queue(self, n: int = 6):
        lib = self.player.library
        if not lib:
            return

        candidates = list(range(len(lib)))
        # avoid recent
        candidates = [i for i in candidates if i not in self._recent_indices[-12:]]
        if not candidates:
            self._recent_indices.clear()
            candidates = list(range(len(lib)))

        if self._mode == "smart" or self._mode == "energy_ramp":
            scored = self._score_candidates(candidates)
            scored.sort(key=lambda x: x[1], reverse=True)
            picks = [i for i, _ in scored[:max(n * 3, 15)]]
            random.shuffle(picks)
            picks = picks[:n]
        elif self._mode == "mood_lock":
            picks = self._mood_locked_picks(candidates, n)
        else:
            picks = random.sample(candidates, min(n, len(candidates)))

        for i in picks:
            if i not in self._dj_queue:
                self._dj_queue.append(i)
        self._append_log(f"[AIDJ] Queue built — {len(self._dj_queue)} tracks ready.")

    def _score_candidates(self, candidates: List[int]) -> List[tuple]:
        """Score each candidate track based on energy proximity and mood compatibility."""
        scored = []
        target_e = self._energy_target
        last_mood = (self._last_mood or {}).get("mood", "FLOW")

        for i in candidates:
            t = self.player.library[i]
            bpm_  = float(self.player._bpm_cache.get(t.get("path",""), 0) or 120)
            rms_  = 0.3   # default if no capture available
            md    = MoodAnalyser.analyse(bpm_, rms_, t.get("genre",""))
            # energy proximity score (Gaussian)
            e_diff = abs(md["energy"] - target_e)
            e_score = math.exp(-4.0 * e_diff ** 2)
            # mood compatibility
            style = MoodAnalyser.transition_style(last_mood, md["mood"])
            compat = {"cut": 0.9, "beatmatch": 1.0, "crossfade": 0.8,
                      "fade_medium": 0.6, "fade_long": 0.4}.get(style, 0.5)
            # diversity bonus — prefer tracks we haven't played recently
            play_count = sum(1 for p in self._tracks_played
                             if p.get("path") == t.get("path"))
            diversity = 1.0 / (1.0 + play_count * 2)
            total = e_score * 0.5 + compat * 0.3 + diversity * 0.2
            scored.append((i, total))
        return scored

    def _mood_locked_picks(self, candidates: List[int], n: int) -> List[int]:
        target = self._mood_lock
        matching = []
        for i in candidates:
            t  = self.player.library[i]
            bm = float(self.player._bpm_cache.get(t.get("path",""), 0) or 120)
            md = MoodAnalyser.analyse(bm, 0.3, t.get("genre",""))
            if md["mood"] == target:
                matching.append(i)
        if len(matching) < n:
            matching += random.sample(
                [c for c in candidates if c not in matching],
                min(n - len(matching), len(candidates) - len(matching))
            )
        return random.sample(matching, min(n, len(matching)))

    # ── playback ──────────────────────────────────────────────────────────────
    def _play_next_dj(self):
        if not self._dj_queue:
            self.build_queue(6)
        if not self._dj_queue:
            self._append_log("[AIDJ] No tracks available.")
            return
        idx = self._dj_queue.pop(0)
        self._recent_indices.append(idx)

        # Apply crossfade override if set
        if self._crossfade_override is not None:
            old_xfade = self.player.settings.get("crossfade_sec", 0)
            self.player.settings["crossfade_sec"] = self._crossfade_override
            self.player.root.after(
                int(self._crossfade_override * 1000) + 500,
                lambda: self.player.settings.__setitem__("crossfade_sec", old_xfade)
            )

        # Trigger playback via player's existing mechanism
        self.player.root.after(0, lambda: self._do_play(idx))

    def _do_play(self, lib_idx: int):
        try:
            self.player.current_idx = lib_idx
            track = self.player.library[lib_idx]
            # use player's existing _play_track if available, else minimal path
            if hasattr(self.player, "_play_track"):
                self.player._play_track(lib_idx)
            else:
                self.player.engine.load(track["path"])
                self.player.engine.play()
            self.on_track_start(track)
        except Exception as e:
            log_exception("aidj_play", e)

    # ── stats + logging ───────────────────────────────────────────────────────
    def get_session_stats(self) -> Dict:
        elapsed = int(time.time() - self._session_start) if self._session_start else 0
        mm, ss = divmod(elapsed, 60)
        hh, mm = divmod(mm, 60)
        moods = [t.get("_mood", {}).get("mood","?") for t in self._tracks_played]
        return {
            "active":         self._active,
            "mode":           self._mode,
            "uptime":         f"{hh:02d}:{mm:02d}:{ss:02d}",
            "tracks_played":  len(self._tracks_played),
            "queue_len":      len(self._dj_queue),
            "energy_target":  int(self._energy_target * 100),
            "current_mood":   (self._last_mood or {}).get("mood", "—"),
            "mood_history":   moods[-8:],
            "commentary_on":  self._commentary_enabled,
        }

    def _append_log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self._log.append(entry)
        if len(self._log) > 200:
            self._log = self._log[-200:]
        if self._on_log_update:
            try:
                self._on_log_update(entry)
            except Exception:
                pass

    def set_mode(self, mode: str):
        if mode in self.MODES:
            self._mode = mode
            self._append_log(f"[AIDJ] Mode → {mode.upper()}")

    def set_mood_lock(self, mood: str):
        self._mood_lock = mood
        self._append_log(f"[AIDJ] Mood lock → {mood}")

    def set_commentary(self, enabled: bool):
        self._commentary_enabled = bool(enabled)
        self._commentary.set_enabled(enabled)
        self._append_log(f"[AIDJ] Commentary {'ON' if enabled else 'OFF'}")

    def set_crossfade(self, sec: Optional[int]):
        self._crossfade_override = sec
        self._append_log(f"[AIDJ] Crossfade override → {sec}s")


# ─────────────────────────────────────────────────────────────────────────────
#  AIDJ VIEW  — tkinter panel
# ─────────────────────────────────────────────────────────────────────────────
class AIDJView:
    """
    Builds and manages the AIDJ tab inside VoidPlayer.
    Call `build(parent_content_frame, player)` once from _build_deferred_views.
    Returns self.frame — the root widget for this view.
    """

    def __init__(self, player):
        self.player = player
        self.frame: Optional[tk.Frame] = None
        self._stats_job = None
        self._energy_canvas = None
        self._mood_bar_labels: Dict[str, tk.Label] = {}

    # ── construction ─────────────────────────────────────────────────────────
    def build(self, parent: tk.Frame) -> tk.Frame:
        p = self.player
        aidj = p.aidj  # AIDJEngine

        self.frame = tk.Frame(parent, bg=C["bg"])

        # ── Header ───────────────────────────────────────────────────────────
        hdr = tk.Frame(self.frame, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(12, 0))
        tk.Label(hdr, text="AI·DJ", font=FMX, fg=C["white"], bg=C["bg"]).pack(side="left")
        self._status_lbl = tk.Label(
            hdr, text="[ STANDBY ]", font=FMS, fg=C["white3"], bg=C["bg"]
        )
        self._status_lbl.pack(side="left", padx=12)
        self._uptime_lbl = tk.Label(
            hdr, text="", font=("Courier New", 7), fg=C["white3"], bg=C["bg"]
        )
        self._uptime_lbl.pack(side="right")
        tk.Frame(self.frame, bg=C["border2"], height=2).pack(fill="x", padx=20, pady=(4, 0))
        tk.Frame(self.frame, bg=C["border"],  height=1).pack(fill="x", padx=20, pady=(1, 8))

        # ── Control row ───────────────────────────────────────────────────────
        ctrl = tk.Frame(self.frame, bg=C["bg"])
        ctrl.pack(fill="x", padx=20, pady=(0, 8))

        self._start_btn = self._make_btn(ctrl, "▶ START SESSION", self._start)
        self._start_btn.pack(side="left", padx=(0, 8))
        self._stop_btn  = self._make_btn(ctrl, "■ STOP",          self._stop,  dim=True)
        self._stop_btn.pack(side="left", padx=(0, 16))

        # Mode selector
        tk.Label(ctrl, text="MODE", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(0, 4))
        self._mode_var = tk.StringVar(value="smart")
        mode_opts = ["smart", "energy_ramp", "mood_lock", "random"]
        mode_menu = tk.OptionMenu(ctrl, self._mode_var, *mode_opts,
                                  command=lambda v: aidj.set_mode(v))
        mode_menu.config(
            bg=C["panel"], fg=C["white2"], activebackground=C["select"],
            activeforeground=C["white"], font=FMS, relief="flat",
            highlightthickness=1, highlightbackground=C["border"],
            indicatoron=False, bd=0, padx=8
        )
        mode_menu["menu"].config(bg=C["panel"], fg=C["white2"], font=FMS,
                                  activebackground=C["select"], bd=0, relief="flat")
        mode_menu.pack(side="left", padx=(0, 16))

        # Commentary toggle
        self._commentary_var = tk.BooleanVar(value=False)
        self._make_toggle(ctrl, "COMMENTARY", self._commentary_var,
                          lambda: aidj.set_commentary(self._commentary_var.get())
                          ).pack(side="left", padx=(0, 12))

        # Crossfade selector
        tk.Label(ctrl, text="XFADE", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(0, 4))
        self._xfade_var = tk.StringVar(value="auto")
        xf_opts = ["auto", "2s", "4s", "6s", "8s"]
        xf_menu = tk.OptionMenu(ctrl, self._xfade_var, *xf_opts,
                                 command=self._on_xfade_change)
        xf_menu.config(
            bg=C["panel"], fg=C["white2"], activebackground=C["select"],
            activeforeground=C["white"], font=FMS, relief="flat",
            highlightthickness=1, highlightbackground=C["border"],
            indicatoron=False, bd=0, padx=8
        )
        xf_menu["menu"].config(bg=C["panel"], fg=C["white2"], font=FMS,
                                 activebackground=C["select"], bd=0, relief="flat")
        xf_menu.pack(side="left")

        tk.Frame(self.frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(0, 8))

        # ── Middle panel: stats + mood ──────────────────────────────────────
        mid = tk.Frame(self.frame, bg=C["bg"])
        mid.pack(fill="x", padx=20, pady=(0, 8))

        # Stats block (left)
        stats_block = tk.Frame(mid, bg=C["panel"], padx=14, pady=10)
        stats_block.pack(side="left", fill="y")
        tk.Label(stats_block, text="SESSION STATS", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["panel"]).pack(anchor="w", pady=(0, 6))
        self._stat_labels: Dict[str, tk.Label] = {}
        for key, caption in [
            ("tracks_played", "TRACKS"),
            ("queue_len",     "QUEUED"),
            ("energy_target", "ENERGY %"),
            ("current_mood",  "MOOD"),
        ]:
            row = tk.Frame(stats_block, bg=C["panel"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{caption}:", font=FMS, fg=C["white3"],
                     bg=C["panel"], width=12, anchor="w").pack(side="left")
            lbl = tk.Label(row, text="—", font=FMS, fg=C["white"],
                           bg=C["panel"], anchor="w")
            lbl.pack(side="left")
            self._stat_labels[key] = lbl

        # Energy canvas (center)
        energy_block = tk.Frame(mid, bg=C["bg"], padx=20)
        energy_block.pack(side="left", fill="both", expand=True)
        tk.Label(energy_block, text="ENERGY CURVE", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(anchor="w")
        self._energy_canvas = tk.Canvas(
            energy_block, bg=C["panel"], height=80, highlightthickness=1,
            highlightbackground=C["border"]
        )
        self._energy_canvas.pack(fill="x", pady=(4, 0))
        self._energy_history: List[float] = []

        # Mood lock (right, only when mode == mood_lock)
        self._mood_lock_frame = tk.Frame(mid, bg=C["bg"])
        self._mood_lock_frame.pack(side="left", fill="y", padx=(20, 0))
        tk.Label(self._mood_lock_frame, text="MOOD LOCK", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(anchor="w", pady=(0, 4))
        for mood in MoodAnalyser.MOODS:
            btn = tk.Label(
                self._mood_lock_frame, text=mood, font=FMS,
                fg=C["white3"], bg=C["bg"], cursor="hand2", padx=6, pady=1
            )
            btn.pack(anchor="w")
            btn.bind("<Button-1>", lambda e, m=mood: self._lock_mood(m))
            btn.bind("<Enter>", lambda e, b=btn: b.config(fg=C["glow"]))
            btn.bind("<Leave>", lambda e, b=btn: b.config(
                fg=C["white"] if b.cget("text") == aidj._mood_lock else C["white3"]
            ))
            self._mood_bar_labels[mood] = btn

        tk.Frame(self.frame, bg=C["border"], height=1).pack(fill="x", padx=20, pady=(0, 8))

        # ── DJ Log ───────────────────────────────────────────────────────────
        log_hdr = tk.Frame(self.frame, bg=C["bg"])
        log_hdr.pack(fill="x", padx=20)
        tk.Label(log_hdr, text="DJ LOG", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(side="left")
        clr = tk.Label(log_hdr, text="[ CLEAR ]", font=FMS, fg=C["white3"],
                       bg=C["bg"], cursor="hand2")
        clr.pack(side="right")
        clr.bind("<Button-1>", lambda e: self._clear_log())
        clr.bind("<Enter>", lambda e: clr.config(fg=C["white"]))
        clr.bind("<Leave>", lambda e: clr.config(fg=C["white3"]))

        log_outer = tk.Frame(self.frame, bg=C["bg"])
        log_outer.pack(fill="both", expand=True, padx=20, pady=(4, 12))
        log_sb = tk.Scrollbar(log_outer, bg=C["panel"], troughcolor=C["bg"],
                               width=6, relief="flat", bd=0)
        log_sb.pack(side="right", fill="y")
        self._log_text = tk.Text(
            log_outer, bg=C["panel"], fg=C["white2"], font=FMS,
            relief="flat", bd=0, highlightthickness=0, wrap="word",
            state="disabled", yscrollcommand=log_sb.set, padx=8, pady=6
        )
        self._log_text.pack(side="left", fill="both", expand=True)
        log_sb.config(command=self._log_text.yview)
        self._log_text.tag_config("info",  foreground=C["white2"])
        self._log_text.tag_config("dj",    foreground=C["white"])
        self._log_text.tag_config("warn",  foreground=C["red"])
        self._log_text.tag_config("mood",  foreground=C["glow"])

        # Wire log callback
        aidj._on_log_update = self._append_log_widget

        # Replay existing log
        for entry in aidj._log:
            self._append_log_widget(entry)

        return self.frame

    # ── callbacks ─────────────────────────────────────────────────────────────
    def _start(self):
        mode = self._mode_var.get()
        self.player.aidj.start_session(mode)
        self._status_lbl.config(text="[ LIVE ]", fg=C["glow"])
        self._start_btn.config(fg=C["white3"])
        self._stop_btn.config(fg=C["white"])
        self._start_stats_poll()

    def _stop(self):
        self.player.aidj.stop_session()
        self._status_lbl.config(text="[ STANDBY ]", fg=C["white3"])
        self._start_btn.config(fg=C["white"])
        self._stop_btn.config(fg=C["white3"])

    def _lock_mood(self, mood: str):
        self.player.aidj.set_mood_lock(mood)
        for m, lbl in self._mood_bar_labels.items():
            lbl.config(fg=C["white"] if m == mood else C["white3"])

    def _on_xfade_change(self, val: str):
        if val == "auto":
            self.player.aidj.set_crossfade(None)
        else:
            try:
                sec = int(val.replace("s",""))
                self.player.aidj.set_crossfade(sec)
            except ValueError:
                self.player.aidj.set_crossfade(None)

    def _clear_log(self):
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.config(state="disabled")

    # ── stats poll ────────────────────────────────────────────────────────────
    def _start_stats_poll(self):
        self._stats_update()

    def _stats_update(self):
        if not self.frame or not self.frame.winfo_exists():
            return
        stats = self.player.aidj.get_session_stats()
        self._stat_labels["tracks_played"].config(text=str(stats["tracks_played"]))
        self._stat_labels["queue_len"].config(text=str(stats["queue_len"]))
        self._stat_labels["energy_target"].config(text=f"{stats['energy_target']}%")
        self._stat_labels["current_mood"].config(text=stats["current_mood"])
        self._uptime_lbl.config(text=stats["uptime"])
        # update energy history canvas
        e = self.player.aidj._energy_target
        self._energy_history.append(e)
        if len(self._energy_history) > 60:
            self._energy_history = self._energy_history[-60:]
        self._draw_energy_curve()
        if stats["active"]:
            self._stats_job = self.frame.after(1000, self._stats_update)

    def _draw_energy_curve(self):
        cv = self._energy_canvas
        if not cv or not cv.winfo_exists():
            return
        cv.delete("all")
        W = cv.winfo_width() or 400
        H = cv.winfo_height() or 80
        data = self._energy_history
        if len(data) < 2:
            return
        step = W / max(len(data) - 1, 1)
        pts = []
        for i, e in enumerate(data):
            x = i * step
            y = H - int(e * (H - 6)) - 3
            pts.append((x, y))
        # fill under curve
        fill_pts = [(0, H)] + pts + [(W, H)]
        try:
            cv.create_polygon(*[c for p in fill_pts for c in p],
                               fill="#1a1a1a", outline="")
        except Exception:
            pass
        # line
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            cv.create_line(x1, y1, x2, y2, fill=C["white3"], width=1)
        # current dot
        if pts:
            lx, ly = pts[-1]
            cv.create_oval(lx-3, ly-3, lx+3, ly+3, fill=C["glow"], outline="")

    # ── log widget ───────────────────────────────────────────────────────────
    def _append_log_widget(self, entry: str):
        if not self._log_text or not self._log_text.winfo_exists():
            return
        tag = "dj" if "[DJ]" in entry else "mood" if "[AIDJ] Mood" in entry else "info"
        self._log_text.config(state="normal")
        self._log_text.insert("end", entry + "\n", (tag,))
        self._log_text.config(state="disabled")
        self._log_text.see("end")

    # ── helpers ───────────────────────────────────────────────────────────────
    def _make_btn(self, parent, text, cmd, dim=False):
        lbl = tk.Label(
            parent, text=text, font=FMS,
            fg=C["white3"] if dim else C["white"],
            bg=C["panel"], cursor="hand2", padx=10, pady=4
        )
        lbl.bind("<Button-1>", lambda e: cmd())
        lbl.bind("<Enter>", lambda e: lbl.config(fg=C["glow"]))
        lbl.bind("<Leave>", lambda e: lbl.config(fg=C["white3"] if dim else C["white"]))
        return lbl

    def _make_toggle(self, parent, label, var, cmd):
        frame = tk.Frame(parent, bg=C["bg"])
        lbl = tk.Label(frame, text=label, font=FMS, fg=C["white3"],
                       bg=C["bg"], cursor="hand2")
        lbl.pack(side="left")
        indicator = tk.Label(frame, text="○", font=FMS, fg=C["white3"],
                              bg=C["bg"], cursor="hand2")
        indicator.pack(side="left", padx=(3, 0))

        def _toggle():
            var.set(not var.get())
            indicator.config(text="●" if var.get() else "○",
                              fg=C["glow"] if var.get() else C["white3"])
            cmd()

        for w in (lbl, indicator, frame):
            w.bind("<Button-1>", lambda e: _toggle())
        return frame

    def on_view_shown(self):
        """Called by _switch_view when this tab becomes visible."""
        stats = self.player.aidj.get_session_stats()
        if stats["active"]:
            self._stats_update()


# ─────────────────────────────────────────────────────────────────────────────
#  INTEGRATION NOTES  (paste these into player.py)
# ─────────────────────────────────────────────────────────────────────────────
"""
STEP 1 — imports at top of player.py (add to both frozen and non-frozen blocks):

    from oternos.aidj import AIDJEngine, AIDJView          # frozen
    from .aidj import AIDJEngine, AIDJView                 # non-frozen

STEP 2 — in VoidPlayer.__init__, after Discord/watcher init (~line 261):

    self.aidj      = AIDJEngine(self)
    self._aidj_view = AIDJView(self)

STEP 3 — in _build_topbar _tabs list (~line 2323), add:

    ("AIDJ", "aidj"),

STEP 4 — in _build_deferred_views _steps list (~line 3243), add:

    self._build_aidj_view,

STEP 5 — add new method to VoidPlayer:

    def _build_aidj_view(self):
        self.aidj_frame = self._aidj_view.build(self.content)

STEP 6 — in _switch_view _do_switch, pack_forget list (~line 9733), add:

    "aidj_frame",

STEP 7 — in _switch_view _do_switch, elif chain (~line 9802), add:

    elif view == "aidj":
        self.aidj_frame.pack(fill="both", expand=True)
        self._aidj_view.on_view_shown()

STEP 8 — in _update_tabs _labels dict, add:

    "aidj": "AIDJ",

STEP 9 — in _on_close, cancel list, add (optional):

    "_aidj_stats_job",

STEP 10 — hook on_track_end into _play_next / _advance.
In your existing track-advance logic (wherever _play_next is called when a
track finishes), add:

    if getattr(self, 'aidj', None) and self.aidj._active:
        self.aidj.on_track_end()
        return   # aidj handles the next track
"""
