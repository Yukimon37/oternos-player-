"""
003_fix_soundcloud.py — Two SC fixes:

1. The ⋯ detail-panel indicator disappears after a list refresh because
   _sc_show_tracks() unconditionally rebuilds every row. This patch wraps
   _sc_show_tracks so it re-highlights the open detail row after drawing.

2. On very fast clicks, _sc_list_click can fire twice spawning two stream
   threads. Add a 400ms guard so only the first click within that window
   triggers a stream start.

   Also wraps _sc_stream itself with a monotonic time guard so that even
   calls that bypass the click handler (repeat_mode=="one" direct thread
   spawns, etc.) cannot double-fire within 400ms.
"""

import threading
import time
import types


def apply(app):
    # sc_list widget was removed from the player — patch disabled to prevent startup crash.
    # Stream debounce is now handled by 004_fix_sc_stream and 016_sc_stream_retry.
    pass
