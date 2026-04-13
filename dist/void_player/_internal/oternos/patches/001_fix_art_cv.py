"""
001_fix_art_cv.py — Ensure art_cv and HoloFrame stay the same size (54×54).

Bug: after some theme switches or DPI changes the canvas can drift from 54px,
causing the HoloFrame to sit misaligned. This patch enforces the size at
startup and re-enforces it whenever the window is configured.
"""

SIZE = 54


def apply(app):
    try:
        cv = app.art_cv
        cv.config(width=SIZE, height=SIZE)

        # Re-enforce on any window resize so DPI scaling can't drift it
        def _relock(e=None):
            try:
                cv.config(width=SIZE, height=SIZE)
            except Exception:
                pass

        cv.bind("<Configure>", _relock, add="+")

        # HoloFrame sits right next to art_cv — make sure its size matches
        if hasattr(app, "_holo_frame"):
            try:
                app._holo_frame.config(width=SIZE, height=SIZE)
            except Exception:
                # HoloFrame may not accept width/height directly; try canvas child
                try:
                    app._holo_frame._cv.config(width=SIZE, height=SIZE)
                except Exception:
                    pass
    except Exception as exc:
        from oternos.diagnostics import log_exception
        log_exception("patch:001_fix_art_cv", exc)
