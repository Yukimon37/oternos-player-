"""
mixer.py — OTERNOS PLAYER
Standalone offline audio editor / mixer.

Drop any audio file in → adjust EQ, dynamics, effects, pan, volume → export.
No live playback dependency. Uses scipy + soundfile for DSP processing.

Tab key: "mixer" | Frame attr: mixer_frame
Lifecycle: build(parent) → on_view_shown() → on_view_hidden() → destroy()
"""

from __future__ import annotations
import sys
import os
import threading
import math
import time
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

if getattr(sys, "frozen", False):
    from oternos.utils import C, FM, FMS, FML, FMX, YT_CACHE
else:
    from .utils import C, FM, FMS, FML, FMX, YT_CACHE

# ── optional DSP deps ─────────────────────────────────────────────────────────
try:
    import numpy as _np
    import soundfile as _sf
    from scipy import signal as _sig
    from scipy.signal import lfilter, resample_poly
    _DSP_OK = True
except ImportError:
    _DSP_OK = False

# ── accent colours ────────────────────────────────────────────────────────────
_GREEN  = "#2cb67d"
_YEL    = "#c8a84b"
_RED    = C["red"]

# ── 10-band EQ centre frequencies ────────────────────────────────────────────
_EQ_BANDS = [
    (32,    "32"),
    (64,    "64"),
    (125,   "125"),
    (250,   "250"),
    (500,   "500"),
    (1000,  "1k"),
    (2000,  "2k"),
    (4000,  "4k"),
    (8000,  "8k"),
    (16000, "16k"),
]
_DB_RANGE   = 12.0
_WAVEFORM_H = 80


# ─────────────────────────────────────────────────────────────────────────────
#  Small helpers
# ─────────────────────────────────────────────────────────────────────────────
def _btn(parent, text, cmd, fg=None, bg=None, font=None, padx=10, pady=3):
    fg   = fg   or C["white2"]
    bg   = bg   or C["panel2"]
    font = font or FMS
    b = tk.Label(parent, text=text, font=font, fg=fg, bg=bg,
                 padx=padx, pady=pady, cursor="hand2", relief="flat")
    b.bind("<Button-1>", lambda e: cmd())
    b.bind("<Enter>",    lambda e: b.config(fg=C["white"],  bg=C["select2"]))
    b.bind("<Leave>",    lambda e: b.config(fg=fg,          bg=bg))
    return b


# ─────────────────────────────────────────────────────────────────────────────
#  Waveform canvas
# ─────────────────────────────────────────────────────────────────────────────
class _Waveform:
    def __init__(self, parent):
        self.cv = tk.Canvas(parent, bg=C["panel"], height=_WAVEFORM_H,
                            highlightthickness=1,
                            highlightbackground=C["border"])
        self.cv.pack(fill="x", padx=20, pady=(4, 0))
        self._data = None
        self._info_lbl = tk.Label(parent, text="", font=FMS,
                                  fg=C["white3"], bg=C["bg"])
        self._info_lbl.pack(anchor="w", padx=22)
        self.cv.bind("<Configure>", lambda e: self._redraw())

    def load(self, data, sr, label=""):
        self._data = data
        self._sr   = sr
        self._info_lbl.config(text=label)
        self._redraw()

    def clear(self):
        self._data = None
        self._info_lbl.config(text="")
        self.cv.delete("all")

    def _redraw(self):
        self.cv.delete("all")
        W = self.cv.winfo_width()
        H = self.cv.winfo_height() or _WAVEFORM_H
        if W < 4 or self._data is None or not _DSP_OK:
            return
        try:
            mono  = self._data[:, 0] if self._data.ndim > 1 else self._data
            chunk = max(1, len(mono) // W)
            mid   = H // 2
            for x in range(min(W, len(mono) // chunk)):
                seg = mono[x*chunk:(x+1)*chunk]
                p   = float(_np.max(_np.abs(seg)))
                ph  = int(p * (mid - 2))
                col = _GREEN if p < 0.7 else (_YEL if p < 0.9 else _RED)
                self.cv.create_line(x, mid - ph, x, mid + ph, fill=col)
            self.cv.create_line(0, mid, W, mid, fill=C["border"])
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  Interactive 10-band EQ display
# ─────────────────────────────────────────────────────────────────────────────
class _EQDisplay:
    def __init__(self, parent, gain_vars: list):
        self.cv = tk.Canvas(parent, bg=C["panel"], height=150,
                            highlightthickness=1,
                            highlightbackground=C["border"])
        self.cv.pack(fill="x", padx=20, pady=(6, 2))
        self._vars  = gain_vars
        self._drag  = None
        self._dy    = 0
        self.cv.bind("<Configure>",       lambda e: self._redraw())
        self.cv.bind("<ButtonPress-1>",   self._press)
        self.cv.bind("<B1-Motion>",       self._move)
        self.cv.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", None))
        self.cv.bind("<Double-Button-1>", self._dbl)

    def _bx(self, i, W):
        m = 28
        return int(m + i * (W - 2*m) / max(len(_EQ_BANDS)-1, 1))

    def _db2y(self, db, H):
        return int(H//2 - db / _DB_RANGE * (H//2 - 12))

    def _y2db(self, y, H):
        return max(-_DB_RANGE, min(_DB_RANGE,
               (H//2 - y) / (H//2 - 12) * _DB_RANGE))

    def _redraw(self):
        self.cv.delete("all")
        W = self.cv.winfo_width()
        H = self.cv.winfo_height() or 150
        if W < 4:
            return
        mid = H // 2
        # Grid
        for db, lbl in [(_DB_RANGE, f"+{int(_DB_RANGE)}dB"), (6,"+6dB"),
                        (0,"0dB"), (-6,"-6dB"), (-_DB_RANGE,f"-{int(_DB_RANGE)}dB")]:
            y  = self._db2y(db, H)
            cl = C["border2"] if db == 0 else C["border"]
            self.cv.create_line(0, y, W, y, fill=cl, dash=(2,4))
            self.cv.create_text(3, y-1, text=lbl, font=("Courier New", 6),
                                fill=C["white3"], anchor="w")
        # Freq labels + node x positions
        xs, ys = [], []
        for i, (_, lbl) in enumerate(_EQ_BANDS):
            x = self._bx(i, W)
            y = self._db2y(self._vars[i].get(), H)
            xs.append(x); ys.append(y)
            self.cv.create_text(x, H - 4, text=lbl,
                                font=("Courier New", 6), fill=C["white3"], anchor="s")
        # Curve
        if len(xs) >= 2:
            pts = []
            for x, y in zip(xs, ys):
                pts += [x, y]
            self.cv.create_line(*pts, fill=C["white3"], width=1, smooth=True)
        # Nodes
        for i, (x, y) in enumerate(zip(xs, ys)):
            db  = self._vars[i].get()
            col = _GREEN if db >= 0 else (_RED if db < -6 else _YEL)
            self.cv.create_oval(x-5, y-5, x+5, y+5,
                                fill=col, outline=C["white"], width=1)
            if abs(db) > 0.4:
                self.cv.create_text(x, y-9, text=f"{db:+.0f}",
                                    font=("Courier New", 6), fill=C["white2"])

    def _press(self, e):
        W = self.cv.winfo_width()
        H = self.cv.winfo_height() or 150
        best, bd = None, 18
        for i in range(len(_EQ_BANDS)):
            x = self._bx(i, W)
            y = self._db2y(self._vars[i].get(), H)
            d = math.hypot(e.x - x, e.y - y)
            if d < bd:
                best, bd = i, d
        self._drag = best
        self._dy   = e.y

    def _move(self, e):
        if self._drag is None:
            return
        H  = self.cv.winfo_height() or 150
        db = self._y2db(e.y, H)
        self._vars[self._drag].set(round(db, 1))
        self._dy = e.y
        self._redraw()

    def _dbl(self, e):
        W = self.cv.winfo_width()
        H = self.cv.winfo_height() or 150
        for i in range(len(_EQ_BANDS)):
            x = self._bx(i, W)
            y = self._db2y(self._vars[i].get(), H)
            if math.hypot(e.x - x, e.y - y) < 16:
                self._vars[i].set(0.0)
                self._redraw()
                return


# ─────────────────────────────────────────────────────────────────────────────
#  MixerView
# ─────────────────────────────────────────────────────────────────────────────
class MixerView:
    def __init__(self, app):
        self.app   = app
        self.frame: tk.Frame | None     = None
        self._popup: tk.Toplevel | None = None
        self._processing = False

        # Source audio
        self._src_path = ""
        self._src_data = None
        self._src_sr   = 44100
        self._src_dur  = 0.0

        # Control vars — created once, shared between tab and popout
        self._vol_var     = tk.DoubleVar(value=1.0)
        self._pan_var     = tk.DoubleVar(value=0.0)
        self._bass_var    = tk.DoubleVar(value=0.0)
        self._treble_var  = tk.DoubleVar(value=0.0)
        self._norm_var    = tk.BooleanVar(value=False)
        self._fade_in     = tk.DoubleVar(value=0.0)
        self._fade_out    = tk.DoubleVar(value=0.0)
        self._trim_start  = tk.DoubleVar(value=0.0)
        self._trim_end    = tk.DoubleVar(value=0.0)
        self._speed_var   = tk.DoubleVar(value=1.0)
        self._rev_var     = tk.BooleanVar(value=False)
        self._fmt_var     = tk.StringVar(value="wav")
        self._quality_var = tk.StringVar(value="192k")
        self._eq_vars     = [tk.DoubleVar(value=0.0) for _ in _EQ_BANDS]

        # UI widget refs
        self._waveform:   _Waveform  | None = None
        self._eq_display: _EQDisplay | None = None
        self._status_lbl: tk.Label   | None = None
        self._file_lbl:   tk.Label   | None = None
        self._vol_lbl:    tk.Label   | None = None
        self._pan_cv:     tk.Canvas  | None = None
        self._pan_dy = 0
        self._eq_val_lbls: list[tk.Label] = []
        self._scroll_cv: tk.Canvas | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def build(self, parent: tk.Frame) -> tk.Frame:
        self.frame = tk.Frame(parent, bg=C["bg"])
        self._build_ui(self.frame)
        return self.frame

    def on_view_shown(self):
        if self.frame and self.frame.winfo_exists():
            self.frame.update_idletasks()
            self.frame.winfo_toplevel().update_idletasks()
        for cv in ([getattr(self, "_scroll_cv", None)] +
                   ([self._waveform.cv]   if self._waveform   else []) +
                   ([self._eq_display.cv] if self._eq_display else []) +
                   ([self._pan_cv]        if self._pan_cv     else [])):
            if cv:
                try: cv.update_idletasks()
                except Exception: pass
        self.app.root.after(80, self._deferred_redraw)

    def _deferred_redraw(self):
        if self._waveform:   self._waveform._redraw()
        if self._eq_display: self._eq_display._redraw()
        if self._pan_cv:     self._draw_pan()

    def on_view_hidden(self):
        pass

    def destroy(self):
        self._close_popup()

    def open_window(self):
        """Called from Settings ⊞ OPEN MIXER button."""
        self._open_popup()

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self, root):
        # ── Menubar (Audacity-style) ──────────────────────────────────────────
        # Only attach a real menubar when root is a Toplevel window
        if isinstance(root, (tk.Tk, tk.Toplevel)):
            mb = tk.Menu(root, bg=C["panel2"], fg=C["white"],
                         activebackground=C["select2"], activeforeground=C["glow"],
                         font=FMS, bd=0, relief="flat", activeborderwidth=0)
            root.config(menu=mb)

            # ── File menu ────────────────────────────────────────────────────
            m_file = tk.Menu(mb, tearoff=0,
                             bg=C["panel2"], fg=C["white"],
                             activebackground=C["select2"], activeforeground=C["glow"],
                             font=FMS, bd=0, relief="flat", activeborderwidth=0)
            mb.add_cascade(label="File", menu=m_file)
            m_file.add_command(label="Load File...",           command=self._load_file)
            m_file.add_command(label="Load from Library",      command=self._load_from_lib)
            m_file.add_separator()
            m_file.add_command(label="Clear",                  command=self._clear_file)

            # ── Edit menu ────────────────────────────────────────────────────
            m_edit = tk.Menu(mb, tearoff=0,
                             bg=C["panel2"], fg=C["white"],
                             activebackground=C["select2"], activeforeground=C["glow"],
                             font=FMS, bd=0, relief="flat", activeborderwidth=0)
            mb.add_cascade(label="Edit", menu=m_edit)
            m_edit.add_command(label="Reset EQ to Flat",       command=self.reset_eq)
            m_edit.add_command(label="Reset All Effects",      command=self.reset_effects)
            m_edit.add_separator()
            m_edit.add_command(label="Apply EQ Preset: Flat",
                               command=lambda: self._apply_preset("flat"))
            m_edit.add_command(label="Apply EQ Preset: Bass Boost",
                               command=lambda: self._apply_preset("bass boost"))
            m_edit.add_command(label="Apply EQ Preset: Treble Boost",
                               command=lambda: self._apply_preset("treble boost"))
            m_edit.add_command(label="Apply EQ Preset: Vocal",
                               command=lambda: self._apply_preset("vocal"))
            m_edit.add_command(label="Apply EQ Preset: Electronic",
                               command=lambda: self._apply_preset("electronic"))
            m_edit.add_command(label="Apply EQ Preset: Rock",
                               command=lambda: self._apply_preset("rock"))
            m_edit.add_command(label="Apply EQ Preset: Classical",
                               command=lambda: self._apply_preset("classical"))
            m_edit.add_command(label="Apply EQ Preset: Podcast",
                               command=lambda: self._apply_preset("podcast"))

            # ── Effects menu ─────────────────────────────────────────────────
            m_fx = tk.Menu(mb, tearoff=0,
                           bg=C["panel2"], fg=C["white"],
                           activebackground=C["select2"], activeforeground=C["glow"],
                           font=FMS, bd=0, relief="flat", activeborderwidth=0)
            mb.add_cascade(label="Effects", menu=m_fx)
            m_fx.add_command(label="Reverse Audio",
                             command=lambda: (self._rev_var.set(not self._rev_var.get()),
                                             self._set_status(
                                                 "Reverse: ON" if self._rev_var.get() else "Reverse: OFF")))
            m_fx.add_command(label="Normalize Output",
                             command=lambda: (self._norm_var.set(not self._norm_var.get()),
                                             self._set_status(
                                                 "Normalize: ON" if self._norm_var.get() else "Normalize: OFF")))
            m_fx.add_separator()
            m_fx.add_command(label="Set Speed: 0.5×  (slow)",
                             command=lambda: self._speed_var.set(0.5))
            m_fx.add_command(label="Set Speed: 1.0×  (normal)",
                             command=lambda: self._speed_var.set(1.0))
            m_fx.add_command(label="Set Speed: 1.5×  (fast)",
                             command=lambda: self._speed_var.set(1.5))
            m_fx.add_command(label="Set Speed: 2.0×  (double)",
                             command=lambda: self._speed_var.set(2.0))
            m_fx.add_separator()
            m_fx.add_command(label="Center Pan",
                             command=lambda: (self._pan_var.set(0.0), self._draw_pan()))
            m_fx.add_command(label="Pan Hard Left",
                             command=lambda: (self._pan_var.set(-1.0), self._draw_pan()))
            m_fx.add_command(label="Pan Hard Right",
                             command=lambda: (self._pan_var.set(1.0), self._draw_pan()))
            m_fx.add_separator()
            m_fx.add_command(label="Volume: 100%  (unity)",
                             command=lambda: self._vol_var.set(1.0))
            m_fx.add_command(label="Volume: 150%  (boost)",
                             command=lambda: self._vol_var.set(1.5))
            m_fx.add_command(label="Volume: 50%   (cut)",
                             command=lambda: self._vol_var.set(0.5))

            # ── Export menu ──────────────────────────────────────────────────
            m_exp = tk.Menu(mb, tearoff=0,
                            bg=C["panel2"], fg=C["white"],
                            activebackground=C["select2"], activeforeground=C["glow"],
                            font=FMS, bd=0, relief="flat", activeborderwidth=0)
            mb.add_cascade(label="Export", menu=m_exp)
            m_exp.add_command(label="Preview in Player",       command=self._preview)
            m_exp.add_separator()
            m_exp.add_command(label="Export as WAV",
                              command=lambda: (self._fmt_var.set("wav"),  self._export()))
            m_exp.add_command(label="Export as FLAC",
                              command=lambda: (self._fmt_var.set("flac"), self._export()))
            m_exp.add_command(label="Export as MP3",
                              command=lambda: (self._fmt_var.set("mp3"),  self._export()))
            m_exp.add_command(label="Export as OGG",
                              command=lambda: (self._fmt_var.set("ogg"),  self._export()))
            m_exp.add_separator()
            m_exp.add_command(label="Export & Add to Library", command=self._export_to_library)

        else:
            # Embedded in a Frame (not a window) — plain header only
            hdr = tk.Frame(root, bg=C["bg"])
            hdr.pack(fill="x", padx=20, pady=(14, 0))
            tk.Label(hdr, text="MIXER", font=FMX,
                     fg=C["white"], bg=C["bg"]).pack(side="left")
            tk.Label(hdr, text="load any file  ·  edit EQ / effects  ·  export",
                     font=FMS, fg=C["white3"], bg=C["bg"]).pack(side="left", padx=12)

        tk.Frame(root, bg=C["border"], height=1).pack(fill="x", pady=(8, 0))

        if not _DSP_OK:
            tk.Label(root,
                     text="⚠  scipy + soundfile not installed — run:  pip install scipy soundfile",
                     font=FM, fg=_RED, bg=C["bg"]).pack(pady=40)
            return

        # Scrollable body
        outer = tk.Frame(root, bg=C["bg"])
        outer.pack(fill="both", expand=True)
        scv = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        vsb = tk.Scrollbar(outer, orient="vertical", command=scv.yview,
                           bg=C["panel2"], troughcolor=C["bg"])
        scv.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        scv.pack(fill="both", expand=True)
        body = tk.Frame(scv, bg=C["bg"])
        wid  = scv.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda e: scv.configure(scrollregion=scv.bbox("all")))
        def _scv_resize(e):
            try: scv.itemconfig(wid, width=e.width)
            except Exception: pass
        scv.bind("<Configure>", _scv_resize)
        scv.bind("<MouseWheel>",
                 lambda e: scv.yview_scroll(-(e.delta // 120), "units"))
        self._scroll_cv = scv

        self._build_load(body)
        self._build_waveform(body)
        self._build_eq(body)
        self._build_dynamics(body)
        self._build_effects(body)
        self._build_export(body)
        self._build_status(body)

    def _section(self, parent, title) -> tk.Frame:
        wrap = tk.Frame(parent, bg=C["bg"])
        wrap.pack(fill="x", padx=20, pady=(14, 0))
        tk.Label(wrap, text=title, font=FML,
                 fg=C["white"], bg=C["bg"]).pack(anchor="w")
        tk.Frame(wrap, bg=C["border"], height=1).pack(fill="x", pady=(4, 8))
        body = tk.Frame(wrap, bg=C["bg"])
        body.pack(fill="x")
        return body

    def _labeled_scale(self, parent, label, var, lo, hi, res=0.1, fmt="{:.1f}",
                       length=200, orient="horizontal"):
        row = tk.Frame(parent, bg=C["bg"])
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, font=FMS, fg=C["white2"], bg=C["bg"],
                 width=18, anchor="w").pack(side="left")
        val_lbl = tk.Label(row, text=fmt.format(var.get()),
                           font=FMS, fg=C["white2"], bg=C["bg"], width=9, anchor="e")
        val_lbl.pack(side="right")
        tk.Scale(row, from_=lo, to=hi, resolution=res, variable=var,
                 orient=orient, length=length, showvalue=False, sliderlength=10,
                 troughcolor=C["bg"], bg=C["bg"], activebackground=C["white"],
                 highlightthickness=0, relief="flat",
                 command=lambda v, l=val_lbl, f=fmt: l.config(text=f.format(float(v)))
                 ).pack(side="left", fill="x", expand=True)
        return val_lbl

    # ── LOAD ─────────────────────────────────────────────────────────────────
    def _build_load(self, parent):
        body = self._section(parent, ">> SOURCE FILE")
        row  = tk.Frame(body, bg=C["bg"])
        row.pack(fill="x")
        _btn(row, "⊕  LOAD FILE",
             self._load_file, fg=C["white"], bg=C["panel2"], font=FM).pack(side="left", padx=(0,6))
        _btn(row, "⊕  FROM LIBRARY",
             self._load_from_lib).pack(side="left", padx=(0,6))
        _btn(row, "✕  CLEAR",
             self._clear_file, fg=C["white3"]).pack(side="left")
        self._file_lbl = tk.Label(body, text="No file loaded — click ⊕ LOAD FILE to begin",
                                  font=FMS, fg=C["white3"], bg=C["bg"])
        self._file_lbl.pack(anchor="w", pady=(6, 0))

    def _build_waveform(self, parent):
        self._waveform = _Waveform(parent)

    # ── EQ ───────────────────────────────────────────────────────────────────
    def _build_eq(self, parent):
        body = self._section(parent, ">> 10-BAND PARAMETRIC EQ  (drag nodes · double-click to reset)")
        # Preset buttons
        prow = tk.Frame(body, bg=C["bg"])
        prow.pack(fill="x", pady=(0, 4))
        tk.Label(prow, text="Preset:", font=FMS,
                 fg=C["white2"], bg=C["bg"]).pack(side="left", padx=(0,6))
        for p in ["flat","bass boost","treble boost","vocal",
                  "electronic","rock","classical","podcast"]:
            _btn(prow, p, lambda pr=p: self._apply_preset(pr),
                 fg=C["white3"], bg=C["panel"], padx=6, pady=2).pack(side="left", padx=2)
        _btn(prow, "↺ reset all", self._reset_eq,
             fg=C["white3"], padx=6, pady=2).pack(side="left", padx=(10, 0))

        # EQ display
        self._eq_display = _EQDisplay(body, self._eq_vars)

        # Numeric value row
        vrow = tk.Frame(body, bg=C["bg"])
        vrow.pack(fill="x", padx=20, pady=(2, 0))
        self._eq_val_lbls = []
        for i, (_, lbl) in enumerate(_EQ_BANDS):
            col = tk.Frame(vrow, bg=C["bg"])
            col.pack(side="left", expand=True)
            tk.Label(col, text=lbl, font=("Courier New", 6),
                     fg=C["white3"], bg=C["bg"]).pack()
            vl = tk.Label(col, text="0.0", font=("Courier New", 6),
                          fg=C["white2"], bg=C["bg"])
            vl.pack()
            self._eq_val_lbls.append(vl)
            self._eq_vars[i].trace_add("write",
                lambda *a, idx=i: self._eq_changed(idx))

    def _eq_changed(self, i):
        try:
            db = self._eq_vars[i].get()
            if i < len(self._eq_val_lbls):
                self._eq_val_lbls[i].config(text=f"{db:+.1f}")
            if self._eq_display:
                self._eq_display._redraw()
        except Exception:
            pass

    def _apply_preset(self, name):
        P = {
            "flat":         [0]*10,
            "bass boost":   [9, 8, 6, 3, 1, 0, 0, 0, 0, 0],
            "treble boost": [0, 0, 0, 0, 1, 2, 4, 6, 7, 7],
            "vocal":        [-2,-1, 0, 2, 5, 5, 3, 1, 0,-1],
            "electronic":   [7, 5, 2,-1,-2,-1, 2, 4, 5, 4],
            "rock":         [5, 4, 2, 0,-1, 0, 2, 3, 4, 4],
            "classical":    [3, 2, 1, 0, 0, 0, 1, 2, 3, 3],
            "podcast":      [-2,-2,-1, 2, 5, 5, 4, 2, 1, 0],
        }
        for i, v in enumerate(P.get(name, [0]*10)[:len(self._eq_vars)]):
            self._eq_vars[i].set(float(v))

    def _reset_eq(self):
        for v in self._eq_vars:
            v.set(0.0)

    # ── DYNAMICS ─────────────────────────────────────────────────────────────
    def _build_dynamics(self, parent):
        body = self._section(parent, ">> VOLUME  ·  PAN  ·  SHELVING")
        cols = tk.Frame(body, bg=C["bg"])
        cols.pack(fill="x")

        # Left: vol + pan
        left = tk.Frame(cols, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 20))

        vrow = tk.Frame(left, bg=C["bg"])
        vrow.pack(fill="x", pady=3)
        tk.Label(vrow, text="Volume  (0 – 200%)", font=FMS,
                 fg=C["white2"], bg=C["bg"], width=20, anchor="w").pack(side="left")
        self._vol_lbl = tk.Label(vrow, text="100%  (0.0 dB)",
                                 font=FMS, fg=C["white2"], bg=C["bg"], width=14, anchor="e")
        self._vol_lbl.pack(side="right")
        tk.Scale(vrow, from_=0.0, to=2.0, resolution=0.01,
                 variable=self._vol_var, orient="horizontal", length=180,
                 showvalue=False, sliderlength=12,
                 troughcolor=C["bg"], bg=C["bg"], activebackground=C["white"],
                 highlightthickness=0, relief="flat",
                 command=self._on_vol).pack(side="left", fill="x", expand=True)

        prow = tk.Frame(left, bg=C["bg"])
        prow.pack(fill="x", pady=6)
        tk.Label(prow, text="Pan  (drag knob · dbl-click center)", font=FMS,
                 fg=C["white2"], bg=C["bg"]).pack(anchor="w")
        self._pan_cv = tk.Canvas(prow, width=70, height=70,
                                 bg=C["bg"], highlightthickness=0)
        self._pan_cv.pack(anchor="w")
        self._draw_pan()
        self._pan_cv.bind("<ButtonPress-1>",   self._pan_press)
        self._pan_cv.bind("<B1-Motion>",       self._pan_drag)
        self._pan_cv.bind("<Double-Button-1>",
                         lambda e: (self._pan_var.set(0.0), self._draw_pan()))

        # Right: shelves + normalize
        right = tk.Frame(cols, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        tk.Label(right, text="Bass shelf  (dB)", font=FMS,
                 fg=C["white2"], bg=C["bg"]).pack(anchor="w")
        self._labeled_scale(right, "", self._bass_var, -_DB_RANGE, _DB_RANGE,
                            res=0.5, fmt="{:+.1f} dB")

        tk.Label(right, text="Treble shelf  (dB)", font=FMS,
                 fg=C["white2"], bg=C["bg"]).pack(anchor="w", pady=(8,0))
        self._labeled_scale(right, "", self._treble_var, -_DB_RANGE, _DB_RANGE,
                            res=0.5, fmt="{:+.1f} dB")

        nrow = tk.Frame(right, bg=C["bg"])
        nrow.pack(fill="x", pady=(10, 0))
        tk.Checkbutton(nrow, text="Normalize output to -0.2 dBFS",
                       variable=self._norm_var, font=FMS,
                       bg=C["bg"], fg=C["white2"], selectcolor=C["panel"],
                       activebackground=C["bg"], activeforeground=C["white"],
                       relief="flat").pack(anchor="w")

    def _on_vol(self, v):
        fv = float(v)
        db = f"{20*math.log10(max(fv, 1e-6)):.1f} dB" if fv > 0 else "-inf dB"
        try:
            self._vol_lbl.config(text=f"{int(fv*100)}%  ({db})")
        except Exception:
            pass

    def _draw_pan(self):
        if not self._pan_cv:
            return
        cv = self._pan_cv
        cv.delete("all")
        cx, cy, r = 35, 35, 22
        cv.create_arc(cx-r, cy-r, cx+r, cy+r,
                      start=225, extent=-270,
                      outline=C["white3"], width=2, style="arc")
        v = self._pan_var.get()
        if abs(v) > 0.02:
            cv.create_arc(cx-r, cy-r, cx+r, cy+r,
                          start=270, extent=-(v*135),
                          outline=C["white"], width=2, style="arc")
        cv.create_oval(cx-3, cy-3, cx+3, cy+3, fill=C["white"], outline="")
        txt = "C" if abs(v) < 0.04 else (f"L{int(abs(v)*100)}" if v < 0 else f"R{int(v*100)}")
        cv.create_text(cx, cy+r+10, text=txt,
                       font=("Courier New", 7, "bold"), fill=C["white2"])

    def _pan_press(self, e): self._pan_dy = e.y
    def _pan_drag(self, e):
        self._pan_var.set(max(-1.0, min(1.0,
            self._pan_var.get() + (self._pan_dy - e.y) / 90.0)))
        self._pan_dy = e.y
        self._draw_pan()

    # ── EFFECTS ──────────────────────────────────────────────────────────────
    def _build_effects(self, parent):
        body = self._section(parent, ">> EFFECTS  ·  TIMING  ·  TRIM")
        cols = tk.Frame(body, bg=C["bg"])
        cols.pack(fill="x")
        left  = tk.Frame(cols, bg=C["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 20))
        right = tk.Frame(cols, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        self._labeled_scale(left,  "Fade in  (s)",    self._fade_in,    0, 60, 0.1, "{:.1f} s")
        self._labeled_scale(left,  "Fade out (s)",    self._fade_out,   0, 60, 0.1, "{:.1f} s")
        self._labeled_scale(left,  "Speed  (0.25×–4×)", self._speed_var, 0.25, 4.0, 0.05, "{:.2f}×")
        self._labeled_scale(right, "Trim start (s)",  self._trim_start, 0, 3600, 0.1, "{:.1f} s")
        self._labeled_scale(right, "Trim end   (s)",  self._trim_end,   0, 3600, 0.1,
                            "{:.1f} s  (0=keep all)")

        rev_row = tk.Frame(left, bg=C["bg"])
        rev_row.pack(fill="x", pady=(8, 0))
        tk.Checkbutton(rev_row, text="Reverse audio",
                       variable=self._rev_var, font=FMS,
                       bg=C["bg"], fg=C["white2"], selectcolor=C["panel"],
                       activebackground=C["bg"], activeforeground=C["white"],
                       relief="flat").pack(anchor="w")

    # ── EXPORT ───────────────────────────────────────────────────────────────
    def _build_export(self, parent):
        body = self._section(parent, ">> EXPORT")
        top  = tk.Frame(body, bg=C["bg"])
        top.pack(fill="x", pady=(0, 8))

        tk.Label(top, text="Format:", font=FMS,
                 fg=C["white2"], bg=C["bg"]).pack(side="left", padx=(0,6))
        for fmt in ["wav", "mp3", "flac", "ogg"]:
            tk.Radiobutton(top, text=fmt.upper(), variable=self._fmt_var, value=fmt,
                           font=FMS, bg=C["bg"], fg=C["white2"],
                           selectcolor=C["select"], activebackground=C["bg"],
                           activeforeground=C["white"], relief="flat",
                           indicatoron=True).pack(side="left", padx=4)

        tk.Label(top, text="   Quality:", font=FMS,
                 fg=C["white2"], bg=C["bg"]).pack(side="left", padx=(12,6))
        for q in ["128k", "192k", "320k", "lossless"]:
            tk.Radiobutton(top, text=q, variable=self._quality_var, value=q,
                           font=FMS, bg=C["bg"], fg=C["white2"],
                           selectcolor=C["select"], activebackground=C["bg"],
                           activeforeground=C["white"], relief="flat").pack(side="left", padx=3)

        btn_row = tk.Frame(body, bg=C["bg"])
        btn_row.pack(fill="x", pady=(0, 4))
        _btn(btn_row, "▶  PREVIEW IN PLAYER",
             self._preview, fg=C["white"], bg=C["panel2"], font=FM).pack(side="left", padx=(0,8))
        _btn(btn_row, "⬇  EXPORT FILE",
             self._export, fg=C["white"], bg=C["select2"], font=FM).pack(side="left", padx=(0,8))
        _btn(btn_row, "⬇+  EXPORT & ADD TO LIBRARY",
             self._export_to_library, fg=C["white"], bg=C["panel2"]).pack(side="left")

    def _build_status(self, parent):
        bar = tk.Frame(parent, bg=C["panel"], height=30)
        bar.pack(fill="x", pady=(14, 0))
        bar.pack_propagate(False)
        self._status_lbl = tk.Label(
            bar, text="No file loaded — use ⊕ LOAD FILE above",
            font=FMS, fg=C["white3"], bg=C["panel"])
        self._status_lbl.pack(side="left", padx=12, fill="y")
        self._prog_cv = tk.Canvas(bar, bg=C["panel"], height=3,
                                  highlightthickness=0, width=160)
        self._prog_cv.pack(side="right", padx=12, pady=13)

    # ── File I/O ──────────────────────────────────────────────────────────────
    def _load_file(self):
        path = filedialog.askopenfilename(
            title="Load Audio File",
            filetypes=[("Audio files", "*.mp3 *.wav *.flac *.ogg *.m4a *.aac *.wma"),
                       ("All files", "*.*")])
        if path:
            self._load(path)

    def _load_from_lib(self):
        if not self.app.library:
            self._set_status("Library is empty"); return
        win = tk.Toplevel(self.app.root)
        win.title("MIXER — Pick from Library")
        win.configure(bg=C["bg"])
        win.geometry("500x380")
        try:
            import ctypes
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                win.winfo_id(), 20, ctypes.byref(ctypes.c_int(1)), 4)
        except Exception:
            pass
        tk.Label(win, text="SELECT TRACK", font=FML,
                 fg=C["white"], bg=C["bg"]).pack(pady=(14,4), padx=16, anchor="w")
        lb = tk.Listbox(win, bg=C["panel"], fg=C["white"], font=FMS,
                        selectbackground=C["select2"], relief="flat",
                        highlightthickness=0, bd=0, activestyle="none")
        lb.pack(fill="both", expand=True, padx=16, pady=(0,8))
        for t in self.app.library:
            lb.insert("end",
                      f"  {t.get('title','?')}   —   {t.get('artist','')}   [{t.get('path','')}]")
        def _pick(e=None):
            sel = lb.curselection()
            if not sel: return
            path = self.app.library[sel[0]].get("path", "")
            win.destroy()
            if path:
                self._load(path)
        lb.bind("<Double-Button-1>", _pick)
        _btn(win, "LOAD SELECTED", _pick,
             fg=C["white"], bg=C["panel2"]).pack(pady=(0,12))

    def _load(self, path: str):
        self._set_status(f"Loading {Path(path).name}…")
        def _do():
            try:
                data, sr = _sf.read(path, always_2d=True)
                dur = len(data) / sr
                self.app.root.after(0, lambda: self._on_loaded(path, data, sr, dur))
            except Exception as ex:
                self.app.root.after(0,
                    lambda m=str(ex): self._set_status(f"Load error: {m}"))
        threading.Thread(target=_do, daemon=True).start()

    def _on_loaded(self, path, data, sr, dur):
        self._src_path = path
        self._src_data = data
        self._src_sr   = sr
        self._src_dur  = dur
        name = Path(path).name
        info = f"{name}   [{sr} Hz  ·  {data.shape[1]}ch  ·  {dur:.1f}s]"
        if self._file_lbl:
            self._file_lbl.config(text=info, fg=C["white2"])
        # Reset trim end to full
        self._trim_end.set(0.0)
        self._waveform.load(data, sr, info)
        self._set_status(f"Loaded: {name}  ({dur:.1f}s  @  {sr}Hz)")

    def _clear_file(self):
        self._src_path = ""
        self._src_data = None
        if self._file_lbl:
            self._file_lbl.config(text="No file loaded", fg=C["white3"])
        self._waveform.clear()
        self._set_status("Cleared")

    # ── DSP pipeline ──────────────────────────────────────────────────────────
    def _process(self):
        """Apply all settings. Returns (np.ndarray, sr) or None."""
        if self._src_data is None:
            return None
        data = self._src_data.astype(_np.float64).copy()
        sr   = self._src_sr

        # 1. Trim
        s0 = int(self._trim_start.get() * sr)
        te = self._trim_end.get()
        s1 = int(te * sr) if te > 0.01 else len(data)
        s0 = max(0, min(s0, len(data)-1))
        s1 = max(s0+1, min(s1, len(data)))
        data = data[s0:s1]

        # 2. Reverse
        if self._rev_var.get():
            data = data[::-1].copy()

        # 3. Speed (resample)
        speed = self._speed_var.get()
        if abs(speed - 1.0) > 0.02:
            try:
                import math as _m
                # Rational approximation: up/down = 1/speed
                # e.g. speed=2.0 → up=1, dn=2 → half as many samples → plays faster
                numer = 1000
                denom = max(1, int(round(speed * 1000)))
                g = _m.gcd(numer, denom)
                up, dn = numer // g, denom // g
                out = _np.empty(
                    (int(len(data) * up / dn + 0.5), data.shape[1]), dtype=_np.float64)
                for ch in range(data.shape[1]):
                    out[:, ch] = resample_poly(data[:, ch], up, dn)
                data = out
            except Exception:
                pass

        # 4. 10-band peaking EQ
        for i, (freq, _) in enumerate(_EQ_BANDS):
            db = self._eq_vars[i].get()
            if abs(db) > 0.1:
                data = _apply_peaking(data, sr, freq, db, Q=1.4)

        # 5. Bass shelf
        bass = self._bass_var.get()
        if abs(bass) > 0.1:
            data = _apply_shelf(data, sr, 200.0, bass, low=True)

        # 6. Treble shelf
        treb = self._treble_var.get()
        if abs(treb) > 0.1:
            data = _apply_shelf(data, sr, 4000.0, treb, low=False)

        # 7. Pan (equal-power)
        pan = self._pan_var.get()
        if abs(pan) > 0.01 and data.shape[1] >= 2:
            l_g = _np.sqrt(max(0.0, (1.0 - pan) / 2.0))
            r_g = _np.sqrt(max(0.0, (1.0 + pan) / 2.0))
            data[:, 0] *= l_g
            data[:, 1] *= r_g

        # 8. Volume
        data *= self._vol_var.get()

        # 9. Fade in / out
        N = len(data)
        fi = self._fade_in.get()
        fo = self._fade_out.get()
        if fi > 0.01:
            n = min(N, int(fi * sr))
            data[:n] *= _np.linspace(0.0, 1.0, n)[:, None]
        if fo > 0.01:
            n = min(N, int(fo * sr))
            data[N-n:] *= _np.linspace(1.0, 0.0, n)[:, None]

        # 10. Normalize
        if self._norm_var.get():
            peak = _np.max(_np.abs(data))
            if peak > 1e-6:
                data = data / peak * 0.98

        _np.clip(data, -1.0, 1.0, out=data)
        return data.astype(_np.float32), sr

    def _set_progress(self, f):
        try:
            cv = self._prog_cv
            if not cv or not cv.winfo_exists(): return
            cv.delete("all")
            W = cv.winfo_width() or 160
            cv.create_rectangle(0, 0, int(W*f), 3, fill=C["white"], outline="")
        except Exception:
            pass

    def _set_status(self, msg: str):
        try:
            if self._status_lbl and self._status_lbl.winfo_exists():
                self._status_lbl.config(text=msg)
        except Exception:
            pass

    # ── Actions ───────────────────────────────────────────────────────────────
    def _preview(self):
        if self._src_data is None:
            self._set_status("No file loaded"); return
        if self._processing:
            self._set_status("Already processing…"); return
        self._processing = True
        self._set_status("Rendering preview…")
        def _do():
            try:
                result = self._process()
                if result is None:
                    self.app.root.after(0, lambda: self._set_status("Processing failed"))
                    return
                data, sr = result
                import tempfile
                fd, tmp = tempfile.mkstemp(suffix=".wav")
                os.close(fd)
                _sf.write(tmp, data, sr, subtype="FLOAT")
                def _play():
                    try:
                        self.app.engine.stop()
                        self.app.engine.load(tmp)
                        self.app.engine.play()
                        self._set_status(f"▶ Previewing — {Path(self._src_path).name}")
                    except Exception as ex:
                        self._set_status(f"Preview error: {ex}")
                self.app.root.after(0, _play)
            except Exception as ex:
                self.app.root.after(0, lambda m=str(ex): self._set_status(f"Error: {m}"))
            finally:
                self._processing = False
        threading.Thread(target=_do, daemon=True).start()

    def _export(self, add_to_library=False):
        if self._src_data is None:
            self._set_status("No file loaded"); return
        if self._processing:
            self._set_status("Already processing…"); return

        fmt  = self._fmt_var.get()
        stem = Path(self._src_path).stem + "_mixed"
        path = filedialog.asksaveasfilename(
            title="Export Mixed Audio",
            defaultextension=f".{fmt}",
            initialfile=stem,
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("All files", "*.*")])
        if not path:
            return

        self._processing = True
        self._set_status("Processing…")
        self._set_progress(0.1)

        def _do():
            try:
                result = self._process()
                if result is None:
                    self.app.root.after(0, lambda: self._set_status("Processing failed"))
                    return
                data, sr = result
                self.app.root.after(0, lambda: self._set_progress(0.6))

                if fmt == "mp3":
                    import tempfile
                    fd, tmp = tempfile.mkstemp(suffix=".wav")
                    os.close(fd)
                    _sf.write(tmp, data, sr, subtype="FLOAT")
                    q = self._quality_var.get().replace("k", "")
                    ret = os.system(f'ffmpeg -y -i "{tmp}" -b:a {q}k "{path}"')
                    try: os.unlink(tmp)
                    except: pass
                    if ret != 0:
                        self.app.root.after(0, lambda: self._set_status(
                            "MP3 needs ffmpeg — install it or choose WAV/FLAC/OGG"))
                        return
                else:
                    st = {"wav":"PCM_16","flac":"PCM_24","ogg":"VORBIS"}.get(fmt,"PCM_16")
                    _sf.write(path, data, sr, subtype=st)

                self.app.root.after(0, lambda: self._set_progress(1.0))
                name = Path(path).name
                if add_to_library:
                    self.app.root.after(0, lambda p=path, n=name: (
                        self.app._import([p]),
                        self._set_status(f"✓ Exported + added to library: {n}")))
                else:
                    self.app.root.after(0, lambda n=name: self._set_status(f"✓ Exported: {n}"))
            except Exception as ex:
                self.app.root.after(0, lambda m=str(ex): self._set_status(f"Export error: {m}"))
            finally:
                self._processing = False
        threading.Thread(target=_do, daemon=True).start()

    def _export_to_library(self):
        self._export(add_to_library=True)

    # -- Popout / window --------------------------------------------------
    def _open_popup(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.lift(); return
        self._popup = tk.Toplevel(self.app.root)
        self._popup.title("OTERNOS  //  MIXER  &  AUDIO EDITOR")
        self._popup.configure(bg=C["bg"])
        self._popup.geometry("960x860")
        self._popup.protocol("WM_DELETE_WINDOW", self._close_popup)
        self._popup.transient("")
        try:
            import ctypes
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                self._popup.winfo_id(), 20,
                ctypes.byref(ctypes.c_int(1)), 4)
        except Exception:
            pass
        self._build_ui(self._popup)

    def _close_popup(self):
        if self._popup:
            try: self._popup.destroy()
            except: pass
            self._popup = None

    # -- Public API -------------------------------------------------------
    def open_window(self):
        self._open_popup()

    def open_window_with_browse(self):
        self._open_popup()
        self.app.root.after(120, self._load_file)

    def open_window_with_current(self):
        self._open_popup()
        def _load():
            try:
                track = (self.app.library[self.app._current_index]
                         if hasattr(self.app, "_current_index") and
                            hasattr(self.app, "library") and
                            0 <= self.app._current_index < len(self.app.library)
                         else None)
                if track:
                    path = track.get("path", "")
                    if path and os.path.isfile(path):
                        self._load(path)
                    else:
                        self._set_status("Current track has no local file.")
                else:
                    self._set_status("No track selected.")
            except Exception as ex:
                self._set_status(f"Could not load current track: {ex}")
        self.app.root.after(150, _load)

    def reset_eq(self):
        for v in self._eq_vars:
            v.set(0.0)
        if self._eq_display:
            self._eq_display._redraw()

    def reset_effects(self):
        self._vol_var.set(1.0)
        self._pan_var.set(0.0)
        self._bass_var.set(0.0)
        self._treble_var.set(0.0)
        self._speed_var.set(1.0)
        self._fade_in.set(0.0)
        self._fade_out.set(0.0)
        self._trim_start.set(0.0)
        self._trim_end.set(0.0)
        self._rev_var.set(False)
        self._norm_var.set(False)

    def quick_export(self):
        self._open_popup()
        self.app.root.after(150, self._export)

    def _close_popup(self):
        if self._popup:
            try: self._popup.destroy()
            except: pass
            self._popup = None


# ─────────────────────────────────────────────────────────────────────────────
#  Module-level DSP helpers (used by _process)
# ─────────────────────────────────────────────────────────────────────────────
def _apply_peaking(data, sr, freq, gain_db, Q=1.4):
    """Peaking EQ biquad (Audio EQ Cookbook)."""
    try:
        w0    = 2.0 * _np.pi * freq / sr
        alpha = _np.sin(w0) / (2.0 * Q)
        A     = 10.0 ** (gain_db / 40.0)
        cw0   = _np.cos(w0)
        b = _np.array([1.0+alpha*A, -2.0*cw0, 1.0-alpha*A])
        a = _np.array([1.0+alpha/A, -2.0*cw0, 1.0-alpha/A])
        b /= a[0]; a /= a[0]
        out = _np.empty_like(data)
        for ch in range(data.shape[1]):
            out[:, ch] = lfilter(b, a, data[:, ch])
        return out
    except Exception:
        return data


def _apply_shelf(data, sr, freq, gain_db, low=True):
    """2nd-order shelving filter from Audio EQ Cookbook (Robert Bristow-Johnson)."""
    try:
        A   = 10.0 ** (gain_db / 40.0)
        w0  = 2.0 * _np.pi * freq / sr
        cw0 = _np.cos(w0)
        sw0 = _np.sin(w0)
        S   = 1.0   # shelf slope — 1.0 = steepest without peaking
        alpha = sw0 / 2.0 * _np.sqrt((A + 1.0/A) * (1.0/S - 1.0) + 2.0)
        sq2A = 2.0 * _np.sqrt(A) * alpha
        if low:
            b = _np.array([
                    A*((A+1) - (A-1)*cw0 + sq2A),
                    2*A*((A-1) - (A+1)*cw0),
                    A*((A+1) - (A-1)*cw0 - sq2A),
                ])
            a = _np.array([
                    (A+1) + (A-1)*cw0 + sq2A,
                    -2*((A-1) + (A+1)*cw0),
                    (A+1) + (A-1)*cw0 - sq2A,
                ])
        else:
            b = _np.array([
                    A*((A+1) + (A-1)*cw0 + sq2A),
                   -2*A*((A-1) + (A+1)*cw0),
                    A*((A+1) + (A-1)*cw0 - sq2A),
                ])
            a = _np.array([
                    (A+1) - (A-1)*cw0 + sq2A,
                    2*((A-1) - (A+1)*cw0),
                    (A+1) - (A-1)*cw0 - sq2A,
                ])
        b /= a[0]; a /= a[0]
        out = _np.empty_like(data)
        for ch in range(data.shape[1]):
            out[:, ch] = lfilter(b, a, data[:, ch])
        return out
    except Exception:
        return data
