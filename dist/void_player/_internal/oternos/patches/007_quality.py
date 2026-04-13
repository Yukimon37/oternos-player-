"""
007_quality_improvements.py — Three quality fixes:

1. Temp file cleanup — SC stream .mp3 files accumulate in AppData/Local/Temp.
   On startup, delete any tmp*.mp3 files older than 1 hour.

2. Queue persistence — save/restore the current queue and position across restarts.

3. Window position memory — save/restore window position and size.
   (Settings already has window_x/y/w/h keys, just needs to be wired up.)
"""
import os
import time
import tempfile
from pathlib import Path


def apply(app):
    _cleanup_temp_files()
    _restore_queue(app)
    _wire_queue_save(app)
    _restore_window_position(app)
    _wire_window_position_save(app)


# ── 1. Temp file cleanup ──────────────────────────────────────────────────────

def _cleanup_temp_files():
    """Delete SC stream temp files older than 1 hour from the system temp dir."""
    try:
        tmp_dir  = Path(tempfile.gettempdir())
        cutoff   = time.time() - 3600  # 1 hour
        removed  = 0
        for f in tmp_dir.glob("tmp*.mp3"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    removed += 1
            except Exception:
                pass
        if removed:
            try:
                from oternos.diagnostics import get_logger
                get_logger().info(f"Cleaned up {removed} temp SC files")
            except Exception:
                pass
    except Exception:
        pass


# ── 2. Queue persistence ──────────────────────────────────────────────────────

def _restore_queue(app):
    """Restore queue and position from last session."""
    try:
        saved = app.settings.get("_saved_queue")
        pos   = app.settings.get("_saved_queue_pos", 0)
        if saved and isinstance(saved, list):
            # Validate indices are still valid
            valid = [i for i in saved if 0 <= i < len(app.library)]
            if valid:
                app.queue     = valid
                app.queue_pos = max(0, min(pos, len(valid) - 1))
    except Exception:
        pass


def _wire_queue_save(app):
    """Save queue to settings on every _save() call."""
    _orig_save = app._save

    def _patched_save():
        try:
            app.settings["_saved_queue"]     = list(app.queue)
            app.settings["_saved_queue_pos"] = app.queue_pos
        except Exception:
            pass
        _orig_save()

    import types
    app._save = _patched_save


# ── 3. Window position memory ────────────────────────────────────────────────

def _restore_window_position(app):
    """Move window to last saved position/size."""
    try:
        x = app.settings.get("window_x", -1)
        y = app.settings.get("window_y", -1)
        w = app.settings.get("window_w", 1100)
        h = app.settings.get("window_h", 700)

        if x >= 0 and y >= 0:
            # Sanity check — make sure it's on screen
            import tkinter as tk
            sw = app.root.winfo_screenwidth()
            sh = app.root.winfo_screenheight()
            x  = max(0, min(x, sw - 200))
            y  = max(0, min(y, sh - 200))
            w  = max(400, min(w, sw))
            h  = max(300, min(h, sh))
            app.root.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass


def _wire_window_position_save(app):
    """Save window position/size on close."""
    _orig_close = app._on_close

    def _patched_close():
        try:
            geo = app.root.geometry()  # "WxH+X+Y"
            parts = geo.replace("+", "x").split("x")
            if len(parts) == 4:
                w, h, x, y = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                app.settings["window_w"] = w
                app.settings["window_h"] = h
                app.settings["window_x"] = x
                app.settings["window_y"] = y
        except Exception:
            pass
        _orig_close()

    import types
    app._on_close = _patched_close
