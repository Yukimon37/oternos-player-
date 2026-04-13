"""
034_waveform_loading.py — Show animated loading bar in waveform scope while
the waveform data is being decoded in the background.

Instead of a blank scope for 5 seconds, shows a scanning line that sweeps
left to right with the text "DECODING..." until real waveform data arrives.
"""
import math


def apply(app):
    scope = app._waveform_scope
    _orig_draw = scope._draw.__func__  # get unbound method

    def _draw_with_loading(self):
        if not self._alive:
            return
        if not self.winfo_ismapped():
            self.after(200, self._draw)
            return

        # Check if we have real waveform data yet
        wf_data = getattr(app, '_waveform_data', None)
        is_library = getattr(app, '_active_source', '') == 'library'
        engine_playing = getattr(app.engine, 'is_playing', False)

        if is_library and engine_playing and wf_data is None:
            # Show loading animation
            try:
                self.delete("all")
                W = self.winfo_width() or int(self["width"])
                H = self.winfo_height() or int(self["height"])
                cy = H / 2

                # Dim background line
                self.create_line(0, cy, W, cy, fill="#1a1a1a", width=1)

                # Scanning bar that sweeps left to right
                scan_x = int((self.t * 3) % W)
                # Glow trail
                for i in range(40):
                    x = scan_x - i
                    if x < 0:
                        x += W
                    alpha = int(30 * (1 - i/40))
                    col = f"#{alpha:02x}{alpha:02x}{alpha:02x}"
                    self.create_line(x, 0, x, H, fill=col, width=1)
                # Bright leading edge
                self.create_line(scan_x, 0, scan_x, H, fill="#454545", width=1)

                # "DECODING..." text centered
                self.create_text(
                    W // 2, cy,
                    text="DECODING WAVEFORM...",
                    font=("Courier New", 7),
                    fill="#2a2a2a",
                    anchor="center"
                )
            except Exception:
                pass
            self.t += 1
            if self._alive:
                from oternos.constants import HW_ACCEL
                self.after(30, self._draw)
            return

        # Normal draw
        _orig_draw(self)

    import types
    scope._draw = types.MethodType(_draw_with_loading, scope)
