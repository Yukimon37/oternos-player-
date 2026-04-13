"""
animation.py - OTERNOS PLAYER
Small animation helpers expected by older player.py builds.
"""

import sys

if getattr(sys, "frozen", False):
    from oternos.constants import ease_out, lerp_color
else:
    from .constants import ease_out, lerp_color


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
        ease_fn=ease_out,
        on_done=None,
    ):
        wid = (id(widget), attr)
        if wid in cls._jobs:
            try:
                root.after_cancel(cls._jobs[wid])
            except Exception:
                pass

        steps = max(1, int(duration_ms / (1000 / fps)))
        delay = max(8, int(1000 / fps))

        def _step(i=0):
            if i > steps:
                try:
                    widget.config(**{attr: to_col})
                except Exception:
                    pass
                cls._jobs.pop(wid, None)
                if on_done:
                    on_done()
                return

            t = ease_fn(i / steps)
            col = lerp_color(from_col, to_col, t)
            try:
                widget.config(**{attr: col})
            except Exception:
                pass
            cls._jobs[wid] = root.after(delay, lambda: _step(i + 1))

        _step()


class FadeOverlay:
    """
    Lightweight tab transition used by the older Tk player.
    It darkens the content frame, swaps the view, then brightens it again.
    """

    STEPS = 6
    INTERVAL = 16
    BG = "#050505"
    MID = "#000000"

    def __init__(self, root, content_frame):
        self.root = root
        self.frame = content_frame
        self._active = False
        self._job = None

    def flash(self, on_midpoint, duration_ms=None):
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
            if step <= self.STEPS:
                t = step / self.STEPS
                col = lerp_color(self.BG, self.MID, t * t)
            else:
                t = (step - self.STEPS) / self.STEPS
                col = lerp_color(self.MID, self.BG, t * t)

            try:
                self.frame.configure(bg=col)
            except Exception:
                pass

            if step == self.STEPS and not mid_done[0]:
                mid_done[0] = True
                try:
                    on_midpoint()
                except Exception:
                    pass

            if step < total:
                self._job = self.root.after(self.INTERVAL, lambda: _tick(step + 1))
            else:
                try:
                    self.frame.configure(bg=self.BG)
                except Exception:
                    pass
                self._active = False
                self._job = None

        _tick(0)
