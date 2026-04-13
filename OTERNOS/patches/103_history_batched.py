"""
103_history_batched.py — Replace _refresh_history_view with a version that
batches widget creation via after() so it doesn't freeze the UI on large
histories. Also adds a 200ms debounce so rapid tab-switch won't hammer it.
"""

import time as _time


def apply(app):
    _job = [None]

    def _refresh_history_view_batched():
        # Debounce
        if _job[0]:
            try:
                app.root.after_cancel(_job[0])
            except Exception:
                pass
        _job[0] = app.root.after(200, _do_refresh)

    def _do_refresh():
        try:
            inner = app._hist_inner
            cv    = app._hist_cv

            # Destroy old children
            for w in inner.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass

            filt = getattr(app, "_hist_filter", None)
            filt = filt.get() if filt else "all"
            entries = list(reversed(app._history))
            if filt != "all":
                entries = [e for e in entries if e.get("source", "library") == filt]

            if not entries:
                import tkinter as tk
                from oternos.constants import C, FM
                tk.Label(
                    inner,
                    text="No history yet — play some tracks.",
                    font=FM,
                    fg=C["white3"],
                    bg=C["bg"],
                ).pack(padx=24, pady=20)
                cv.configure(scrollregion=cv.bbox("all") or (0, 0, 0, 0))
                return

            # Build in batches of 30 to keep UI responsive
            BATCH = 30
            _build_batch(entries, 0, BATCH)
        except Exception as exc:
            try:
                from oternos.diagnostics import log_exception
                log_exception("patch:103_history_batched", exc)
            except Exception:
                pass

    def _build_batch(entries, start, batch_size):
        import tkinter as tk
        from oternos.constants import C, FM, FMS

        src_colors = {
            "library":    C["white3"],
            "spotify":    "#1db954",
            "youtube":    "#ff0000",
            "soundcloud": "#ff5500",
            "deezer":     "#a238ff",
            "archive":    "#4a9eff",
            "bandcamp":   "#1da0c3",
        }
        src_badges = {
            "library": "SRC::LIB", "spotify": "SRC::SPT",
            "youtube": "SRC::YT",  "soundcloud": "SRC::SC",
            "deezer": "SRC::DZ",   "archive": "SRC::IA",
            "bandcamp": "SRC::BC",
        }

        inner = app._hist_inner
        cv    = app._hist_cv

        end = min(start + batch_size, len(entries))
        for i in range(start, end):
            e   = entries[i]
            bg  = C["select"] if i % 2 == 0 else C["bg"]
            row = tk.Frame(inner, bg=bg, cursor="hand2")
            row.pack(fill="x")

            ts_str    = _time.strftime("%H:%M:%S", _time.localtime(e.get("ts", 0)))
            src       = e.get("source", "library")
            src_col   = src_colors.get(src, C["white3"])
            src_badge = src_badges.get(src, "SRC::???")

            tk.Label(row, text=f"0x{i:04X}", font=("Courier New", 6),
                     fg=C["white3"], bg=bg, width=7, anchor="w"
                     ).pack(side="left", padx=(10, 0), pady=5)
            tk.Label(row, text=f"[{ts_str}]", font=("Courier New", 7),
                     fg=C["white3"], bg=bg, width=11, anchor="w"
                     ).pack(side="left")
            tk.Label(row, text=src_badge, font=("Courier New", 8, "bold"),
                     fg=src_col, bg=bg, width=9, anchor="w"
                     ).pack(side="left")
            tk.Label(row, text=e.get("title", "")[:36], font=FM,
                     fg=C["white"], bg=bg, anchor="w"
                     ).pack(side="left", padx=6)
            tk.Label(row, text=e.get("artist", "")[:24], font=FMS,
                     fg=C["white3"], bg=bg, anchor="w"
                     ).pack(side="left")

            def _make_hover(r, orig_bg):
                r.bind("<Enter>", lambda ev: r.config(bg=C["select2"]))
                r.bind("<Leave>", lambda ev: r.config(bg=orig_bg))
                for child in r.winfo_children():
                    child.bind("<Enter>", lambda ev, _r=r: _r.config(bg=C["select2"]))
                    child.bind("<Leave>", lambda ev, _r=r, _b=orig_bg: _r.config(bg=_b))

            _make_hover(row, bg)

        # Update scroll region after each batch
        try:
            cv.configure(scrollregion=cv.bbox("all") or (0, 0, 0, 0))
        except Exception:
            pass

        # Schedule next batch
        if end < len(entries):
            app.root.after(8, lambda: _build_batch(entries, end, batch_size))

    # Replace the method on the live instance
    import types
    app._refresh_history_view = _refresh_history_view_batched
