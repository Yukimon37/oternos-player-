"""
006_disable_tl_hover_zoom.py — Disable track list hover zoom and increase
debounce to prevent flicker from rapid mouse movement.

_refresh_tracks takes ~47ms. With a 40ms debounce it fires constantly on
mouse move, causing visible flicker on the playing row scan line.
Increased to 80ms so redraws complete before the next one starts.
"""
import types


def apply(app):
    # Kill the zoom animation entirely
    def _noop(self, target_row, expanding=True):
        pass
    app._tl_animate_zoom = types.MethodType(_noop, app)

    # Replace motion handler with 80ms debounce
    _hover_job = [None]

    def _motion_fast(self, event):
        cy  = self._tl_canvas_y(event)
        row = self._tl_row_at(cy)
        if row == self._tl_hover_idx:
            return
        self._tl_hover_idx = row
        if _hover_job[0]:
            try:
                self.root.after_cancel(_hover_job[0])
            except Exception:
                pass
        _hover_job[0] = self.root.after(80, self._refresh_tracks)

    app._tl_on_motion = types.MethodType(_motion_fast, app)
    app.track_list.bind("<Motion>", app._tl_on_motion)

    # Reset any stuck zoom state
    app._tl_zoom_h   = getattr(app, "_tl_row_h", 26)
    app._tl_zoom_row = -1
    if getattr(app, "_tl_zoom_job", None):
        try:
            app.root.after_cancel(app._tl_zoom_job)
        except Exception:
            pass
        app._tl_zoom_job = None

    app._refresh_tracks()
