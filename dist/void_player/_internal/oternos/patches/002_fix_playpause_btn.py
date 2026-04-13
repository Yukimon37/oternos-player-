"""
002_fix_playpause_btn.py — Keep btn_play text in sync with actual engine state.

Bug: after certain source switches (Spotify → local, stream timeout, etc.)
the btn_play label can get stuck showing ⏸ when audio is stopped, or ▶
when playing. This patch installs a lightweight poll that syncs the symbol
every 2 seconds.
"""


def apply(app):
    INTERVAL = 2000  # ms

    def _sync():
        try:
            # Spotify mode — let Spotify handle its own button state
            if getattr(app, "_sp_mode", False) or getattr(app, "_active_source", "") == "spotify":
                pass
            else:
                eng = app.engine
                playing = getattr(eng, "is_playing", False)
                paused  = getattr(eng, "is_paused", False)
                correct = "⏸" if playing else "▶"
                current = app.btn_play.cget("text")
                if current not in ("▶", "⏸"):
                    # Some other label got in there (shouldn't happen) — fix it
                    app.btn_play.config(text=correct)
                elif current == "⏸" and not playing and not paused:
                    app.btn_play.config(text="▶")
                elif current == "▶" and playing:
                    app.btn_play.config(text="⏸")
        except Exception:
            pass
        finally:
            app.root.after(INTERVAL, _sync)

    app.root.after(INTERVAL, _sync)
