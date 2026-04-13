"""
013_fix_close_flash.py — Prevent white window flash when closing the player.

_on_close() calls root.overrideredirect(False) before root.destroy() to avoid
a Windows crash. This briefly shows the default Windows title bar (white flash).
Fix: withdraw the window first so it's invisible before overrideredirect changes.
"""
import types


def apply(app):
    _orig_close = app._on_close

    def _patched_close():
        try:
            app.root.withdraw()
        except Exception:
            pass
        _orig_close()

    app._on_close = _patched_close
