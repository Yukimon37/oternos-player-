"""
constants.py — OTERNOS PLAYER
Compatibility shim: constants.py was merged into utils.py.
All existing `from oternos.constants import ...` imports continue to work.
"""

from .utils import (  # noqa: F401  (re-exported on purpose)
    C,
    FM,
    FMS,
    FML,
    FMX,
    DATA_FILE,
    YT_CACHE,
    HW_ACCEL,
    _ICON_B64,
    hw_fps,
    LASTFM_API_KEY,
    LASTFM_API_SECRET,
    LASTFM_API_ROOT,
    ease_out,
    ease_in_out,
    lerp,
    lerp_color,
    hex_to_rgb,
    rgb_to_hex,
)
