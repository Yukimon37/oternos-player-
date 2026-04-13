"""
101_library_scroll_debounce.py — Increase the track-list scroll debounce
from 120ms to 80ms for snappier response, and add a Configure debounce
so rapid window resizes don't hammer _refresh_tracks on every pixel.
"""


def apply(app):
    _resize_job = [None]

    def _debounced_refresh(e=None):
        if _resize_job[0]:
            try:
                app.root.after_cancel(_resize_job[0])
            except Exception:
                pass
        _resize_job[0] = app.root.after(120, app._refresh_tracks)

    try:
        # Replace the raw Configure binding with the debounced version
        app.track_list.bind("<Configure>", _debounced_refresh)
    except Exception:
        pass
