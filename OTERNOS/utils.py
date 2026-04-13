"""
utils.py — OTERNOS PLAYER
Merged from: constants.py + diagnostics.py + animation.py

  § 1  Global constants, palette, fonts, paths
  § 2  Logging + safe-call helpers  (was diagnostics.py)
  § 3  ColorAnim + FadeOverlay      (was animation.py)
"""

# ══════════════════════════════════════════════════════════════════════════════
#  § 1  CONSTANTS  (was constants.py)
# ══════════════════════════════════════════════════════════════════════════════
from pathlib import Path

# ── Last.fm credentials ───────────────────────────────────────────────────────
LASTFM_API_KEY    = ""
LASTFM_API_SECRET = ""
LASTFM_API_ROOT   = "https://ws.audioscrobbler.com/2.0/"

# ── Palette — White Void Cybercore ────────────────────────────────────────────
C = {
    "bg":      "#000000",
    "panel":   "#000000",
    "panel2":  "#050505",
    "border":  "#222222",
    "border2": "#3a3a3a",
    "white":   "#f0f0f0",
    "white2":  "#aaaaaa",
    "white3":  "#555555",
    "glow":    "#ffffff",
    "select":  "#111111",
    "select2": "#1a1a1a",
    "red":     "#ff3333",
    "accent":  "#2f2f2f",
}

# ── Hardware accelerator flag ─────────────────────────────────────────────────
HW_ACCEL = True

def hw_fps(hi, lo=8):
    """Return frame interval (ms) based on HW_ACCEL state."""
    return hi if HW_ACCEL else lo * 16

# ── Fonts ─────────────────────────────────────────────────────────────────────
FM  = ("Courier New", 9)
FMS = ("Courier New", 8)
FML = ("Courier New", 10, "bold")
FMX = ("Courier New", 13, "bold")

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_FILE = Path.home() / ".voidplayer.json"
YT_CACHE  = Path.home() / ".voidplayer_cache"
YT_CACHE.mkdir(exist_ok=True)

# ── Embedded app icon (base64 PNG) ────────────────────────────────────────────
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAEMElEQVR4nO1bubHjMAzF"
    "92ykEpTKZagOBarDZagOBarDZdipS1C8wQ48NAQSB0HbM39fsp6/EgQ8gjh4/MCb0HXd"
    "zfL8vu/nVrqk+Gkl2GqwhFaEnKIFdl130xq/LMvQQq4Ff6IEtVCu9J0oj6ieAl7DH4"
    "/Hc/T7vr97v19LhJuAmhFPjUfUkADgJ8IVA6KMX9eV/fs7dTJ7QAvjAQDmeX7+fueU"
    "UHtAbRQuGQ/wanSNN1j1VBFQG+E1AW9ZliGKBAC9zmIajBh1i0tzJHinRNd1N2lKiDHA"
    "Q0BJcan4uVwuh3dqiJAIKHqA1/jalEaB8jyyJS/IeoDV+Fp3bf2dHAksARbjOYUsNb4F"
    "6fTwEMGR4O4FcgosyzJw8zgCqex0WnB6aHEgQBr9d7m6FhYiuHiQrQOoGz8ej0HKzS1H"
    "H+DfFJCmF6dn6Z0XD0hH/3K53KmgdV3ZNPUNwJFflmWY5zlbfFEveAmC1P1RCFe6psCR"
    "0ZKDcqdpgm3bDkZIwG9J3oD9BZWbEvD0AG/FZzXa8oxEiIYEDqkXFHsBVCDt1DhIoz+O"
    "48EwlI2/OWNzpNWMPsUJoN3oY0Datg2maQJq6PV6fXnfQoJWhxzQZnU7nPtQbvRpEKLG"
    "5pB6Bicr1SfnBRZSRAJSRVLB2sDnqRc4EjhwOqS/Nd82L4lp2I0sllAGjSNe3Sh+NPOf"
    "68I0rg8QQ8I4jgOmy1yLTXXRdo7hGyMUtSs7AMdgGQkXAZa5/46ewVsPAAR7AJ37kvGY"
    "JjVeQpueKJgJiGp4qCG1hnm9IGxv0IKcsaXANY7jME1TuC6mLGApeUuBqzTapWmjSa+o"
    "Y5MsILnZtm2wbVvTqF2CZ3o2T4McciPziVUmVyWY8wJLpKbG5oxHWZL7e4PzR4IgQpMm"
    "039bwDUFNClHU7tLsK4Qeb5x8hwsKC1J9X1/p0tdNUhJKPUBnhpg3/ezqxCSnsEsEOG6"
    "ls7SQ4JIQGpE+gEt8zXzWLsMT/XSvg9giAFWdrkVHS0J4zi+9AfW9GjR9QTgP2AkeYFm"
    "jS8NltIaouXbElSrwtp9gRJyJKRdINcR1laTqLPkdc86YN/3s2d1OB2JXCqiJOSUit4Y"
    "ycG8M4SQtsZa7w1qvoFbYylUO0P4H0gCd2hpnmeY5/mrdocRpbXIlDQa7w4HJGq3x993"
    "PsCqF4IScOgFpFgQdTAhChY9uGz364/I/D8kVXqpxTE5zzlBrewcSoVecT3AUxv0fX+P"
    "9oaWByWbnBRFlE6Scc9z21vc+xZUnRRFAV4SuCUy7SqQ5lkJmh5H1Q3WXkuhBZWUy+k7"
    "Hmh1VrfD+76fa4iQDjxEXpiw6Om6MxR5f2Bd14/dFgH40KUpgPiLU17v/Ni1OYCYOV8b"
    "n6p3hmpiQ9/393Vd3fk94vJk2MYIKtP6Bmn0HeJff3m6GQEU33p9/i+ic9mwtWarfgAA"
    "AABJRU5ErkJggg=="
)

# ── Animation math ────────────────────────────────────────────────────────────
def _ease_out(t):
    """Cubic ease-out: fast start, smooth stop."""
    return 1 - (1 - t) ** 3

def _ease_in_out(t):
    """Smooth S-curve easing."""
    return t * t * (3 - 2 * t)

def _lerp(a, b, t):
    return a + (b - a) * t

def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def _rgb_to_hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

def _lerp_color(c1, c2, t):
    """Smoothly interpolate between two hex colors."""
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(_lerp(r1, r2, t), _lerp(g1, g2, t), _lerp(b1, b2, t))

# Public aliases
ease_out   = _ease_out
ease_in_out = _ease_in_out
lerp        = _lerp
lerp_color  = _lerp_color
hex_to_rgb  = _hex_to_rgb
rgb_to_hex  = _rgb_to_hex


# ══════════════════════════════════════════════════════════════════════════════
#  § 2  DIAGNOSTICS  (was diagnostics.py)
# ══════════════════════════════════════════════════════════════════════════════
import logging
from logging.handlers import RotatingFileHandler
import traceback
from typing import Any, Callable, Optional

_LOGGER: Optional[logging.Logger] = None


def get_log_path() -> Path:
    return Path.home() / ".voidplayer.log"


def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER
    logger = logging.getLogger("oternos")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(
            get_log_path(), maxBytes=512 * 1024, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(handler)
    _LOGGER = logger
    return logger


def set_debug(enabled: bool) -> None:
    get_logger().setLevel(logging.DEBUG if enabled else logging.INFO)


def log_exception(context: str, exc: BaseException) -> None:
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    get_logger().error("%s\n%s", context, tb)


def safe_call(
    context: str,
    fn: Callable[[], Any],
    *,
    on_error: Optional[Callable[[str], None]] = None,
    default: Any = None,
) -> Any:
    try:
        return fn()
    except Exception as exc:
        log_exception(context, exc)
        if on_error is not None:
            try:
                on_error(context)
            except Exception:
                pass
        return default


# ══════════════════════════════════════════════════════════════════════════════
#  § 3  ANIMATION  (was animation.py)
# ══════════════════════════════════════════════════════════════════════════════
import sys as _sys


class ColorAnim:
    """Animate a widget fg or bg color smoothly."""

    _jobs = {}

    @classmethod
    def run(
        cls, root, widget, attr, from_col, to_col,
        duration_ms=120, fps=30, ease_fn=_ease_out, on_done=None,
    ):
        wid = (id(widget), attr)
        if wid in cls._jobs:
            try:
                root.after_cancel(cls._jobs[wid])
            except Exception:
                pass
        steps = max(1, int(duration_ms / (1000 / fps)))
        delay = max(8, int(1000 / fps))

        def _step(i=0):
            if i > steps:
                try:
                    widget.config(**{attr: to_col})
                except Exception:
                    pass
                cls._jobs.pop(wid, None)
                if on_done:
                    on_done()
                return
            col = _lerp_color(from_col, to_col, ease_fn(i / steps))
            try:
                widget.config(**{attr: col})
            except Exception:
                pass
            cls._jobs[wid] = root.after(delay, lambda: _step(i + 1))

        _step()


class FadeOverlay:
    """
    Tab transition via background colour animation only — no overlays, no place().
    Fades content frame bg to black at midpoint (view swap), then back to app bg.
    """

    STEPS    = 6
    INTERVAL = 16
    BG       = "#050505"
    MID      = "#000000"

    def __init__(self, root, content_frame):
        self.root    = root
        self.frame   = content_frame
        self._active = False
        self._job    = None

    def flash(self, on_midpoint, duration_ms=None):
        if self._job:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

        self._active = True
        mid_done = [False]

        def _tick(step=0):
            total = self.STEPS * 2
            if step <= self.STEPS:
                t = step / self.STEPS
                col = _lerp_color(self.BG, self.MID, t * t)
            else:
                t = (step - self.STEPS) / self.STEPS
                col = _lerp_color(self.MID, self.BG, t * t)
            try:
                self.frame.configure(bg=col)
            except Exception:
                pass
            if step == self.STEPS and not mid_done[0]:
                mid_done[0] = True
                try:
                    on_midpoint()
                except Exception:
                    pass
            if step < total:
                self._job = self.root.after(self.INTERVAL, lambda: _tick(step + 1))
            else:
                try:
                    self.frame.configure(bg=self.BG)
                except Exception:
                    pass
                self._active = False
                self._job = None

        _tick(0)
