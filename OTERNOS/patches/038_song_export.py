"""
038_song_export.py — Song Export System

Two features:
1. [ SAVE ] button in the now-playing panel — appears whenever a SC/YT
   track is playing. One click copies the buffered stream file to the
   export folder and adds it to the library.
2. Export Manager window (accessible from Settings) for batch exporting.
"""

import os
import shutil
import threading
import tkinter as tk
from pathlib import Path


def apply(app):
    if "export_folder" not in app.settings:
        app.settings["export_folder"] = str(Path.home() / "Downloads")

    # ── Inject [ SAVE ] button below source_badge ─────────────────────────
    try:
        from oternos.constants import C, FM, FMS

        save_btn = tk.Label(
            app.source_badge.master,
            text="[ SAVE TO LIBRARY ]",
            font=("Courier New", 8, "bold"),
            fg="#378ADD", bg=C["panel"],
            cursor="hand2", anchor="w",
        )
        # Start hidden — only show when SC/YT is active
        save_btn.pack(anchor="w")
        save_btn.pack_forget()
        app._export_save_btn = save_btn

        save_btn.bind("<Button-1>", lambda e: _save_now_playing(app))
        save_btn.bind("<Enter>",    lambda e: save_btn.config(fg=C["white"]))
        save_btn.bind("<Leave>",    lambda e: save_btn.config(fg="#378ADD"))

        # Hook _set_source_badge to show/hide the button
        _orig_badge = app._set_source_badge

        def _patched_badge(source):
            _orig_badge(source)
            try:
                if source in ("soundcloud", "youtube"):
                    save_btn.pack(anchor="w")
                else:
                    save_btn.pack_forget()
            except Exception:
                pass

        import types
        app._set_source_badge = _patched_badge

    except Exception as exc:
        try:
            from oternos.diagnostics import log_exception
            log_exception("export_save_btn", exc)
        except Exception:
            pass

    # ── Hook Settings window ───────────────────────────────────────────────
    _orig_open = app._open_settings

    def _patched_open():
        _orig_open()
        app.root.after(200, lambda: _inject_into_body(app))

    app._open_settings = _patched_open
    app._open_export_manager = lambda: _open_export_window(app)


# ─────────────────────────────────────────────────────────────────────────────
#  One-click save of currently playing SC/YT track
# ─────────────────────────────────────────────────────────────────────────────

def _save_now_playing(app):
    from oternos.constants import C

    btn = getattr(app, "_export_save_btn", None)

    # Read live state
    try:
        title  = app.now_title.cget("text").replace("…", "").strip()
        artist = app.now_artist.cget("text").strip()
    except Exception:
        title = artist = ""

    source = getattr(app, "_active_source", "none")
    cached = getattr(app, "_current_play_path", "") or ""

    if not title or source not in ("soundcloud", "youtube"):
        _flash_btn(app, "NOT PLAYING", "#cc3333")
        return

    if not cached or not os.path.exists(cached):
        _flash_btn(app, "NO CACHED FILE", "#cc3333")
        return

    if os.path.getsize(cached) < 10_000:
        _flash_btn(app, "FILE TOO SMALL", "#cc3333")
        return

    folder = app.settings.get("export_folder", str(Path.home() / "Downloads"))
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as exc:
        _flash_btn(app, "FOLDER ERROR", "#cc3333")
        return

    def _do():
        try:
            ext   = os.path.splitext(cached)[1] or ".mp3"
            fname = (f"{_safe_filename(artist)} - {_safe_filename(title)}{ext}"
                     if artist else f"{_safe_filename(title)}{ext}")
            dest  = _unique_dest(folder, fname)
            shutil.copy2(cached, dest)
            _tag_file(dest, title, artist,
                      album="SoundCloud" if source == "soundcloud" else "YouTube")
            _add_to_library(app, dest, title, artist,
                            album="SoundCloud" if source == "soundcloud" else "YouTube")
            app.root.after(0, lambda: _flash_btn(app, "SAVED ✓", "#63c16e"))
        except Exception as exc:
            msg = str(exc)[:20]
            app.root.after(0, lambda m=msg: _flash_btn(app, f"ERROR: {m}", "#cc3333"))

    _flash_btn(app, "SAVING...", C["white"])
    threading.Thread(target=_do, daemon=True).start()


def _flash_btn(app, text, color, restore_ms=2500):
    """Temporarily change the save button text/color then restore."""
    btn = getattr(app, "_export_save_btn", None)
    if not btn:
        return
    try:
        btn.config(text=f"[ {text} ]", fg=color)
        app.root.after(restore_ms, lambda: _restore_btn(app))
    except Exception:
        pass


def _restore_btn(app):
    btn = getattr(app, "_export_save_btn", None)
    if not btn:
        return
    try:
        btn.config(text="[ SAVE TO LIBRARY ]", fg="#378ADD")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  Settings injection
# ─────────────────────────────────────────────────────────────────────────────

def _inject_into_body(app):
    from oternos.constants import C, FM, FMS

    try:
        win = getattr(app, "_settings_win", None)
        if not win or not win.winfo_exists():
            return

        body = _find_body_frame(win)
        if not body:
            return

        if getattr(body, "_export_injected", False):
            return
        body._export_injected = True

        tk.Frame(body, bg=C["bg"], height=10).pack(fill="x")

        hf = tk.Frame(body, bg=C["bg"])
        hf.pack(fill="x", padx=20)
        tk.Label(hf, text="↗", font=("Courier New", 9, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(0, 6))
        tk.Label(hf, text="SONG EXPORT", font=("Courier New", 8, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(side="left")

        tk.Frame(body, bg=C["border2"], height=1).pack(fill="x", padx=20, pady=(3, 0))
        tk.Frame(body, bg=C["border"],  height=1).pack(fill="x", padx=20, pady=(1, 3))

        # Export folder setting
        fr = tk.Frame(body, bg=C["bg"])
        fr.pack(fill="x", padx=28, pady=(8, 4))
        tk.Label(fr, text="EXPORT FOLDER:", font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(0, 8))

        folder_var = tk.StringVar(
            value=app.settings.get("export_folder", str(Path.home() / "Downloads")))
        tk.Entry(fr, textvariable=folder_var, font=("Courier New", 7),
                 bg=C["panel"], fg=C["white"], insertbackground=C["white"],
                 relief="flat", bd=0, highlightthickness=1,
                 highlightbackground=C["border2"]
                 ).pack(side="left", fill="x", expand=True, ipady=3, padx=(0, 6))

        def _browse():
            import tkinter.filedialog as fd
            path = fd.askdirectory(parent=win, initialdir=folder_var.get())
            if path:
                folder_var.set(path)
                app.settings["export_folder"] = path
                app._save()

        bb = tk.Label(fr, text="[ BROWSE ]", font=("Courier New", 7),
                      fg=C["white3"], bg=C["panel"], cursor="hand2", padx=6, pady=3)
        bb.pack(side="left")
        bb.bind("<Button-1>", lambda e: _browse())
        bb.bind("<Enter>",    lambda e: bb.config(fg=C["white"]))
        bb.bind("<Leave>",    lambda e: bb.config(fg=C["white3"]))

        def _save_folder(*_):
            app.settings["export_folder"] = folder_var.get().strip()
            app._save()
        folder_var.trace_add("write", _save_folder)

        tk.Label(body,
                 text="While a SoundCloud or YouTube track is playing, a [ SAVE TO LIBRARY ] button\n"
                      "appears below the source badge. Click it to copy the track instantly.",
                 font=("Courier New", 7), fg=C["white3"], bg=C["bg"],
                 justify="left"
                 ).pack(anchor="w", padx=28, pady=(4, 8))

        btn = tk.Label(body, text="[ OPEN EXPORT MANAGER ]",
                       font=("Courier New", 9, "bold"),
                       fg=C["white3"], bg=C["panel"],
                       cursor="hand2", padx=14, pady=8)
        btn.pack(anchor="w", padx=28, pady=(0, 20))
        btn.bind("<Button-1>", lambda e: _open_export_window(app))
        btn.bind("<Enter>",    lambda e: btn.config(fg=C["white"]))
        btn.bind("<Leave>",    lambda e: btn.config(fg=C["white3"]))

    except Exception as exc:
        try:
            from oternos.diagnostics import log_exception
            log_exception("export_inject", exc)
        except Exception:
            pass


def _find_body_frame(win):
    best = [None, 0]

    def _scan(w):
        if isinstance(w, tk.Frame):
            n = sum(1 for c in w.winfo_children() if isinstance(c, tk.Label))
            if n > best[1]:
                best[0] = w
                best[1] = n
        for child in w.winfo_children():
            _scan(child)

    _scan(win)
    return best[0]


# ─────────────────────────────────────────────────────────────────────────────
#  Export Manager window (batch)
# ─────────────────────────────────────────────────────────────────────────────

def _open_export_window(app):
    from oternos.constants import C, FM, FMS

    existing = getattr(app, "_export_win", None)
    if existing:
        try:
            if existing.winfo_exists():
                existing.lift()
                return
        except Exception:
            pass

    win = tk.Toplevel(app.root)
    win.title("OTERNOS // EXPORT MANAGER")
    win.configure(bg=C["bg"])
    win.geometry("720x640")
    win.resizable(True, True)
    app._export_win = win

    try:
        app._popup_fadein(win)
    except Exception:
        pass

    # Header
    hdr = tk.Canvas(win, bg=C["panel"], height=52, highlightthickness=0)
    hdr.pack(fill="x")

    def _draw_hdr(e=None):
        hdr.delete("all")
        W = hdr.winfo_width() or 720
        for y in range(0, 52, 3):
            hdr.create_line(0, y, W, y, fill="#0a0a0a", width=1)
        hdr.create_line(0, 50, W, 50, fill=C["border2"], width=2)
        hdr.create_text(20, 26, text="[ EXPORT MANAGER ]",
                        font=("Courier New", 11, "bold"),
                        fill=C["white"], anchor="w")
        hdr.create_text(W - 20, 26, text="v1.3",
                        font=("Courier New", 8), fill=C["white3"], anchor="e")

    hdr.bind("<Configure>", lambda e: _draw_hdr())
    win.after(10, _draw_hdr)

    cl = tk.Label(hdr, text="[ ✕ ]", font=("Courier New", 10),
                  fg=C["white3"], bg=C["panel"], cursor="hand2", padx=10)
    cl.place(relx=1.0, rely=0.5, anchor="e", x=-8)
    cl.bind("<Button-1>", lambda e: win.destroy())
    cl.bind("<Enter>",    lambda e: cl.config(fg=C["red"]))
    cl.bind("<Leave>",    lambda e: cl.config(fg=C["white3"]))

    # Folder row
    fp = tk.Frame(win, bg=C["panel"])
    fp.pack(fill="x")
    tk.Frame(fp, bg=C["border"], height=1).pack(fill="x")
    fr = tk.Frame(fp, bg=C["panel"])
    fr.pack(fill="x", padx=16, pady=8)

    tk.Label(fr, text="EXPORT TO:", font=("Courier New", 8, "bold"),
             fg=C["white3"], bg=C["panel"]).pack(side="left", padx=(0, 8))

    folder_var = tk.StringVar(
        value=app.settings.get("export_folder", str(Path.home() / "Downloads")))
    tk.Entry(fr, textvariable=folder_var, font=("Courier New", 8),
             bg=C["bg"], fg=C["white"], insertbackground=C["white"],
             relief="flat", bd=0, highlightthickness=1,
             highlightbackground=C["border2"]
             ).pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 8))

    def _browse():
        import tkinter.filedialog as fd
        path = fd.askdirectory(title="Choose Export Folder",
                               initialdir=folder_var.get() or str(Path.home()),
                               parent=win)
        if path:
            folder_var.set(path)
            app.settings["export_folder"] = path
            app._save()

    bb = tk.Label(fr, text="[ BROWSE ]", font=FMS,
                  fg=C["white3"], bg=C["bg"], cursor="hand2", padx=8, pady=4)
    bb.pack(side="left")
    bb.bind("<Button-1>", lambda e: _browse())
    bb.bind("<Enter>",    lambda e: bb.config(fg=C["white"]))
    bb.bind("<Leave>",    lambda e: bb.config(fg=C["white3"]))

    def _save_folder(*_):
        app.settings["export_folder"] = folder_var.get().strip()
        app._save()
    folder_var.trace_add("write", _save_folder)
    tk.Frame(fp, bg=C["border"], height=1).pack(fill="x")

    # Toolbar
    toolbar = tk.Frame(win, bg=C["bg"])
    toolbar.pack(fill="x", padx=12, pady=(8, 4))

    check_vars  = []
    sel_all_var = tk.BooleanVar(value=True)

    def _toggle_all():
        v = sel_all_var.get()
        for cv, _ in check_vars:
            cv.set(v)
        try:
            for row in list_inner.winfo_children():
                for child in row.winfo_children():
                    if isinstance(child, tk.Label) and child.cget("text") in ("☑", "☐"):
                        child.config(text="☑" if v else "☐",
                                     fg=C["white"] if v else C["white3"])
        except Exception:
            pass

    _sa_btn = tk.Label(toolbar, text="☑", font=("Courier New", 10),
                       fg=C["white"], bg=C["bg"], cursor="hand2")
    _sa_btn.pack(side="left")

    def _toggle_all_click(e=None):
        new_val = not sel_all_var.get()
        sel_all_var.set(new_val)
        _sa_btn.config(text="☑" if new_val else "☐",
                       fg=C["white"] if new_val else C["white3"])
        _toggle_all()

    _sa_btn.bind("<Button-1>", _toggle_all_click)

    tk.Label(toolbar, text="SELECT ALL", font=("Courier New", 7, "bold"),
             fg=C["white3"], bg=C["bg"]).pack(side="left", padx=(2, 16))

    _filter_var  = tk.StringVar(value="all")
    _filter_btns = []

    def _set_filter(src):
        _filter_var.set(src)
        _populate()
        for lbl, key in _filter_btns:
            lbl.config(fg=C["white"] if key == src else C["white3"])

    for label, key in [("ALL", "all"), ("LIBRARY", "library"),
                        ("SOUNDCLOUD", "soundcloud"), ("YOUTUBE", "youtube")]:
        b = tk.Label(toolbar, text=f"[ {label} ]", font=("Courier New", 7),
                     fg=C["white"] if key == "all" else C["white3"],
                     bg=C["bg"], cursor="hand2")
        b.pack(side="left", padx=2)
        b.bind("<Button-1>", lambda e, k=key: _set_filter(k))
        _filter_btns.append((b, key))

    count_lbl = tk.Label(toolbar, text="", font=("Courier New", 7),
                         fg=C["white3"], bg=C["bg"])
    count_lbl.pack(side="right")

    # Song list
    lo = tk.Frame(win, bg=C["bg"])
    lo.pack(fill="both", expand=True, padx=8, pady=(0, 4))

    list_cv = tk.Canvas(lo, bg=C["bg"], highlightthickness=0)
    list_sb = tk.Scrollbar(lo, orient="vertical", command=list_cv.yview,
                           bg=C["panel"], troughcolor=C["bg"],
                           width=6, relief="flat", bd=0)
    list_cv.configure(yscrollcommand=list_sb.set)
    list_sb.pack(side="right", fill="y")
    list_cv.pack(side="left", fill="both", expand=True)

    list_inner = tk.Frame(list_cv, bg=C["bg"])
    win_id = list_cv.create_window((0, 0), window=list_inner, anchor="nw")
    list_inner.bind("<Configure>",
                    lambda e: list_cv.configure(scrollregion=list_cv.bbox("all")))
    list_cv.bind("<Configure>",
                 lambda e: list_cv.itemconfig(win_id, width=e.width))
    list_cv.bind("<MouseWheel>",
                 lambda e: list_cv.yview_scroll(int(-1 * e.delta / 120) * 3, "units"))

    col_hdr = tk.Frame(list_inner, bg=C["panel"])
    col_hdr.pack(fill="x")
    for txt, w in [("✓", 2), ("SRC", 8), ("TITLE", 36), ("ARTIST", 20), ("STATUS", 14)]:
        tk.Label(col_hdr, text=txt, font=("Courier New", 7, "bold"),
                 fg=C["white3"], bg=C["panel"], width=w, anchor="w"
                 ).pack(side="left", padx=(8, 0), pady=4)

    _SRC_COLOR = {"library": C["white3"], "soundcloud": "#ff5500", "youtube": "#cc3333"}
    _SRC_BADGE = {"library": "LIB", "soundcloud": "SC", "youtube": "YT"}

    def _populate():
        nonlocal check_vars
        for w in list(list_inner.winfo_children()):
            try:
                if w is not col_hdr:
                    w.destroy()
            except Exception:
                pass

        tk.Frame(list_inner, bg=C["border2"], height=1).pack(fill="x")
        check_vars = []
        tracks = _collect_tracks(app, _filter_var.get())
        count_lbl.config(text=f"{len(tracks)} tracks")

        if not tracks:
            tk.Label(list_inner,
                     text="No tracks found.\nPlay a SoundCloud or YouTube track to see it here.",
                     font=("Courier New", 7), fg=C["white3"], bg=C["bg"],
                     justify="left"
                     ).pack(anchor="w", padx=20, pady=12)
        else:
            for i, track in enumerate(tracks):
                bg  = C["panel"] if i % 2 == 0 else C["bg"]
                row = tk.Frame(list_inner, bg=bg)
                row.pack(fill="x")

                cv = tk.BooleanVar(value=True)
                check_vars.append((cv, track))

                cb = tk.Label(row, text="☑", font=("Courier New", 10),
                              fg=C["white"], bg=bg, cursor="hand2")
                cb.pack(side="left", padx=(6, 0))

                def _toggle_row(e, var=cv, lbl=cb):
                    var.set(not var.get())
                    lbl.config(text="☑" if var.get() else "☐",
                               fg=C["white"] if var.get() else C["white3"])

                cb.bind("<Button-1>", _toggle_row)

                src = track.get("source", "library")
                tk.Label(row, text=_SRC_BADGE.get(src, src[:3].upper()),
                         font=("Courier New", 7, "bold"),
                         fg=_SRC_COLOR.get(src, C["white3"]),
                         bg=bg, width=8, anchor="w"
                         ).pack(side="left", padx=(4, 0))

                title  = (track.get("title") or "Unknown")[:38]
                artist = (track.get("artist") or "")[:22]

                tk.Label(row, text=title, font=("Courier New", 8),
                         fg=C["white"], bg=bg, width=36, anchor="w"
                         ).pack(side="left", padx=4)
                tk.Label(row, text=artist, font=("Courier New", 7),
                         fg=C["white3"], bg=bg, width=20, anchor="w"
                         ).pack(side="left")

                sl = tk.Label(row, text="—", font=("Courier New", 7),
                              fg=C["white3"], bg=bg, width=14, anchor="w")
                sl.pack(side="left", padx=4)
                track["_status_lbl"] = sl

                row.bind("<Enter>", lambda e, r=row:       r.config(bg=C["select"]))
                row.bind("<Leave>", lambda e, r=row, b=bg: r.config(bg=b))

        tk.Frame(list_inner, bg=C["border"], height=1).pack(fill="x", pady=4)

    _populate()

    # Footer
    foot = tk.Frame(win, bg=C["panel"])
    foot.pack(fill="x", side="bottom")
    tk.Frame(foot, bg=C["border2"], height=2).pack(fill="x")
    tk.Frame(foot, bg=C["border"],  height=1).pack(fill="x")
    fi = tk.Frame(foot, bg=C["panel"])
    fi.pack(fill="x", padx=12, pady=8)

    prog_bg   = tk.Frame(fi, bg=C["border"], height=4)
    prog_bg.pack(fill="x", pady=(0, 4))
    prog_fill = tk.Frame(prog_bg, bg=C["white3"], height=4)
    prog_fill.place(x=0, y=0, relwidth=0.0, height=4)

    prog_lbl = tk.Label(fi, text="", font=("Courier New", 7),
                        fg=C["white3"], bg=C["panel"])
    prog_lbl.pack(anchor="w")

    btn_row = tk.Frame(fi, bg=C["panel"])
    btn_row.pack(fill="x", pady=(6, 0))

    _running = [False]

    def _set_prog(done, total, msg=""):
        pct = done / total if total > 0 else 0
        try:
            prog_fill.place(x=0, y=0, relwidth=pct, height=4)
            prog_lbl.config(text=msg or f"{done}/{total} exported")
        except Exception:
            pass

    def _upd(track, msg, color=None):
        try:
            lbl = track.get("_status_lbl")
            if lbl and lbl.winfo_exists():
                lbl.config(text=msg)
                if color:
                    lbl.config(fg=color)
        except Exception:
            pass

    def _start_export():
        if _running[0]:
            return
        folder = folder_var.get().strip()
        if not folder:
            _browse()
            folder = folder_var.get().strip()
        if not folder:
            return
        selected = [(cv, t) for cv, t in check_vars if cv.get()]
        if not selected:
            prog_lbl.config(text="No tracks selected.")
            return
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as exc:
            prog_lbl.config(text=f"Cannot create folder: {exc}")
            return

        _running[0] = True
        export_btn.config(fg=C["white3"], cursor="arrow")
        prog_fill.config(bg="#378ADD")

        def _run():
            total = len(selected)
            done  = 0
            ok_count = 0
            for _cv, track in selected:
                src   = track.get("source", "library")
                title = track.get("title") or "Unknown"
                win.after(0, lambda d=done, t=total, ti=title:
                          _set_prog(d, t, f"Exporting {d+1}/{t} — {ti[:28]}..."))
                win.after(0, lambda tr=track: _upd(tr, "exporting…"))
                try:
                    if   src == "library":    ok, msg = _export_library(app, track, folder)
                    elif src == "soundcloud": ok, msg = _export_sc(app, track, folder)
                    elif src == "youtube":    ok, msg = _export_yt(app, track, folder)
                    else:                     ok, msg = False, "unsupported source"
                except Exception as exc:
                    ok, msg = False, str(exc)[:30]
                done += 1
                if ok:
                    ok_count += 1
                status_text  = "✓ saved" if ok else f"✗ {msg[:18]}"
                status_color = "#63c16e" if ok else "#cc3333"
                win.after(0, lambda tr=track, s=status_text, c=status_color:
                          _upd(tr, s, c))

            summary = f"Done — {ok_count}/{total} exported."
            if ok_count < total:
                summary += f"  ({total - ok_count} failed)"
            win.after(0, lambda: _set_prog(done, total, summary))
            win.after(0, lambda: prog_fill.config(bg=C["white3"]))
            win.after(0, lambda: export_btn.config(fg=C["white3"], cursor="hand2"))
            _running[0] = False

        threading.Thread(target=_run, daemon=True).start()

    export_btn = tk.Label(btn_row, text="[ EXPORT SELECTED ]",
                          font=("Courier New", 9, "bold"),
                          fg=C["white3"], bg=C["bg"],
                          cursor="hand2", padx=14, pady=6)
    export_btn.pack(side="left")
    export_btn.bind("<Button-1>", lambda e: _start_export())
    export_btn.bind("<Enter>",    lambda e: export_btn.config(fg=C["white"]))
    export_btn.bind("<Leave>",    lambda e: export_btn.config(fg=C["white3"]))

    for txt, cmd in [("[ REFRESH ]", _populate), ("[ CLOSE ]", win.destroy)]:
        side = "left" if txt == "[ REFRESH ]" else "right"
        b = tk.Label(btn_row, text=txt, font=FM, fg=C["white3"],
                     bg=C["panel"], cursor="hand2", padx=10, pady=6)
        b.pack(side=side, padx=6)
        b.bind("<Button-1>", lambda e, c=cmd: c())
        b.bind("<Enter>",    lambda e, w=b: w.config(fg=C["white"]))
        b.bind("<Leave>",    lambda e, w=b: w.config(fg=C["white3"]))


# ─────────────────────────────────────────────────────────────────────────────
#  Track collection
# ─────────────────────────────────────────────────────────────────────────────

def _collect_tracks(app, src_filter="all"):
    tracks = []
    seen   = set()

    def _key(title, artist):
        return (str(title).lower().strip(), str(artist).lower().strip())

    if src_filter in ("all", "library"):
        for t in getattr(app, "library", []):
            k = _key(t.get("title", ""), t.get("artist", ""))
            if k not in seen:
                seen.add(k)
                tracks.append(dict(t, source="library"))

    active = getattr(app, "_active_source", "none")
    if active in ("soundcloud", "youtube") and src_filter in ("all", active):
        try:
            title  = app.now_title.cget("text").replace("…", "").strip()
            artist = app.now_artist.cget("text").strip()
            play_path = getattr(app, "_current_play_path", "") or ""
        except Exception:
            title = artist = play_path = ""

        if title and title not in ("", "⚠  LOAD FAILED"):
            k = _key(title, artist)
            if k not in seen:
                seen.add(k)
                tracks.append({
                    "source":    active,
                    "title":     title,
                    "artist":    artist,
                    "path":      play_path,
                    "_sc_track": getattr(app, "_sc_current_track", None),
                    "_yt_track": getattr(app, "_yt_current_track", None),
                })

    sc_wanted = src_filter in ("all", "soundcloud")
    yt_wanted = src_filter in ("all", "youtube")

    for entry in reversed(getattr(app, "_history", [])):
        src = entry.get("source", "library")
        if src == "soundcloud" and not sc_wanted:
            continue
        if src == "youtube" and not yt_wanted:
            continue
        if src not in ("soundcloud", "youtube"):
            continue
        title  = entry.get("title", "")
        artist = entry.get("artist", "")
        k = _key(title, artist)
        if k not in seen:
            seen.add(k)
            tracks.append({
                "source": src, "title": title, "artist": artist,
                "path": "", "_sc_track": None, "_yt_track": None,
            })

    return tracks


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_filename(name):
    keep = set(" abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.,()")
    return "".join(c if c in keep else "_" for c in str(name)).strip() or "track"


def _tag_file(path, title, artist, album=""):
    try:
        from mutagen.id3 import ID3, TIT2, TPE1, TALB, ID3NoHeaderError
        try:    tags = ID3(path)
        except ID3NoHeaderError: tags = ID3()
        tags["TIT2"] = TIT2(encoding=3, text=title)
        tags["TPE1"] = TPE1(encoding=3, text=artist)
        if album: tags["TALB"] = TALB(encoding=3, text=album)
        tags.save(path)
    except Exception:
        pass


def _add_to_library(app, path, title, artist, album=""):
    try:
        if any(t.get("path") == path for t in app.library):
            return
        app.library.append({"path": path, "title": title,
                             "artist": artist, "album": album})
        app._tracks_dirty = True
        app._save()
        app.root.after(0, app._refresh_tracks)
    except Exception:
        pass


def _unique_dest(folder, fname):
    dest = os.path.join(folder, fname)
    if not os.path.exists(dest):
        return dest
    base, ext = os.path.splitext(dest)
    i = 1
    while os.path.exists(f"{base}_{i}{ext}"):
        i += 1
    return f"{base}_{i}{ext}"


def _export_library(app, track, folder):
    src = track.get("path", "")
    if not src or not os.path.exists(src):
        return (False, "file not found")
    title  = track.get("title", "track")
    artist = track.get("artist", "")
    ext    = os.path.splitext(src)[1] or ".mp3"
    fname  = (f"{_safe_filename(artist)} - {_safe_filename(title)}{ext}"
              if artist else f"{_safe_filename(title)}{ext}")
    dest   = _unique_dest(folder, fname)
    shutil.copy2(src, dest)
    _tag_file(dest, title, artist, track.get("album", ""))
    return (True, "")


def _export_sc(app, track, folder):
    title  = track.get("title", "track")
    artist = track.get("artist", "")
    cached = track.get("path", "")

    if cached and os.path.exists(cached) and os.path.getsize(cached) > 10_000:
        fname = (f"{_safe_filename(artist)} - {_safe_filename(title)}.mp3"
                 if artist else f"{_safe_filename(title)}.mp3")
        dest = _unique_dest(folder, fname)
        shutil.copy2(cached, dest)
        _tag_file(dest, title, artist, album="SoundCloud")
        _add_to_library(app, dest, title, artist, album="SoundCloud")
        return (True, "")

    sc_track = track.get("_sc_track")
    if not sc_track:
        return (False, "history item — no cached file")

    try:
        import urllib.request as _ur
        sc_api = getattr(app, "sc_api", None)
        if not sc_api:
            return (False, "SC API not initialised")
        stream_url = sc_api.get_stream_url(sc_track)
        if not stream_url:
            try: sc_api.refresh_client_id()
            except Exception: pass
            stream_url = sc_api.get_stream_url(sc_track)
        if not stream_url:
            return (False, "no stream URL")
        fname = (f"{_safe_filename(artist)} - {_safe_filename(title)}.mp3"
                 if artist else f"{_safe_filename(title)}.mp3")
        dest  = _unique_dest(folder, fname)
        req   = _ur.Request(stream_url, headers={"User-Agent": "Mozilla/5.0"})
        with _ur.urlopen(req, timeout=60) as resp:
            with open(dest, "wb") as f:
                shutil.copyfileobj(resp, f)
        if os.path.getsize(dest) < 10_000:
            os.unlink(dest)
            return (False, "download too small")
        _tag_file(dest, title, artist, album="SoundCloud")
        _add_to_library(app, dest, title, artist, album="SoundCloud")
        return (True, "")
    except Exception as exc:
        return (False, str(exc)[:40])


def _export_yt(app, track, folder):
    import subprocess, sys
    title  = track.get("title", "track")
    artist = track.get("artist", "")
    cached = track.get("path", "")

    if cached and os.path.exists(cached) and os.path.getsize(cached) > 10_000:
        ext   = os.path.splitext(cached)[1] or ".mp3"
        fname = (f"{_safe_filename(artist)} - {_safe_filename(title)}{ext}"
                 if artist else f"{_safe_filename(title)}{ext}")
        dest  = _unique_dest(folder, fname)
        shutil.copy2(cached, dest)
        _tag_file(dest, title, artist, album="YouTube")
        _add_to_library(app, dest, title, artist, album="YouTube")
        return (True, "")

    yt  = track.get("_yt_track") or getattr(app, "_yt_current_track", None)
    url = None
    if yt:
        url = (yt.get("url") or yt.get("webpage_url") or
               yt.get("original_url") or yt.get("id"))
        if url and not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={url}"
    if not url:
        return (False, "history item — no cached file")

    fname_base   = (f"{_safe_filename(artist)} - {_safe_filename(title)}"
                    if artist else _safe_filename(title))
    out_template = os.path.join(folder, f"{fname_base}.%(ext)s")
    cmd = [sys.executable, "-m", "yt_dlp",
           "--extract-audio", "--audio-format", "mp3",
           "--audio-quality", "0", "--no-playlist",
           "--output", out_template, url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except FileNotFoundError:
        return (False, "yt-dlp not found")
    except Exception as exc:
        return (False, str(exc)[:40])

    dest = os.path.join(folder, f"{fname_base}.mp3")
    if not os.path.exists(dest):
        for f in Path(folder).glob(f"{fname_base}*"):
            dest = str(f); break

    if os.path.exists(dest):
        _tag_file(dest, title, artist, album="YouTube")
        _add_to_library(app, dest, title, artist, album="YouTube")
        return (True, "")
    return (False, (result.stderr or "")[-40:] or "yt-dlp failed")
