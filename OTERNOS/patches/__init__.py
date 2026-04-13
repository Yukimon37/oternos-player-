"""
patches/__init__.py — OTERNOS PATCH LOADER

Drop a .py file in this folder with an apply(app) function.
It will be auto-loaded alphabetically on startup.
Name files with a numeric prefix so order is predictable:
  001_fix_art_cv.py, 002_fix_playpause.py, 100_smooth_scroll.py …

EXTERNAL PATCHES (no rebuild needed):
When running as a built exe, the loader also checks for a `patches/` folder
sitting next to void_player.exe. Files there load AFTER bundled patches and
override any bundled patch with the same filename stem.

Layout next to the exe:
  void_player.exe
  patches/
      my_fix.py        <- loaded automatically, no rebuild needed
"""

import importlib.util
import sys
from pathlib import Path


def _get_patches_dirs() -> list:
    dirs = []

    # 1. Bundled patches (inside the exe temp dir or source tree)
    bundled = Path(__file__).parent
    dirs.append(bundled)

    # 2. External patches folder next to the exe (frozen only)
    if getattr(sys, "frozen", False):
        exe_dir  = Path(sys.executable).parent
        external = exe_dir / "patches"
        if external.exists() and external.resolve() != bundled.resolve():
            dirs.append(external)

    return dirs


def load_all(app) -> list:
    """
    Import every patch module from all patch directories alphabetically.
    External patches (next to exe) override bundled ones with the same stem.
    Returns list of patch names that were applied successfully.
    """
    # Collect all patch files — later dirs win on name collision
    seen = {}
    for patches_dir in _get_patches_dirs():
        try:
            for p in sorted(patches_dir.glob("*.py")):
                if p.name == "__init__.py" or p.name.startswith("_"):
                    continue
                seen[p.stem] = p
        except Exception:
            pass

    applied = []
    failed  = []

    for name, path in sorted(seen.items()):
        try:
            spec = importlib.util.spec_from_file_location(
                f"oternos.patches.{name}", path
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "apply"):
                mod.apply(app)
                applied.append(name)
        except Exception as exc:
            failed.append((name, exc))
            try:
                from oternos.diagnostics import log_exception
                log_exception(f"patch:{name}", exc)
            except Exception:
                pass

    try:
        from oternos.diagnostics import get_logger
        log = get_logger()
        log.info("Patches applied: %s", applied)
        if failed:
            log.warning("Patches FAILED: %s", [n for n, _ in failed])
    except Exception:
        pass

    return applied
