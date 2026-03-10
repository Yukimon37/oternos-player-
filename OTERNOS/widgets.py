"""
widgets.py
─────────────────────────────────────────────────────────────────────────────
OTERNOS PLAYER  —  Custom tkinter canvas widgets.
  • WaveVisualizer   — animated bar waveform in the player bar
  • OternosLogo      — Arasaka-style hex emblem
  • MikuLogo         — teal hex logo for MIKU theme
  • MikuCornerDeco   — corner decoration for MIKU theme
  • MikuTicker       — scrolling data ticker for MIKU theme
  • CornerBrackets   — four-corner bracket decoration
  • DataTicker       — hex data scrolling strip
  • MosaicArt        — album art mosaic background renderer
  • TrackRecommender — content-based track recommendation engine
  • NormMeter        — slim RMS/peak level meter
─────────────────────────────────────────────────────────────────────────────
"""

import tkinter as tk
import math
import random
import threading
from pathlib import Path

from .constants import C, HW_ACCEL


# ─────────────────────────────────────────
#  WAVEFORM VISUALIZER
# ─────────────────────────────────────────
class WaveVisualizer(tk.Canvas):
    def __init__(self, parent, **kw):
        # Match the panel background so there's no hard box edge
        super().__init__(parent, bg=C["panel"], highlightthickness=0, **kw)
        self.bars   = 48
        self.phases = [random.uniform(0, math.pi*2) for _ in range(self.bars)]
        self.speeds = [random.uniform(0.03, 0.09)   for _ in range(self.bars)]
        self.t      = 0
        self.active = False
        self._draw()

    def set_active(self, v):
        self.active = v

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w > 1 and h > 1:
            bw = w / self.bars
            # Derive panel background brightness from current theme
            try:
                ph = C["panel"].lstrip("#")
                PBG = int(ph[0:2], 16)
            except Exception:
                PBG = 17
            for i in range(self.bars):
                # Edge fade: bars near the sides fade toward the panel bg colour
                edge = abs(i - self.bars / 2) / (self.bars / 2)  # 0=center, 1=edge
                edge_fade = 1.0 - edge ** 1.6  # softer roll-off

                if self.active:
                    amp = (math.sin(self.t * self.speeds[i]*10 + self.phases[i])*0.5+0.5)**1.5
                    amp = max(0.04, amp)
                    # Active: bright center bars, fade to panel at edges
                    peak = int(200 * edge_fade + 30)
                    br = int(PBG + (peak - PBG) * amp * edge_fade)
                else:
                    amp = 0.03 + 0.015 * math.sin(self.t * 0.5 + i * 0.3)
                    # Idle: very subtle, barely above panel colour
                    peak = int(48 * edge_fade + PBG)
                    br = int(PBG + (peak - PBG) * amp * 18)

                br = max(PBG, min(255, br))
                bh = amp * h * 0.80
                x1, x2 = i*bw+1, i*bw+bw-2
                y1, y2 = (h-bh)/2, (h+bh)/2
                self.create_rectangle(x1, y1, x2, y2,
                                      fill=f"#{br:02x}{br:02x}{br:02x}", outline="")
        self.t += 1
        self.after(30 if HW_ACCEL else 120, self._draw)


# ─────────────────────────────────────────
#  OTERNOS LOGO  — Arasaka-style hex emblem
# ─────────────────────────────────────────
class OternosLogo(tk.Canvas):
    """
    Layered cyberpunk hex emblem:
      • Outer hex ring with angular notch cuts at each vertex
      • Mid hex — slightly smaller, counter-rotates slowly
      • Six sharp spike fins radiating outward at each vertex
      • Inner O ring with 12 tick marks around it
      • Centre dot
    Animates: slow idle drift, pulses when is_playing=True.
    """
    def __init__(self, parent, size=54, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self.size      = size
        self._bg       = bg
        self.t         = 0
        self.is_playing = False
        self._draw()

    # ── helpers ──────────────────────────
    def _hex_pts(self, cx, cy, r, rot, flat=False):
        pts = []
        offset = math.pi / 6 if flat else 0
        for i in range(6):
            a = i / 6 * math.pi * 2 + rot + offset
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        return pts

    def _notched_hex(self, cx, cy, r, rot, notch=0.13):
        """Hex with small angular notches cut inward at each vertex."""
        pts = []
        for i in range(6):
            a0 = i / 6 * math.pi * 2 + rot
            a1 = (i + 1) / 6 * math.pi * 2 + rot
            # approach vertex from previous edge
            pts += [cx + r * math.cos(a0 - notch), cy + r * math.sin(a0 - notch)]
            # notch dip inward
            pts += [cx + r * 0.88 * math.cos(a0),  cy + r * 0.88 * math.sin(a0)]
            # leave vertex toward next edge
            pts += [cx + r * math.cos(a0 + notch), cy + r * math.sin(a0 + notch)]
        return pts

    def _draw(self):
        try:
            self.delete("all")
            S  = self.size
            cx, cy = S / 2, S / 2
            R  = S * 0.46
            t  = self.t
            pl = self.is_playing

            pulse = (math.sin(t * 0.07) * 0.5 + 0.5) if pl else 0.0
            hi    = min(255, int(190 + pulse * 65))
            mid   = min(255, int(95  + pulse * 55))
            dim   = min(255, int(42  + pulse * 20))
            hc    = f"#{hi:02x}{hi:02x}{hi:02x}"
            mc    = f"#{mid:02x}{mid:02x}{mid:02x}"
            dc    = f"#{dim:02x}{dim:02x}{dim:02x}"
            rot_outer = t * 0.006
            rot_mid   = -t * 0.009 + math.pi / 6

            pad = R * 0.06
            self.create_oval(cx-R-pad, cy-R-pad, cx+R+pad, cy+R+pad,
                             fill=C["bg"], outline="")

            for i in range(6):
                a  = i / 6 * math.pi * 2 + rot_outer
                bw = math.pi / 18
                tx = cx + R * math.cos(a);          ty = cy + R * math.sin(a)
                lx = cx + R*0.68*math.cos(a-bw);    ly = cy + R*0.68*math.sin(a-bw)
                rx = cx + R*0.68*math.cos(a+bw);    ry = cy + R*0.68*math.sin(a+bw)
                self.create_polygon(lx,ly,tx,ty,rx,ry, fill=mc, outline="")

            op_flat = self._notched_hex(cx, cy, R*0.92, rot_outer, notch=0.18)
            self.create_polygon(op_flat, outline=hc, fill="", width=2)

            mp_flat = [c for pt in self._hex_pts(cx, cy, R*0.70, rot_mid) for c in pt]
            self.create_polygon(mp_flat, outline=mc, fill="", width=1)

            for i in range(6):
                a  = i/6*math.pi*2 + rot_outer + math.pi/6
                self.create_line(cx+R*0.74*math.cos(a), cy+R*0.74*math.sin(a),
                                 cx+R*0.62*math.cos(a), cy+R*0.62*math.sin(a),
                                 fill=dc, width=1)

            rO = R * 0.42;  rOi = R * 0.28
            self.create_oval(cx-rO, cy-rO, cx+rO, cy+rO, outline=hc, fill="", width=2)
            self.create_oval(cx-rOi, cy-rOi, cx+rOi, cy+rOi, outline=dc, fill="", width=1)

            for i in range(12):
                a    = i/12*math.pi*2 + rot_outer*0.4
                long = (i % 3 == 0)
                r2   = rO * (0.78 if long else 0.87)
                self.create_line(cx+rO*math.cos(a), cy+rO*math.sin(a),
                                 cx+r2*math.cos(a), cy+r2*math.sin(a),
                                 fill=(mc if long else dc), width=(2 if long else 1))

            cr = 2 + pulse * 2
            self.create_oval(cx-cr, cy-cr, cx+cr, cy+cr, fill=hc, outline="")
        except Exception:
            pass
        self.t += 1
        self.after(30 if HW_ACCEL else 150, self._draw)


# keep old name as alias so sidebar still works
GeoAccent = OternosLogo


# ─────────────────────────────────────────
#  MIKU LOGO — proper twin-tail silhouette
# ─────────────────────────────────────────
class MikuLogo(tk.Canvas):
    """
    Animated Miku emblem:
      • Head silhouette with twin ponytail bases
      • Two long flowing twin-tails that sway independently
      • ♪ note at centre of head
      • Soft teal glow halo, pink pulse ring when playing
      • Tiny floating sparkles ✦ around the emblem
    """
    def __init__(self, parent, size=54, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self.size = size
        self._bg  = bg
        self.t    = 0
        self.is_playing = False
        # Sparkle positions: (angle_offset, radius_frac, speed, phase)
        self._sparkles = [
            (i * math.pi * 2 / 6, 0.44 + (i % 2) * 0.06,
             0.012 + i * 0.003, i * 1.1)
            for i in range(6)
        ]
        self._draw()

    def _draw(self):
        try:
            self.delete("all")
            S  = self.size
            cx = S / 2
            t  = self.t
            pl = self.is_playing
            pulse  = (math.sin(t * 0.07) * 0.5 + 0.5) if pl else 0.15
            sway_l = math.sin(t * 0.038) * 0.22
            sway_r = math.sin(t * 0.031 + 0.8) * 0.20

            # ── outer glow halo ──
            hr  = S * 0.46
            cy  = S * 0.50
            if pl:
                gv = int(30 + pulse * 50)
                self.create_oval(cx-hr-2, cy-hr-2, cx+hr+2, cy+hr+2,
                                 outline=f"#0a{gv+10:02x}{gv:02x}", fill="", width=3)
            self.create_oval(cx-hr, cy-hr, cx+hr, cy+hr,
                             outline="#0d4a5e", fill="", width=1)

            # ── twin-tail LEFT (flows down-left, brighter teal) ──
            tail_base_lx = cx - S * 0.20
            tail_base_ly = S * 0.30
            pts_l = []
            for i in range(28):
                frac  = i / 27
                # curve: starts near head, sweeps left and down
                angle = math.pi * (0.70 + frac * 0.75) + sway_l * (frac ** 0.6)
                r     = S * (0.04 + frac * 0.42)
                px    = tail_base_lx + r * math.cos(angle)
                py    = tail_base_ly + r * math.sin(angle) * 1.1
                pts_l.extend([px, py])
            if len(pts_l) >= 4:
                # draw thick base tapering to thin tip — two passes
                self.create_line(pts_l, fill="#1e8a84", width=4,
                                 smooth=True, capstyle="round")
                self.create_line(pts_l, fill="#39c5bb", width=2,
                                 smooth=True, capstyle="round")

            # ── twin-tail RIGHT (flows down-right, slightly lighter) ──
            tail_base_rx = cx + S * 0.20
            tail_base_ry = S * 0.28
            pts_r = []
            for i in range(28):
                frac  = i / 27
                angle = math.pi * (0.30 - frac * 0.75) + sway_r * (frac ** 0.6)
                r     = S * (0.04 + frac * 0.40)
                px    = tail_base_rx + r * math.cos(angle)
                py    = tail_base_ry + r * math.sin(angle) * 1.1
                pts_r.extend([px, py])
            if len(pts_r) >= 4:
                self.create_line(pts_r, fill="#1e8a84", width=4,
                                 smooth=True, capstyle="round")
                self.create_line(pts_r, fill="#4dd8d0", width=2,
                                 smooth=True, capstyle="round")

            # ── head silhouette (small rounded oval) ──
            hy  = S * 0.34
            hrx = S * 0.17
            hry = S * 0.15
            head_fill = "#071a28" if not pl else f"#07{int(0x1a+pulse*8):02x}{int(0x28+pulse*10):02x}"
            self.create_oval(cx-hrx, hy-hry, cx+hrx, hy+hry,
                             fill=head_fill, outline="#39c5bb", width=1)

            # ── twin-tail bun circles at top of head ──
            bun_r = S * 0.055
            for bx in (cx - S*0.13, cx + S*0.13):
                self.create_oval(bx-bun_r, hy-hry-bun_r*0.6,
                                 bx+bun_r, hy-hry+bun_r*0.8,
                                 fill="#0a2535", outline="#39c5bb", width=1)

            # ── ♪ note inside head ──
            note_br = int(180 + pulse * 75) if pl else 130
            note_br = min(255, note_br)
            note_col = f"#{note_br:02x}{min(255,note_br+40):02x}{min(255,note_br+38):02x}"
            self.create_text(cx, hy + S*0.01, text="♪",
                             font=("Consolas", max(6, int(S*0.18))),
                             fill=note_col, anchor="center")

            # ── floating sparkles ✦ ──
            for a_off, r_frac, spd, phase in self._sparkles:
                angle = a_off + t * spd + phase
                r     = S * r_frac
                sx    = cx + r * math.cos(angle)
                sy    = S*0.50 + r * math.sin(angle) * 0.85
                spark_v = (math.sin(t * spd * 3 + phase) * 0.5 + 0.5)
                # alternate teal and pink sparkles
                if int(phase) % 2 == 0:
                    sv = int(20 + spark_v * 57)
                    sc = f"#{sv:02x}{min(255,sv*4+30):02x}{min(255,sv*4+25):02x}"
                else:
                    sv = int(20 + spark_v * 60)
                    sc = f"#{min(255,sv*4+50):02x}{sv:02x}{min(255,sv*3+40):02x}"
                self.create_text(sx, sy, text="✦",
                                 font=("Consolas", max(5, int(S*0.10))),
                                 fill=sc, anchor="center")

            # ── pink pulse ring when playing ──
            if pl:
                pr  = S * (0.46 + pulse * 0.04)
                pv  = int(40 + pulse * 80)
                self.create_oval(cx-pr, cy-pr, cx+pr, cy+pr,
                                 outline=f"#{min(255,pv+160):02x}{pv//3:02x}{min(255,pv+100):02x}",
                                 fill="", width=1)

        except Exception:
            pass
        self.t += 1
        self.after(28 if HW_ACCEL else 150, self._draw)


# ─────────────────────────────────────────
#  MIKU CORNER DECO — sakura petals + stars
# ─────────────────────────────────────────
class MikuCornerDeco(tk.Canvas):
    """
    Animated corner deco for Miku theme:
      • Soft rounded sakura-petal corners in teal/pink
      • A tiny spinning ♫ or ✦ at each corner tip
      • Gentle twinkle animation
    """
    def __init__(self, parent, size=28, bg=None, **kw):
        bg = bg or "#03080f"
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self._bg  = bg
        self.size = size
        self.t    = 0
        self._draw()

    def _draw(self):
        try:
            self.delete("all")
            S     = self.size
            t     = self.t
            pulse = (math.sin(t * 0.055) * 0.5 + 0.5)
            p2    = (math.sin(t * 0.040 + 1.2) * 0.5 + 0.5)

            tv = int(25 + pulse * 52)
            pv = int(20 + p2    * 55)
            teal = f"#{tv:02x}{min(255,tv*4+10):02x}{min(255,tv*4+5):02x}"
            pink = f"#{min(255,pv*3+80):02x}{pv//2:02x}{min(255,pv*2+60):02x}"

            M = 2
            L = int(S * 0.40)

            # ── rounded corner arcs (two lines per corner with curved feel) ──
            #    teal: top-left, bottom-right  |  pink: top-right, bottom-left
            def _corner(ox, oy, dx, dy, col):
                # main arm
                self.create_line(ox, oy, ox + dx*L, oy,        fill=col, width=2, capstyle="round")
                self.create_line(ox, oy, ox,        oy + dy*L, fill=col, width=2, capstyle="round")
                # inner accent line (shorter, dimmer)
                dim = _dim(col, 0.45)
                self.create_line(ox + dx*2, oy + dy*2,
                                 ox + dx*(L-2), oy + dy*2,    fill=dim, width=1)
                self.create_line(ox + dx*2, oy + dy*2,
                                 ox + dx*2, oy + dy*(L-2),    fill=dim, width=1)

            def _dim(hexcol, factor):
                r,g,b = int(hexcol[1:3],16), int(hexcol[3:5],16), int(hexcol[5:7],16)
                return f"#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}"

            _corner(M,   M,   +1, +1, teal)
            _corner(S-M, M,   -1, +1, pink)
            _corner(M,   S-M, +1, -1, pink)
            _corner(S-M, S-M, -1, -1, teal)

            # ── centre: alternating ♪ / ✦ that fades in/out ──
            sym   = "♪" if (t // 40) % 2 == 0 else "✦"
            sym_v = int(15 + pulse * 45)
            sym_c = f"#{sym_v:02x}{min(255,sym_v*4):02x}{min(255,sym_v*4-3):02x}"
            self.create_text(S//2, S//2, text=sym,
                             font=("Consolas", max(5, S//4)),
                             fill=sym_c, anchor="center")

        except Exception:
            pass
        self.t += 1
        self.after(38 if HW_ACCEL else 200, self._draw)


# ─────────────────────────────────────────
#  MIKU DATA TICKER — notes, JP, lyrics snippets
# ─────────────────────────────────────────
class MikuTicker(tk.Canvas):
    """
    Scrolling Miku ticker:
      • Music notes (♪ ♫ ♩ ♬) and Vocaloid JP characters
      • Short lyric/phrase fragments
      • Alternating teal and pink coloring per token
      • Occasional ✦ sparkle bursts
    """
    # Tokens: notes, JP chars, short phrases
    _TOKENS = [
        "♪", "♫", "♩", "♬", "✦", "✧",
        "ミ", "ク", "初", "音", "歌", "声", "楽", "夢",
        "MIKU", "VOCA", "39♪", "歌声", "音楽",
        "♪ ♫", "✦ ✦",
    ]

    def __init__(self, parent, width=200, height=12, bg=None, **kw):
        bg = bg or "#071520"
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg     = bg
        self._width  = width
        self._height = height
        self.t       = 0
        self._scroll = 0.0
        self._data   = self._gen()  # list of (token, color_mode) tuples
        self._draw()

    def _gen(self):
        import random
        result = []
        for _ in range(self._width // 18 + 8):
            tok   = random.choice(self._TOKENS)
            mode  = random.choice(("teal", "pink", "dim"))
            result.append((tok, mode))
        return result

    def _draw(self):
        try:
            self.delete("all")
            import random
            self.t       += 1
            self._scroll += 0.28
            step = 18
            if self._scroll >= step:
                self._scroll -= step
                self._data.pop(0)
                tok  = random.choice(self._TOKENS)
                mode = random.choice(("teal", "pink", "dim"))
                self._data.append((tok, mode))
            if self.t % 10 == 0:
                idx  = random.randint(0, len(self._data)-1)
                tok  = random.choice(self._TOKENS)
                mode = random.choice(("teal", "pink", "dim"))
                self._data[idx] = (tok, mode)

            t = self.t
            off = -self._scroll
            for i, (tok, mode) in enumerate(self._data):
                x = off + i * step
                if x > self._width: break
                fade = max(0.0, min(1.0, x / max(1, self._width * 0.15)))
                flicker = (math.sin(t * 0.08 + i * 0.7) * 0.5 + 0.5)
                if mode == "teal":
                    v = int((18 + fade * 38) * (0.6 + flicker * 0.4))
                    col = f"#{v:02x}{min(255,v*4+10):02x}{min(255,v*4+5):02x}"
                elif mode == "pink":
                    v = int((15 + fade * 35) * (0.6 + flicker * 0.4))
                    col = f"#{min(255,v*3+50):02x}{v//2:02x}{min(255,v*2+40):02x}"
                else:
                    v = int(12 + fade * 22)
                    col = f"#{v:02x}{min(255,v+18):02x}{min(255,v+16):02x}"
                self.create_text(x + 2, self._height // 2, text=tok,
                    font=("Consolas", 6), fill=col, anchor="w")
        except Exception:
            pass
        self.after(48 if HW_ACCEL else 999, self._draw)


class CornerBrackets(tk.Canvas):
    """
    Animated corner bracket decoration.
    Draws L-shaped corner marks that pulse and occasionally glitch.
    """
    def __init__(self, parent, size=60, bg=None, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=size, height=size, **kw)
        self._bg  = bg
        self.size = size
        self.t    = 0
        self._glitch_t = 0
        self._draw()

    def _draw(self):
        try:
            self.delete("all")
            S = self.size
            t = self.t
            L = int(S * 0.35)   # bracket arm length
            W = 2               # line width
            M = 3               # margin from edge
            pulse = (math.sin(t * 0.05) * 0.5 + 0.5)
            base = int(38 + pulse * 28)
            col  = f"#{base:02x}{base:02x}{base:02x}"
            # Glitch: occasionally offset one corner
            gx, gy = 0, 0
            if self.t % 47 < 3:
                gx = (self.t % 3) - 1
                gy = (self.t % 2)
            # Top-left
            self.create_line(M,       M,       M+L,     M,       fill=col, width=W)
            self.create_line(M,       M,       M,       M+L,     fill=col, width=W)
            # Top-right
            self.create_line(S-M,     M+gx,    S-M-L,   M+gx,    fill=col, width=W)
            self.create_line(S-M,     M+gx,    S-M,     M+L+gx,  fill=col, width=W)
            # Bottom-left
            self.create_line(M+gy,    S-M,     M+L+gy,  S-M,     fill=col, width=W)
            self.create_line(M+gy,    S-M,     M+gy,    S-M-L,   fill=col, width=W)
            # Bottom-right
            self.create_line(S-M,     S-M,     S-M-L,   S-M,     fill=col, width=W)
            self.create_line(S-M,     S-M,     S-M,     S-M-L,   fill=col, width=W)
            # Centre crosshair — faint
            cx_col = f"#{int(base*0.4):02x}{int(base*0.4):02x}{int(base*0.4):02x}"
            cx = S // 2
            cy = S // 2
            self.create_line(cx-4, cy, cx+4, cy, fill=cx_col, width=1)
            self.create_line(cx, cy-4, cx, cy+4, fill=cx_col, width=1)
        except Exception:
            pass
        self.t += 1
        self.after(40 if HW_ACCEL else 200, self._draw)


class DataTicker(tk.Canvas):
    """
    Scrolling hex data ticker strip — Signalis-style ambient UI decoration.
    Renders a horizontal strip of slowly scrolling fake hex/binary values.
    """
    _CHARS = "0123456789ABCDEF"
    def __init__(self, parent, width=200, height=14, bg=None, **kw):
        bg = bg or C["panel"]
        super().__init__(parent, bg=bg, highlightthickness=0,
                         width=width, height=height, **kw)
        self._bg     = bg
        self._width  = width
        self._height = height
        self.t       = 0
        self._cols   = max(1, width // 22)
        self._data   = self._gen()
        self._scroll = 0.0
        self._draw()

    def _gen(self):
        import random
        return [
            f"{random.randint(0,0xFFFF):04X}"
            for _ in range(self._cols + 4)
        ]

    def _draw(self):
        try:
            self.delete("all")
            import random
            self.t += 1
            self._scroll += 0.18
            if self._scroll >= 22:
                self._scroll -= 22
                self._data.pop(0)
                self._data.append(f"{random.randint(0,0xFFFF):04X}")
            # Occasionally mutate a cell
            if self.t % 8 == 0:
                idx = random.randint(0, len(self._data)-1)
                self._data[idx] = f"{random.randint(0,0xFFFF):04X}"
            off = -self._scroll
            for i, val in enumerate(self._data):
                x = off + i * 22
                if x > self._width: break
                fade = max(0, min(1, (x / max(1, self._width))))
                brightness = int(22 + fade * 20)
                col = f"#{brightness:02x}{brightness:02x}{brightness:02x}"
                self.create_text(x + 2, self._height // 2, text=val,
                    font=("Courier New", 6), fill=col, anchor="w")
        except Exception:
            pass
        self.after(60 if HW_ACCEL else 999, self._draw)


# ─────────────────────────────────────────
#  PLAYLIST MOSAIC ART GENERATOR
# ─────────────────────────────────────────
class MosaicArt:
    """Generates a 2×2 mosaic thumbnail from up to 4 album art images."""

    @staticmethod
    def from_tracks(tracks, size=64):
        """Return a PhotoImage mosaic from a list of track dicts (need 'art_url' or 'path')."""
        try:
            from PIL import Image as PILImage
        except ImportError:
            return MosaicArt._placeholder(size)

        imgs = []
        seen_paths = set()
        for t in tracks:
            if len(imgs) >= 4:
                break
            src = t.get("art_path") or t.get("path", "")
            if src and src not in seen_paths:
                seen_paths.add(src)
                try:
                    img = MosaicArt._extract_art(src, size // 2)
                    if img:
                        imgs.append(img)
                except Exception:
                    pass

        if not imgs:
            return MosaicArt._placeholder(size)

        canvas = PILImage.new("RGB", (size, size), (17, 17, 17))
        half = size // 2
        positions = [(0, 0), (half, 0), (0, half), (half, half)]
        for i, pos in enumerate(positions):
            img = imgs[i % len(imgs)].resize((half, half), PILImage.LANCZOS)
            canvas.paste(img, pos)

        import io
        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        buf.seek(0)
        import base64
        b64 = base64.b64encode(buf.read()).decode()
        return tk.PhotoImage(data=b64)

    @staticmethod
    def _extract_art(path, size):
        """Try to extract embedded album art from an audio file."""
        try:
            from PIL import Image as PILImage
            import io
            try:
                from mutagen.mp3 import MP3
                from mutagen.id3 import ID3
                tags = ID3(path)
                for tag in tags.values():
                    if hasattr(tag, "data"):
                        return PILImage.open(io.BytesIO(tag.data)).convert("RGB")
            except Exception:
                pass
        except ImportError:
            pass
        return None

    @staticmethod
    def _placeholder(size):
        """Return a simple dark placeholder PhotoImage."""
        data = f"P6\n{size} {size}\n255\n" + bytes([17, 17, 17] * size * size)
        try:
            import tempfile, os
            f = tempfile.NamedTemporaryFile(suffix=".ppm", delete=False)
            f.write(f"P6\n{size} {size}\n255\n".encode())
            f.write(bytes([17, 17, 17] * size * size))
            f.close()
            img = tk.PhotoImage(file=f.name)
            os.unlink(f.name)
            return img
        except Exception:
            return None


# ─────────────────────────────────────────
#  TRACK RECOMMENDER
# ─────────────────────────────────────────
class TrackRecommender:
    """Simple content-based recommender using listening history + metadata similarity."""

    def __init__(self, library, history):
        self.library = library
        self.history = history  # list of {title, artist, album, ts}

    def recommend(self, n=20):
        """Return list of library indices scored by similarity to recent listening."""
        if not self.history or not self.library:
            return list(range(min(n, len(self.library))))

        # Build frequency map of artists/albums from recent 50 plays
        from collections import Counter
        recent = self.history[-50:]
        artists = Counter(e.get("artist","").lower() for e in recent)
        albums  = Counter(e.get("album","").lower()  for e in recent)
        played  = {(e.get("artist","").lower(), e.get("title","").lower())
                   for e in recent}

        scores = []
        for i, t in enumerate(self.library):
            a  = t.get("artist","").lower()
            al = t.get("album","").lower()
            ti = t.get("title","").lower()
            # Skip recently played
            if (a, ti) in played:
                continue
            score = artists.get(a, 0) * 3 + albums.get(al, 0) * 1.5
            scores.append((score, i))

        scores.sort(key=lambda x: -x[0])
        # Mix top-scored with some random discovery
        top    = [i for _, i in scores[:n*2]]
        result = top[:n//2]
        if len(top) > n//2:
            result += random.sample(top[n//2:], min(n//2, len(top)-n//2))
        if len(result) < n:
            # Pad with random unplayed tracks
            remaining = [i for i in range(len(self.library))
                         if i not in result and
                         (self.library[i].get("artist","").lower(),
                          self.library[i].get("title","").lower()) not in played]
            random.shuffle(remaining)
            result += remaining[:n - len(result)]
        return result[:n]


# ─────────────────────────────────────────
#  NORMALIZATION METER
# ─────────────────────────────────────────
class NormMeter:
    """Real-time RMS loudness meter drawn as a segmented bar."""

    def __init__(self, parent, width=180, height=8):
        self.cv     = tk.Canvas(parent, bg=C["panel"], width=width, height=height,
                                highlightthickness=0)
