"""
audio.py — OTERNOS PLAYER
AudioEngine (pygame-based) and EQProcessor (scipy biquad IIR filters).
"""

import os
import threading
import time
from pathlib import Path
from contextlib import contextmanager
import sys

if getattr(sys, "frozen", False):
    from oternos.diagnostics import log_exception
else:
    from .diagnostics import log_exception

@contextmanager
def _silence_stderr():
    """Redirect OS-level stderr (fd 2) to devnull for the duration of the block.
    Suppresses C-library warnings (e.g. mpg123 ID3 spam) that bypass Python logging."""
    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        saved_fd   = os.dup(2)
        os.dup2(devnull_fd, 2)
        os.close(devnull_fd)
        try:
            yield
        finally:
            os.dup2(saved_fd, 2)
            os.close(saved_fd)
    except Exception:
        yield  # if fd tricks fail, just proceed normally

# ── Optional deps ──────────────────────────────────────────────────────────────
try:
    import os as _os

    _os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame

    pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=1024)
    pygame.init()
    pygame.mixer.init()
    _PYGAME_OK = True
except Exception:
    _PYGAME_OK = False

try:
    from mutagen import File as _MutagenFile

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

try:
    import numpy as _np
    from scipy import signal as _signal
    from scipy.signal import resample_poly
    import soundfile as _sf
    from math import gcd as _gcd

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
#  AUDIO ENGINE
# ──────────────────────────────────────────────────────────────────────────────
class AudioEngine:
    """
    pygame.mixer-based audio engine.

    Public API used by VoidPlayer:
        load(path)              → bool
        play(start_ms=0)        → bool
        pause()
        unpause()
        stop()
        seek(pos_s)
        get_position()          → float  (seconds)
        is_done()               → bool
        set_volume(vol)         vol 0.0–1.0 (or 0–100 int, normalised internally)
        get_metadata(path)      → dict
        duration                property (float, seconds)
        volume                  property (float 0.0–1.0)
        is_playing              bool
        is_paused               bool
        _pos_cache              float  (last known position in seconds)
    """

    def __init__(self):
        self._path = None
        self._duration = 0.0
        self._volume = 0.8
        self._is_playing = False
        self._is_paused = False
        self._start_time = 0.0  # wall-clock when play() was called
        self._seek_offset = 0.0  # seconds already played before last seek
        self._pos_cache = 0.0
        self._preload_path = None
        self._preload_ready = False
        self._preload_duration = 0.0
        self._seeked_while_paused = False  # set in seek(); guards unpause correction
        self._lock = threading.Lock()
        self._seek_lock = threading.Lock()   # prevents concurrent seek calls
        self._speed = 1.0  # current playback speed
        self._speed_tmp = None  # path to resampled temp file (if speed != 1.0)

    # ── properties ─────────────────────────────────────────────────────────────
    @property
    def duration(self):
        return self._duration

    @duration.setter
    def duration(self, value):
        self._duration = float(value)

    @property
    def volume(self):
        return self._volume

    @property
    def is_playing(self):
        return self._is_playing

    @is_playing.setter
    def is_playing(self, value):
        self._is_playing = value

    @property
    def is_paused(self):
        return self._is_paused

    # ── load ───────────────────────────────────────────────────────────────────
    def load(self, path):
        """Load an audio file. Returns True on success."""
        if not _PYGAME_OK:
            return False
        # Use pre-loaded data if available for this exact path
        if getattr(self, "_preload_path", None) == path and getattr(
            self, "_preload_ready", False
        ):
            self.stop()
            self._path = path
            self._duration = self._preload_duration
            self._seek_offset = 0.0
            self._pos_cache = 0.0
            self._preload_path = None
            self._preload_ready = False
            # File was already loaded by preload() — just need to re-load since stop() unloads
            try:
                with _silence_stderr():
                    pygame.mixer.music.load(path)
                return True
            except Exception as e:
                log_exception("audio_engine.load_preload", e)
                return False
        try:
            self.stop()
            with _silence_stderr():
                pygame.mixer.music.load(path)
            self._path = path
            # Use pre-loaded duration if available, otherwise read it async after play starts
            if getattr(self, "_preload_path", None) == path and getattr(
                self, "_preload_ready", False
            ):
                self._duration = self._preload_duration
            else:
                self._duration = 0.0  # will be filled by async read after play()
            self._seek_offset = 0.0
            self._pos_cache = 0.0
            return True
        except Exception as e:
            log_exception("audio_engine.load", e)
            return False

    def preload(self, path):
        """Pre-read duration in background so load() is faster when called."""
        self._preload_path = path
        self._preload_ready = False
        self._preload_duration = 0.0

        def _worker():
            try:
                dur = self._read_duration(path)
                if self._preload_path == path:  # still relevant
                    self._preload_duration = dur
                    self._preload_ready = True
            except Exception:
                pass

        import threading as _th

        _th.Thread(target=_worker, daemon=True).start()

    # ── play ───────────────────────────────────────────────────────────────────
    def play(self, start_ms=0):
        """Start playback, optionally from start_ms milliseconds."""
        if not _PYGAME_OK:
            return False
        try:
            start_s = start_ms / 1000.0
            pygame.mixer.music.play(start=start_s)
            pygame.mixer.music.set_volume(self._volume)
            self._seek_offset = start_s
            self._start_time = time.monotonic()
            self._is_playing = True
            self._is_paused = False
            # If duration unknown, read it async so progress bar can show ratio
            if self._duration <= 0 and self._path:
                _p = self._path

                def _read_dur():
                    d = self._read_duration(_p)
                    if self._path == _p and d > 0:
                        self._duration = d

                import threading as _th

                _th.Thread(target=_read_dur, daemon=True).start()
            return True
        except Exception as e:
            log_exception("audio_engine.play", e)
            return False

    # ── pause / unpause ────────────────────────────────────────────────────────
    def pause(self):
        if not _PYGAME_OK or not self._is_playing:
            return
        try:
            self._pos_cache = self.get_position()
            pygame.mixer.music.pause()
            self._is_playing = False
            self._is_paused = True
        except Exception as e:
            log_exception("audio_engine.pause", e)

    def unpause(self):
        if not _PYGAME_OK or not self._is_paused:
            return
        try:
            # _seek_offset and _pos_cache are already correct whether or not
            # a seek happened while paused (seek() handles both cases now).
            self._start_time = time.monotonic()
            pygame.mixer.music.unpause()
            self._is_playing = True
            self._is_paused = False
        except Exception as e:
            log_exception("audio_engine.unpause", e)

    # ── stop ───────────────────────────────────────────────────────────────────
    def stop(self):
        if not _PYGAME_OK:
            return
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self._is_playing = False
        self._is_paused = False
        self._pos_cache = 0.0
        self._seek_offset = 0.0
        self._cleanup_speed_tmp()
        self._speed = 1.0

    def seek(self, pos_s):
        if not _PYGAME_OK:
            return
        # Only clamp to duration if we actually know it — clamping to 0 when
        # _duration is 0 would force every seek to position 0
        if self._duration > 0:
            pos_s = max(0.0, min(self._duration, float(pos_s)))
        else:
            pos_s = max(0.0, float(pos_s))
        was_paused = self._is_paused
        # Serialise concurrent seeks — a second call waits for the first to
        # finish rather than both hammering pygame simultaneously.
        if not self._seek_lock.acquire(blocking=True, timeout=2.0):
            return
        try:
            pygame.mixer.music.stop()
            if self._path:
                pygame.mixer.music.load(self._path)
            pygame.mixer.music.play(start=pos_s)
            pygame.mixer.music.set_volume(self._volume)
            time.sleep(0.05)
            raw_ms = pygame.mixer.music.get_pos()
            self._seek_offset = pos_s
            self._start_time = time.monotonic() - (max(0, raw_ms) / 1000.0)
            self._pos_cache = pos_s
            self._is_playing = True
            self._is_paused = False
            if was_paused:
                pygame.mixer.music.pause()
                self._is_playing = False
                self._is_paused = True
                self._seeked_while_paused = False
        except Exception as e:
            pass
        finally:
            self._seek_lock.release()

    def get_position(self):
        if not _PYGAME_OK:
            return self._pos_cache
        if self._is_playing:
            raw_ms = pygame.mixer.music.get_pos()
            if raw_ms >= 0:
                pos = self._seek_offset + raw_ms / 1000.0
            else:
                elapsed = time.monotonic() - self._start_time
                pos = self._seek_offset + elapsed
            if self._duration > 0:
                pos = min(pos, self._duration)
            self._pos_cache = pos
            return pos
        return self._pos_cache

    # ── done detection ─────────────────────────────────────────────────────────
    def is_done(self):
        """Return True when track has naturally finished."""
        if not _PYGAME_OK:
            return False
        if not self._is_playing and not self._is_paused:
            return False
        if self._duration > 0 and self.get_position() >= self._duration - 0.5:
            return True
        try:
            return not pygame.mixer.music.get_busy()
        except Exception:
            return False

    # ── volume ─────────────────────────────────────────────────────────────────
    def set_volume(self, vol):
        """Set volume. Accepts 0.0–1.0 float or 0–100 int."""
        if isinstance(vol, int) and vol > 1:
            vol = vol / 100.0
        vol = max(0.0, min(1.0, float(vol)))
        self._volume = vol
        if _PYGAME_OK:
            try:
                pygame.mixer.music.set_volume(vol)
            except Exception:
                pass

    # ── metadata ───────────────────────────────────────────────────────────────
    def get_metadata(self, path):
        """Return a dict with title, artist, album, duration. Uses mutagen."""
        meta = {
            "title": os.path.splitext(os.path.basename(path))[0],
            "artist": "",
            "album": "",
            "duration": 0.0,
        }
        if not MUTAGEN_AVAILABLE:
            return meta
        try:
            f = _MutagenFile(path, easy=True)
            if f is None:
                return meta
            meta["title"] = str(f.get("title", [meta["title"]])[0])
            meta["artist"] = str(f.get("artist", [""])[0])
            meta["album"] = str(f.get("album", [""])[0])
            meta["duration"] = getattr(f.info, "length", 0.0)
        except Exception:
            pass
        return meta

    # ── speed ──────────────────────────────────────────────────────────────────
    def set_speed(self, speed, on_done=None, on_error=None):
        """
        Change playback speed without pitch shift using scipy resampling.
        Runs in a background thread. Calls on_done() when ready, on_error(msg) on failure.
        """
        speed = round(float(speed), 2)

        if not SCIPY_AVAILABLE:
            if on_error:
                on_error("scipy/soundfile not available")
            return

        src_path = self._path
        if not src_path:
            if on_error:
                on_error("no track loaded")
            return

        self.get_position()
        was_paused = self._is_paused
        orig_dur = self._duration

        # Cancel token — if _path changes before we finish, abort
        expected_path = src_path

        def _worker():
            try:
                if speed == 1.0:
                    self._cleanup_speed_tmp()
                    self._speed = 1.0
                    snap_pos = self.get_position()
                    pygame.mixer.music.load(src_path)
                    pygame.mixer.music.play(start=snap_pos)
                    pygame.mixer.music.set_volume(self._volume)
                    self._path = src_path
                    self._duration = orig_dur
                    self._seek_offset = snap_pos
                    self._start_time = time.monotonic()
                    self._is_playing = True
                    self._is_paused = False
                    if was_paused:
                        pygame.mixer.music.pause()
                        self._is_playing = False
                        self._is_paused = True
                    if on_done:
                        on_done()
                    return

                # Decode via soundfile — handles MP3, FLAC, WAV, OGG, M4A etc.
                # (pygame.mixer.Sound can't decode most MP3s; audioop removed in Py 3.13)
                import tempfile
                try:
                    data_f, sr = _sf.read(src_path, always_2d=True, dtype="float32")
                except Exception as e:
                    if on_error:
                        on_error(f"soundfile decode failed: {e}")
                    return

                if self._path != expected_path:
                    return

                # Resample to achieve speed change without pitch shift
                orig_len = data_f.shape[0]
                new_len = max(1, int(round(orig_len / speed)))
                resampled = resample_poly(
                    data_f,
                    new_len,
                    orig_len,
                    axis=0,
                ).astype("float32")
                _np.clip(resampled, -1.0, 1.0, out=resampled)

                fd, tmp = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                _sf.write(tmp, resampled, sr, subtype="FLOAT")

                if self._path != expected_path:
                    try:
                        os.unlink(tmp)
                    except Exception:
                        pass
                    return

                snap_pos = self.get_position()
                adj_pos = snap_pos / speed
                new_dur = orig_dur / speed if orig_dur > 0 else 0.0

                self._cleanup_speed_tmp()
                self._speed_tmp = tmp
                self._speed = speed

                pygame.mixer.music.load(tmp)
                pygame.mixer.music.play(start=adj_pos)
                pygame.mixer.music.set_volume(self._volume)
                self._path = src_path
                self._duration = new_dur
                self._seek_offset = adj_pos
                self._start_time = time.monotonic()
                self._is_playing = True
                self._is_paused = False
                if was_paused:
                    pygame.mixer.music.pause()
                    self._is_playing = False
                    self._is_paused = True
                if on_done:
                    on_done()

            except Exception as e:
                import traceback

                traceback.print_exc()
                self._speed = 1.0
                if on_error:
                    on_error(str(e))

        threading.Thread(target=_worker, daemon=True).start()

    def _cleanup_speed_tmp(self):
        """Delete previous speed-resampled temp file if any."""
        if self._speed_tmp:
            try:
                os.unlink(self._speed_tmp)
            except Exception:
                pass
            self._speed_tmp = None

    # ── internal ───────────────────────────────────────────────────────────────
    def _read_duration(self, path):
        """Read track duration via mutagen, fallback to 0."""
        if MUTAGEN_AVAILABLE:
            try:
                f = _MutagenFile(path)
                if f and hasattr(f, "info"):
                    return float(f.info.length)
            except Exception:
                pass
        return 0.0


# ──────────────────────────────────────────────────────────────────────────────
#  EQ PROCESSOR
# ──────────────────────────────────────────────────────────────────────────────
class EQProcessor:
    """
    Apply an EQ preset to an audio file using scipy biquad IIR filters.
    Writes output to out_path (WAV). Returns True on success.

    Presets: lists of (freq_hz, gain_db, Q) peaking EQ bands.
    Keys match the UI dropdown values exactly (spaces, not underscores).
    """

    PRESETS = {
        # (freq_hz, gain_db, Q)
        "bass boost": [(60, 9, 0.8), (120, 6, 1.0), (250, 3, 1.2)],
        "treble boost": [(4000, 3, 1.0), (8000, 6, 0.9), (16000, 5, 1.0)],
        "vocal": [(250, -3, 1.2), (1000, 5, 1.5), (3000, 4, 1.0), (8000, 2, 1.0)],
        "electronic": [
            (60, 6, 0.8),
            (200, 3, 1.0),
            (2000, -2, 1.0),
            (8000, 4, 1.0),
            (16000, 3, 1.0),
        ],
        "rock": [
            (80, 5, 0.9),
            (200, 3, 1.0),
            (1000, -1, 1.0),
            (4000, 3, 1.0),
            (12000, 4, 1.0),
        ],
        "classical": [(80, 2, 1.2), (500, -1, 1.0), (2000, 1, 1.0), (8000, 2, 1.2)],
        "podcast": [(120, -4, 1.0), (1000, 3, 1.5), (3000, 4, 1.2), (8000, 2, 1.0)],
        "flat": [],
    }

    @classmethod
    def process(cls, in_path, preset_name, out_path):
        """Apply preset EQ to in_path, write to out_path. Returns True on success."""
        if not SCIPY_AVAILABLE:
            return False
        # Normalise name — handle legacy underscore keys from old saves
        name = preset_name.replace("_", " ")
        bands = cls.PRESETS.get(name, [])
        if not bands:
            return False
        try:
            import numpy as _np

            data, sr = _sf.read(in_path, always_2d=True)
            # Convert to float64 for filter precision
            data = data.astype(_np.float64)
            for freq, gain_db, Q in bands:
                data = cls._apply_peaking(data, sr, freq, gain_db, Q)
            # Clip to prevent clipping distortion, write as float32 WAV
            _np.clip(data, -1.0, 1.0, out=data)
            _sf.write(out_path, data.astype(_np.float32), sr, subtype="FLOAT")
            return True
        except Exception as e:
            log_exception("eq_processor.process", e)
            return False

    @staticmethod
    def _apply_peaking(data, sr, freq, gain_db, Q):
        """Apply a single peaking EQ band using Audio EQ Cookbook coefficients."""
        try:
            import numpy as _np

            w0 = 2.0 * _np.pi * freq / sr
            alpha = _np.sin(w0) / (2.0 * Q)
            A = 10.0 ** (gain_db / 40.0)
            cos_w0 = _np.cos(w0)
            b = _np.array([1.0 + alpha * A, -2.0 * cos_w0, 1.0 - alpha * A])
            a = _np.array([1.0 + alpha / A, -2.0 * cos_w0, 1.0 - alpha / A])
            # Normalise so a[0] = 1
            b /= a[0]
            a /= a[0]
            out = _np.empty_like(data)
            for ch in range(data.shape[1]):
                out[:, ch] = _signal.lfilter(b, a, data[:, ch])
            return out
        except Exception:
            return data


# ──────────────────────────────────────────────────────────────────────────────
#  UI SOUND EFFECTS
# ──────────────────────────────────────────────────────────────────────────────
class UISounds:
    """
    File-based UI sound effects using pygame.mixer.Sound.
    Looks for WAV files next to the package (or in a 'sounds' subfolder).
    Falls back silently if files are missing or pygame is unavailable.

    Expected files:
        Click, Hover_Sound, Play_button, Tab_Switch
    """

    _FILE_MAP = {
        "click":      "Click",
        "hover":      "Hover_Sound",
        "play":       "Play_button",
        "tab_switch": "Tab_Switch",
    }

    def __init__(self, sounds_dir=None, volume=0.18):
        self._vol = volume
        self._enabled = _PYGAME_OK
        self._sounds = {}

        if not self._enabled:
            return

        pkg_dir = Path(__file__).parent
        search = []
        if sounds_dir:
            search.append(Path(sounds_dir))
        search += [pkg_dir, pkg_dir / "sounds"]

        for name, fname in self._FILE_MAP.items():
            for d in search:
                # Try with .wav extension first, then without
                candidates = [d / (fname + ".wav"), d / fname]
                for p in candidates:
                    if p.exists():
                        try:
                            snd = pygame.mixer.Sound(str(p))
                            snd.set_volume(self._vol)
                            self._sounds[name] = snd
                        except Exception:
                            pass
                        break
                if name in self._sounds:
                    break

    def play(self, name):
        if not self._enabled:
            return
        snd = self._sounds.get(name)
        if snd:
            try:
                snd.play()
            except Exception:
                pass

    def set_volume(self, vol):
        self._vol = max(0.0, min(1.0, float(vol)))
        for snd in self._sounds.values():
            try:
                snd.set_volume(self._vol)
            except Exception:
                pass

    def set_enabled(self, v):
        self._enabled = bool(v) and _PYGAME_OK
