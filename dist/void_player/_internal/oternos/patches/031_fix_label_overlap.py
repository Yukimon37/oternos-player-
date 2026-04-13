"""
031_fix_label_overlap.py — Fix library track titles bleeding into stream tabs.

When switching from a library track to SC/YT, the glitch animation
(017_enhanced_glitch) is still running its after() chain on now_title/
now_artist/now_album. These fire AFTER the stream has already set its own
labels, overwriting them with the old library text.

Fix: track an animation generation counter per widget. Each _anim_label_change
call increments the counter for that widget. Each frame checks if it's still
the "current" animation — if a newer one started, the old one stops silently.
"""
import types
import random


def apply(app):
    # Generation counters per widget id
    _gen = {}

    _glitch_chars = "█▓░▒▐▌╳╬◼◻▪▫⣿⣶⣤⠿"

    def _corrupt(text, intensity=0.4):
        if not text:
            return text
        chars = list(text)
        n = max(1, int(len(chars) * intensity))
        for i in random.sample(range(len(chars)), min(n, len(chars))):
            chars[i] = random.choice(_glitch_chars)
        return "".join(chars)

    def _anim_label_change(self, widget, new_text, base_col=None):
        from oternos.constants import C
        from oternos.animation import ColorAnim

        if base_col is None:
            try:
                base_col = widget.cget("fg")
            except Exception:
                base_col = C["white2"]

        # Bump generation for this widget — any older animation will see a
        # mismatched generation and abort
        wid = id(widget)
        gen = _gen.get(wid, 0) + 1
        _gen[wid] = gen

        frames = [
            (_corrupt(new_text, 0.8),  C["white3"], 35),
            (_corrupt(new_text, 0.7),  C["white3"], 35),
            (_corrupt(new_text, 0.6),  C["white3"], 40),
            (_corrupt(new_text, 0.5),  C["white2"], 40),
            (_corrupt(new_text, 0.35), C["white2"], 45),
            (_corrupt(new_text, 0.25), C["white"],  45),
            (_corrupt(new_text, 0.15), C["white"],  50),
            (_corrupt(new_text, 0.08), base_col,    45),
            (_corrupt(new_text, 0.03), base_col,    40),
            (new_text,                 base_col,    0),
        ]

        def _do_glitch():
            # Check we're still the current animation for this widget
            if _gen.get(wid) != gen:
                return

            def _gf(i=0):
                # Abort if superseded
                if _gen.get(wid) != gen:
                    return
                if i >= len(frames):
                    ColorAnim.run(self.root, widget, "fg",
                                  C["white2"], base_col, duration_ms=120)
                    return
                text, col, delay = frames[i]
                try:
                    widget.config(text=text, fg=col)
                except Exception:
                    return
                if i < len(frames) - 1:
                    widget.after(delay, lambda: _gf(i + 1))
                else:
                    ColorAnim.run(self.root, widget, "fg",
                                  C["white2"], base_col, duration_ms=120)

            _gf()

        ColorAnim.run(
            self.root, widget, "fg",
            base_col, C["bg"],
            duration_ms=60,
            on_done=_do_glitch,
        )

    app._anim_label_change = types.MethodType(_anim_label_change, app)
