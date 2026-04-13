"""
015_library_single_click.py — Single-click to play library tracks.
No debounce timer — uses time-based guard so UI never freezes.
Double-click within 400ms cancels the single-click play.
"""
import time


def apply(app):
    _last_click_time = [0.0]
    _last_click_row  = [-1]

    def _on_click(event):
        now = time.monotonic()
        try:
            cy  = app.track_list.canvasy(event.y)
            row = app._tl_row_at(cy)
        except Exception:
            return

        # Two clicks on same row within 400ms = double-click, skip single-click
        if row == _last_click_row[0] and (now - _last_click_time[0]) < 0.4:
            return

        _last_click_time[0] = now
        _last_click_row[0]  = row

        try:
            if row < 0 or row >= len(app._display_indices):
                return
            lib_idx       = app._display_indices[row]
            app.queue     = list(app._display_indices)
            app.queue_pos = app.queue.index(lib_idx)
            app._play_item(app.queue_pos, force=True)
        except Exception:
            pass

    app.track_list.bind("<Button-1>", _on_click)
