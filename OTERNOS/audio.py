"""
audio.py
─────────────────────────────────────────────────────────────────────────────
OTERNOS PLAYER  —  Audio playback engine + EQ processor.
  • AudioEngine   — pygame-based playback (load / play / pause / seek / vol)
  • EQProcessor   — 8-band parametric biquad EQ via scipy
─────────────────────────────────────────────────────────────────────────────
"""

import os
import time
import threading
from pathlib import Path

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TIT2, TPE1, TALB
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

try:
    import numpy as _np
    import scipy.signal as _sig
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# ─────────────────────────────────────────
#  EQ PROCESSOR  — real biquad IIR filters
# ─────────────────────────────────────────
class EQProcessor:
    """
    Applies a real 8-band parametric EQ to an audio file,
    writing a processed temp WAV. Uses scipy biquad filters.
    Falls back to passthrough if scipy unavailable.
    """
    EQ_PRESETS = {
        "flat":         [0,  0,  0,  0,  0,  0,  0,  0],
        "bass boost":   [7,  6,  4,  1,  0,  0,  0,  0],
        "treble boost": [0,  0,  0,  0,  1,  3,  6,  7],
        "vocal":        [-2,-1,  2,  5,  5,  2, -1, -2],
        "electronic":   [5,  4,  0, -2, -1,  2,  4,  4],
        "rock":         [4,  3,  1,  0,  0,  1,  3,  4],
        "classical":    [3,  2,  0,  0,  0,  0,  2,  3],
        "podcast":      [-1,-1,  2,  5,  4,  1,  0, -1],
    }
    BAND_FREQS = [60, 150, 400, 1000, 2400, 6000, 12000, 16000]

    @classmethod
    def process(cls, src_path, preset, out_path):
        """Process src_path with EQ preset, write WAV to out_path.
        Returns True on success, False on any failure (caller uses original)."""
        if not SCIPY_AVAILABLE or not MUTAGEN_AVAILABLE:
            return False
        gains = cls.EQ_PRESETS.get(preset, [0]*8)
        if all(g == 0 for g in gains):
            return False   # flat — no processing needed
        try:
            import wave, tempfile

            # ── Decode source to WAV using pygame ──────────────────────────
            # We use a temp pygame Sound decode rather than MCI, so this works
            # cross-platform and inside PyInstaller bundles.
            try:
                import pygame as _pg
                if not _pg.mixer.get_init():
                    _pg.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
                snd      = _pg.mixer.Sound(str(src_path))
                raw_arr  = _pg.sndarray.array(snd)   # shape (frames,) or (frames, 2)
                rate     = _pg.mixer.get_init()[0]    # sample rate
                n_ch     = 1 if raw_arr.ndim == 1 else raw_arr.shape[1]
            except Exception:
                return False

            pcm = raw_arr.astype(_np.float32)
            if n_ch == 2:
                pcm = pcm / 32768.0
            else:
                pcm = pcm / 32768.0

            # ── Apply biquad peaking EQ per band ───────────────────────────
            for freq, gain_db in zip(cls.BAND_FREQS, gains):
                if abs(gain_db) < 0.1:
                    continue
                b, a = cls._peaking_eq(freq, gain_db, 1.4, rate)
                if n_ch == 2:
                    pcm[:, 0] = _sig.lfilter(b, a, pcm[:, 0])
                    pcm[:, 1] = _sig.lfilter(b, a, pcm[:, 1])
                else:
                    pcm = _sig.lfilter(b, a, pcm)

            # Soft clip + convert back to int16
            pcm     = _np.tanh(pcm)
            pcm_int = (pcm * 32767).astype(_np.int16)

            # ── Write processed WAV ────────────────────────────────────────
            with wave.open(out_path, 'wb') as wf:
                wf.setnchannels(n_ch)
                wf.setsampwidth(2)
                wf.setframerate(rate)
                wf.writeframes(pcm_int.tobytes())
            return True

        except Exception:
            return False

    @staticmethod
    def _peaking_eq(freq, gain_db, Q, fs):
        """Compute biquad peaking EQ coefficients."""
        A     = 10 ** (gain_db / 40.0)
        w0    = 2 * _np.pi * freq / fs
        alpha = _np.sin(w0) / (2 * Q)
        b0 =  1 + alpha * A;  b1 = -2 * _np.cos(w0);  b2 = 1 - alpha * A
        a0 =  1 + alpha / A;  a1 = -2 * _np.cos(w0);  a2 = 1 - alpha / A
        return [b0/a0, b1/a0, b2/a0], [1.0, a1/a0, a2/a0]


# ─────────────────────────────────────────
#  AUDIO ENGINE  — pygame mixer
# ─────────────────────────────────────────
class AudioEngine:
    """
    Pygame-based audio engine.
    Public API: load / play / pause / unpause / stop / seek /
                get_position / set_volume / is_done / get_metadata
    All other code should treat this as a black box.
    """

    def __init__(self):
        self.current_track = None
        self.is_playing    = False
        self.is_paused     = False
        self.volume        = 0.7
        self.duration      = 0.0
        self._pos_cache    = 0.0
        self._play_start   = 0.0
        self._seek_offset  = 0.0
        self._open         = False

        try:
            import pygame
            if not pygame.get_init():
                pygame.init()
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            self._pygame = pygame
        except Exception:
            self._pygame = None

    # ── internal ──────────────────────────────────────────────────────────────
    def _get_dur(self, path):
        if MUTAGEN_AVAILABLE:
            try:
                from mutagen import File as _MFile
                f = _MFile(path)
                if f and f.info:
                    return f.info.length
            except Exception:
                pass
        try:
            if self._pygame:
                s = self._pygame.mixer.Sound(path)
                return s.get_length()
        except Exception:
            pass
        return 0.0

    # ── public API ────────────────────────────────────────────────────────────
    def load(self, path):
        self.stop()
        if not self._pygame:
            return False
        if not os.path.exists(str(path)):
            return False
        try:
            self._pygame.mixer.music.load(str(path))
            self.current_track = path
            self.duration      = self._get_dur(path)
            self._pos_cache    = 0.0
            self._seek_offset  = 0.0
            self._play_start   = 0.0
            self._open         = True
            return True
        except Exception:
            return False

    def play(self, start_ms=0):
        if not self._pygame or not self._open:
            return
        try:
            self._seek_offset = start_ms / 1000.0
            self._pygame.mixer.music.play(start=self._seek_offset)
            self._pygame.mixer.music.set_volume(self.volume)
            self._play_start = time.time()
            self._pos_cache  = self._seek_offset
            self.is_playing  = True
            self.is_paused   = False
        except Exception:
            pass

    def pause(self):
        if not self._pygame or not self.is_playing:
            return
        try:
            self._pos_cache = self.get_position()
            self._pygame.mixer.music.pause()
            self.is_playing = False
            self.is_paused  = True
        except Exception:
            pass

    def unpause(self):
        if not self._pygame or not self.is_paused:
            return
        try:
            self._pygame.mixer.music.unpause()
            self._play_start = time.time() - (self._pos_cache - self._seek_offset)
            self.is_playing  = True
            self.is_paused   = False
        except Exception:
            pass

    def stop(self):
        if not self._pygame:
            return
        try:
            self._pygame.mixer.music.stop()
        except Exception:
            pass
        self.is_playing = False
        self.is_paused  = False
        self._pos_cache = 0.0
        self._open      = False

    def seek(self, pos_sec):
        if not self._pygame or not self._open:
            return
        was_playing = self.is_playing
        try:
            self._pygame.mixer.music.play(start=float(pos_sec))
            self._pygame.mixer.music.set_volume(self.volume)
            self._seek_offset = pos_sec
            self._play_start  = time.time()
            self._pos_cache   = pos_sec
            self.is_playing   = True
            self.is_paused    = False
            if not was_playing:
                self._pygame.mixer.music.pause()
                self.is_playing = False
                self.is_paused  = True
        except Exception:
            pass

    def get_position(self):
        if not self._pygame:
            return self._pos_cache
        if self.is_playing:
            try:
                elapsed = time.time() - self._play_start
                self._pos_cache = self._seek_offset + elapsed
            except Exception:
                pass
        return self._pos_cache

    def set_volume(self, vol):
        self.volume = max(0.0, min(1.0, vol / 100.0 if vol > 1 else vol))
        if self._pygame:
            try:
                self._pygame.mixer.music.set_volume(self.volume)
            except Exception:
                pass

    def is_done(self):
        if not self._pygame or not self.is_playing:
            return False
        try:
            return not self._pygame.mixer.music.get_busy()
        except Exception:
            return False

    def get_metadata(self, path):
        m = {"title": Path(path).stem, "artist": "Unknown", "album": "Unknown"}
        if MUTAGEN_AVAILABLE:
            try:
                tags = ID3(path)
                if TIT2 in tags: m["title"]  = str(tags[TIT2])
                if TPE1 in tags: m["artist"] = str(tags[TPE1])
                if TALB in tags: m["album"]  = str(tags[TALB])
            except Exception:
                try:
                    from mutagen import File as _MF
                    f = _MF(path)
                    if f:
                        m["title"]  = str(f.get("title",  [Path(path).stem])[0])
                        m["artist"] = str(f.get("artist", ["Unknown"])[0])
                        m["album"]  = str(f.get("album",  ["Unknown"])[0])
                except Exception:
                    pass
        return m

    # ── legacy API stubs (kept for compatibility) ─────────────────────────────
    def _ensure_time_fmt(self): pass
    def _bg_vol(self):          pass
    def _v(self):               return self.volume
    def _bg(self, fn, *args):   threading.Thread(target=fn, args=args, daemon=True).start()
