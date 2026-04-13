"""
boot/__init__.py — OTERNOS PLAYER
Package init. Re-exports all public symbols so that existing imports
in __main__.py and anywhere else continue to work unchanged:

    from .boot import TronBoot, _focused_on_entry   ← same as before
    from .boot import run_boot_only_mode             ← was .boot_html
    from .boot import run_html_boot, run_html_init   ← was .boot_html

Structure:
    boot/
    ├── __init__.py      ← this file (re-exports only, no logic)
    ├── boot.py          ← TronBoot + _focused_on_entry  (was root boot.py)
    └── html_boot.py     ← HTML boot logic              (was boot_html.py)
"""

# ── Tkinter boot sequence ─────────────────────────────────────────────────────
from .boot import TronBoot, _focused_on_entry

# ── HTML boot sequence ────────────────────────────────────────────────────────
# html_boot.py is the renamed boot_html.py — drop it in this folder as-is.
from .html_boot import run_boot_only_mode, run_html_boot, run_html_init

__all__ = [
    "TronBoot",
    "_focused_on_entry",
    "run_boot_only_mode",
    "run_html_boot",
    "run_html_init",
]
