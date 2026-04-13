"""
008_art_cache.py — Cache decoded album art images in memory.

Without this, every track switch re-fetches and re-decodes the album art
from disk or network even if the same art was shown recently.
This patch caches the last 30 PhotoImage objects keyed by URL/path.
"""
import threading
from pathlib import Path


_CACHE_SIZE = 30


def apply(app):
    # Install the cache on the app instance
    if not hasattr(app, "_art_img_cache"):
        app._art_img_cache    = {}   # key -> PhotoImage
        app._art_img_keys     = []   # ordered list of keys for LRU eviction

    # Wrap _set_album_art to check cache first
    _orig_set_art = app._set_album_art

    def _cached_set_art(url_or_path):
        key = str(url_or_path)
        if key in app._art_img_cache:
            # Cache hit — apply directly without re-fetching
            try:
                photo = app._art_img_cache[key]
                _apply_photo(app, photo, key)
                return
            except Exception:
                # Cache entry invalid — remove and fall through
                app._art_img_cache.pop(key, None)
                try:
                    app._art_img_keys.remove(key)
                except ValueError:
                    pass

        # Cache miss — let original load, then cache the result
        _orig_set_art(url_or_path)
        # Schedule cache capture after the image is loaded
        app.root.after(500, lambda k=key: _capture_to_cache(app, k))

    import types
    app._set_album_art = types.MethodType(
        lambda self, u: _cached_set_art(u), app
    )


def _apply_photo(app, photo, key):
    """Apply a cached PhotoImage to the art canvas."""
    try:
        SIZE = 54
        cv = app.art_cv
        cv.delete("all")
        cv.create_image(SIZE // 2, SIZE // 2, image=photo, anchor="center")
        app._art_photo    = photo
        app._art_url_last = key
        # Move to end of LRU
        try:
            app._art_img_keys.remove(key)
        except ValueError:
            pass
        app._art_img_keys.append(key)
    except Exception:
        pass


def _capture_to_cache(app, key):
    """After art loads, grab the PhotoImage and store it."""
    try:
        photo = getattr(app, "_art_photo", None)
        if photo is None:
            return
        # Only cache if this key is still the current art
        if getattr(app, "_art_url_last", None) != key:
            return
        app._art_img_cache[key] = photo
        if key not in app._art_img_keys:
            app._art_img_keys.append(key)
        # Evict oldest if over limit
        while len(app._art_img_keys) > _CACHE_SIZE:
            oldest = app._art_img_keys.pop(0)
            app._art_img_cache.pop(oldest, None)
    except Exception:
        pass
