"""
018_glitch_all_sources.py — Glitch animation for stream now-playing labels.

Intercepts .config(text=...) calls on now_title and now_artist widgets.
When the active source is a stream and text is being set to a real value,
runs the glitch animation instead of setting text directly.
"""


def apply(app):
    _skip = {'', '—', '-', 'NO TRACK', 'Unknown', 'SoundCloud',
             'YouTube', 'Deezer', 'Internet Archive', 'Bandcamp'}
    _glitch_chars = set('█▓░▒▐▌╳╬◼◻▪▫⣿⣶⣤⠿')
    _stream_sources = {'soundcloud', 'youtube', 'deezer', 'archive', 'bandcamp', 'netstream'}

    def _make_interceptor(widget, orig_config):
        def _intercepted_config(**kwargs):
            text = kwargs.get('text')
            source = getattr(app, '_active_source', '')

            if (text is not None and
                len(kwargs) == 1 and
                source in _stream_sources and
                str(text).strip() not in _skip and
                not any(c in str(text) for c in _glitch_chars)):
                app._anim_label_change(widget, str(text))
            else:
                orig_config(**kwargs)

        return _intercepted_config

    app.now_title._orig_config  = app.now_title.config
    app.now_artist._orig_config = app.now_artist.config

    app.now_title.config  = _make_interceptor(app.now_title,  app.now_title._orig_config)
    app.now_artist.config = _make_interceptor(app.now_artist, app.now_artist._orig_config)
