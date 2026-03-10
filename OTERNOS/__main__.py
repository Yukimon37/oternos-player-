"""
__main__.py
─────────────────────────────────────────────────────────────────────────────
OTERNOS PLAYER  —  Entry point.

Run with:
    python -m oternos
or (legacy):
    python void_player.py
─────────────────────────────────────────────────────────────────────────────
"""

import tkinter as tk
import json
from pathlib import Path

from .boot    import TronBoot, _focused_on_entry
from .player  import VoidPlayer


def main():
    root = tk.Tk()
    root.withdraw()   # hide main window during boot

    def _launch():
        root.deiconify()
        app = VoidPlayer(root)

        def _guard(fn):
            def _handler(e):
                if not _focused_on_entry(root):
                    fn()
            return _handler

        root.bind("<MouseWheel>",    app._route_scroll)
        root.bind("<space>",         _guard(app._toggle_play))
        root.bind("<Right>",         _guard(app._next))
        root.bind("<Left>",          _guard(app._prev))
        root.bind("<Up>",            _guard(lambda: (app.engine.set_volume(app.engine.volume + 0.05), app._upd_vol())))
        root.bind("<Down>",          _guard(lambda: (app.engine.set_volume(app.engine.volume - 0.05), app._upd_vol())))
        root.bind("<Control-Right>", _guard(lambda: app._seek_relative(+10)))
        root.bind("<Control-Left>",  _guard(lambda: app._seek_relative(-10)))
        root.bind("<Control-p>",     _guard(app._toggle_play))

    # Count saved library tracks so the boot screen can show them
    _n_tracks = 0
    _boot_fs  = True
    try:
        _d        = json.loads(Path.home().joinpath(".voidplayer.json").read_text())
        _n_tracks = len(_d.get("library", []))
        _boot_fs  = _d.get("settings", {}).get("boot_fullscreen", True)
    except Exception:
        pass

    TronBoot(root, on_done=_launch, track_count=_n_tracks, fullscreen=_boot_fs)
    root.mainloop()


if __name__ == "__main__":
    main()
