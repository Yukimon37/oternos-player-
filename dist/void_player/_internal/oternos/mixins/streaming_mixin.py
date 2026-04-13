"""
streaming_mixin.py — OTERNOS PLAYER
Auto-extracted mixin for VoidPlayer.
Contains all streaming-related methods.
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


class StreamingMixin:
    """Mixin: streaming methods for VoidPlayer."""
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
            # Auto-launch the HTML webview (no-op if already running)
            threading.Thread(target=self._sc_open_html_view, daemon=True).start()
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
