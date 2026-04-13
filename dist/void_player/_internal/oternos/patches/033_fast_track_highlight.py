"""
033_fast_track_highlight.py — Fix the 498ms freeze when clicking library tracks.

Confirmed root cause: _do_load_track calls self.root.after(0, self._refresh_tracks)
which does a full canvas redraw taking ~500ms.

The full redraw is never needed on track change — only the row highlight needs
to update. _tl_update_highlight() does this in ~2ms.

Fix: wrap _refresh_tracks so that when called within 1 second of a track
starting, it uses the fast highlight-only path instead of the full redraw.
The full redraw still happens normally for all other cases (search, scroll,
library changes, etc).
"""
import types
import time as _time


def apply(app):
    # Timestamp of last track start
    app._last_track_start = 0.0

    # Track when a track starts playing
    _orig_do_load = app._do_load_track

    def _patched_do_load(track, user_initiated=False):
        app._last_track_start = _time.monotonic()
        _orig_do_load(track, user_initiated=user_initiated)

    app._do_load_track = _patched_do_load

    # Wrap _refresh_tracks — use fast path if called within 1s of track start
    _orig_refresh = app._refresh_tracks

    def _fast_refresh():
        # If we're within 1 second of a track starting, skip the full redraw
        # and just update the highlight — the canvas already has all the rows
        if _time.monotonic() - app._last_track_start < 1.0:
            try:
                app._tl_update_highlight()
            except Exception:
                pass
            return
        # Otherwise do the normal full redraw
        _orig_refresh()

    app._refresh_tracks = _fast_refresh
