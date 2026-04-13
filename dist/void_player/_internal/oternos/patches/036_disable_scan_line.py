"""
036_disable_scan_line.py — Remove the radar sweep line from the playing row.

_scan_tick runs every 50ms and redraws a vertical sweep line across the
currently playing track row. This causes constant canvas redraws and
visible flickering especially when hovering over the track list.
"""
import types


def apply(app):
    # Kill _scan_tick entirely
    if getattr(app, '_scan_job', None):
        try:
            app.root.after_cancel(app._scan_job)
        except Exception:
            pass
        app._scan_job = None

    app._scan_tick = types.MethodType(lambda self: None, app)

    # Remove the scan line from _tl_update_highlight
    _orig_highlight = app._tl_update_highlight

    def _highlight_no_scan(self):
        _orig_highlight()
        # Delete any leftover scan line
        try:
            self.track_list.delete('radar_sweep')
        except Exception:
            pass

    app._tl_update_highlight = types.MethodType(_highlight_no_scan, app)
