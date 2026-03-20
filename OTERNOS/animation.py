import sys

"""
animation.py — OTERNOS PLAYER
ColorAnim and FadeOverlay widget animation helpers.
"""
if getattr(sys, "frozen", False):
    from oternos.constants import _lerp_color, _ease_out
else:
    from .constants import _lerp_color, _ease_out


class ColorAnim:
    """Animate a widget fg or bg color smoothly."""

    _jobs = {}

    @classmethod
    def run(
        cls,
        root,
        widget,
        attr,
        from_col,
        to_col,
        duration_ms=120,
        fps=60,
        ease_fn=_ease_out,
        on_done=None,
    ):
        wid = (id(widget), attr)
        if wid in cls._jobs:
            try:
                root.after_cancel(cls._jobs[wid])
            except:
                pass
        steps = max(1, int(duration_ms / (1000 / fps)))
        delay = max(8, int(1000 / fps))

        def _step(i=0):
            if i > steps:
                try:
                    widget.config(**{attr: to_col})
                except:
                    pass
                cls._jobs.pop(wid, None)
                if on_done:
                    on_done()
                return
            t = ease_fn(i / steps)
            col = _lerp_color(from_col, to_col, t)
            try:
                widget.config(**{attr: col})
            except:
                pass
            cls._jobs[wid] = root.after(delay, lambda: _step(i + 1))

        _step()


class FadeOverlay:
    """Stub — just calls the midpoint callback immediately. No canvas placement."""

    def __init__(self, root, content_frame):
        self.root = root
        self.frame = content_frame
        self._active = False

    def flash(self, on_midpoint, duration_ms=50):
        on_midpoint()


# ─────────────────────────────────────────
#  EQ PROCESSOR  — real biquad IIR filters
# ─────────────────────────────────────────
