"""
300_dev_console.py — OTERNOS DEV CONSOLE
Ctrl+D opens a separate draggable window with REPL + live log + quick actions.
Uses the player's own _popup_setup so it matches the app's cybercore style.
"""
import tkinter as tk
import threading
import traceback
import sys
import os
import importlib
import importlib.util
import io
from pathlib import Path

_BG  = "#050505"
_P   = "#0c0c0c"
_W   = "#e8e8e8"
_W2  = "#9a9a9a"
_W3  = "#424242"
_GR  = "#00ff41"
_GR2 = "#00cc33"
_GR3 = "#003310"
_RED = "#cc2222"
_YEL = "#ccaa00"
_P2  = "#0a1a0a"
_F   = ("Courier New", 9)
_FB  = ("Courier New", 9, "bold")
_FS  = ("Courier New", 8)


def apply(app):
    app._dev_win     = None
    app._dev_log_pos = [0]
    app._dev_tail    = False

    def _toggle(e=None):
        if app._dev_win and app._dev_win.winfo_exists():
            _close(app)
        else:
            _open(app)

    app.root.bind("<F12>", _toggle)
    app.root.bind("<Control-d>", _toggle)
    app.root.bind("<Control-D>", _toggle)
    app._dev_toggle = _toggle

    # Close dev console when main app closes
    _orig_close = app._on_close
    def _patched_close():
        _close(app)
        _orig_close()
    import types
    app._on_close = _patched_close


def _close(app):
    app._dev_tail = False
    try:
        app._dev_win.withdraw()
        app._dev_win.destroy()
    except Exception:
        pass
    app._dev_win = None


def _open(app):
    win = tk.Toplevel(app.root)
    win.title("OTERNOS // DEV CONSOLE")
    win.configure(bg=_BG)
    win.geometry("960x580")
    win.resizable(True, True)
    app._dev_win = win
    win.bind("<Escape>", lambda e: _close(app))
    win.bind("<Control-d>", lambda e: _close(app))
    win.protocol("WM_DELETE_WINDOW", lambda: _close(app))
    # Hide dev console when main window hides
    app.root.bind("<Unmap>", lambda e: win.withdraw() if win.winfo_exists() else None, add="+")
    app.root.bind("<Map>",   lambda e: win.deiconify() if win.winfo_exists() and getattr(app, "_dev_win", None) else None, add="+")

    hdr = tk.Frame(win, bg="#001800", height=28)
    hdr.pack(fill="x"); hdr.pack_propagate(False)
    tk.Label(hdr, text="[ DEV CONSOLE ]", font=_FB, fg=_GR, bg="#001800").pack(side="left", padx=10)
    tk.Label(hdr, text="Ctrl+D / Esc to close  |  app = VoidPlayer", font=_FS, fg=_W3, bg="#001800").pack(side="left")
    cb = tk.Label(hdr, text="[ X ]", font=_FB, fg=_W3, bg="#001800", cursor="hand2")
    cb.pack(side="right", padx=8)
    cb.bind("<Button-1>", lambda e: _close(app))
    cb.bind("<Enter>", lambda e: cb.config(fg=_RED)); cb.bind("<Leave>", lambda e: cb.config(fg=_W3))
    tk.Frame(win, bg=_GR3, height=1).pack(fill="x")

    C = {"bg": _BG, "panel": _P, "white": _W, "white2": _W2, "white3": _W3, "border2": "#2e2e2e"}

    body = tk.Frame(win, bg=_BG)
    body.pack(fill="both", expand=True)
    _build_repl(app, win, body, C)
    _build_log(app, body, C)
    _build_quickbar(app, win, C)

    app._dev_tail = True
    _tailtick(app)
    win.after(100, lambda: app._dev_entry.focus_set())
    win.update_idletasks()
    x = (win.winfo_screenwidth()  - 960) // 2
    y = (win.winfo_screenheight() - 580) // 2
    win.geometry(f"960x580+{x}+{y}")


def _build_repl(app, win, parent, C):
    lf = tk.Frame(parent, bg=C["bg"])
    lf.pack(side="left", fill="both", expand=True, padx=(10, 4), pady=8)

    tk.Label(lf, text="PYTHON REPL  —  app = VoidPlayer",
             font=_FS, fg=C["white3"], bg=C["bg"]).pack(anchor="w", pady=(0, 3))

    # Output
    ow = tk.Frame(lf, bg=_P2, highlightthickness=1, highlightbackground=_GR3)
    ow.pack(fill="both", expand=True)
    out = tk.Text(ow, bg=_P2, fg=_GR, font=_F, insertbackground=_GR,
                  relief="flat", bd=0, wrap="word", state="disabled", padx=6, pady=4)
    sb = tk.Scrollbar(ow, command=out.yview, bg=C["panel"],
                      troughcolor=C["bg"], relief="flat", width=8)
    out.config(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    out.pack(fill="both", expand=True)
    app._dev_out = out

    out.tag_config("prompt",  foreground=_GR2)
    out.tag_config("result",  foreground=C["white"])
    out.tag_config("error",   foreground=_RED)
    out.tag_config("info",    foreground=_YEL)
    out.tag_config("comment", foreground=C["white3"])

    for line in [
        "# app = VoidPlayer  |  reload_patch('name')  |  reload_mixin('soundcloud')",
        "# Try:  app._set_status('hi')   app.settings   app.library",
        "",
    ]:
        _w(app, line, "comment")

    # Input — multi-line Text widget
    # Enter = run, Shift+Enter = newline, Ctrl+Enter = run, Up/Down = history
    inp_wrap = tk.Frame(lf, bg=_P2, highlightthickness=1,
                        highlightbackground=_GR3)
    inp_wrap.pack(fill="x", pady=(4, 0))

    inp_hdr = tk.Frame(inp_wrap, bg=_P2)
    inp_hdr.pack(fill="x")
    tk.Label(inp_hdr, text=">>> (Enter=run  Shift+Enter=newline  ↑↓=history)",
             font=("Courier New", 7), fg=_W3, bg=_P2).pack(side="left", padx=4, pady=1)

    ent = tk.Text(inp_wrap, bg=_P2, fg=_GR, font=_F, insertbackground=_GR,
                  relief="flat", bd=0, height=4, wrap="none",
                  padx=6, pady=4)
    ent_sb = tk.Scrollbar(inp_wrap, command=ent.yview, bg=_P,
                          troughcolor=_BG, relief="flat", width=6)
    ent.config(yscrollcommand=ent_sb.set)
    ent_sb.pack(side="right", fill="y")
    ent.pack(fill="x", expand=True)
    app._dev_entry = ent
    app._dev_hist  = []
    app._dev_hi    = [-1]

    def _exec(e=None):
        code = ent.get("1.0", "end").strip()
        if not code:
            return "break"
        app._dev_hist.append(code)
        app._dev_hi[0] = len(app._dev_hist)
        ent.delete("1.0", "end")
        first = code.split("\n")[0]
        display = first + (" \u2026" if "\n" in code else "")
        _w(app, f">>> {display}", "prompt")
        _run(app, code)
        return "break"

    def _shift_enter(e):
        ent.insert("insert", "\n")
        return "break"

    def _up(e):
        # Only navigate history if cursor is on first line
        row_num = int(ent.index("insert").split(".")[0])
        if row_num > 1:
            return
        h = app._dev_hist
        i = app._dev_hi
        if not h:
            return "break"
        i[0] = max(0, i[0] - 1)
        ent.delete("1.0", "end")
        ent.insert("1.0", h[i[0]])
        return "break"

    def _dn(e):
        # Only navigate history if cursor is on last line
        last_row = int(ent.index("end-1c").split(".")[0])
        cur_row  = int(ent.index("insert").split(".")[0])
        if cur_row < last_row:
            return
        h = app._dev_hist
        i = app._dev_hi
        i[0] = min(len(h), i[0] + 1)
        ent.delete("1.0", "end")
        if i[0] < len(h):
            ent.insert("1.0", h[i[0]])
        return "break"

    ent.bind("<Return>",         _exec)
    ent.bind("<Control-Return>", _exec)
    ent.bind("<Shift-Return>",   _shift_enter)
    ent.bind("<Up>",             _up)
    ent.bind("<Down>",           _dn)
    ent.bind("<Control-d>",      lambda e: _close(app))

    btn_row = tk.Frame(lf, bg=C["bg"])
    btn_row.pack(fill="x", pady=(2, 0))
    rb = tk.Label(btn_row, text="[RUN]", font=_FB, fg=C["white3"], bg=C["bg"],
                  cursor="hand2", padx=6)
    rb.pack(side="left", padx=(0, 0))
    rb.bind("<Button-1>", _exec)
    rb.bind("<Enter>", lambda e: rb.config(fg=_GR))
    rb.bind("<Leave>", lambda e: rb.config(fg=C["white3"]))


def _build_log(app, parent, C):
    rf = tk.Frame(parent, bg=C["bg"], width=320)
    rf.pack(side="right", fill="both", padx=(4, 10), pady=8)
    rf.pack_propagate(False)

    h = tk.Frame(rf, bg=C["bg"])
    h.pack(fill="x")
    tk.Label(h, text="LIVE LOG", font=_FS, fg=C["white3"], bg=C["bg"]).pack(side="left", pady=(0, 3))
    clr = tk.Label(h, text="[CLEAR]", font=_FS, fg=C["white3"], bg=C["bg"], cursor="hand2")
    clr.pack(side="right")

    wr = tk.Frame(rf, bg=C["panel"], highlightthickness=1, highlightbackground=C["border2"])
    wr.pack(fill="both", expand=True)
    log = tk.Text(wr, bg=C["panel"], fg=C["white2"], font=_FS,
                  relief="flat", bd=0, wrap="none", state="disabled", padx=6, pady=4)
    sby = tk.Scrollbar(wr, command=log.yview, bg=C["panel"],
                       troughcolor=C["bg"], relief="flat", width=8)
    log.config(yscrollcommand=sby.set)
    sby.pack(side="right", fill="y")
    log.pack(fill="both", expand=True)
    app._dev_log = log

    log.tag_config("err",  foreground=_RED)
    log.tag_config("warn", foreground=_YEL)
    log.tag_config("ok",   foreground=C["white2"])

    def _clr(e=None):
        log.config(state="normal")
        log.delete("1.0", "end")
        log.config(state="disabled")
    clr.bind("<Button-1>", _clr)
    clr.bind("<Enter>", lambda e: clr.config(fg=_RED))
    clr.bind("<Leave>", lambda e: clr.config(fg=C["white3"]))


def _build_quickbar(app, parent, C):
    tk.Frame(parent, bg="#2e2e2e", height=1).pack(fill="x")
    qb = tk.Frame(parent, bg=C["panel"], height=28)
    qb.pack(fill="x")
    qb.pack_propagate(False)
    tk.Label(qb, text="QUICK:", font=_FS, fg=C["white3"], bg=C["panel"]).pack(side="left", padx=(10, 4))
    for lbl, cmd in [
        ("REFRESH TRACKS", lambda: _refresh(app)),
        ("RELOAD PATCHES", lambda: _rall(app)),
        ("CLEAR YT CACHE", lambda: _clrcache(app)),
        ("DUMP STATE",     lambda: _dump(app)),
        ("LIST PATCHES",   lambda: _lspatches(app)),
    ]:
        b = tk.Label(qb, text=f"[{lbl}]", font=_FS, fg=C["white3"],
                     bg=C["panel"], cursor="hand2", padx=4)
        b.pack(side="left")
        b.bind("<Button-1>", lambda e, c=cmd: c())
        b.bind("<Enter>", lambda e, w=b: w.config(fg=_GR))
        b.bind("<Leave>", lambda e, w=b: w.config(fg=C["white3"]))


# ── REPL execution ────────────────────────────────────────────────────────────

def _run(app, code):
    def _do():
        ns = {
            "app":          app,
            "tk":           tk,
            "sys":          sys,
            "os":           os,
            "Path":         Path,
            "reload_patch": lambda n: _rpatch(app, n),
            "reload_mixin": lambda n: _rmixin(app, n),
        }
        old = sys.stdout
        sys.stdout = sys.stderr = io.StringIO()
        try:
            try:
                r = eval(compile(code, "<dev>", "eval"), ns)
                cap = sys.stdout.getvalue()
                if cap:
                    app.root.after(0, lambda v=cap: _w(app, v.rstrip(), "result"))
                if r is not None:
                    app.root.after(0, lambda rv=repr(r): _w(app, rv, "result"))
            except SyntaxError:
                exec(compile(code, "<dev>", "exec"), ns)
                cap = sys.stdout.getvalue()
                if cap:
                    app.root.after(0, lambda v=cap: _w(app, v.rstrip(), "result"))
                else:
                    app.root.after(0, lambda: _w(app, "  OK", "info"))
        except Exception:
            err = traceback.format_exc()
            app.root.after(0, lambda e=err: _w(app, e.strip(), "error"))
        finally:
            sys.stdout = old
    threading.Thread(target=_do, daemon=True).start()


def _w(app, text, tag="result"):
    try:
        w = app._dev_out
        w.config(state="normal")
        w.insert("end", text + "\n", tag)
        w.see("end")
        w.config(state="disabled")
    except Exception:
        pass


# ── Log tail ──────────────────────────────────────────────────────────────────

def _tailtick(app):
    if not app._dev_tail:
        return
    try:
        p = Path.home() / ".voidplayer.log"
        if p.exists():
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                f.seek(app._dev_log_pos[0])
                new = f.read()
                app._dev_log_pos[0] = f.tell()
            if new:
                _logappend(app, new)
    except Exception:
        pass
    app.root.after(1000, lambda: _tailtick(app))


def _logappend(app, text):
    try:
        w = app._dev_log
        w.config(state="normal")
        for line in text.splitlines():
            lo = line.lower()
            tag = "err" if ("error" in lo or "traceback" in lo or "exception" in lo) \
                  else "warn" if "warn" in lo else "ok"
            w.insert("end", line + "\n", tag)
        w.see("end")
        w.config(state="disabled")
    except Exception:
        pass


# ── Hot reload ────────────────────────────────────────────────────────────────

def _rpatch(app, name):
    pd = Path(__file__).parent
    name = name.replace(".py", "")
    ms = sorted(pd.glob(f"*{name}*.py"))
    if not ms:
        _w(app, f"  not found: {name}", "error")
        return
    p = ms[0]
    try:
        sp = importlib.util.spec_from_file_location(f"_pr_{name}", p)
        m  = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        if hasattr(m, "apply"):
            m.apply(app)
            _w(app, f"  OK  {p.name}", "info")
        else:
            _w(app, f"  no apply() in {p.name}", "error")
    except Exception:
        _w(app, traceback.format_exc(), "error")


def _rmixin(app, name):
    import types as _t
    md   = Path(__file__).parent.parent / "mixins"
    name = name.replace("_mixin", "").replace(".py", "")
    p    = md / f"{name}_mixin.py"
    if not p.exists():
        _w(app, f"  not found: {p}", "error")
        return
    try:
        sp = importlib.util.spec_from_file_location(f"_mr_{name}", p)
        m  = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        n = 0
        for a in dir(m):
            obj = getattr(m, a)
            if callable(obj) and not a.startswith("__"):
                try:
                    setattr(app, a, _t.MethodType(obj, app))
                    n += 1
                except Exception:
                    pass
        _w(app, f"  OK  {p.name}  ({n} methods rebound)", "info")
    except Exception:
        _w(app, traceback.format_exc(), "error")


def _rall(app):
    pd   = Path(__file__).parent
    done = []
    for p in sorted(pd.glob("*.py")):
        if p.name == "__init__.py":
            continue
        try:
            sp = importlib.util.spec_from_file_location(f"_pr_{p.stem}", p)
            m  = importlib.util.module_from_spec(sp)
            sp.loader.exec_module(m)
            if hasattr(m, "apply"):
                m.apply(app)
                done.append(p.name)
        except Exception as ex:
            _w(app, f"  ERR {p.name}: {ex}", "error")
    _w(app, f"  reloaded {len(done)} patches", "info")


def _refresh(app):
    try:
        app._refresh_tracks()
        _w(app, "  tracks refreshed", "info")
    except Exception as ex:
        _w(app, str(ex), "error")


def _clrcache(app):
    try:
        c  = Path.home() / ".voidplayer_cache"
        fs = list(c.glob("*"))
        for f in fs:
            try:
                f.unlink()
            except Exception:
                pass
        _w(app, f"  cleared {len(fs)} files", "info")
    except Exception:
        _w(app, traceback.format_exc(), "error")


def _dump(app):
    for line in [
        f"  view:          {getattr(app, 'view', '?')}",
        f"  active_source: {getattr(app, '_active_source', '?')}",
        f"  library:       {len(getattr(app, 'library', []))} tracks",
        f"  queue:         {len(getattr(app, 'queue', []))} tracks",
        f"  history:       {len(getattr(app, '_history', []))} entries",
        f"  is_playing:    {getattr(app.engine, 'is_playing', '?')}",
        f"  is_paused:     {getattr(app.engine, 'is_paused', '?')}",
        f"  sp_mode:       {getattr(app, '_sp_mode', '?')}",
    ]:
        _w(app, line, "info")


def _lspatches(app):
    pd = Path(__file__).parent
    fs = sorted(p.name for p in pd.glob("*.py") if p.name != "__init__.py")
    _w(app, f"  {len(fs)} patch files:", "info")
    for f in fs:
        _w(app, f"    {f}", "result")
