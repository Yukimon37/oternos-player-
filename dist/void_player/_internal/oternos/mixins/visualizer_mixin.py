"""
visualizer_mixin.py — OTERNOS PLAYER
Auto-extracted mixin for VoidPlayer.
Contains all visualizer-related methods.
"""

import sys
import tkinter as tk
import threading
import time
import os
import json
import re
import math
import random
import urllib.request
import urllib.parse
import urllib.error
import webbrowser
from pathlib import Path

if getattr(sys, "frozen", False):
    from oternos.constants import C, FM, FMS, FML, FMX, DATA_FILE, YT_CACHE, HW_ACCEL
    from oternos.diagnostics import log_exception
else:
    from ..constants import C, FM, FMS, FML, FMX, DATA_FILE, YT_CACHE, HW_ACCEL
    from ..diagnostics import log_exception


class VisualizerMixin:
    """Mixin: visualizer methods for VoidPlayer."""
    def _viz_tick(self):
        if self.view != "visualizer":
            self._viz_job = None
            return
        self._draw_visualizer()
        self._viz_t += 1
        interval = getattr(self, "_viz_interval", 16 if HW_ACCEL else 150)
        self._viz_job = self.viz_cv.after(interval, self._viz_tick)

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
