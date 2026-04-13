"""
039_edex_init.py — eDEX-style initialization sequence.

_create_overlay() is called from __main__.py BEFORE root.deiconify()
so the overlay is the first thing visible — no player flash.

The overlay shows a terminal boot sequence then slides up revealing
the player underneath.
"""
import tkinter as tk


def apply(app):
    # Patch already applied via __main__.py calling _create_overlay directly
    pass


def _create_overlay(root, app):
    from oternos.constants import C

    W = root.winfo_screenwidth()
    H = root.winfo_screenheight()

    overlay = tk.Frame(root, bg=C["bg"])
    overlay.place(x=0, y=0, relwidth=1.0, relheight=1.0)
    overlay.lift()

    cv = tk.Canvas(overlay, bg=C["bg"], highlightthickness=0)
    cv.place(x=0, y=0, relwidth=1.0, relheight=1.0)

    lines = []

    def _redraw():
        try:
            cv.delete("all")
            W = cv.winfo_width() or root.winfo_width() or 900
            H = cv.winfo_height() or root.winfo_height() or 600
            cx = W // 2
            cy = H // 2 - 20

            bw = min(600, W - 80)
            bh = 240
            bx = cx - bw // 2
            by = cy - bh // 2

            # Outer border
            cv.create_rectangle(bx, by, bx+bw, by+bh,
                                outline="#1e1e1e", width=1, fill=C["bg"])
            cv.create_rectangle(bx+2, by+2, bx+bw-2, by+bh-2,
                                outline="#141414", width=1)

            # Header bar
            cv.create_rectangle(bx, by, bx+bw, by+26,
                                fill="#0c0c0c", outline="")
            cv.create_text(bx+12, by+13,
                          text="OTERNOS // SYSTEM INITIALIZATION",
                          font=("Courier New", 8, "bold"),
                          fill="#2a2a2a", anchor="w")
            # Corner dots
            for dx, dy in [(6,6),(bw-6,6),(6,bh-6),(bw-6,bh-6)]:
                cv.create_rectangle(bx+dx-1, by+dy-1, bx+dx+1, by+dy+1,
                                   fill="#1a1a1a", outline="")

            # Separator
            cv.create_line(bx, by+27, bx+bw, by+27, fill="#161616", width=1)

            # Log lines
            y = by + 42
            for text, color in lines[-7:]:
                cv.create_text(bx+18, y, text=text,
                              font=("Courier New", 8),
                              fill=color, anchor="w")
                y += 22

            # Blinking cursor
            import time
            if int(time.monotonic() * 2) % 2 == 0:
                cv.create_text(bx+18, y, text="_",
                              font=("Courier New", 8),
                              fill="#1e1e1e", anchor="w")

            # Bottom bar
            cv.create_line(bx, by+bh-24, bx+bw, by+bh-24,
                          fill="#0f0f0f", width=1)
            n_tracks = len(getattr(app, 'library', []))
            cv.create_text(cx, by+bh-12,
                          text=f"VOID PLAYER v1.1  ·  {n_tracks} TRACKS  ·  INITIALIZING",
                          font=("Courier New", 6),
                          fill="#1a1a1a", anchor="center")
        except Exception:
            pass

    # Cursor blink loop
    def _blink():
        if not overlay.winfo_exists():
            return
        _redraw()
        root.after(500, _blink)

    root.after(100, _blink)

    def _add(text, color="#222222"):
        lines.append((text, color))
        _redraw()

    def _ok():
        if lines:
            t, _ = lines[-1]
            if not t.endswith("[ OK ]"):
                lines[-1] = (t + "  [ OK ]", "#2d6b2d")
        _redraw()

    def _err():
        if lines:
            t, _ = lines[-1]
            lines[-1] = (t + "  [ ERR ]", "#6b2d2d")
        _redraw()

    # Sequence
    seq = [
        (0,    lambda: _add("> BOOT SEQUENCE STARTED", "#1e2e1e")),
        (350,  lambda: _add("> INITIALIZING AUDIO ENGINE...")),
        (700,  lambda: _ok()),
        (800,  lambda: _add("> SCANNING LIBRARY INDEX...")),
        (1100, lambda: _ok()),
        (1200, lambda: _add("> MOUNTING UI SUBSYSTEMS...")),
        (1500, lambda: _ok()),
        (1600, lambda: _add("> ESTABLISHING VISUALIZER...")),
        (1900, lambda: _ok()),
        (2000, lambda: _add("> LOADING PATCH MODULES...")),
        (2300, lambda: _ok()),
        (2400, lambda: _add("> ALL SYSTEMS NOMINAL", "#2d5a2d")),
        (2700, lambda: _add("> LAUNCHING INTERFACE...", "#1e3e1e")),
        (3000, lambda: _slideup(overlay, root, app)),
    ]

    for delay, fn in seq:
        root.after(delay, fn)


def _slideup(overlay, root, app):
    """Slide overlay upward revealing the player."""
    H = root.winfo_height() or 600

    def _step(offset=0):
        if not overlay.winfo_exists():
            return
        total = 20
        if offset >= total:
            try:
                overlay.destroy()
            except Exception:
                pass
            # Push to status matrix
            if hasattr(app, '_status_matrix'):
                try:
                    app._status_matrix.push("OTERNOS ONLINE")
                except Exception:
                    pass
            return

        # Ease in-out
        t = offset / total
        ease = t * t * (3 - 2 * t)
        y = int(-H * ease)
        try:
            overlay.place(x=0, y=y, relwidth=1.0, relheight=1.0)
        except Exception:
            pass
        root.after(16, lambda: _step(offset + 1))

    _step()
