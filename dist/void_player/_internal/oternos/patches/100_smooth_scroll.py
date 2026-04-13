"""
100_smooth_scroll.py — Wire SmoothScroller to every list widget that doesn't
already use it. The lists built after startup (deferred views) are covered
by a deferred pass run 1.5 s after launch.

List widgets already wired at startup: sc_list, dz_list, ia_items_list,
ia_files_list, bc_list. This patch adds: yt_list_cv, sp_list_cv, _hist_cv,
_lyrics_cv, _alb_cv, _lp_cv, and the main track_list canvas.
"""


def _wire(app, attr, use_yview=False):
    """Bind <MouseWheel> on widget `attr` to _scroller or fallback yview."""
    if not hasattr(app, attr):
        return
    w = getattr(app, attr)
    try:
        if use_yview:
            w.bind(
                "<MouseWheel>",
                lambda e, _w=w: _w.yview_scroll(int(-1 * (e.delta / 120)) * 3, "units"),
                add="+",
            )
        else:
            w.bind(
                "<MouseWheel>",
                lambda e, _w=w: app._scroller.scroll(_w, e.delta),
                add="+",
            )
    except Exception:
        pass


def apply(app):
    # Widgets that exist at startup
    for attr in ("sp_list_cv", "yt_list_cv"):
        _wire(app, attr, use_yview=True)

    for attr in ("_hist_cv", "_lyrics_cv", "_alb_cv", "_lp_cv"):
        _wire(app, attr, use_yview=True)

    # track_list is a canvas with yview — smooth-scroll it
    _wire(app, "track_list", use_yview=False)

    # Deferred views may not exist yet — retry after 1.5 s
    def _deferred():
        for attr in ("_hist_cv", "_lyrics_cv", "_alb_cv", "_lp_cv",
                     "netstream_list", "_alb_grid_cv"):
            _wire(app, attr, use_yview=True)

    app.root.after(1500, _deferred)
