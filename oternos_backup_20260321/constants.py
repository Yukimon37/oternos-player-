"""
constants.py — OTERNOS PLAYER
Global constants, palette, fonts, paths, animation math.
"""

from pathlib import Path

# ── Last.fm credentials (user fills these in Settings) ──
LASTFM_API_KEY = ""
LASTFM_API_SECRET = ""
LASTFM_API_ROOT = "https://ws.audioscrobbler.com/2.0/"

# ── Spotify imports (stdlib only — no spotipy needed) ──

# ─────────────────────────────────────────
#  PALETTE — White Void Cybercore
# ─────────────────────────────────────────
C = {
    "bg": "#050505",  # near-black void
    "panel": "#0c0c0c",  # surface
    "panel2": "#131313",  # alt row — subtly lighter than panel
    "border": "#1f1f1f",  # hairline separator
    "border2": "#2e2e2e",  # slightly brighter border
    "white": "#e8e8e8",  # primary text
    "white2": "#9a9a9a",  # secondary text
    "white3": "#424242",  # muted / disabled
    "glow": "#ffffff",  # hover / active
    "select": "#1e1e1e",  # selection bg — clearly visible
    "select2": "#242424",  # deeper select
    "red": "#cc2222",  # error / warning
}

# ─────────────────────────────────────────
#  HARDWARE ACCELERATOR FLAG
#  When True: GPU rendering hints, higher FPS, lower CPU overhead
#  When False: all animations throttled, poll rate halved
# ─────────────────────────────────────────
HW_ACCEL = True  # default on — user can toggle in settings


def hw_fps(hi, lo=8):
    """Return frame interval (ms) based on HW_ACCEL state."""
    return hi if HW_ACCEL else lo * 16


FM = ("Courier New", 9)
FMS = ("Courier New", 8)
FML = ("Courier New", 10, "bold")
FMX = ("Courier New", 13, "bold")

DATA_FILE = Path.home() / ".voidplayer.json"
YT_CACHE = Path.home() / ".voidplayer_cache"
YT_CACHE.mkdir(exist_ok=True)

# Embedded app icon (hex-O emblem, 64x64 PNG, base64)
_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAEMElEQVR4nO1bubHjMAzF"
    "92ykEpTKZagOBarDZagOBarDZdipS1C8wQ48NAQSB0HbM39fsp6/EgQ8gjh4/MCb0HXd"
    "zfL8vu/nVrqk+Gkl2GqwhFaEnKIFdl130xq/LMvQQq4Ff6IEtVCu9J0oj6ieAl7DH4"
    "/Hc/T7vr97v19LhJuAmhFPjUfUkADgJ8IVA6KMX9eV/fs7dTJ7QAvjAQDmeX7+fueU"
    "UHtAbRQuGQ/wanSNN1j1VBFQG+E1AW9ZliGKBAC9zmIajBh1i0tzJHinRNd1N2lKiDHA"
    "Q0BJcan4uVwuh3dqiJAIKHqA1/jalEaB8jyyJS/IeoDV+Fp3bf2dHAksARbjOYUsNb4F"
    "6fTwEMGR4O4FcgosyzJw8zgCqex0WnB6aHEgQBr9d7m6FhYiuHiQrQOoGz8ej0HKzS1H"
    "H+DfFJCmF6dn6Z0XD0hH/3K53KmgdV3ZNPUNwJFflmWY5zlbfFEveAmC1P1RCFe6psCR"
    "0ZKDcqdpgm3bDkZIwG9J3oD9BZWbEvD0AG/FZzXa8oxEiIYEDqkXFHsBVCDt1DhIoz+O"
    "48EwlI2/OWNzpNWMPsUJoN3oY0Datg2maQJq6PV6fXnfQoJWhxzQZnU7nPtQbvRpEKLG"
    "5pB6Bicr1SfnBRZSRAJSRVLB2sDnqRc4EjhwOqS/Nd82L4lp2I0sllAGjSNe3Sh+NPOf"
    "68I0rg8QQ8I4jgOmy1yLTXXRdo7hGyMUtSs7AMdgGQkXAZa5/46ewVsPAAR7AJ37kvGY"
    "JjVeQpueKJgJiGp4qCG1hnm9IGxv0IKcsaXANY7jME1TuC6mLGApeUuBqzTapWmjSa+o"
    "Y5MsILnZtm2wbVvTqF2CZ3o2T4McciPziVUmVyWY8wJLpKbG5oxHWZL7e4PzR4IgQpMm"
    "039bwDUFNClHU7tLsK4Qeb5x8hwsKC1J9X1/p0tdNUhJKPUBnhpg3/ezqxCSnsEsEOG6"
    "ls7SQ4JIQGpE+gEt8zXzWLsMT/XSvg9giAFWdrkVHS0J4zi+9AfW9GjR9QTgP2AkeYFm"
    "jS8NltIaouXbElSrwtp9gRJyJKRdINcR1laTqLPkdc86YN/3s2d1OB2JXCqiJOSUit4Y"
    "ycG8M4SQtsZa7w1qvoFbYylUO0P4H0gCd2hpnmeY5/mrdocRpbXIlDQa7w4HJGq3x993"
    "PsCqF4IScOgFpFgQdTAhChY9uGz364/I/D8kVXqpxTE5zzlBrewcSoVecT3AUxv0fX+P"
    "9oaWByWbnBRFlE6Scc9z21vc+xZUnRRFAV4SuCUy7SqQ5lkJmh5H1Q3WXkuhBZWUy+k7"
    "Hmh1VrfD+76fa4iQDjxEXpiw6Om6MxR5f2Bd14/dFgH40KUpgPiLU17v/Ni1OYCYOV8b"
    "n6p3hmpiQ9/393Vd3fk94vJk2MYIKtP6Bmn0HeJff3m6GQEU33p9/i+ic9mwtWarfgAA"
    "AABJRU5ErkJggg=="
)


# ─────────────────────────────────────────
#  SMOOTH ANIMATION UTILITIES
# ─────────────────────────────────────────
def _ease_out(t):
    """Cubic ease-out: fast start, smooth stop."""
    return 1 - (1 - t) ** 3


def _ease_in_out(t):
    """Smooth S-curve easing."""
    return t * t * (3 - 2 * t)


def _lerp(a, b, t):
    return a + (b - a) * t


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def _lerp_color(c1, c2, t):
    """Smoothly interpolate between two hex colors."""
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(_lerp(r1, r2, t), _lerp(g1, g2, t), _lerp(b1, b2, t))


ease_out = _ease_out
ease_in_out = _ease_in_out
lerp = _lerp
lerp_color = _lerp_color
hex_to_rgb = _hex_to_rgb
rgb_to_hex = _rgb_to_hex