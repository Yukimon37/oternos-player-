"""
boot/html_boot.py — OTERNOS PLAYER
HTML-based boot screen via PyQt5 subprocess (no pywebview dependency).

Spawns the same executable with --boot-only so the Qt event loop runs in its own
process — completely isolated from the Tk main loop. Reliable in both source and
PyInstaller frozen environments.
"""

from __future__ import annotations

import sys
import os
import subprocess
from pathlib import Path


# ── Locate HTML files ───────────────────────────────────────────────────────────────────────────────────
def _find_html() -> str | None:
    candidates = []
    try:
        candidates.append(Path(__file__).parent / "boot_screen.html")
    except Exception:
        pass
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "oternos" / "boot_screen.html")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "boot_screen.html")
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def _find_init_html() -> str | None:
    candidates = []
    try:
        candidates.append(Path(__file__).parent / "init_screen.html")
    except Exception:
        pass
    if hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "oternos" / "init_screen.html")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / "init_screen.html")
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def _build_args(mode: str, html_path: str, track_count: int, fullscreen: bool) -> list[str]:
    if getattr(sys, "frozen", False):
        args = [sys.executable, mode, "--boot-html", html_path, "--boot-tracks", str(track_count)]
    else:
        args = [sys.executable, "-m", "oternos", mode, "--boot-html", html_path, "--boot-tracks", str(track_count)]
    if fullscreen:
        args.append("--boot-fullscreen")
    return args


# ── Main public function ──────────────────────────────────────────────────────
def _pyqt5_available() -> bool:
    """Check if PyQt5 + WebEngine are importable before spawning a subprocess."""
    try:
        import importlib
        importlib.import_module("PyQt5.QtWidgets")
        importlib.import_module("PyQt5.QtWebEngineWidgets")
        return True
    except Exception:
        return False


def run_html_boot(on_done, track_count: int = 0, fullscreen: bool = True) -> bool:
    """
    Show the HTML boot screen and call on_done() when it finishes.
    Spawns the current executable with --boot-only so PyQt5's event loop
    runs fully isolated from Tkinter's main loop.
    Returns True if boot ran, False if dependencies missing.
    """
    if not _pyqt5_available():
        return False

    html_path = _find_html()
    if not html_path:
        return False

    args = _build_args("--boot-only", html_path, track_count, fullscreen)
    try:
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
    except Exception:
        return False

    try:
        on_done()
    except Exception:
        pass
    return True


def run_html_init(track_count: int = 0) -> None:
    """
    Show the HTML init screen as an overlay on top of the player.
    Blocks until the init animation completes (~4 seconds).
    """
    if not _pyqt5_available():
        return
    html_path = _find_init_html()
    if not html_path:
        return
    args = _build_args("--init-only", html_path, track_count, fullscreen=False)
    try:
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()  # blocking — caller must run this in a thread
    except Exception:
        pass




# ── Boot-only mode (called when --boot-only arg is present) ──────────────────
def run_boot_only_mode():
    """
    Runs the Qt boot window and exits. Called from __main__.py when
    the --boot-only argument is detected.
    """
    import sys

    args = sys.argv
    fullscreen   = "--boot-fullscreen" in args
    html_path    = None
    track_count  = 0

    try:
        idx = args.index("--boot-html")
        html_path = args[idx + 1]
    except (ValueError, IndexError):
        html_path = _find_html()

    try:
        idx = args.index("--boot-tracks")
        track_count = int(args[idx + 1])
    except (ValueError, IndexError):
        pass

    if not html_path or not Path(html_path).exists():
        sys.exit(1)

    try:
        html = Path(html_path).read_text(encoding="utf-8")
        html = html.replace("__TRACK_COUNT__", str(track_count))
    except Exception:
        sys.exit(1)

    try:
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        from PyQt5.QtCore import Qt, QUrl
        from PyQt5.QtGui import QColor

        app = QApplication(sys.argv)

        screen = app.primaryScreen().geometry()
        is_init = "--init-only" in sys.argv
        is_player = "--player-only" in sys.argv

        if is_init or is_player:
            # Match the player window size exactly (1100x700)
            w, h = min(1100, screen.width()), min(700, screen.height())
        elif fullscreen:
            w, h = screen.width(), screen.height()
        else:
            w = min(screen.width(), 900)
            h = min(screen.height(), 580)

        view = QWebEngineView()
        view.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        view.page().setBackgroundColor(QColor(0, 0, 0))
        view.resize(w, h)
        view.move((screen.width() - w) // 2, (screen.height() - h) // 2)

        def _on_title_changed(title):
            if not is_player and "BOOT_DONE" in title:
                app.quit()

        view.titleChanged.connect(_on_title_changed)
        
        if is_player:
            try:
                port = args[args.index("--port") + 1]
            except:
                port = "47389"
            view.setUrl(QUrl(f"http://127.0.0.1:{port}/"))
        else:
            view.setHtml(html, QUrl("file:///"))
            
        view.show()
        app.exec_()

    except Exception:
        pass

    sys.exit(0)
