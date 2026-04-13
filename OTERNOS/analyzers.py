"""
analyzers.py — OTERNOS PLAYER
Real-time audio analyzers: Oscilloscope, LUFS Meter, Spectrum Analyzer,
Goniometer (stereo field), and EQ Curve Display.

All visualizers tap into the player's existing FFT/audio pipeline:
  - player._fft_bars       : 48-band live FFT (WASAPI loopback)
  - player._fft_file_bars  : 48-band file-decoded FFT (fallback)
  - player._get_fft_bars() : unified accessor

No extra dependencies — stdlib + tkinter only.
"""

from __future__ import annotations

import sys
import math
import time
import threading
import colorsys
from typing import Optional, List

try:
    import tkinter as tk
except ImportError:
    tk = None

if getattr(sys, "frozen", False):
    from oternos.utils import C, FM, FMS, FML, FMX
    from oternos.utils import log_exception
else:
    try:
        from .utils import C, FM, FMS, FML, FMX
        from .utils import log_exception
    except ImportError:
        C = {
            "bg": "#050505", "panel": "#0c0c0c", "border": "#1f1f1f",
            "border2": "#2e2e2e", "white": "#e8e8e8", "white2": "#9a9a9a",
            "white3": "#424242", "glow": "#ffffff", "select": "#1e1e1e",
            "select2": "#242424", "red": "#cc2222",
        }
        FM  = ("Courier New", 9)
        FMS = ("Courier New", 8)
        FML = ("Courier New", 10, "bold")
        FMX = ("Courier New", 13, "bold")
        def log_exception(c, e): pass


# ─────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────
def _lerp(a, b, t):
    return a + (b - a) * t

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

def _dim(hex_col, factor):
    """Dim a hex colour by factor (0-1)."""
    h = hex_col.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return _hex(r * factor, g * factor, b * factor)


# ─────────────────────────────────────────────────────────────────
#  BASE ANALYZER WIDGET
# ─────────────────────────────────────────────────────────────────
class _BaseAnalyzer:
    """Canvas-based analyzer that polls player FFT data."""
    INTERVAL = 33   # ~30fps default

    def __init__(self, parent, player, width=0, height=0, bg=None):
        self.player  = player
        self._active = False
        self._job    = None
        bg = bg or C["bg"]
        kw = dict(bg=bg, highlightthickness=0)
        if width:  kw["width"]  = width
        if height: kw["height"] = height
        self.cv = tk.Canvas(parent, **kw)

    def pack(self, **kw):
        self.cv.pack(**kw)
        # Force layout so winfo_width/height return real values sooner
        self.cv.update_idletasks()
        return self

    def start(self):
        self._active = True
        # Bind resize so we redraw immediately when canvas gets its real size
        self.cv.bind("<Configure>", lambda e: self._draw() if self._active else None)
        # Small delay to let tkinter finish layout before first draw
        self.cv.after(300, self._tick)

    def stop(self):
        self._active = False
        if self._job:
            try:
                self.cv.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _get_bars(self) -> List[float]:
        """Return 48 FFT magnitude bars (0.0–1.0) from player."""
        try:
            # Try real WASAPI FFT first
            if hasattr(self.player, "_fft_bars") and self.player._fft_bars is not None:
                with self.player._fft_lock:
                    bars = list(self.player._fft_bars)
                if max(bars) > 0.001:
                    return bars

            # Fall back to file-decode FFT
            if hasattr(self.player, "_fft_file_bars") and self.player._fft_file_bars:
                with self.player._fft_file_lock:
                    bars = list(self.player._fft_file_bars)
                if max(bars) > 0.001:
                    return bars

            # Fall back to _sim_bars if available
            if hasattr(self.player, "_sim_bars"):
                playing = getattr(self.player.engine, "is_playing", False)
                return self.player._sim_bars(time.time(), playing)

        except Exception:
            pass
        return [0.0] * 48

    def _tick(self):
        if not self._active:
            return
        try:
            if self.cv.winfo_exists():
                # Wait until canvas has been laid out and has real dimensions
                self.cv.update_idletasks()
                if self.cv.winfo_width() > 1 and self.cv.winfo_height() > 1:
                    self._draw()
        except Exception:
            pass
        self._job = self.cv.after(self.INTERVAL, self._tick)

    def _draw(self):
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────────
#  1. OSCILLOSCOPE
# ─────────────────────────────────────────────────────────────────
class OscilloscopeAnalyzer(_BaseAnalyzer):
    """
    Waveform / oscilloscope — synthesises a pseudo-waveform from FFT bars
    by treating each band as a sine component and summing them.
    Looks like the FL Studio oscilloscope panel.
    """
    INTERVAL = 16   # 60fps — oscilloscope needs to be smooth

    def __init__(self, parent, player, **kw):
        super().__init__(parent, player, **kw)
        self._phase   = 0.0
        self._history = []   # list of y-point lists for ghost trails
        self._smooth  = [0.0] * 48

    def _draw(self):
        cv = self.cv
        cv.delete("all")
        W = cv.winfo_width()  or 400
        H = cv.winfo_height() or 120
        if W < 2 or H < 2:
            return

        bars = self._get_bars()
        # No signal fallback
        if not any(b > 0.001 for b in bars):
            cv.create_text(W // 2, H // 2, text="NO SIGNAL",
                          font=("Courier New", 8), fill=C["white3"], anchor="center")
            cv.create_line(0, H // 2, W, H // 2, fill=C["border"], width=1)
            return
        for i, b in enumerate(bars):
            self._smooth[i] = _lerp(self._smooth[i], b, 0.25)

        cy = H // 2
        self._phase += 0.04

        # Build waveform by summing frequency components
        N = W
        pts = []
        for x in range(N):
            t = x / N
            y = 0.0
            for i, mag in enumerate(self._smooth):
                freq = 1.0 + i * 0.6
                y += mag * math.sin(2 * math.pi * freq * t + self._phase * (1 + i * 0.05))
            pts.append(y)

        # Normalize
        peak = max(abs(v) for v in pts) or 1.0
        amp  = (H * 0.42) / peak

        # Ghost trail (3 faded copies)
        self._history.append([cy - int(v * amp) for v in pts])
        if len(self._history) > 4:
            self._history.pop(0)

        for gi, ghost in enumerate(self._history[:-1]):
            alpha = (gi + 1) / len(self._history)
            col   = _dim(C["white"], alpha * 0.18)
            coords = []
            for x, y in enumerate(ghost):
                coords.extend([x, y])
            if len(coords) >= 4:
                cv.create_line(coords, fill=col, width=1, smooth=True)

        # Main waveform
        ys = [cy - int(v * amp) for v in pts]
        coords = []
        for x, y in enumerate(ys):
            coords.extend([x, y])
        if len(coords) >= 4:
            cv.create_line(coords, fill=C["white"], width=1, smooth=True)

        # Centre line
        cv.create_line(0, cy, W, cy, fill=C["border2"], width=1)

        # Label
        cv.create_text(6, 4, text="SCOPE", font=("Courier New", 6, "bold"),
                       fill=C["white3"], anchor="nw")

        # Energy dot
        energy = sum(self._smooth) / 48
        r = int(3 + energy * 8)
        peak_x = W - 16
        cv.create_oval(peak_x - r, cy - r, peak_x + r, cy + r,
                       fill=C["white"] if energy > 0.3 else C["white3"], outline="")


# ─────────────────────────────────────────────────────────────────
#  2. LUFS METER
# ─────────────────────────────────────────────────────────────────
class LUFSMeter(_BaseAnalyzer):
    """
    Integrated loudness meter styled like the FL Studio LUFS display.
    Estimates loudness from FFT energy — not a true K-weighting meter
    but visually accurate and music-reactive.
    """
    INTERVAL = 50   # 20fps is plenty for a meter

    def __init__(self, parent, player, **kw):
        super().__init__(parent, player, **kw)
        self._lufs_smooth  = -60.0
        self._peak_hold    = -60.0
        self._peak_timer   = 0
        self._history      = []   # rolling 3s of LUFS values

    def _estimate_lufs(self, bars):
        """Rough LUFS estimate from FFT bars using A-weighting approximation."""
        if not any(bars):
            return -60.0
        # A-weighting: boost 1-4kHz, cut lows and extreme highs
        # Map 48 bars to ~20Hz-20kHz log scale
        weights = []
        for i in range(48):
            freq = 20 * (20000 / 20) ** (i / 47)  # log freq
            # simplified A-weight curve
            if freq < 100:
                w = 0.1
            elif freq < 500:
                w = 0.4 + (freq - 100) / 400 * 0.4
            elif freq < 4000:
                w = 0.8 + (freq - 500) / 3500 * 0.2
            elif freq < 10000:
                w = 1.0 - (freq - 4000) / 6000 * 0.3
            else:
                w = 0.4
            weights.append(w)

        energy = sum(b * b * w for b, w in zip(bars, weights)) / 48
        if energy < 1e-10:
            return -60.0
        lufs = 10 * math.log10(energy) * 2.5 - 14
        return _clamp(lufs, -60.0, 0.0)

    def _draw(self):
        cv = self.cv
        cv.delete("all")
        W = cv.winfo_width()  or 80
        H = cv.winfo_height() or 200
        if W < 2 or H < 2:
            return

        bars = self._get_bars()
        lufs = self._estimate_lufs(bars)

        # Smooth
        spd  = 0.15 if lufs > self._lufs_smooth else 0.04
        self._lufs_smooth = _lerp(self._lufs_smooth, lufs, spd)

        # Peak hold
        if self._lufs_smooth > self._peak_hold:
            self._peak_hold  = self._lufs_smooth
            self._peak_timer = 60  # frames to hold
        elif self._peak_timer > 0:
            self._peak_timer -= 1
        else:
            self._peak_hold = _lerp(self._peak_hold, -60.0, 0.02)

        # History for integrated display
        self._history.append(self._lufs_smooth)
        if len(self._history) > 60:
            self._history.pop(0)

        # Draw scale
        LUFS_MIN = -60.0
        LUFS_MAX =   0.0
        bar_x   = W // 2 - 10
        bar_w   = 18
        bar_top = 28
        bar_bot = H - 32

        def lufs_to_y(v):
            t = (v - LUFS_MIN) / (LUFS_MAX - LUFS_MIN)
            return int(bar_bot - t * (bar_bot - bar_top))

        # Background track
        cv.create_rectangle(bar_x, bar_top, bar_x + bar_w, bar_bot,
                            fill=C["panel"], outline=C["border"])

        # Colour gradient segments
        seg_count = 40
        for s in range(seg_count):
            t    = s / seg_count
            v    = LUFS_MIN + t * (LUFS_MAX - LUFS_MIN)
            y1   = lufs_to_y(v + (LUFS_MAX - LUFS_MIN) / seg_count)
            y2   = lufs_to_y(v)
            active = v <= self._lufs_smooth
            if active:
                if v > -6:
                    col = "#cc2222"
                elif v > -14:
                    col = "#888822"
                else:
                    col = _hex(
                        int(40 + t * 60),
                        int(100 + t * 60),
                        int(40 + t * 20),
                    )
            else:
                col = C["select"]
            cv.create_rectangle(bar_x + 2, y1 + 1, bar_x + bar_w - 2, y2 - 1,
                                fill=col, outline="")

        # Peak hold line
        if self._peak_hold > LUFS_MIN:
            py  = lufs_to_y(self._peak_hold)
            col = "#cc2222" if self._peak_hold > -6 else C["white"]
            cv.create_line(bar_x, py, bar_x + bar_w, py, fill=col, width=2)

        # Scale ticks
        for v in (-60, -48, -36, -24, -18, -12, -9, -6, -3, 0):
            y   = lufs_to_y(v)
            col = C["white3"] if v % 12 == 0 else C["border2"]
            cv.create_line(bar_x - 3, y, bar_x, y, fill=col)
            if v % 12 == 0 or v in (-6, -3):
                cv.create_text(bar_x - 4, y, text=str(v), font=("Courier New", 5),
                               fill=C["white3"], anchor="e")

        # Numeric readout
        cv.create_text(W // 2, bar_bot + 10, anchor="n",
                       text=f"{self._lufs_smooth:.1f}", font=("Courier New", 8, "bold"),
                       fill=C["white"])
        cv.create_text(W // 2, bar_bot + 20, anchor="n",
                       text="LUFS", font=("Courier New", 6),
                       fill=C["white3"])
        cv.create_text(W // 2, bar_top - 14, anchor="n",
                       text="LUFS", font=("Courier New", 6, "bold"),
                       fill=C["white3"])

        # Integrated bar (small horizontal at top)
        if len(self._history) > 1:
            integrated = sum(self._history) / len(self._history)
            cv.create_text(W // 2, bar_top - 6, anchor="n",
                           text=f"INT {integrated:.1f}",
                           font=("Courier New", 5), fill=C["white3"])


# ─────────────────────────────────────────────────────────────────
#  3. SPECTRUM ANALYZER
# ─────────────────────────────────────────────────────────────────
class SpectrumAnalyzer(_BaseAnalyzer):
    """
    Frequency spectrum mountain — filled bars with peak dots,
    log-scaled frequency axis. Styled like FL Studio's spectrum display.
    """
    INTERVAL = 25   # ~40fps

    def __init__(self, parent, player, **kw):
        super().__init__(parent, player, **kw)
        self._smooth  = [0.0] * 48
        self._peaks   = [0.0] * 48
        self._p_timer = [0]   * 48

    def _draw(self):
        cv = self.cv
        cv.delete("all")
        W = cv.winfo_width()  or 400
        H = cv.winfo_height() or 160
        if W < 2 or H < 2:
            return

        bars = self._get_bars()
        N    = len(bars)

        # Smooth + peaks
        for i, b in enumerate(bars):
            spd = 0.3 if b > self._smooth[i] else 0.08
            self._smooth[i] = _lerp(self._smooth[i], b, spd)
            if self._smooth[i] > self._peaks[i]:
                self._peaks[i]   = self._smooth[i]
                self._p_timer[i] = 45
            elif self._p_timer[i] > 0:
                self._p_timer[i] -= 1
            else:
                self._peaks[i] = _lerp(self._peaks[i], 0.0, 0.04)

        # Grid lines
        for frac in (0.25, 0.5, 0.75):
            y = int(H * (1 - frac))
            cv.create_line(0, y, W, y, fill=C["border"], width=1)

        # Bars
        pad   = 2
        bw    = max(2, (W - pad * 2) // N)
        gap   = 1

        for i, mag in enumerate(self._smooth):
            x1  = pad + i * bw
            x2  = x1 + bw - gap
            bh  = int(mag * (H - 4))
            y1  = H - bh
            y2  = H

            # Colour: cold blue at bottom, white at top
            t   = mag
            r   = int(_lerp(30,  220, t))
            g   = int(_lerp(80,  220, t))
            b_  = int(_lerp(160, 255, t))
            col = _hex(r, g, b_)

            if bh > 0:
                cv.create_rectangle(x1, y1, x2, y2, fill=col, outline="")

            # Peak dot
            if self._peaks[i] > 0.01:
                py = H - int(self._peaks[i] * (H - 4))
                cv.create_rectangle(x1, py - 1, x2, py + 1,
                                   fill=C["white"], outline="")

        # Frequency labels
        freq_labels = {0: "20", 6: "100", 12: "500", 18: "1k",
                       24: "2k", 30: "5k", 36: "10k", 42: "16k", 47: "20k"}
        for idx, lbl in freq_labels.items():
            x = pad + idx * bw + bw // 2
            cv.create_text(x, H - 2, text=lbl, font=("Courier New", 5),
                           fill=C["white3"], anchor="s")

        # Label
        cv.create_text(4, 4, text="SPECTRUM", font=("Courier New", 6, "bold"),
                       fill=C["white3"], anchor="nw")


# ─────────────────────────────────────────────────────────────────
#  4. GONIOMETER (STEREO FIELD)
# ─────────────────────────────────────────────────────────────────
class Goniometer(_BaseAnalyzer):
    """
    Stereo field / goniometer — Lissajous-style dot cloud showing
    stereo width and phase. Synthesised from FFT since we don't have
    raw PCM — uses odd/even bands as L/R proxies.
    """
    INTERVAL = 25

    def __init__(self, parent, player, **kw):
        super().__init__(parent, player, **kw)
        self._dots   = []    # list of (x, y, age)
        self._phase  = 0.0
        self._smooth = [0.0] * 48

    def _draw(self):
        cv = self.cv
        cv.delete("all")
        W = cv.winfo_width()  or 200
        H = cv.winfo_height() or 200
        if W < 2 or H < 2:
            return

        cx, cy = W // 2, H // 2
        r      = min(cx, cy) - 8

        bars = self._get_bars()
        for i, b in enumerate(bars):
            self._smooth[i] = _lerp(self._smooth[i], b, 0.2)

        self._phase += 0.03

        # Crosshair + circle
        cv.create_oval(cx - r, cy - r, cx + r, cy + r,
                       outline=C["border"], width=1)
        cv.create_line(cx - r, cy, cx + r, cy, fill=C["border"], width=1)
        cv.create_line(cx, cy - r, cx, cy + r, fill=C["border"], width=1)
        # Diagonal guides
        d = int(r * 0.707)
        cv.create_line(cx - d, cy - d, cx + d, cy + d, fill=C["border"], width=1)
        cv.create_line(cx - d, cy + d, cx + d, cy - d, fill=C["border"], width=1)

        # Generate dots from FFT
        # odd bars → L channel proxy, even bars → R channel proxy
        energy = sum(self._smooth) / 48
        if energy > 0.005:
            new_dots = []
            for i in range(0, 48, 2):
                l = self._smooth[i]     if i < 48 else 0.0
                r_ = self._smooth[i+1] if i+1 < 48 else 0.0

                # Add phase wobble based on freq band
                ph = self._phase * (1 + i * 0.03)
                l_v = l * math.sin(ph)
                r_v = r_ * math.cos(ph)

                # Goniometer rotation: 45 degrees
                # mid = L+R, side = L-R
                mid  = (l_v + r_v) * 0.5
                side = (l_v - r_v) * 0.5

                px = cx + int(side * r * 1.4)
                py = cy - int(mid  * r * 1.4)

                px = _clamp(px, cx - r, cx + r)
                py = _clamp(py, cy - r, cy + r)

                mag = (l + r_) / 2
                new_dots.append((px, py, mag))

            self._dots = new_dots

        # Fade old dots + draw
        for px, py, mag in self._dots:
            sz  = max(1, int(mag * 3))
            bright = int(60 + mag * 180)
            bright = min(255, bright)
            col = _hex(bright, bright, bright)
            cv.create_oval(px - sz, py - sz, px + sz, py + sz,
                          fill=col, outline="")

        # Corner labels
        cv.create_text(cx - r - 2, cy, text="L", font=("Courier New", 6),
                       fill=C["white3"], anchor="e")
        cv.create_text(cx + r + 2, cy, text="R", font=("Courier New", 6),
                       fill=C["white3"], anchor="w")
        cv.create_text(cx, cy - r - 2, text="+", font=("Courier New", 6),
                       fill=C["white3"], anchor="s")
        cv.create_text(cx, cy + r + 2, text="−", font=("Courier New", 6),
                       fill=C["white3"], anchor="n")

        # Label
        cv.create_text(4, 4, text="GONIO", font=("Courier New", 6, "bold"),
                       fill=C["white3"], anchor="nw")

        # Stereo width readout
        if len(self._smooth) >= 2:
            l_e = sum(self._smooth[0::2]) / 24
            r_e = sum(self._smooth[1::2]) / 24
            diff = abs(l_e - r_e)
            width_pct = int(_clamp(diff * 500, 0, 100))
            cv.create_text(cx, H - 4, text=f"WIDTH {width_pct}%",
                           font=("Courier New", 6), fill=C["white3"], anchor="s")


# ─────────────────────────────────────────────────────────────────
#  5. EQ CURVE DISPLAY
# ─────────────────────────────────────────────────────────────────
class EQCurveDisplay(_BaseAnalyzer):
    """
    Smooth EQ curve — frequency response line with filled area beneath.
    Reacts to music like FL Studio's parametric EQ display.
    """
    INTERVAL = 33

    def __init__(self, parent, player, **kw):
        super().__init__(parent, player, **kw)
        self._smooth  = [0.0] * 48
        self._history = []

    def _draw(self):
        cv = self.cv
        cv.delete("all")
        W = cv.winfo_width()  or 400
        H = cv.winfo_height() or 120
        if W < 2 or H < 2:
            return

        bars = self._get_bars()
        for i, b in enumerate(bars):
            self._smooth[i] = _lerp(self._smooth[i], b, 0.12)

        N  = len(self._smooth)
        bw = W / N

        # Grid
        for frac in (0.25, 0.5, 0.75):
            y = int(H * frac)
            cv.create_line(0, y, W, y, fill=C["border"], width=1)

        # dB labels on right
        for db, frac in [("0dB", 0.0), ("-12", 0.25), ("-24", 0.5),
                         ("-36", 0.75), ("-inf", 0.97)]:
            y = int(H * frac)
            cv.create_text(W - 2, y, text=db, font=("Courier New", 5),
                           fill=C["border2"], anchor="e")

        # Build smooth curve points
        pts = []
        for i, mag in enumerate(self._smooth):
            x = int((i + 0.5) * bw)
            y = int(H * (1.0 - mag * 0.92) - 2)
            pts.append((x, y))

        if len(pts) < 2:
            return

        # Filled area
        poly = []
        for x, y in pts:
            poly.extend([x, y])
        poly.extend([pts[-1][0], H, pts[0][0], H])
        cv.create_polygon(poly, fill=_dim(C["white"], 0.06), outline="")

        # Ghost history lines
        self._history.append(list(pts))
        if len(self._history) > 5:
            self._history.pop(0)

        for gi, ghost in enumerate(self._history[:-1]):
            alpha = (gi + 1) / len(self._history) * 0.12
            col   = _dim(C["white"], alpha)
            coords = []
            for x, y in ghost:
                coords.extend([x, y])
            if len(coords) >= 4:
                cv.create_line(coords, fill=col, width=1, smooth=True)

        # Main curve line
        coords = []
        for x, y in pts:
            coords.extend([x, y])
        cv.create_line(coords, fill=C["white"], width=2, smooth=True)

        # Dot at peak frequency
        peak_i = self._smooth.index(max(self._smooth))
        px, py = pts[peak_i]
        cv.create_oval(px - 3, py - 3, px + 3, py + 3,
                       fill=C["white"], outline="")

        # Freq labels
        freq_labels = {0: "20Hz", 8: "200", 16: "1k", 24: "2k",
                       32: "8k", 40: "16k", 47: "20k"}
        for idx, lbl in freq_labels.items():
            if idx < len(pts):
                x, _ = pts[idx]
                cv.create_text(x, H - 1, text=lbl, font=("Courier New", 5),
                               fill=C["white3"], anchor="s")

        # Label
        cv.create_text(4, 4, text="EQ CURVE", font=("Courier New", 6, "bold"),
                       fill=C["white3"], anchor="nw")


# ─────────────────────────────────────────────────────────────────
#  ANALYZER VIEW  (full tab panel)
# ─────────────────────────────────────────────────────────────────
class AnalyzerView:
    """
    Builds the ANALYZE tab content and manages all 5 analyzer widgets.
    Call build(parent) to get the frame, start() when tab is shown,
    stop() when tab is hidden.
    """

    def __init__(self, player):
        self.player   = player
        self.frame    = None
        self._widgets: List[_BaseAnalyzer] = []
        self._running = False

    def build(self, parent) -> tk.Frame:
        self.frame = tk.Frame(parent, bg=C["bg"])
        self._build_header()
        self._build_body()
        return self.frame

    def _build_header(self):
        top = tk.Frame(self.frame, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(top, text="ANALYZERS", font=FMX,
                 fg=C["white"], bg=C["bg"]).pack(side="left")
        tk.Label(top, text="real-time audio analysis", font=FMS,
                 fg=C["white3"], bg=C["bg"]).pack(side="left", padx=12)
        tk.Frame(self.frame, bg=C["border"], height=1).pack(
            fill="x", pady=(8, 0))

    def _build_body(self):
        body = tk.Frame(self.frame, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=12, pady=8)

        # ── Row 0: Oscilloscope + LUFS ────────────────────────────────
        row0 = tk.Frame(body, bg=C["bg"])
        row0.pack(fill="x", pady=(0, 6))

        scope_outer = tk.Frame(row0, bg=C["border2"])
        scope_outer.pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Label(scope_outer, text="OSCILLOSCOPE", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["panel"]).pack(anchor="w", padx=6, pady=(3, 0))
        tk.Frame(scope_outer, bg=C["border"], height=1).pack(fill="x", padx=4)
        scope = OscilloscopeAnalyzer(scope_outer, self.player)
        scope.cv.config(height=120)
        scope.cv.pack(fill="x", padx=4, pady=4)
        self._widgets.append(scope)

        lufs_outer = tk.Frame(row0, bg=C["border2"])
        lufs_outer.pack(side="left")
        tk.Label(lufs_outer, text="LUFS", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["panel"]).pack(anchor="w", padx=6, pady=(3, 0))
        tk.Frame(lufs_outer, bg=C["border"], height=1).pack(fill="x", padx=4)
        lufs = LUFSMeter(lufs_outer, self.player, width=90, height=120)
        lufs.cv.pack(padx=4, pady=4)
        self._widgets.append(lufs)

        # ── Row 1: Spectrum + Goniometer ─────────────────────────────
        row1 = tk.Frame(body, bg=C["bg"])
        row1.pack(fill="x", pady=(0, 6))

        spec_outer = tk.Frame(row1, bg=C["border2"])
        spec_outer.pack(side="left", fill="x", expand=True, padx=(0, 4))
        tk.Label(spec_outer, text="SPECTRUM", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["panel"]).pack(anchor="w", padx=6, pady=(3, 0))
        tk.Frame(spec_outer, bg=C["border"], height=1).pack(fill="x", padx=4)
        spec = SpectrumAnalyzer(spec_outer, self.player)
        spec.cv.config(height=140)
        spec.cv.pack(fill="x", padx=4, pady=4)
        self._widgets.append(spec)

        gonio_outer = tk.Frame(row1, bg=C["border2"])
        gonio_outer.pack(side="left")
        tk.Label(gonio_outer, text="GONIOMETER", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["panel"]).pack(anchor="w", padx=6, pady=(3, 0))
        tk.Frame(gonio_outer, bg=C["border"], height=1).pack(fill="x", padx=4)
        gonio = Goniometer(gonio_outer, self.player, width=160, height=160)
        gonio.cv.pack(padx=4, pady=4)
        self._widgets.append(gonio)

        # ── Row 2: EQ Curve ───────────────────────────────────────────
        row2 = tk.Frame(body, bg=C["bg"])
        row2.pack(fill="x")

        eq_outer = tk.Frame(row2, bg=C["border2"])
        eq_outer.pack(fill="x")
        tk.Label(eq_outer, text="EQ CURVE", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["panel"]).pack(anchor="w", padx=6, pady=(3, 0))
        tk.Frame(eq_outer, bg=C["border"], height=1).pack(fill="x", padx=4)
        eq = EQCurveDisplay(eq_outer, self.player)
        eq.cv.config(height=110)
        eq.cv.pack(fill="x", padx=4, pady=4)
        self._widgets.append(eq)

    def _panel(self, parent, label: str) -> tk.Frame:
        """Bordered panel with a label header. Returns inner frame."""
        outer = tk.Frame(parent, bg=C["border2"], bd=0)
        inner = tk.Frame(outer, bg=C["panel"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        inner.columnconfigure(0, weight=1)
        # Row 0 = header, row 1 = canvas (weight=1 so it expands)
        inner.rowconfigure(0, weight=0)
        inner.rowconfigure(1, weight=1)
        hdr = tk.Frame(inner, bg=C["panel"])
        hdr.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))
        tk.Label(hdr, text=label, font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["panel"]).pack(side="left")
        tk.Frame(inner, bg=C["border"], height=1).grid(
            row=0, column=0, sticky="ew", padx=4, pady=(22, 0))
        return inner

    def on_view_shown(self):
        # Frame is now visible — force full layout propagation
        if self.frame and self.frame.winfo_exists():
            self.frame.update_idletasks()
            self.frame.winfo_toplevel().update_idletasks()
        self.start()

    def start(self):
        if self._running:
            return
        self._running = True
        for w in self._widgets:
            try:
                w.cv.update_idletasks()
                w.start()
            except Exception:
                pass

    def stop(self):
        self._running = False
        for w in self._widgets:
            try:
                w.stop()
            except Exception:
                pass

    def cleanup(self):
        self.stop()
