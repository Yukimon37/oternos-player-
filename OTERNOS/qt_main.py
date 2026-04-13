"""Entry point for the experimental PySide6 OTERNOS shell."""

from __future__ import annotations

import sys


def main() -> int:
    if getattr(sys, "frozen", False):
        from oternos.ui_qt.shell import run
    else:
        try:
            from .ui_qt.shell import run
        except ImportError:
            from oternos.ui_qt.shell import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
