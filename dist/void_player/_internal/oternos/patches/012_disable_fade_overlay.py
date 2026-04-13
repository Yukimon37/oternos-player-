"""
012_disable_fade_overlay.py — Disable the FadeOverlay animation on tab switches.

The FadeOverlay darkens/brightens the content frame on every tab switch.
When switching tabs rapidly, multiple fade animations queue up and jam the
event loop causing severe lag. This patch replaces flash() with a no-op.
"""
import types


def apply(app):
    try:
        # Replace flash() with instant midpoint call — no animation
        def _instant_flash(self, on_midpoint, duration_ms=None):
            try:
                on_midpoint()
            except Exception:
                pass

        app._fade_overlay.flash = types.MethodType(_instant_flash, app._fade_overlay)
    except Exception as exc:
        try:
            from oternos.diagnostics import log_exception
            log_exception("disable_fade_overlay", exc)
        except Exception:
            pass
