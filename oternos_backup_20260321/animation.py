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
        fps=30,
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
    """
    Tab transition using background colour animation only — no overlays,
    no place(), nothing that can block content.

    Fades the content frame bg from its current colour toward black at the
    midpoint (where the view swap happens), then back to the app bg colour.
    Child frames inherit the bg so it reads as a gentle darkening flash.
    """

    STEPS    = 6     # frames per half-transition
    INTERVAL = 16    # ms per frame
    BG       = "#050505"   # app background colour
    MID      = "#000000"   # darkest point colour

    def __init__(self, root, content_frame):
        self.root    = root
        self.frame   = content_frame
        self._active = False
        self._job    = None

    def flash(self, on_midpoint, duration_ms=None):
        """Darken → swap view → brighten. No canvas, no blocking."""
        # Cancel any in-progress animation
        if self._job:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

        self._active = True
        mid_done = [False]

        def _tick(step=0):
            total = self.STEPS * 2

            # ease-in to midpoint, ease-out back
            if step <= self.STEPS:
                t = step / self.STEPS
                col = _lerp_color(self.BG, self.MID, t * t)
            else:
                t = (step - self.STEPS) / self.STEPS
                col = _lerp_color(self.MID, self.BG, t * t)

            try:
                self.frame.configure(bg=col)
            except Exception:
                pass

            # Swap the view at the darkest point
            if step == self.STEPS and not mid_done[0]:
                mid_done[0] = True
                try:
                    on_midpoint()
                except Exception:
                    pass

            if step < total:
                self._job = self.root.after(self.INTERVAL, lambda: _tick(step + 1))
            else:
                # Ensure we land exactly on the app bg colour
                try:
                    self.frame.configure(bg=self.BG)
                except Exception:
                    pass
                self._active = False
                self._job = None

        _tick(0)


# ─────────────────────────────────────────
#  EQ PROCESSOR  — real biquad IIR filters
# ─────────────────────────────────────────