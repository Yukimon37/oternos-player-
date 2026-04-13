"""
cyberui.py — OTERNOS PLAYER
Animated cybercore UI elements — drop-in additions to the existing player.

New widgets:
  HexGrid          — animated hex tessellation background for content area
  GlitchText       — label that randomly corrupts characters and self-repairs
  ScanlineOverlay  — CRT scanline + phosphor glow on any canvas
  CircuitLines     — PCB trace network that pulses with music energy
  DataStream       — vertical falling encrypted data columns (per-widget Matrix)
  RadarSweep       — rotating radar/sonar ring with blips
  FrequencyRing    — circular FFT spectrum ring (alternative to bar visualizer)
  StatusMatrix     — scrolling system status readout (fake syslog feed)
  BinaryRain       — horizontal binary rain strip for the topbar/sidebar
  NodeGraph        — animated node-edge network graph that reacts to BPM
  TerminalCursor   — blinking block cursor with typewriter text
  GlowBorder       — animated glow border around any frame

Integration:
  All widgets are self-contained tk.Canvas subclasses or tk.Frame wrappers.
  Import from .cyberui and pack anywhere.
  All respect HW_ACCEL and call .destroy() cleanly.

  To wire into player.py see INTEGRATION NOTES at bottom.
"""

from __future__ import annotations

import sys
import math
import random
import time
import threading
import tkinter as tk
from typing import Optional, List, Tuple

if getattr(sys, "frozen", False):
    from oternos.utils import C, HW_ACCEL, _lerp_color
else:
    try:
        from .utils import C, HW_ACCEL, _lerp_color
    except ImportError:
        C = {"bg":"#050505","panel":"#0c0c0c","border":"#1f1f1f","border2":"#2e2e2e",
             "white":"#e8e8e8","white2":"#9a9a9a","white3":"#424242","glow":"#ffffff",
             "select":"#1e1e1e","select2":"#242424","red":"#cc2222"}
        HW_ACCEL = True
        def _lerp_color(c1, c2, t):
            def h(c): return tuple(int(c.lstrip("#")[i:i+2],16) for i in (0,2,4))
            r1,g1,b1 = h(c1); r2,g2,b2 = h(c2)
            return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"

_FAST = 30 if HW_ACCEL else 80
_MED  = 50 if HW_ACCEL else 150
_SLOW = 80 if HW_ACCEL else 250


# ─────────────────────────────────────────────────────────────────────────────
#  GLITCH TEXT  — label that randomly corrupts and self-repairs
# ─────────────────────────────────────────────────────────────────────────────
class GlitchText(tk.Canvas):
    """
    A text label that randomly corrupts 1–2 characters into random symbols
    then repairs them. Intensity scales with energy (0–1).

    Usage:
        g = GlitchText(parent, text="OTERNOS", font=("Courier New",12,"bold"),
                       fg=C["white"], bg=C["bg"], width=120, height=24)
        g.pack()
        g.set_energy(0.8)   # call from _spec_tick with FFT energy
    """

    _GLYPHS = "▓▒░█▄▀■□▪▫◈◉○●◆◇△▽◁▷⊕⊗⊘01XZ#@%&!?/|"

    def __init__(self, parent, text="", font=None, fg=None, bg=None,
                 width=200, height=22, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._text   = text
        self._shown  = list(text)
        self._font   = font or ("Courier New", 10, "bold")
        self._fg     = fg or C["white"]
        self._bg     = bg
        self._energy = 0.0
        self._alive  = True
        self._glitch_indices: List[int] = []
        self._repair_countdown: dict = {}
        self._draw()

    def set_text(self, text: str):
        self._text  = text
        self._shown = list(text)
        self._glitch_indices.clear()
        self._repair_countdown.clear()

    def set_energy(self, energy: float):
        self._energy = max(0.0, min(1.0, float(energy)))

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            # Random glitch
            if self._text and random.random() < self._energy * 0.18:
                idx = random.randint(0, len(self._text) - 1)
                if idx not in self._glitch_indices:
                    self._glitch_indices.append(idx)
                    self._shown[idx] = random.choice(self._GLYPHS)
                    self._repair_countdown[idx] = random.randint(3, 12)

            # Repair
            for idx in list(self._glitch_indices):
                self._repair_countdown[idx] -= 1
                if self._repair_countdown[idx] <= 0:
                    self._shown[idx] = self._text[idx]
                    self._glitch_indices.remove(idx)
                    del self._repair_countdown[idx]

            self.delete("all")
            W = self.winfo_width() or int(self["width"])
            H = self.winfo_height() or int(self["height"])

            # Draw each character with individual colour for glitched ones
            # Approximate character width
            text = "".join(self._shown)
            # Glitched chars in red/white flash
            if self._glitch_indices:
                # Draw base text
                self.create_text(W // 2, H // 2, text=text,
                                 font=self._font, fill=self._fg, anchor="center")
                # Overdraw glitched chars slightly offset for chromatic aberration
                for idx in self._glitch_indices:
                    "".join(self._shown[:idx])
                    char = self._shown[idx]
                    # Rough x position
                    char_w = 8  # approximate monospace char width
                    x = (W // 2 - len(self._shown) * char_w // 2 +
                         idx * char_w + char_w // 2)
                    self.create_text(x + 1, H // 2 + 1, text=char,
                                     font=self._font, fill=C["red"], anchor="center")
                    self.create_text(x, H // 2, text=char,
                                     font=self._font, fill=C["glow"], anchor="center")
            else:
                self.create_text(W // 2, H // 2, text=text,
                                 font=self._font, fill=self._fg, anchor="center")
        except Exception:
            pass

        if self._alive:
            self.after(_FAST, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  CIRCUIT LINES  — PCB trace network that pulses with energy
# ─────────────────────────────────────────────────────────────────────────────
class CircuitLines(tk.Canvas):
    """
    Animated PCB-style trace network. Traces pulse with a travelling light dot.
    Great as a background element in the sidebar or below the playerbar.

    Usage:
        c = CircuitLines(parent, width=200, height=80)
        c.pack(fill="x")
        c.set_energy(0.6)
    """

    def __init__(self, parent, width=200, height=60, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg     = bg
        self._energy = 0.0
        self._alive  = True
        self.t       = 0
        self._traces: List[dict] = []
        self._nodes:  List[Tuple[int,int]] = []
        self._build(width, height)
        self._draw()

    def _build(self, W: int, H: int):
        """Generate a random Manhattan-style trace network."""
        rng = random.Random(42)
        # Grid nodes
        cols, rows = max(2, W // 40), max(2, H // 20)
        nodes = []
        for r in range(rows + 1):
            for c in range(cols + 1):
                jx = rng.randint(-8, 8)
                jy = rng.randint(-4, 4)
                x = int(c / cols * W) + jx
                y = int(r / rows * H) + jy
                nodes.append((max(0,min(W,x)), max(0,min(H,y))))
        self._nodes = nodes

        # Traces: random Manhattan paths between nearby nodes
        traces = []
        used = set()
        for i, (x1,y1) in enumerate(nodes):
            for j, (x2,y2) in enumerate(nodes):
                if i >= j:
                    continue
                dist = abs(x1-x2) + abs(y1-y2)
                if dist > W * 0.45:
                    continue
                key = (min(i,j), max(i,j))
                if key in used:
                    continue
                used.add(key)
                # Manhattan bend
                bend_x = x2
                bend_y = y1
                traces.append({
                    "pts": [(x1,y1),(bend_x,bend_y),(x2,y2)],
                    "phase": rng.uniform(0, math.pi*2),
                    "speed": rng.uniform(0.02, 0.06),
                    "pulse_pos": rng.uniform(0, 1.0),
                })
        self._traces = traces[:28]   # cap count

    def set_energy(self, energy: float):
        self._energy = max(0.0, min(1.0, float(energy)))

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            e = self._energy

            base_br = int(18 + e * 22)
            base_col = f"#{base_br:02x}{base_br:02x}{base_br:02x}"

            for tr in self._traces:
                pts = tr["pts"]
                # Draw trace lines
                for k in range(len(pts)-1):
                    x1,y1 = pts[k]; x2,y2 = pts[k+1]
                    self.create_line(x1,y1,x2,y2, fill=base_col, width=1)

                # Travelling pulse dot
                tr["pulse_pos"] = (tr["pulse_pos"] +
                                   tr["speed"] * (1.0 + e * 2)) % 1.0
                pos = tr["pulse_pos"]
                # Find point along path
                total_len = sum(
                    abs(pts[k+1][0]-pts[k][0]) + abs(pts[k+1][1]-pts[k][1])
                    for k in range(len(pts)-1)
                )
                if total_len < 1:
                    continue
                target = pos * total_len
                acc = 0
                px, py = pts[0]
                for k in range(len(pts)-1):
                    seg_len = (abs(pts[k+1][0]-pts[k][0]) +
                               abs(pts[k+1][1]-pts[k][1]))
                    if acc + seg_len >= target:
                        frac = (target - acc) / max(1, seg_len)
                        px = pts[k][0] + (pts[k+1][0]-pts[k][0]) * frac
                        py = pts[k][1] + (pts[k+1][1]-pts[k][1]) * frac
                        break
                    acc += seg_len

                pulse_br = int(60 + e * 180)
                pulse_br = min(255, pulse_br)
                pcol = f"#{pulse_br:02x}{pulse_br:02x}{pulse_br:02x}"
                r = 2 + e * 1.5
                self.create_oval(px-r, py-r, px+r, py+r,
                                 fill=pcol, outline="")

            # Node dots
            for nx, ny in self._nodes:
                br = int(25 + e * 30)
                nc = f"#{br:02x}{br:02x}{br:02x}"
                self.create_oval(nx-2, ny-2, nx+2, ny+2, fill=nc, outline="")

        except Exception:
            pass

        self.t += 1
        if self._alive:
            self.after(_MED, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  RADAR SWEEP  — rotating sonar ring with random blips
# ─────────────────────────────────────────────────────────────────────────────
class RadarSweep(tk.Canvas):
    """
    Rotating radar ring with fading sweep trail and random target blips.
    Blip frequency increases with energy.

    Usage:
        r = RadarSweep(parent, size=120)
        r.pack()
        r.set_energy(0.5)
    """

    def __init__(self, parent, size=100, bg=None, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self._size   = size
        self._bg     = bg
        self._energy = 0.0
        self._alive  = True
        self.t       = 0
        self._blips: List[dict] = []
        self._draw()

    def set_energy(self, energy: float):
        self._energy = max(0.0, min(1.0, float(energy)))

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            S  = self._size
            cx = cy = S / 2
            R  = S * 0.44
            t  = self.t
            e  = self._energy

            # Concentric rings
            for i in range(4):
                r = R * (i + 1) / 4
                br = int(12 + i * 6)
                self.create_oval(cx-r, cy-r, cx+r, cy+r,
                                 outline=f"#{br:02x}{br:02x}{br:02x}", width=1)

            # Cross hairs
            lbr = 18
            lc  = f"#{lbr:02x}{lbr:02x}{lbr:02x}"
            self.create_line(cx-R, cy, cx+R, cy, fill=lc, width=1)
            self.create_line(cx, cy-R, cx, cy+R, fill=lc, width=1)

            # Sweep — sector fill with fading trail
            sweep_speed = 0.025 + e * 0.03
            sweep_angle = (t * sweep_speed) % (2 * math.pi)
            trail_arc   = math.pi * 0.55   # how wide the trail is

            n_trail = 18
            for i in range(n_trail):
                frac  = i / n_trail
                angle = sweep_angle - trail_arc * (1 - frac)
                # Alpha via brightness
                br    = int(frac * (30 + e * 60))
                br    = min(255, br)
                col   = f"#{br:02x}{br:02x}{br:02x}"
                # Draw thin sector line from centre
                lx = cx + R * math.cos(angle)
                ly = cy + R * math.sin(angle)
                self.create_line(cx, cy, lx, ly, fill=col, width=1)

            # Sweep leading edge — bright line
            br_lead = int(80 + e * 175)
            lx = cx + R * math.cos(sweep_angle)
            ly = cy + R * math.sin(sweep_angle)
            self.create_line(cx, cy, lx, ly,
                             fill=f"#{br_lead:02x}{br_lead:02x}{br_lead:02x}",
                             width=2)

            # Spawn new blips under sweep
            if random.random() < 0.04 + e * 0.12:
                dist_frac = random.uniform(0.25, 0.92)
                ang_off   = random.uniform(-0.05, 0.05)
                self._blips.append({
                    "angle": sweep_angle + ang_off,
                    "dist":  dist_frac,
                    "life":  random.randint(18, 55),
                    "max_life": 55,
                })

            # Draw and age blips
            for blip in self._blips[:]:
                frac = blip["life"] / blip["max_life"]
                br   = int(frac * (100 + e * 155))
                br   = min(255, br)
                bx   = cx + R * blip["dist"] * math.cos(blip["angle"])
                by_  = cy + R * blip["dist"] * math.sin(blip["angle"])
                br2  = max(1, int(frac * 3))
                self.create_oval(bx-br2, by_-br2, bx+br2, by_+br2,
                                 fill=f"#{br:02x}{br:02x}{br:02x}", outline="")
                blip["life"] -= 1
                if blip["life"] <= 0:
                    self._blips.remove(blip)

            # Centre dot
            cr = 2 + e * 1.5
            cbr = int(80 + e * 175)
            self.create_oval(cx-cr, cy-cr, cx+cr, cy+cr,
                             fill=f"#{cbr:02x}{cbr:02x}{cbr:02x}", outline="")

        except Exception:
            pass

        self.t += 1
        if self._alive:
            self.after(_FAST, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  FREQUENCY RING  — circular FFT spectrum
# ─────────────────────────────────────────────────────────────────────────────
class FrequencyRing(tk.Canvas):
    """
    Circular spectrum ring. Bars radiate outward from a centre ring.
    Feed it the same FFT bar data as WaveVisualizer.

    Usage:
        fr = FrequencyRing(parent, size=140)
        fr.pack()
        fr.update_bars([0.1, 0.8, 0.3, ...])   # list of 0-1 values
    """

    def __init__(self, parent, size=120, bg=None, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self._size   = size
        self._bg     = bg
        self._bars   = [0.0] * 48
        self._smooth = [0.0] * 48
        self._alive  = True
        self.t       = 0
        self._draw()

    def update_bars(self, bars: list):
        n = min(len(bars), len(self._bars))
        for i in range(n):
            self._bars[i] = float(bars[i])

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            S  = self._size
            cx = cy = S / 2
            R  = S * 0.32   # inner ring radius
            t  = self.t

            # Smooth bars
            for i in range(len(self._bars)):
                self._smooth[i] += (self._bars[i] - self._smooth[i]) * 0.22

            n = len(self._smooth)

            # Inner ring
            self.create_oval(cx-R, cy-R, cx+R, cy+R,
                             outline=C["border2"], width=1)

            # Bars
            for i, val in enumerate(self._smooth):
                angle  = i / n * math.pi * 2 - math.pi / 2
                bar_h  = val * S * 0.28
                x0 = cx + R * math.cos(angle)
                y0 = cy + R * math.sin(angle)
                x1 = cx + (R + bar_h) * math.cos(angle)
                y1 = cy + (R + bar_h) * math.sin(angle)

                br  = int(30 + val * 210)
                br  = min(255, br)
                lw  = max(1, int(1 + val * 2))
                col = f"#{br:02x}{br:02x}{br:02x}"
                self.create_line(x0, y0, x1, y1, fill=col, width=lw)

            # Rotating accent ring
            rot = t * 0.008
            ring_r = R * 0.72
            n_ticks = 24
            for i in range(n_ticks):
                a   = i / n_ticks * math.pi * 2 + rot
                br  = 35 if i % 6 != 0 else 65
                r1  = ring_r
                r2  = ring_r * (0.82 if i % 6 == 0 else 0.92)
                self.create_line(
                    cx + r1*math.cos(a), cy + r1*math.sin(a),
                    cx + r2*math.cos(a), cy + r2*math.sin(a),
                    fill=f"#{br:02x}{br:02x}{br:02x}", width=1,
                )

            # Centre dot
            energy = sum(self._smooth) / max(1, len(self._smooth))
            cr  = 2 + energy * 3
            cbr = int(60 + energy * 190)
            cbr = min(255, cbr)
            self.create_oval(cx-cr, cy-cr, cx+cr, cy+cr,
                             fill=f"#{cbr:02x}{cbr:02x}{cbr:02x}", outline="")

        except Exception:
            pass

        self.t += 1
        if self._alive:
            self.after(_FAST, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  STATUS MATRIX  — scrolling fake syslog / system readout
# ─────────────────────────────────────────────────────────────────────────────
class StatusMatrix(tk.Canvas):
    """
    Scrolling system status feed — fake syslog lines that scroll upward.
    Mix of real player data and cyberpunk-flavoured noise.

    Usage:
        sm = StatusMatrix(parent, width=300, height=80)
        sm.pack()
        sm.push("TRACK LOADED: some_song.mp3")   # inject a real line
    """

    _NOISE = [
        "SYS::AUDIO_ENGINE  OK",
        "BUFFER_UNDERRUN    0x00",
        "FFT_LOCK           ACQUIRED",
        "THERMAL_ZONE       28°C",
        "ENTROPY_POOL       FULL",
        "CODEC_PIPELINE     ACTIVE",
        "LATENCY            4.2ms",
        "CLOCK_DRIFT        ±0.001%",
        "WAVEFORM_HASH      0x{:04X}",
        "SECTOR_SCAN        CLEAN",
        "CIPHER_INIT        AES-256",
        "NODE_SYNC          LOCKED",
        "PROTOCOL_STACK     v2.4.1",
        "FRAME_COUNTER      {:06d}",
        "SIGNAL_NOISE       -{:02d}dB",
        "HEAP_ALLOC         OK",
        "KERNEL_TICK        {:08X}",
    ]

    def __init__(self, parent, width=300, height=72, bg=None, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg     = bg
        self._alive  = True
        self.t       = 0
        self._lines: List[Tuple[str, int]] = []   # (text, age)
        self._line_h = 12
        self._max_lines = max(1, height // self._line_h) + 2
        self._inject_counter = 0
        self._draw()

    def push(self, text: str):
        """Inject a real system message into the stream."""
        self._lines.append((f"▸ {text}", 0))

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            self.winfo_width() or int(self["width"])
            H = self.winfo_height() or int(self["height"])

            # Inject noise lines periodically
            self._inject_counter += 1
            if self._inject_counter >= 12:
                self._inject_counter = 0
                tmpl = random.choice(self._NOISE)
                line = tmpl.format(
                    random.randint(0, 0xFFFF),
                    random.randint(0, 999999),
                    random.randint(60, 99),
                    random.randint(0, 0xFFFFFFFF),
                )
                self._lines.append((line, 0))

            # Trim old lines
            if len(self._lines) > self._max_lines:
                self._lines = self._lines[-self._max_lines:]

            # Age lines
            self._lines = [(txt, age + 1) for txt, age in self._lines]

            # Draw lines bottom to top
            for i, (txt, age) in enumerate(reversed(self._lines)):
                y = H - (i + 1) * self._line_h
                if y < -self._line_h:
                    break
                # Fade in new lines, dim old ones
                max_age = self._max_lines * 12
                fade = min(1.0, age / 4.0) * max(0.0, 1.0 - age / max_age)
                br   = int(fade * 52)
                if "▸" in txt:
                    br = int(fade * 140)   # injected lines brighter
                col = f"#{br:02x}{br:02x}{br:02x}"
                self.create_text(8, y + self._line_h // 2,
                                 text=txt[:52], font=("Courier New", 7),
                                 fill=col, anchor="w")

        except Exception:
            pass

        self.t += 1
        if self._alive:
            self.after(_MED, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  BINARY RAIN  — horizontal binary strip for topbar / sidebar accent
# ─────────────────────────────────────────────────────────────────────────────
class BinaryRain(tk.Canvas):
    """
    Scrolling binary + hex characters in a thin strip.
    Use as a decorative accent bar.

    Usage:
        br = BinaryRain(parent, width=400, height=8)
        br.pack(fill="x")
    """

    _CHARS = "01" * 8 + "ABCDEF0123456789◈◉▪▫"

    def __init__(self, parent, width=400, height=8, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg    = bg
        self._alive = True
        self.t      = 0
        rng = random.Random(7)
        # Each column: position, speed, char index, phase
        n_cols = max(1, width // 7)
        self._cols = [
            {"x": i * 7, "phase": rng.uniform(0, math.pi*2),
             "speed": rng.uniform(0.02, 0.06), "char": rng.choice(self._CHARS)}
            for i in range(n_cols)
        ]
        self._draw()

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            H = self.winfo_height() or int(self["height"])
            for col in self._cols:
                col["phase"] += col["speed"]
                brightness = math.sin(col["phase"]) * 0.5 + 0.5
                br = int(12 + brightness * 30)
                br = min(255, br)
                # Randomly flip character
                if random.random() < 0.03:
                    col["char"] = random.choice(self._CHARS)
                self.create_text(
                    col["x"] + 3, H // 2,
                    text=col["char"],
                    font=("Courier New", max(6, H - 2)),
                    fill=f"#{br:02x}{br:02x}{br:02x}",
                    anchor="center",
                )
        except Exception:
            pass
        self.t += 1
        if self._alive:
            self.after(_SLOW, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  GLOW BORDER  — animated pulsing glow around any frame
# ─────────────────────────────────────────────────────────────────────────────
class GlowBorder(tk.Canvas):
    """
    Thin canvas that draws an animated glow border effect.
    Place it overlapping a frame's edges using place().

    Usage:
        gb = GlowBorder(parent, width=w+4, height=h+4)
        gb.place(x=-2, y=-2)
        gb.set_energy(0.7)
    """

    def __init__(self, parent, width=200, height=100, bg=None, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg     = bg
        self._energy = 0.0
        self._alive  = True
        self.t       = 0
        self._draw()

    def set_energy(self, energy: float):
        self._energy = max(0.0, min(1.0, float(energy)))

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            W = self.winfo_width()  or int(self["width"])
            H = self.winfo_height() or int(self["height"])
            t = self.t
            e = self._energy

            pulse = math.sin(t * 0.04) * 0.5 + 0.5
            intensity = e * 0.7 + pulse * 0.3

            # Draw 3 concentric border rects with decreasing brightness
            for i in range(3):
                br  = int(intensity * (40 - i * 12))
                br  = max(0, min(255, br))
                col = f"#{br:02x}{br:02x}{br:02x}"
                pad = i
                self.create_rectangle(pad, pad, W-1-pad, H-1-pad,
                                      outline=col, width=1)

            # Corner accents — bright dots at corners
            cbr = int(intensity * 160)
            cbr = min(255, cbr)
            ccol = f"#{cbr:02x}{cbr:02x}{cbr:02x}"
            sz = 3
            for x, y in [(0,0),(W-1,0),(0,H-1),(W-1,H-1)]:
                self.create_rectangle(x-sz, y-sz, x+sz, y+sz,
                                      fill=ccol, outline="")

        except Exception:
            pass

        self.t += 1
        if self._alive:
            self.after(_MED, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  NODE GRAPH  — animated node-edge network reacting to BPM
# ─────────────────────────────────────────────────────────────────────────────
class NodeGraph(tk.Canvas):
    """
    Animated node-edge graph. Nodes drift slowly, edges appear/disappear
    based on proximity. BPM pulses propagate through the network.

    Usage:
        ng = NodeGraph(parent, width=200, height=120)
        ng.pack()
        ng.pulse(bpm=128)   # call on beat
    """

    def __init__(self, parent, width=200, height=120, bg=None, n_nodes=18, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg      = bg
        self._alive   = True
        self._energy  = 0.0
        self.t        = 0
        self._pulse   = 0.0
        rng = random.Random(13)
        self._nodes = [
            {
                "x": rng.uniform(10, width-10),
                "y": rng.uniform(10, height-10),
                "vx": rng.uniform(-0.3, 0.3),
                "vy": rng.uniform(-0.2, 0.2),
                "lit": 0.0,
            }
            for _ in range(n_nodes)
        ]
        self._W = width
        self._H = height
        self._draw()

    def set_energy(self, energy: float):
        self._energy = max(0.0, min(1.0, float(energy)))

    def pulse(self, bpm: float = 120.0):
        """Trigger a beat pulse — lights up nodes nearest the centre."""
        self._pulse = 1.0
        cx, cy = self._W / 2, self._H / 2
        for nd in self._nodes:
            dist = math.hypot(nd["x"] - cx, nd["y"] - cy)
            if dist < self._W * 0.35:
                nd["lit"] = 1.0

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            W, H = self._W, self._H
            e = self._energy

            # Move nodes
            for nd in self._nodes:
                nd["x"] += nd["vx"] * (1 + e * 0.8)
                nd["y"] += nd["vy"] * (1 + e * 0.8)
                # Bounce
                if nd["x"] < 5 or nd["x"] > W-5:
                    nd["vx"] *= -1
                if nd["y"] < 5 or nd["y"] > H-5:
                    nd["vy"] *= -1
                nd["x"] = max(5, min(W-5, nd["x"]))
                nd["y"] = max(5, min(H-5, nd["y"]))
                # Decay lit
                nd["lit"] = max(0.0, nd["lit"] - 0.04)

            # Decay pulse
            self._pulse = max(0.0, self._pulse - 0.06)

            # Edges
            threshold = W * 0.38 + e * W * 0.1
            for i, n1 in enumerate(self._nodes):
                for n2 in self._nodes[i+1:]:
                    dist = math.hypot(n1["x"]-n2["x"], n1["y"]-n2["y"])
                    if dist < threshold:
                        frac = 1.0 - dist / threshold
                        lit  = max(n1["lit"], n2["lit"])
                        br   = int(frac * (14 + e*18) + lit * 55)
                        br   = min(255, br)
                        self.create_line(
                            n1["x"], n1["y"], n2["x"], n2["y"],
                            fill=f"#{br:02x}{br:02x}{br:02x}", width=1,
                        )

            # Nodes
            for nd in self._nodes:
                lit = nd["lit"]
                br  = int(20 + e*25 + lit*200)
                br  = min(255, br)
                r   = 2 + lit * 3
                self.create_oval(nd["x"]-r, nd["y"]-r,
                                 nd["x"]+r, nd["y"]+r,
                                 fill=f"#{br:02x}{br:02x}{br:02x}", outline="")

        except Exception:
            pass

        self.t += 1
        if self._alive:
            self.after(_FAST, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  TERMINAL CURSOR  — blinking cursor with typewriter label
# ─────────────────────────────────────────────────────────────────────────────
class TerminalCursor(tk.Canvas):
    """
    Text display with blinking block cursor and optional typewriter effect.

    Usage:
        tc = TerminalCursor(parent, width=200, height=18)
        tc.pack()
        tc.set_text("SIGNAL ACQUIRED")
        tc.typewrite("NEW MESSAGE")   # types out letter by letter
    """

    def __init__(self, parent, width=200, height=18, bg=None,
                 font=None, fg=None, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg     = bg
        self._fg     = fg or C["white2"]
        self._font   = font or ("Courier New", 8)
        self._text   = ""
        self._shown  = ""
        self._typing = False
        self._cursor_on = True
        self._alive  = True
        self.t       = 0
        self._draw()

    def set_text(self, text: str):
        self._text  = text
        self._shown = text
        self._typing = False

    def typewrite(self, text: str, delay_ms: int = 40):
        """Type text out letter by letter."""
        self._text   = text
        self._shown  = ""
        self._typing = True
        self._type_idx = 0
        self._type_delay = delay_ms
        self._type_next()

    def _type_next(self):
        if not self._alive or not self._typing:
            return
        if self._type_idx < len(self._text):
            self._shown = self._text[:self._type_idx + 1]
            self._type_idx += 1
            self.after(self._type_delay, self._type_next)
        else:
            self._typing = False

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            self.winfo_width()  or int(self["width"])
            H = self.winfo_height() or int(self["height"])

            # Blink cursor every 15 frames
            if self.t % 30 < 15:
                self._cursor_on = True
            else:
                self._cursor_on = False

            text = self._shown + ("█" if self._cursor_on else " ")
            self.create_text(6, H // 2, text=text,
                             font=self._font, fill=self._fg, anchor="w")
        except Exception:
            pass

        self.t += 1
        if self._alive:
            self.after(_MED, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  WAVEFORM SCOPE  — real-time oscilloscope waveform above the progress bar
# ─────────────────────────────────────────────────────────────────────────────
class WaveformScope(tk.Canvas):
    """
    Oscilloscope-style animated waveform. Feed it raw bar data or let it
    generate a synthetic signal from energy alone.

    Usage:
        ws = WaveformScope(parent, width=400, height=28)
        ws.pack(fill="x")
        ws.update_bars([0.1, 0.8, ...])
    """

    def __init__(self, parent, width=400, height=28, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg     = bg
        self._bars   = [0.0] * 64
        self._smooth = [0.0] * 64
        self._alive  = True
        self._energy = 0.0
        self.t       = 0
        self._draw()

    def update_bars(self, bars: list):
        n = min(len(bars), len(self._bars))
        for i in range(n):
            self._bars[i] = float(bars[i])
        self._energy = sum(self._bars[:16]) / 16

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            W = self.winfo_width() or int(self["width"])
            H = self.winfo_height() or int(self["height"])
            cy = H / 2
            t  = self.t
            e  = self._energy

            # Smooth bars
            for i in range(len(self._bars)):
                self._smooth[i] += (self._bars[i] - self._smooth[i]) * 0.3

            n = len(self._smooth)
            # Build waveform points — mirror around centre
            pts = []
            for i in range(W):
                idx  = int(i / W * n)
                val  = self._smooth[idx] if idx < n else 0.0
                # Add subtle sine shimmer on idle
                if e < 0.05:
                    val = 0.03 * math.sin(i * 0.08 + t * 0.04)
                y = cy - val * cy * 0.85
                pts.append((i, y))

            # Draw filled waveform
            if len(pts) >= 2:
                # Bottom fill
                fill_pts = [(0, H)] + pts + [(W, H)]
                flat = [c for p in fill_pts for c in p]
                br_fill = int(8 + e * 18)
                try:
                    self.create_polygon(*flat, fill=f"#{br_fill:02x}{br_fill:02x}{br_fill:02x}",
                                        outline="")
                except Exception:
                    pass

                # Top line
                line_pts = [c for p in pts for c in p]
                br_line = int(40 + e * 200)
                br_line = min(255, br_line)
                self.create_line(*line_pts, fill=f"#{br_line:02x}{br_line:02x}{br_line:02x}",
                                 width=1, smooth=True)

                # Centre zero line — very dim
                self.create_line(0, cy, W, cy,
                                 fill=f"#{int(18+e*12):02x}{int(18+e*12):02x}{int(18+e*12):02x}",
                                 width=1)

        except Exception:
            pass
        self.t += 1
        if self._alive:
            self.after(_FAST, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  BEAT PULSE  — concentric ring burst that fires on each beat
# ─────────────────────────────────────────────────────────────────────────────
class BeatPulse(tk.Canvas):
    """
    Fires expanding concentric rings outward from the centre on each .fire().
    Place over or near the play button.

    Usage:
        bp = BeatPulse(parent, size=80)
        bp.place(relx=0.5, rely=0.5, anchor="center")
        bp.fire()   # call on beat / track start
    """

    def __init__(self, parent, size=80, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self._size   = size
        self._bg     = bg
        self._alive  = True
        self._rings: List[dict] = []
        self.t = 0
        self._draw()

    def fire(self, intensity: float = 1.0):
        """Trigger a ring burst."""
        self._rings.append({
            "r":         0.0,
            "max_r":     self._size * 0.48,
            "alpha":     min(1.0, float(intensity)),
            "speed":     3.0 + intensity * 4.0,
            "width":     max(1, int(intensity * 2.5)),
        })

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            S  = self._size
            cx = cy = S / 2

            for ring in self._rings[:]:
                ring["r"]     += ring["speed"]
                ring["alpha"] *= 0.88
                if ring["r"] >= ring["max_r"] or ring["alpha"] < 0.02:
                    self._rings.remove(ring)
                    continue
                br = int(ring["alpha"] * 220)
                br = min(255, br)
                r  = ring["r"]
                self.create_oval(cx - r, cy - r, cx + r, cy + r,
                                 outline=f"#{br:02x}{br:02x}{br:02x}",
                                 width=ring["width"])
        except Exception:
            pass
        self.t += 1
        if self._alive:
            self.after(_FAST, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  GLYPH WALL  — ambient dim glyph background for large areas
# ─────────────────────────────────────────────────────────────────────────────
class GlyphWall(tk.Canvas):
    """
    Very dim scrolling field of random unicode + hex glyphs.
    Use as a background layer behind content — low opacity, purely ambient.
    Place with place(x=0,y=0,relwidth=1,relheight=1) then lower it.

    Usage:
        gw = GlyphWall(parent)
        gw.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        gw.tk.call("lower", gw._w)
        gw.set_energy(0.3)
    """

    _CHARS = ("01" * 6 + "ABCDEF0123456789" +
              "◈◉○●□■▪▫▸△▽◁▷⊕⊗" * 2 +
              "アイウエオカキクケコサシスセソ")

    def __init__(self, parent, bg=None, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0, **kw)
        self._bg     = bg
        self._energy = 0.0
        self._alive  = True
        self.t       = 0
        self._cols: List[dict] = []
        self._built  = False
        self._draw()

    def _build(self, W: int, H: int):
        rng = random.Random(99)
        col_w = 14
        n = max(1, W // col_w)
        self._cols = [
            {
                "x":     i * col_w + rng.randint(-3, 3),
                "y":     rng.uniform(0, H),
                "speed": rng.uniform(0.15, 0.55),
                "char":  rng.choice(self._CHARS),
                "phase": rng.uniform(0, math.pi * 2),
                "flip_t": rng.randint(20, 80),
                "flip_c": 0,
            }
            for i in range(n)
        ]
        self._built = True

    def set_energy(self, energy: float):
        self._energy = max(0.0, min(1.0, float(energy)))

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            W = self.winfo_width()
            H = self.winfo_height()
            if W < 4 or H < 4:
                if self._alive:
                    self.after(200, self._draw)
                return

            if not self._built:
                self._build(W, H)

            self.delete("all")
            e  = self._energy
            t  = self.t

            for col in self._cols:
                col["y"] += col["speed"] * (1.0 + e * 0.5)
                if col["y"] > H + 20:
                    col["y"] = -20
                # Flip char occasionally
                col["flip_c"] += 1
                if col["flip_c"] >= col["flip_t"]:
                    col["flip_c"] = 0
                    col["char"] = random.choice(self._CHARS)

                # Pulsing brightness — very dim
                pulse = math.sin(t * 0.015 + col["phase"]) * 0.5 + 0.5
                br = int(6 + pulse * (8 + e * 14))
                br = min(255, max(4, br))

                self.create_text(
                    col["x"], int(col["y"]),
                    text=col["char"],
                    font=("Courier New", 9),
                    fill=f"#{br:02x}{br:02x}{br:02x}",
                    anchor="center",
                )
        except Exception:
            pass

        self.t += 1
        if self._alive:
            self.after(_SLOW, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  SPECTRUM BARS  — horizontal FFT bar strip for edges/headers
# ─────────────────────────────────────────────────────────────────────────────
class SpectrumBars(tk.Canvas):
    """
    Thin horizontal strip of vertical FFT bars.
    Use as a decorative accent along an edge or below a header.

    Usage:
        sb = SpectrumBars(parent, width=600, height=20)
        sb.pack(fill="x")
        sb.update_bars([...])
    """

    def __init__(self, parent, width=600, height=20, bg=None,
                 mirror=False, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg     = bg
        self._mirror = mirror   # bars grow from top instead of bottom
        self._bars   = [0.0] * 48
        self._smooth = [0.0] * 48
        self._peaks  = [0.0] * 48
        self._alive  = True
        self.t = 0
        self._draw()

    def update_bars(self, bars: list):
        n = min(len(bars), len(self._bars))
        for i in range(n):
            self._bars[i] = float(bars[i])

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            W = self.winfo_width() or int(self["width"])
            H = self.winfo_height() or int(self["height"])
            n = len(self._smooth)

            for i in range(n):
                self._smooth[i] += (self._bars[i] - self._smooth[i]) * 0.25
                if self._bars[i] > self._peaks[i]:
                    self._peaks[i] = self._bars[i]
                else:
                    self._peaks[i] = max(0.0, self._peaks[i] - 0.015)

            bw = W / n
            for i, val in enumerate(self._smooth):
                x0 = i * bw
                x1 = x0 + bw - 1
                bar_h = max(1, int(val * H * 0.92))

                if self._mirror:
                    y0, y1 = 0, bar_h
                else:
                    y0, y1 = H - bar_h, H

                br = int(18 + val * 210)
                br = min(255, max(8, br))
                self.create_rectangle(x0, y0, x1, y1,
                                      fill=f"#{br:02x}{br:02x}{br:02x}",
                                      outline="")

                # Peak dot
                if self._peaks[i] > 0.05:
                    py = H - int(self._peaks[i] * H) if not self._mirror else int(self._peaks[i] * H)
                    pbr = int(60 + self._peaks[i] * 190)
                    pbr = min(255, pbr)
                    self.create_line(x0, py, x1, py,
                                     fill=f"#{pbr:02x}{pbr:02x}{pbr:02x}",
                                     width=1)
        except Exception:
            pass
        self.t += 1
        if self._alive:
            self.after(_FAST, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  HOLO FRAME  — holographic corner brackets that pulse with energy
# ─────────────────────────────────────────────────────────────────────────────
class HoloFrame(tk.Canvas):
    """
    Animated corner brackets with a scanning line and energy pulse.
    Place over the album art canvas for a targeting-reticle effect.

    Usage:
        hf = HoloFrame(parent, size=50)
        hf.place(x=0, y=0)
        hf.set_energy(0.8)
    """

    def __init__(self, parent, size=50, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self._size   = size
        self._bg     = bg
        self._energy = 0.0
        self._alive  = True
        self.t       = 0
        self._scan_y = 0.0
        self._draw()

    def set_energy(self, energy: float):
        self._energy = max(0.0, min(1.0, float(energy)))

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            S  = self._size
            t  = self.t
            e  = self._energy

            pulse = math.sin(t * 0.06) * 0.5 + 0.5
            intensity = e * 0.6 + pulse * 0.4
            br_hi  = int(intensity * 200)
            br_hi  = min(255, br_hi)
            br_lo  = max(0, br_hi // 3)
            hi_col = f"#{br_hi:02x}{br_hi:02x}{br_hi:02x}"
            lo_col = f"#{br_lo:02x}{br_lo:02x}{br_lo:02x}"

            arm = max(6, int(S * 0.28))
            M   = 2

            # Four corner L-brackets
            for ox, oy, sx, sy in [
                (M,   M,   1,  1),
                (S-M, M,  -1,  1),
                (M,   S-M, 1, -1),
                (S-M, S-M,-1, -1),
            ]:
                self.create_line(ox, oy, ox + sx*arm, oy,
                                 fill=hi_col, width=2)
                self.create_line(ox, oy, ox, oy + sy*arm,
                                 fill=hi_col, width=2)
                # Inner micro tick
                self.create_line(ox + sx*arm, oy,
                                 ox + sx*(arm+4), oy,
                                 fill=lo_col, width=1)

            # Horizontal scan line
            self._scan_y = (self._scan_y + 0.8 + e * 1.2) % S
            scan_br = int(intensity * 80)
            scan_br = min(255, scan_br)
            self.create_line(M, self._scan_y, S-M, self._scan_y,
                             fill=f"#{scan_br:02x}{scan_br:02x}{scan_br:02x}",
                             width=1)

            # Centre crosshair dot — tiny
            if e > 0.1:
                cr = max(1, int(intensity * 2))
                cbr = int(intensity * 160)
                self.create_oval(S//2-cr, S//2-cr, S//2+cr, S//2+cr,
                                 fill=f"#{cbr:02x}{cbr:02x}{cbr:02x}",
                                 outline="")

        except Exception:
            pass
        self.t += 1
        if self._alive:
            self.after(_FAST, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  SIGNAL METER  — multi-channel vertical level meter with hold & decay
# ─────────────────────────────────────────────────────────────────────────────
class SignalMeter(tk.Canvas):
    """
    4-channel vertical signal meter — L/R/MID/SIDE or custom labels.
    Each channel has independent hold-and-decay peak markers.

    Usage:
        sm = SignalMeter(parent, width=48, height=80)
        sm.pack()
        sm.update(l=0.7, r=0.8, mid=0.5, side=0.3)
    """

    def __init__(self, parent, width=48, height=80, bg=None,
                 labels=("L", "R", "M", "S"), **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg      = bg
        self._labels  = labels
        self._n       = len(labels)
        self._levels  = [0.0] * self._n
        self._smooth  = [0.0] * self._n
        self._peaks   = [0.0] * self._n
        self._peak_hold = [0]  * self._n
        self._alive   = True
        self.t        = 0
        self._draw()

    def update(self, **kwargs):
        """Update channels: l=, r=, mid=, side= or by index."""
        key_map = {lbl.lower(): i for i, lbl in enumerate(self._labels)}
        for key, val in kwargs.items():
            idx = key_map.get(key.lower())
            if idx is not None:
                self._levels[idx] = max(0.0, min(1.0, float(val)))

    def update_from_bars(self, bars: list):
        """Derive L/R/Mid/Side from FFT bars."""
        if not bars:
            return
        n = len(bars)
        bass  = min(1.0, sum(bars[:n//8]) / (n//8) * 3.5)
        mid   = min(1.0, sum(bars[n//8:n//3]) / (n//5) * 3.0)
        hi    = min(1.0, sum(bars[n//3:n//2]) / (n//6) * 4.0)
        air   = min(1.0, sum(bars[n//2:]) / (n//4) * 4.0)
        self._levels = [bass, hi, mid, air]

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            W = self.winfo_width() or int(self["width"])
            H = self.winfo_height() or int(self["height"])
            n = self._n
            bw = W // n
            lbl_h = 10
            bar_h = H - lbl_h - 2

            for i in range(n):
                # Smooth
                self._smooth[i] += (self._levels[i] - self._smooth[i]) * 0.28
                val = self._smooth[i]

                # Peak hold
                if val >= self._peaks[i]:
                    self._peaks[i] = val
                    self._peak_hold[i] = 25
                else:
                    if self._peak_hold[i] > 0:
                        self._peak_hold[i] -= 1
                    else:
                        self._peaks[i] = max(0.0, self._peaks[i] - 0.012)

                x0 = i * bw + 1
                x1 = (i + 1) * bw - 1

                # Background track
                self.create_rectangle(x0, 0, x1, bar_h,
                                      fill=C["bg"], outline="")

                # Filled bar — segmented
                segs = 12
                seg_h = bar_h / segs
                filled = int(val * segs)
                for s in range(filled):
                    sy0 = bar_h - (s + 1) * seg_h + 1
                    sy1 = bar_h - s * seg_h - 1
                    frac = s / segs
                    if frac < 0.65:
                        br = int(55 + val * 140)
                    elif frac < 0.85:
                        br = int(100 + val * 120)
                    else:
                        br = int(160 + val * 90)
                    br = min(255, br)
                    self.create_rectangle(x0, sy0, x1, sy1,
                                          fill=f"#{br:02x}{br:02x}{br:02x}",
                                          outline="")

                # Peak marker
                if self._peaks[i] > 0.02:
                    py = bar_h - self._peaks[i] * bar_h
                    pbr = int(120 + self._peaks[i] * 135)
                    pbr = min(255, pbr)
                    self.create_line(x0, py, x1, py,
                                     fill=f"#{pbr:02x}{pbr:02x}{pbr:02x}",
                                     width=2)

                # Label
                lbr = int(35 + val * 55)
                self.create_text(
                    (x0 + x1) // 2, bar_h + lbl_h // 2 + 1,
                    text=self._labels[i],
                    font=("Courier New", 7, "bold"),
                    fill=f"#{lbr:02x}{lbr:02x}{lbr:02x}",
                    anchor="center",
                )

        except Exception:
            pass
        self.t += 1
        if self._alive:
            self.after(_MED, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  PLASMA RING  — swirling plasma / lissajous ring around a centre
# ─────────────────────────────────────────────────────────────────────────────
class PlasmaRing(tk.Canvas):
    """
    A parametric Lissajous curve that morphs with energy.
    Looks like a plasma ring or oscilloscope XY pattern.
    Place next to the RadarSweep for contrast.

    Usage:
        pr = PlasmaRing(parent, size=80)
        pr.pack()
        pr.set_energy(0.6)
    """

    def __init__(self, parent, size=80, bg=None, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self._size   = size
        self._bg     = bg
        self._energy = 0.0
        self._alive  = True
        self.t       = 0
        self._draw()

    def set_energy(self, energy: float):
        self._energy = max(0.0, min(1.0, float(energy)))

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            S  = self._size
            cx = cy = S / 2
            R  = S * 0.42
            t  = self.t
            e  = self._energy

            # Lissajous parameters morph with energy
            a  = 2.0 + e * 1.0          # x frequency
            b  = 3.0 + e * 0.5          # y frequency
            d  = t * 0.015 + e * 0.3    # phase delta
            n_pts = 180

            pts = []
            for i in range(n_pts + 1):
                angle = i / n_pts * math.pi * 2
                x = cx + R * math.sin(a * angle + d) * (0.7 + e * 0.3)
                y = cy + R * math.sin(b * angle)     * (0.7 + e * 0.3)
                pts.append((x, y))

            # Draw with fading colour by position
            for i in range(len(pts) - 1):
                frac = i / (len(pts) - 1)
                br = int(15 + frac * (30 + e * 140))
                br = min(255, br)
                self.create_line(
                    pts[i][0], pts[i][1],
                    pts[i+1][0], pts[i+1][1],
                    fill=f"#{br:02x}{br:02x}{br:02x}",
                    width=1,
                )

            # Centre glow
            cr = 1 + e * 2
            cbr = int(30 + e * 120)
            self.create_oval(cx-cr, cy-cr, cx+cr, cy+cr,
                             fill=f"#{cbr:02x}{cbr:02x}{cbr:02x}", outline="")

        except Exception:
            pass
        self.t += 1
        if self._alive:
            self.after(_FAST, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  DATA BURST  — text explosion on track load
# ─────────────────────────────────────────────────────────────────────────────
class DataBurst(tk.Canvas):
    """
    Fires a burst of random data strings that fly outward from centre
    then fade. Trigger on track load for a satisfying transition effect.
    Place with place() over the now-playing area.

    Usage:
        db = DataBurst(parent, width=300, height=100)
        db.place(x=0, y=0, relwidth=1, relheight=1)
        db.burst()   # call on track change
    """

    _FRAGMENTS = [
        "0x{:04X}", "SIG::{:03d}", "LOCK", "TX:OK", "ACK",
        "▸▸▸", "LOAD", "◈{:02X}", "SYS", "RDY",
        "0b{:08b}", "CH:{:02d}", "BUF:OK", "▶",
    ]

    def __init__(self, parent, width=300, height=80, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg       = bg
        self._alive    = True
        self._particles: List[dict] = []
        self.t         = 0
        self._draw()

    def burst(self, n: int = 14):
        """Trigger a data particle burst from the centre."""
        W = self.winfo_width() or int(self["width"])
        H = self.winfo_height() or int(self["height"])
        cx, cy = W / 2, H / 2
        for _ in range(n):
            angle = random.uniform(0, math.pi * 2)
            speed = random.uniform(1.5, 5.0)
            tmpl  = random.choice(self._FRAGMENTS)
            try:
                text = tmpl.format(random.randint(0, 0xFFFF))
            except Exception:
                text = tmpl
            self._particles.append({
                "x":     cx,
                "y":     cy,
                "vx":    math.cos(angle) * speed,
                "vy":    math.sin(angle) * speed * 0.7,
                "alpha": 1.0,
                "text":  text,
                "size":  random.choice([7, 8, 9]),
            })

    def destroy(self):
        self._alive = False
        try:
            super().destroy()
        except Exception:
            pass

    def _draw(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return
        try:
            self.delete("all")
            for p in self._particles[:]:
                p["x"]     += p["vx"]
                p["y"]     += p["vy"]
                p["vy"]    += 0.12   # gravity
                p["alpha"] *= 0.91
                if p["alpha"] < 0.04:
                    self._particles.remove(p)
                    continue
                br = int(p["alpha"] * 200)
                br = min(255, max(0, br))
                self.create_text(
                    int(p["x"]), int(p["y"]),
                    text=p["text"],
                    font=("Courier New", p["size"]),
                    fill=f"#{br:02x}{br:02x}{br:02x}",
                    anchor="center",
                )
        except Exception:
            pass
        self.t += 1
        if self._alive:
            self.after(_FAST, self._draw)


# ─────────────────────────────────────────────────────────────────────────────
#  INTEGRATION NOTES
# ─────────────────────────────────────────────────────────────────────────────
"""
STEP 1 — Add to player.py imports (both frozen + non-frozen):

    from oternos.cyberui import (
        GlitchText, CircuitLines, RadarSweep,
        FrequencyRing, StatusMatrix, BinaryRain,
        GlowBorder, NodeGraph, TerminalCursor,
        WaveformScope, BeatPulse, GlyphWall,
        SpectrumBars, HoloFrame, SignalMeter,
        PlasmaRing, DataBurst,
    )
"""
