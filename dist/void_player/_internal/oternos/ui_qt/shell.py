"""
shell.py - static PySide6 prototype shell.

This is a non-invasive visual prototype. It does not replace the legacy Tkinter
app and does not wire real playback yet.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
import sys
import time
from urllib.parse import urlparse

from ..core.app_state import TrackSummary, load_app_snapshot, snapshot_file_marker
from ..core.runtime_commands import write_runtime_command
from ..core.runtime_state import load_runtime_snapshot, runtime_file_marker


STYLE = """
* {
    font-family: "Segoe UI", "Inter", Arial, sans-serif;
    letter-spacing: 0;
}
QMainWindow, QWidget#root {
    background: #000000;
    color: #f0f0f0;
}
QFrame#sidebar {
    background: #050505;
    border-right: 1px solid #222222;
}
QLabel#brand {
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 22px;
    font-weight: 800;
}
QLabel#caption, QLabel#muted {
    color: #aaaaaa;
    font-size: 12px;
}
QLabel#micro {
    color: #777777;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
}
QLabel#mono {
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
}
QLabel#statusGood {
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
    font-weight: 700;
}
QLabel#statusWarn {
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
    font-weight: 700;
}
QPushButton {
    background: transparent;
    color: #aaaaaa;
    border: 1px solid transparent;
    border-radius: 3px;
    padding: 10px 12px;
    text-align: left;
    font-size: 13px;
}
QPushButton:hover {
    background: #111111;
    color: #f0f0f0;
    border-color: #f0f0f0;
}
QPushButton[active="true"] {
    background: #141414;
    color: #f0f0f0;
    border-color: #f0f0f0;
}
QPushButton#control {
    background: #050505;
    color: #f0f0f0;
    border: 1px solid #3a3a3a;
    text-align: center;
    min-width: 48px;
}
QPushButton#control:hover {
    background: #141414;
    border-color: #f0f0f0;
}
QPushButton#uvDragonfly {
    background: #050505;
    color: #f0f0f0;
    border: 1px solid #4a4a4a;
    border-left: 3px solid #f0f0f0;
    border-radius: 2px;
    padding: 9px 13px;
    text-align: center;
    min-width: 58px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-weight: 850;
}
QPushButton#uvDragonfly:hover {
    background: #f0f0f0;
    color: #000000;
    border-color: #ffffff;
    border-left-color: #777777;
}
QPushButton#uvDragonfly:pressed {
    background: #000000;
    color: #ffffff;
    border-color: #ffffff;
}
QPushButton#uvPug {
    background: #f0f0f0;
    color: #000000;
    border: 2px solid #ffffff;
    border-radius: 5px;
    padding: 9px 14px;
    text-align: center;
    min-width: 62px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-weight: 950;
}
QPushButton#uvPug:hover {
    background: #000000;
    color: #ffffff;
    border-color: #ffffff;
}
QPushButton#uvPug:pressed {
    background: #777777;
    color: #000000;
    border-color: #f0f0f0;
}
QPushButton#uvSloth {
    background: #080808;
    color: #f0f0f0;
    border: 1px solid #ffffff;
    border-top: 3px solid #ffffff;
    border-radius: 4px;
    padding: 8px 13px;
    text-align: center;
    min-width: 58px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-weight: 850;
}
QPushButton#uvSloth:hover {
    background: #181818;
    color: #ffffff;
    border-color: #f0f0f0;
    border-top-color: #777777;
}
QPushButton#uvSloth:pressed {
    background: #f0f0f0;
    color: #000000;
}
QPushButton#uvStingray {
    background: #050505;
    color: #f0f0f0;
    border: 1px solid #777777;
    border-bottom: 3px solid #f0f0f0;
    border-radius: 2px;
    padding: 8px 13px 9px 13px;
    text-align: center;
    min-width: 58px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-weight: 850;
}
QPushButton#uvStingray:hover {
    background: #141414;
    color: #ffffff;
    border-color: #ffffff;
    border-bottom-color: #777777;
}
QPushButton#uvStingray:pressed {
    background: #ffffff;
    color: #000000;
}
QPushButton#uvEmu {
    background: #000000;
    color: #f0f0f0;
    border: 1px solid #f0f0f0;
    border-right: 3px solid #777777;
    border-radius: 5px;
    padding: 8px 13px;
    text-align: center;
    min-width: 58px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-weight: 900;
}
QPushButton#uvEmu:hover {
    background: #ffffff;
    color: #000000;
    border-color: #ffffff;
    border-right-color: #000000;
}
QPushButton#uvEmu:pressed {
    background: #141414;
    color: #ffffff;
}
QPushButton#primaryControl {
    background: #f0f0f0;
    color: #000000;
    border: 1px solid #ffffff;
    text-align: center;
    min-width: 64px;
    font-weight: 750;
}
QPushButton:disabled {
    background: #030303;
    color: #555555;
    border-color: #141414;
}
QPushButton#primaryControl:disabled {
    background: #111111;
    color: #555555;
    border-color: #222222;
}
QPushButton#uvPlay {
    background: #f0f0f0;
    color: #000000;
    border: 1px solid #ffffff;
    border-radius: 3px;
    padding: 9px 12px;
    text-align: center;
    min-width: 56px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-weight: 900;
}
QPushButton#uvPlay:hover {
    background: #ffffff;
    color: #000000;
    border-color: #ffffff;
}
QPushButton#uvPlay:pressed {
    background: #111111;
    color: #f0f0f0;
    border-color: #f0f0f0;
}
QPushButton#uvAdd {
    background: #080808;
    color: #f0f0f0;
    border: 1px solid #f0f0f0;
    border-radius: 3px;
    padding: 9px 12px;
    text-align: center;
    min-width: 56px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-weight: 800;
}
QPushButton#uvAdd:hover {
    background: #141414;
    color: #f0f0f0;
    border-color: #ffffff;
}
QPushButton#uvAdd:pressed {
    background: #f0f0f0;
    color: #000000;
}
QPushButton#uvList {
    background: #080808;
    color: #f0f0f0;
    border: 1px solid #666666;
    border-radius: 3px;
    padding: 9px 12px;
    text-align: center;
    min-width: 56px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-weight: 800;
}
QPushButton#uvList:hover {
    background: #181818;
    color: #ffffff;
    border-color: #f0f0f0;
}
QPushButton#uvDanger {
    background: #080808;
    color: #f0f0f0;
    border: 1px solid #666666;
    border-radius: 3px;
    padding: 9px 12px;
    text-align: center;
    min-width: 56px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-weight: 900;
}
QPushButton#uvDanger:hover {
    background: #181818;
    color: #ffffff;
    border-color: #f0f0f0;
}
QPushButton#uvPlay:disabled,
QPushButton#uvAdd:disabled,
QPushButton#uvList:disabled,
QPushButton#uvDanger:disabled,
QPushButton#uvDragonfly:disabled,
QPushButton#uvPug:disabled,
QPushButton#uvSloth:disabled,
QPushButton#uvStingray:disabled,
QPushButton#uvEmu:disabled {
    background: #030303;
    color: #555555;
    border-color: #141414;
}
QLineEdit {
    background: #050505;
    color: #f0f0f0;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 10px 14px;
    font-size: 13px;
}
QLineEdit:focus {
    border-color: #f0f0f0;
}
QDialog {
    background: #000000;
    color: #f0f0f0;
}
QListWidget {
    background: #050505;
    color: #f0f0f0;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 6px;
}
QListWidget::item {
    border-radius: 5px;
    padding: 8px;
}
QListWidget::item:selected {
    background: #141414;
    color: #f0f0f0;
}
QFrame#panel, QFrame#card, QFrame#playerbar {
    background: #050505;
    border: 1px solid #222222;
    border-radius: 4px;
}
QFrame#terminalPanel {
    background: #000000;
    border: 1px solid #f0f0f0;
    border-radius: 4px;
}
QFrame#signalPanel {
    background: #050505;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
}
QFrame#telemetryPanel {
    background: #030303;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
}
QFrame#card:hover {
    border-color: #f0f0f0;
    background: #111111;
}
QFrame#art {
    background: #000000;
    border: 1px solid #f0f0f0;
    border-radius: 4px;
}
QFrame#miniArt {
    background: #000000;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
}
QFrame#queueThumb {
    background: #000000;
    border: 1px solid #222222;
    border-radius: 3px;
}
QLabel#sourceResultThumb {
    background: #000000;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    font-weight: 800;
}
QLabel#coverImage {
    background: #000000;
    border: none;
}
QLabel#artHint {
    color: #777777;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 10px;
}
QFrame#divider {
    background: #3a3a3a;
    border: none;
    min-height: 1px;
    max-height: 1px;
}
QFrame#scanline {
    background: #f0f0f0;
    border: none;
    min-height: 2px;
    max-height: 2px;
}
QFrame#cyberPanel {
    background: #000000;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
}
QFrame#matrixCell {
    background: #080808;
    border: 1px solid #2a2a2a;
    border-radius: 2px;
}
QFrame#meterBar {
    background: #f0f0f0;
    border: none;
    border-radius: 1px;
}
QFrame#meterBarDim {
    background: #f0f0f0;
    border: none;
    border-radius: 1px;
}
QLabel#chip {
    color: #f0f0f0;
    background: #050505;
    border: 1px solid #3a3a3a;
    border-radius: 3px;
    padding: 6px 9px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
}
QLabel#chipLive {
    color: #f0f0f0;
    background: #080808;
    border: 1px solid #f0f0f0;
    border-radius: 3px;
    padding: 6px 9px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
    font-weight: 700;
}
QLabel#chipStale {
    color: #f0f0f0;
    background: #111111;
    border: 1px solid #666666;
    border-radius: 3px;
    padding: 6px 9px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
    font-weight: 700;
}
QLabel#chipOffline {
    color: #f0f0f0;
    background: #080808;
    border: 1px solid #666666;
    border-radius: 3px;
    padding: 6px 9px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
    font-weight: 700;
}
QLabel#timecode {
    color: #aaaaaa;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
    min-width: 42px;
}
QLabel#bigNumber {
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 28px;
    font-weight: 800;
}
QLabel#title {
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 26px;
    font-weight: 800;
}
QLabel#heroTitle {
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 32px;
    font-weight: 800;
}
QLabel#section {
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 16px;
    font-weight: 800;
}
QLabel#trackTitle {
    color: #f0f0f0;
    font-size: 13px;
    font-weight: 700;
}
QLabel#accent {
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    font-weight: 700;
}
QLabel#warningAccent {
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    font-weight: 700;
}
QLabel#dangerAccent {
    color: #f0f0f0;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12px;
    font-weight: 700;
}
QLabel#glyph {
    color: #f0f0f0;
    background: #080808;
    border: 1px solid #3a3a3a;
    border-radius: 2px;
    padding: 5px 7px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 11px;
}
QSlider::groove:horizontal {
    height: 5px;
    background: #1a1a1a;
    border-radius: 1px;
}
QSlider::handle:horizontal {
    background: #f0f0f0;
    width: 12px;
    margin: -4px 0;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #f0f0f0;
    border-radius: 1px;
}
QSlider:disabled::groove:horizontal {
    background: #111111;
}
QSlider:disabled::handle:horizontal {
    background: #555555;
}
QSlider:disabled::sub-page:horizontal {
    background: #555555;
}
QScrollArea {
    border: none;
    background: transparent;
}
"""


def run(argv: list[str] | None = None) -> int:
    """Launch the static Qt shell prototype."""
    try:
        from PySide6.QtCore import QUrl, Qt, QTimer
        from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
        from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
        from PySide6.QtWidgets import (
            QApplication,
            QDialog,
            QDialogButtonBox,
            QFrame,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QMainWindow,
            QPushButton,
            QScrollArea,
            QSlider,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise SystemExit(
            "PySide6 with QtNetwork is not installed. Install PySide6 in your Python environment "
            "to run the Phase 2 Qt prototype."
        ) from exc

    app = QApplication(argv or sys.argv)
    app.setStyleSheet(STYLE)

    class CyberVisualizer(QWidget):
        def __init__(self, runtime, *, minimum_height: int = 132, mode: str = "spectrum", parent=None):
            super().__init__(parent)
            self.setMinimumHeight(minimum_height)
            self._mode = mode
            self._phase = 0
            self._is_live = bool(runtime.is_live)
            self._is_playing = bool(runtime.is_playing)
            self._position = float(runtime.position or 0.0)
            self._duration = float(runtime.duration or 0.0)
            self._bars = tuple(float(value) for value in getattr(runtime, "visualizer_bars", ())[:48])
            self._clock_started = time.monotonic()
            self._timer = QTimer(self)
            self._timer.setInterval(80)
            self._timer.timeout.connect(self._advance)
            self._timer.start()

        def _advance(self):
            if self._is_live:
                self._phase = int(self._playhead() * 18)
            else:
                self._phase += 1
            self.update()

        def paintEvent(self, _event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            rect = self.rect()
            width = max(1, rect.width())
            height = max(1, rect.height())
            painter.fillRect(rect, QColor("#000000"))

            self._paint_grid(painter, width, height)
            playhead = self._playhead()
            activity = self._activity()
            progress = self._progress(playhead)
            if self._mode == "radar":
                self._paint_radar(painter, width, height, activity, progress)
            elif self._mode == "ring":
                self._paint_ring(painter, width, height, activity, progress)
            elif self._mode == "circuit":
                self._paint_circuit(painter, width, height, activity, progress)
            elif self._mode == "nodes":
                self._paint_nodes(painter, width, height, activity, progress)
            elif self._mode == "burst":
                self._paint_burst(painter, width, height, activity, progress)
            elif self._mode == "scope":
                self._paint_scope(painter, width, height, activity, progress)
            else:
                self._paint_spectrum(painter, width, height, activity, progress)

            scan_y = int((self._phase * 3) % height)
            painter.fillRect(0, scan_y, width, 2, QColor("#f0f0f0"))

            painter.setPen(QPen(QColor("#aaaaaa")))
            status = "LIVE SIGNAL" if self._is_live else "OFFLINE TRACE"
            painter.drawText(12, 18, f"{self._mode.upper()} // {status}")
            painter.drawText(12, height - 6, f"POS {int(playhead):04d}s / DUR {int(self._duration):04d}s")

        def _paint_grid(self, painter: QPainter, width: int, height: int):
            grid_pen = QPen(QColor("#222222"))
            grid_pen.setWidth(1)
            painter.setPen(grid_pen)
            for x in range(0, width, 24):
                painter.drawLine(x, 0, x, height)
            for y in range(0, height, 18):
                painter.drawLine(0, y, width, y)
            painter.setPen(QPen(QColor("#3a3a3a")))
            painter.drawLine(0, height // 2, width, height // 2)

        def _activity(self):
            base = 1.0 if self._is_live and self._is_playing else (0.35 if self._is_live else 0.14)
            if self._bars and self._is_playing:
                return max(base, min(1.25, 0.35 + self._energy() * 1.4))
            return base

        def _playhead(self):
            position = self._position
            if self._is_live and self._is_playing:
                position += time.monotonic() - self._clock_started
            if self._duration > 0:
                position = min(position, self._duration)
            return max(0.0, position)

        def _energy(self, start: float = 0.0, end: float = 1.0):
            if not self._bars:
                return 0.0
            lo = max(0, min(len(self._bars) - 1, int(len(self._bars) * start)))
            hi = max(lo + 1, min(len(self._bars), int(len(self._bars) * end)))
            band = self._bars[lo:hi]
            return sum(band) / max(1, len(band))

        def _progress(self, position: float):
            return position / self._duration if self._duration > 0 else 0.0

        def _bar_level(self, index: int, total: int):
            if not self._bars:
                return None
            bar_index = max(0, min(len(self._bars) - 1, int(index * len(self._bars) / max(1, total))))
            return self._bars[bar_index]

        def _paint_spectrum(self, painter: QPainter, width: int, height: int, activity: float, progress: float):
            bars = 36
            gap = 3
            margin = 14
            bar_width = max(3, int((width - (margin * 2) - (gap * (bars - 1))) / bars))
            base = height - 18

            for index in range(bars):
                wave = (math.sin((self._phase * 0.12) + (index * 0.48)) + 1.0) / 2.0
                pulse = (math.sin((progress * 12.0) + (index * 0.31)) + 1.0) / 2.0
                signal = self._bar_level(index, bars)
                if signal is None:
                    level = (wave * 0.68 + pulse * 0.32) * activity
                else:
                    level = max(0.04, signal * 0.82 + wave * 0.18) * (1.0 if self._is_playing else 0.28)
                bar_height = max(4, int(level * (height - 38)))
                x = margin + index * (bar_width + gap)
                color = QColor("#f0f0f0" if index % 5 else "#777777")
                painter.fillRect(x, base - bar_height, bar_width, bar_height, color)

        def _paint_radar(self, painter: QPainter, width: int, height: int, activity: float, progress: float):
            cx = width // 2
            cy = height // 2
            radius = max(24, min(width, height) // 2 - 18)
            painter.setPen(QPen(QColor("#777777")))
            for ring in (1, 2, 3):
                r = int(radius * ring / 3)
                painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
            angle = (self._phase * 0.045) + (progress * math.pi * 2)
            sweep_x = int(cx + math.cos(angle) * radius)
            sweep_y = int(cy + math.sin(angle) * radius)
            sweep_pen = QPen(QColor("#f0f0f0"))
            sweep_pen.setWidth(2)
            painter.setPen(sweep_pen)
            painter.drawLine(cx, cy, sweep_x, sweep_y)
            core = max(4, int(4 + self._energy(0.0, 0.2) * 10))
            painter.fillRect(cx - core // 2, cy - core // 2, core, core, QColor("#f0f0f0"))
            for index in range(8):
                blip_angle = index * 0.77 + progress * 3.0
                distance = radius * (0.22 + ((index * 17) % 63) / 100)
                signal = self._bar_level(index, 8)
                pulse = signal if signal is not None else (math.sin(self._phase * 0.16 + index) + 1.0) / 2.0
                size = max(3, int((3 + pulse * 5) * activity))
                x = int(cx + math.cos(blip_angle) * distance)
                y = int(cy + math.sin(blip_angle) * distance)
                painter.fillRect(x - size // 2, y - size // 2, size, size, QColor("#f0f0f0" if index % 2 else "#777777"))

        def _paint_ring(self, painter: QPainter, width: int, height: int, activity: float, progress: float):
            cx = width // 2
            cy = height // 2
            radius = max(22, min(width, height) // 4)
            painter.setPen(QPen(QColor("#777777")))
            painter.drawEllipse(cx - radius, cy - radius, radius * 2, radius * 2)
            spokes = 48
            for index in range(spokes):
                angle = (math.pi * 2 * index / spokes) + progress * 0.8
                wave = (math.sin(self._phase * 0.1 + index * 0.42) + 1.0) / 2.0
                signal = self._bar_level(index, spokes)
                level = signal if signal is not None else wave
                length = int((8 + level * 34) * activity)
                inner = radius + 8
                outer = inner + max(4, length)
                x1 = int(cx + math.cos(angle) * inner)
                y1 = int(cy + math.sin(angle) * inner)
                x2 = int(cx + math.cos(angle) * outer)
                y2 = int(cy + math.sin(angle) * outer)
                pen = QPen(QColor("#f0f0f0" if index % 4 else "#777777"))
                pen.setWidth(2 if index % 4 else 1)
                painter.setPen(pen)
                painter.drawLine(x1, y1, x2, y2)
            painter.setPen(QPen(QColor("#f0f0f0")))
            painter.drawText(cx - 34, cy + 4, "FREQ RING")

        def _paint_circuit(self, painter: QPainter, width: int, height: int, activity: float, progress: float):
            cols = 7
            rows = 4
            points: list[tuple[int, int]] = []
            for row in range(rows):
                for col in range(cols):
                    x = int((col + 0.5) * width / cols)
                    y = int((row + 0.5) * height / rows)
                    points.append((x, y))
            painter.setPen(QPen(QColor("#777777")))
            for index, (x, y) in enumerate(points):
                if index + 1 < len(points) and (index + 1) % cols:
                    nx, ny = points[index + 1]
                    painter.drawLine(x, y, nx, y)
                    painter.drawLine(nx, y, nx, ny)
                if index + cols < len(points) and index % 2 == 0:
                    nx, ny = points[index + cols]
                    painter.drawLine(x, y, x, ny)
                    painter.drawLine(x, ny, nx, ny)
            for index, (x, y) in enumerate(points):
                signal = self._bar_level(index, len(points))
                pulse = signal if signal is not None else (math.sin(self._phase * 0.12 + index + progress * 4.0) + 1.0) / 2.0
                size = max(3, int((4 + pulse * 7) * activity))
                painter.fillRect(x - size // 2, y - size // 2, size, size, QColor("#f0f0f0" if pulse > 0.6 else "#777777"))

        def _paint_nodes(self, painter: QPainter, width: int, height: int, activity: float, progress: float):
            nodes: list[tuple[int, int, float]] = []
            count = 18
            for index in range(count):
                angle = index * 2.399 + progress * 1.2
                radius = 0.18 + ((index * 37) % 64) / 100
                drift = math.sin(self._phase * 0.028 + index) * 18 * activity
                x = int(width / 2 + math.cos(angle) * width * radius * 0.44 + drift)
                y = int(height / 2 + math.sin(angle * 1.31) * height * radius * 0.34)
                signal = self._bar_level(index, count)
                pulse = signal if signal is not None else (math.sin(self._phase * 0.11 + index) + 1.0) / 2.0
                nodes.append((x, y, pulse))

            painter.setPen(QPen(QColor("#3a3a3a")))
            for i, (x1, y1, _pulse) in enumerate(nodes):
                for j in range(i + 1, min(len(nodes), i + 4)):
                    x2, y2, _ = nodes[j]
                    if abs(x1 - x2) + abs(y1 - y2) < width * 0.45:
                        painter.drawLine(x1, y1, x2, y2)

            for index, (x, y, pulse) in enumerate(nodes):
                size = max(4, int((5 + pulse * 8) * activity))
                painter.fillRect(x - size // 2, y - size // 2, size, size, QColor("#f0f0f0" if index % 3 else "#777777"))
            painter.setPen(QPen(QColor("#aaaaaa")))
            painter.drawText(width - 118, 18, "NODE GRAPH")

        def _paint_burst(self, painter: QPainter, width: int, height: int, activity: float, progress: float):
            cx = width // 2
            cy = height // 2
            rays = 52
            for index in range(rays):
                angle = (math.pi * 2 * index / rays) + self._phase * 0.01
                signal = self._bar_level(index, rays)
                wave = signal if signal is not None else (math.sin(self._phase * 0.09 + index * 0.7 + progress * 8) + 1.0) / 2.0
                inner = 12 + int(wave * 18)
                outer = inner + int((28 + wave * min(width, height) * 0.32) * activity)
                x1 = int(cx + math.cos(angle) * inner)
                y1 = int(cy + math.sin(angle) * inner)
                x2 = int(cx + math.cos(angle) * outer)
                y2 = int(cy + math.sin(angle) * outer)
                pen = QPen(QColor("#f0f0f0" if index % 6 else "#777777"))
                pen.setWidth(2 if wave > 0.68 else 1)
                painter.setPen(pen)
                painter.drawLine(x1, y1, x2, y2)
            painter.setPen(QPen(QColor("#f0f0f0")))
            painter.drawEllipse(cx - 10, cy - 10, 20, 20)
            painter.drawText(cx - 34, cy + 34, "DATA BURST")

        def _paint_scope(self, painter: QPainter, width: int, height: int, activity: float, progress: float):
            pen = QPen(QColor("#f0f0f0"))
            pen.setWidth(2)
            painter.setPen(pen)
            last_x = 0
            last_y = height // 2
            points = 120
            amplitude = max(8, int(height * 0.34 * activity))
            for index in range(points + 1):
                x = int(index * width / points)
                t = index / points
                wave = math.sin(t * math.pi * 8 + self._phase * 0.11)
                carrier = math.sin(t * math.pi * 23 + progress * 12)
                signal = self._bar_level(index, points + 1)
                if signal is None:
                    level = wave * 0.72 + carrier * 0.28
                else:
                    level = (signal - 0.5) * 1.45 + carrier * 0.18
                y = int(height / 2 + level * amplitude)
                if index:
                    painter.drawLine(last_x, last_y, x, y)
                last_x, last_y = x, y
            painter.setPen(QPen(QColor("#aaaaaa")))
            painter.drawText(width - 128, 18, "WAVEFORM SCOPE")

    class Shell(QMainWindow):
        def __init__(self):
            super().__init__()
            self.snapshot = load_app_snapshot()
            self.runtime = load_runtime_snapshot()
            self._snapshot_marker = self._state_marker()
            self._current_page = "Home"
            self._page_history: list[str] = []
            self._page_forward: list[str] = []
            self._search_query = ""
            self._source_query = ""
            self._action_message = self._default_action_message()
            self._action_kind = self._default_action_kind()
            self._action_token = 0
            self._pending_command_id = ""
            self._pending_command_action = ""
            self._visualizer_mode = "spectrum"
            self._defer_page_rebuild = False
            self._state_timer: QTimer | None = None
            self._cover_cache_dir = Path.home() / ".voidplayer_cache" / "art"
            self._cover_manager = QNetworkAccessManager(self)
            self._cover_requests: set[str] = set()
            self._cover_failures: set[str] = set()
            self.setWindowTitle("OTERNOS // Qt Prototype")
            self.resize(1280, 820)
            self.setMinimumSize(1040, 680)
            self._nav_buttons: list[QPushButton] = []
            self._page_title: QLabel | None = None
            self._page_caption: QLabel | None = None
            self._content_stack: QVBoxLayout | None = None
            self._main_scroll: QScrollArea | None = None
            self._action_chip: QLabel | None = None
            self._source_status_labels: dict[str, QLabel] = {}
            self._source_result_cards: list[tuple[QFrame, QLabel, QLabel, QLabel, QLabel, QPushButton]] = []
            self._build()
            self._start_state_timer()

        def _build(self):
            self._nav_buttons = []
            self._content_stack = None
            self._main_scroll = None
            root = QWidget()
            root.setObjectName("root")
            self.setCentralWidget(root)

            layout = QHBoxLayout(root)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            layout.addWidget(self._build_sidebar())
            layout.addWidget(self._build_main(), 1)
            self._set_page(self._current_page)

        def _start_state_timer(self):
            self._state_timer = QTimer(self)
            self._state_timer.setInterval(self._state_timer_interval())
            self._state_timer.timeout.connect(lambda: self._reload_snapshot())
            self._state_timer.start()

        def _build_sidebar(self):
            side = QFrame()
            side.setObjectName("sidebar")
            side.setFixedWidth(232)

            layout = QVBoxLayout(side)
            layout.setContentsMargins(18, 20, 18, 18)
            layout.setSpacing(10)

            brand = QLabel("OTERNOS//VOIDNET")
            brand.setObjectName("brand")
            layout.addWidget(brand)

            cap = QLabel("personal audio intrusion deck")
            cap.setObjectName("caption")
            layout.addWidget(cap)
            build = QLabel("QT SHELL // PHASE 2AB // MONO CYBER")
            build.setObjectName("micro")
            layout.addWidget(build)
            layout.addWidget(self._scanline())
            layout.addSpacing(16)

            for name in (
                "Home",
                "Search",
                "Library",
                "Playlists",
                "Sources",
                "Now Playing",
                "Visualizer",
                "Queue",
                "Settings",
            ):
                btn = QPushButton(f"[ {name.upper()} ]")
                btn.setProperty("pageName", name)
                btn.clicked.connect(lambda _=False, page=name: self._set_page(page))
                self._nav_buttons.append(btn)
                layout.addWidget(btn)

            layout.addStretch(1)

            layout.addWidget(self._sidebar_meter())
            state = self._system_state_text()
            status = self._small_panel("SYSTEM", state)
            layout.addWidget(status)
            return side

        def _build_main(self):
            main = QWidget()
            outer = QVBoxLayout(main)
            outer.setContentsMargins(22, 18, 22, 18)
            outer.setSpacing(16)

            outer.addLayout(self._build_topbar())

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            self._main_scroll = scroll
            scroll_content = QWidget()
            self._content_stack = QVBoxLayout(scroll_content)
            self._content_stack.setContentsMargins(0, 0, 0, 0)
            self._content_stack.setSpacing(16)
            scroll.setWidget(scroll_content)
            outer.addWidget(scroll, 1)

            outer.addWidget(self._build_playerbar())
            return main

        def _build_topbar(self):
            row = QHBoxLayout()
            row.setSpacing(12)

            back = QPushButton("[ RETREAT ]")
            back.setObjectName("uvDragonfly")
            back.setEnabled(bool(self._page_history))
            back.clicked.connect(lambda _=False: self._go_back())
            row.addWidget(back)

            forward = QPushButton("[ ADVANCE ]")
            forward.setObjectName("uvDragonfly")
            forward.setEnabled(bool(self._page_forward))
            forward.clicked.connect(lambda _=False: self._go_forward())
            row.addWidget(forward)

            search = QLineEdit()
            search.setPlaceholderText("scan local vault, SoundCloud, YouTube, Archive")
            search.returnPressed.connect(lambda field=search: self._open_search(field.text()))
            row.addWidget(search, 1)

            row.addWidget(self._chip("CORE//ONLINE", "live"))
            row.addWidget(self._chip(f"VAULT//{self.snapshot.library_count}"))
            row.addWidget(self._chip(self._runtime_link_label(), self._runtime_chip_kind()))
            self._action_chip = self._chip(self._action_message, self._action_kind)
            row.addWidget(self._action_chip)

            refresh = QPushButton("[ RESYNC ]")
            refresh.setObjectName("uvStingray")
            refresh.clicked.connect(lambda _=False: self._reload_snapshot(force=True))
            row.addWidget(refresh)

            profile = QPushButton("IKARI//ROOT")
            profile.setObjectName("uvEmu")
            profile.clicked.connect(
                lambda _=False: self._set_action_message("PROFILE LATER PHASE", "stale")
            )
            row.addWidget(profile)

            return row

        def _set_page(self, page: str, *, record_history: bool = True):
            if page != self._current_page and record_history:
                self._page_history.append(self._current_page)
                self._page_forward.clear()
            self._current_page = page
            self._sync_state_timer_interval()
            for btn in self._nav_buttons:
                btn.setProperty("active", btn.property("pageName") == page)
                btn.style().unpolish(btn)
                btn.style().polish(btn)

            if not self._content_stack:
                return
            while self._content_stack.count():
                item = self._content_stack.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

            header = QWidget()
            h = QVBoxLayout(header)
            h.setContentsMargins(2, 0, 2, 0)
            h.setSpacing(4)

            title = QLabel(page)
            title.setObjectName("title")
            h.addWidget(title)

            caption = QLabel(self._caption_for(page))
            caption.setObjectName("muted")
            h.addWidget(caption)
            self._content_stack.addWidget(header)

            self._content_stack.addWidget(self._page_body(page))
            self._content_stack.addStretch(1)

        def _go_back(self):
            if not self._page_history:
                self._set_action_message("NO BACK TRACE", "stale")
                return
            previous = self._page_history.pop()
            self._page_forward.append(self._current_page)
            self._set_page(previous, record_history=False)

        def _go_forward(self):
            if not self._page_forward:
                self._set_action_message("NO FORWARD TRACE", "stale")
                return
            next_page = self._page_forward.pop()
            self._page_history.append(self._current_page)
            self._set_page(next_page, record_history=False)

        def _reload_snapshot_if_changed(self):
            marker = self._state_marker()
            if marker != self._snapshot_marker:
                self._reload_snapshot(force=True, marker=marker)

        def _reload_snapshot(self, *, force: bool = False, marker=None, rebuild: bool | None = None):
            marker = self._state_marker() if marker is None else marker
            if not force and marker == self._snapshot_marker and not self._defer_page_rebuild:
                return
            should_rebuild = (force or self._current_page not in {"Search", "Sources"}) if rebuild is None else rebuild
            action_was_idle = self._action_is_idle()
            self.snapshot = load_app_snapshot()
            self.runtime = load_runtime_snapshot()
            self._apply_command_ack()
            if action_was_idle and not self._pending_command_id:
                self._action_message = self._default_action_message()
                self._action_kind = self._default_action_kind()
            self._snapshot_marker = marker
            if self._text_input_has_focus():
                self._defer_page_rebuild = True
                self._sync_live_widgets()
                return
            if not should_rebuild:
                self._defer_page_rebuild = False
                self._sync_live_widgets()
                return
            self._defer_page_rebuild = False
            scroll_value = self._main_scroll.verticalScrollBar().value() if self._main_scroll else 0
            self._build()
            QTimer.singleShot(0, lambda value=scroll_value: self._restore_scroll(value))

        def _text_input_has_focus(self):
            widget = QApplication.focusWidget()
            return isinstance(widget, QLineEdit)

        def _sync_live_widgets(self):
            if self._action_chip is not None:
                self._action_chip.setText(self._action_message)
                self._set_chip_kind(self._action_chip, self._action_kind)
            self._sync_source_status_labels()
            self._sync_source_result_cards()
            self._sync_state_timer_interval()

        def _restore_scroll(self, value: int):
            if not self._main_scroll:
                return
            bar = self._main_scroll.verticalScrollBar()
            bar.setValue(max(0, min(value, bar.maximum())))

        def _state_marker(self):
            return (snapshot_file_marker(), runtime_file_marker())

        def _caption_for(self, page: str) -> str:
            captions = {
                "Home": "command surface for local vault audio, live bridge state, and recent signal traces",
                "Search": "packet scan across local files, SoundCloud, YouTube, Archive, and saved sources",
                "Library": "indexed vault tracks, albums, artists, tags, favorites, and offline caches",
                "Playlists": "personal collections, generated runs, midnight loops, and queue captures",
                "Sources": "source uplinks, stream relays, NetStream status, and local storage health",
                "Now Playing": "art feed, telemetry, queue pressure, visual channel, and playback trace",
                "Visualizer": "monochrome signal canvas, runtime trace, and playback motion surface",
                "Queue": "manual up-next stack, active context, source handoff, and repeat logic",
                "Settings": "bridge files, runtime state, source controls, cache, and build diagnostics",
            }
            return captions.get(page, "OTERNOS prototype")

        def _page_body(self, page: str):
            routes = {
                "Home": self._build_home_page,
                "Search": self._build_search_page,
                "Library": self._build_library_page,
                "Playlists": self._build_playlists_page,
                "Sources": self._build_sources_page,
                "Now Playing": self._build_now_playing_page,
                "Visualizer": self._build_visualizer_page,
                "Queue": self._build_queue_page,
                "Settings": self._build_settings_page,
            }
            return routes.get(page, self._build_home_page)()

        def _state_timer_interval(self):
            if self._current_page == "Visualizer" and self.runtime.is_live and self.runtime.is_playing:
                return 250
            return 1000

        def _sync_state_timer_interval(self):
            if self._state_timer:
                self._state_timer.setInterval(self._state_timer_interval())

        def _build_home_page(self):
            return self._build_dashboard("Home")

        def _build_search_page(self):
            wrapper = QWidget()
            grid = QGridLayout(wrapper)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            search_panel, search_layout = self._panel("Packet Search", "local vault and stream relays")
            search = QLineEdit()
            search.setPlaceholderText("scan tracks, artists, albums, streams")
            search.setText(self._search_query)
            search.returnPressed.connect(
                lambda field=search: self._set_action_message(
                    "SEARCH FILTERED" if field.text().strip() else "SEARCH READY",
                    "live",
                )
            )
            search_layout.addWidget(search)
            search_layout.addLayout(self._metric_row("LOCAL", str(self.snapshot.library_count), "RECENT", str(len(self.snapshot.recent_tracks))))
            search_layout.addWidget(self._divider())
            for source in self.snapshot.sources:
                search_layout.addLayout(self._status_line(source.name, source.state, source.healthy))
            search_layout.addStretch(1)

            results_panel, results_layout = self._panel("Trace Matches", "saved tracks filtered inside Qt")
            result_status = QLabel()
            result_status.setObjectName("accent")
            results_layout.addWidget(result_status)
            result_wrap = QWidget()
            result_grid = QGridLayout(result_wrap)
            result_grid.setContentsMargins(0, 0, 0, 0)
            result_grid.setHorizontalSpacing(12)
            result_grid.setVerticalSpacing(12)
            results_layout.addWidget(result_wrap)
            self._update_search_results(result_grid, result_status, self._search_query)
            search.textChanged.connect(
                lambda text, grid=result_grid, status=result_status: self._update_search_results(
                    grid,
                    status,
                    text,
                )
            )

            grid.addWidget(search_panel, 0, 0)
            grid.addWidget(results_panel, 0, 1)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 2)
            return wrapper

        def _build_library_page(self):
            wrapper = QWidget()
            layout = QVBoxLayout(wrapper)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(14)
            layout.addWidget(self._signal_strip())

            panel, body = self._panel("Vault Index", "local collection preview")
            body.addLayout(
                self._metric_row(
                    "TRACKS",
                    str(self.snapshot.library_count),
                    "PLAYLISTS",
                    str(self.snapshot.playlist_count),
                )
            )
            body.addWidget(self._track_grid(self.snapshot.library_preview or self._recent_summaries(), columns=4))
            layout.addWidget(panel)
            return wrapper

        def _build_playlists_page(self):
            panel, layout = self._panel("Playlist Vaults", "saved sets and listening runs")
            layout.addLayout(self._metric_row("TOTAL", str(self.snapshot.playlist_count), "REPEAT", self.snapshot.repeat_mode.upper()))
            layout.addWidget(self._divider())
            playlists = self.snapshot.playlist_previews
            grid = QGridLayout()
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(12)
            if playlists:
                for i, playlist in enumerate(playlists[:12]):
                    grid.addWidget(self._playlist_card(playlist), i // 3, i % 3)
            else:
                grid.addWidget(self._playlist_empty_card(), 0, 0)
            layout.addLayout(grid)
            return panel

        def _build_sources_page(self):
            wrapper = QWidget()
            layout = QVBoxLayout(wrapper)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(14)

            layout.addWidget(self._source_handoff_panel())
            layout.addWidget(self._source_telemetry_panel())
            layout.addWidget(self._source_results_panel())

            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            for i, source in enumerate(self.snapshot.sources):
                grid.addWidget(self._source_card(source), i // 3, i % 3)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(2, 1)
            layout.addLayout(grid)
            layout.addWidget(self._now_panel("Sources"))
            return wrapper

        def _build_now_playing_page(self):
            wrapper = QWidget()
            grid = QGridLayout(wrapper)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            grid.addWidget(self._now_panel("Now Playing"), 0, 0, 1, 2)
            grid.addWidget(self._queue_panel(), 0, 2)
            grid.addWidget(self._shelf_panel(), 1, 0, 1, 3)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(2, 1)
            return wrapper

        def _build_visualizer_page(self):
            wrapper = QWidget()
            grid = QGridLayout(wrapper)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            visual, visual_layout = self._panel("Visualizer Deck", "monochrome runtime signal")
            visual_layout.addLayout(self._visualizer_mode_buttons())
            visual_layout.addWidget(
                self._visualizer_panel(
                    minimum_height=320,
                    title=self._visualizer_mode_title(self._visualizer_mode),
                    mode=self._visualizer_mode,
                )
            )
            visual_layout.addLayout(
                self._metric_row(
                    "LINK",
                    self._runtime_link_label(),
                    "STATUS",
                    self._runtime_status(),
                )
            )
            grid.addWidget(visual, 0, 0, 2, 2)

            modes, modes_layout = self._panel("Legacy Modes", "ported visualizer language")
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="RADAR SWEEP", mode="radar"))
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="FREQUENCY RING", mode="ring"))
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="CIRCUIT LINES", mode="circuit"))
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="NODE GRAPH", mode="nodes"))
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="DATA BURST", mode="burst"))
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="WAVEFORM SCOPE", mode="scope"))
            grid.addWidget(modes, 0, 2, 2, 1)

            track = self._now_summary()
            signal, signal_layout = self._panel("Trace Lock", "current signal metadata")
            signal_layout.addWidget(self._cover_thumb(track, 98, image_size=78))
            signal_layout.addWidget(self._text_line("TRACK", track.title))
            signal_layout.addWidget(self._text_line("ARTIST", track.artist))
            signal_layout.addWidget(self._text_line("SOURCE", track.source.upper()))
            signal_layout.addWidget(self._divider())
            signal_layout.addLayout(self._metric_row("POSITION", self._format_seconds(self.runtime.position), "DURATION", self._format_seconds(self.runtime.duration)))
            signal_layout.addLayout(self._metric_row("VOLUME", f"{self._runtime_volume_percent():02d}%", "QUEUE", str(self.runtime.queue_count if self.runtime.is_live else len(self.snapshot.queue_preview))))
            signal_layout.addStretch(1)
            grid.addWidget(signal, 2, 2)

            grid.addWidget(self._bridge_activity_panel(), 2, 0, 1, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(2, 1)
            return wrapper

        def _build_queue_page(self):
            wrapper = QWidget()
            grid = QGridLayout(wrapper)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            grid.addWidget(self._queue_panel(), 0, 0, 2, 2)
            controls, control_layout = self._panel("Queue Overrides", "live command bridge")
            control_layout.addLayout(self._metric_row("COMMANDS", "READY" if self._commands_enabled() else "OFFLINE", "POSITION", str(self.runtime.queue_position)))
            control_layout.addWidget(self._divider())
            for label, command in (("Previous", "previous"), ("Play / Pause", "toggle_play"), ("Next", "next")):
                btn = QPushButton(label.upper())
                btn.setObjectName("uvPug" if command == "toggle_play" else "uvDragonfly")
                btn.setEnabled(self._commands_enabled())
                btn.clicked.connect(lambda _=False, action=command: self._send_command(action))
                control_layout.addWidget(btn)
            control_layout.addStretch(1)
            grid.addWidget(controls, 0, 2)
            grid.addWidget(self._shelf_panel(), 2, 0, 1, 3)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(2, 1)
            return wrapper

        def _build_settings_page(self):
            wrapper = QWidget()
            grid = QGridLayout(wrapper)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            cards = (
                ("Theme", self.snapshot.active_theme.upper()),
                ("Flow", "ON" if self.snapshot.flow_mode else "OFF"),
                ("Autoplay", "ON" if self.snapshot.autoplay else "OFF"),
                ("Repeat", self.snapshot.repeat_mode.upper()),
                ("Runtime", self._runtime_link_label()),
                ("Saved State", "READY" if self.snapshot.data_file_exists else "MISSING"),
            )
            for i, (label, value) in enumerate(cards):
                grid.addWidget(self._settings_card(label, value), i // 3, i % 3)

            state, state_layout = self._panel("State Files", "read-only bridge files")
            state_layout.addWidget(self._text_line("SAVED", self.snapshot.data_file))
            state_layout.addWidget(self._text_line("RUNTIME", self.runtime.data_file))
            state_layout.addWidget(self._text_line("SYSTEM", self._system_state_text()))
            grid.addWidget(state, 2, 0, 1, 3)

            grid.addWidget(self._bridge_activity_panel(), 3, 0, 1, 3)
            return wrapper

        def _build_dashboard(self, page: str):
            wrapper = QWidget()
            grid = QGridLayout(wrapper)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            grid.addWidget(self._signal_strip(), 0, 0, 1, 3)
            grid.addWidget(self._threat_matrix_panel(), 1, 0, 1, 3)
            grid.addWidget(self._now_panel(page), 2, 0, 2, 2)
            grid.addWidget(self._source_panel(), 2, 2, 1, 1)
            grid.addWidget(self._queue_panel(), 3, 2, 1, 1)

            shelves = self._shelf_panel()
            grid.addWidget(shelves, 4, 0, 1, 3)

            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(2, 1)
            return wrapper

        def _now_panel(self, page: str):
            panel = QFrame()
            panel.setObjectName("terminalPanel")
            layout = QHBoxLayout(panel)
            layout.setContentsMargins(20, 20, 20, 20)
            layout.setSpacing(20)

            track_data = self._now_summary()
            layout.addWidget(self._art_panel(track_data))

            copy = QVBoxLayout()
            copy.setSpacing(8)
            live_status = "LIVE RUNTIME" if self.runtime.is_live else "SAVED SNAPSHOT"
            live = QLabel(f"AUDIO TRACE // {live_status}")
            live.setObjectName("accent")
            copy.addWidget(live)
            track = QLabel(track_data.title)
            track.setObjectName("heroTitle")
            copy.addWidget(track)
            artist = QLabel(f"{track_data.artist} / {track_data.album}")
            artist.setObjectName("muted")
            copy.addWidget(artist)
            desc = QLabel(self._caption_for(page))
            desc.setWordWrap(True)
            desc.setObjectName("muted")
            copy.addWidget(desc)
            copy.addWidget(self._visualizer_panel())
            copy.addWidget(self._playback_telemetry_panel())
            copy.addWidget(self._divider())

            copy.addLayout(self._metric_row("SOURCE", track_data.source.upper(), "LIBRARY", str(self.snapshot.library_count)))
            copy.addLayout(self._metric_row("PLAYLISTS", str(self.snapshot.playlist_count), "REPEAT", self.snapshot.repeat_mode.upper()))
            mode = self._runtime_mode()
            copy.addLayout(self._metric_row("STATUS", self._runtime_status(), "MODE", mode))
            copy.addSpacing(4)

            progress = QSlider(Qt.Horizontal)
            progress.setRange(0, 100)
            progress.setValue(self._runtime_progress_percent())
            progress.setEnabled(self._commands_enabled() and self.runtime.duration > 0)
            progress.sliderReleased.connect(lambda slider=progress: self._seek_to_percent(slider.value()))
            copy.addWidget(progress)
            copy.addLayout(
                self._metric_row(
                    self._format_seconds(self.runtime.position if self.runtime.is_live else 0),
                    "POSITION",
                    self._format_seconds(self.runtime.duration) if self.runtime.is_live else track_data.duration,
                    "DURATION",
                )
            )
            copy.addStretch(1)

            layout.addLayout(copy, 1)
            return panel

        def _art_panel(self, track: TrackSummary):
            art = QFrame()
            art.setObjectName("art")
            art.setFixedSize(214, 214)
            art_layout = QVBoxLayout(art)
            art_layout.setContentsMargins(8, 8, 8, 8)
            art_layout.setAlignment(Qt.AlignCenter)
            art_layout.setSpacing(5)

            pixmap = self._cover_pixmap(track)
            if pixmap is not None:
                cover = QLabel()
                cover.setObjectName("coverImage")
                cover.setPixmap(
                    pixmap.scaled(
                        160,
                        160,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                cover.setAlignment(Qt.AlignCenter)
                art_layout.addWidget(cover, alignment=Qt.AlignCenter)
            else:
                art_text = QLabel(self._source_initials(track.source))
                art_text.setObjectName("heroTitle")
                art_layout.addWidget(art_text, alignment=Qt.AlignCenter)
                art_sub = QLabel(self._remote_cover_state(track.art_url) if track.art_url else "SIGNAL LOCKED")
                art_sub.setObjectName("accent")
                art_layout.addWidget(art_sub, alignment=Qt.AlignCenter)

            art_meta = QLabel(f"{track.source.upper()} // {self._runtime_link_label()}")
            art_meta.setObjectName("micro")
            art_layout.addWidget(art_meta, alignment=Qt.AlignCenter)
            if track.art_path or track.art_url:
                art_hint = QLabel("LOCAL COVER" if track.art_path else self._remote_cover_hint(track.art_url))
                art_hint.setObjectName("artHint")
                art_layout.addWidget(art_hint, alignment=Qt.AlignCenter)
            return art

        def _source_panel(self):
            panel = QFrame()
            panel.setObjectName("panel")
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(10)

            title = QLabel("UPLINK MATRIX")
            title.setObjectName("section")
            layout.addWidget(title)
            layout.addWidget(self._scanline())
            for source in self.snapshot.sources:
                layout.addLayout(self._status_line(source.name, source.state, source.healthy))
            layout.addStretch(1)
            return panel

        def _queue_panel(self):
            panel = QFrame()
            panel.setObjectName("panel")
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(10)

            title = QLabel("QUEUE STACK")
            title.setObjectName("section")
            layout.addWidget(title)

            layout.addLayout(
                self._metric_row(
                    "TOTAL",
                    str(self.runtime.queue_count if self.runtime.is_live else len(self.snapshot.queue_preview)),
                    "MANUAL",
                    str(self.runtime.manual_queue_count if self.runtime.is_live else 0),
                )
            )
            layout.addWidget(self._divider())

            if self.runtime.is_live and self.runtime.queue_preview:
                for item in self.runtime.queue_preview[:6]:
                    layout.addLayout(self._queue_item_line(item))
            elif self.snapshot.queue_preview:
                for track in self.snapshot.queue_preview[:3]:
                    layout.addLayout(self._queue_line(track))
            else:
                empty = QLabel("NO QUEUE PREVIEW")
                empty.setObjectName("micro")
                layout.addWidget(empty)
            layout.addStretch(1)
            return panel

        def _shelf_panel(self):
            panel = QFrame()
            panel.setObjectName("panel")
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)

            title = QLabel("RECENT CAPTURES")
            title.setObjectName("section")
            layout.addWidget(title)
            layout.addWidget(self._scanline())

            cards = QGridLayout()
            cards.setHorizontalSpacing(12)
            cards.setVerticalSpacing(12)
            tracks = self._recent_summaries()
            for i, track in enumerate(tracks):
                cards.addWidget(self._track_card(track), 0, i)
            layout.addLayout(cards)
            return panel

        def _track_card(self, track: TrackSummary):
            card = QFrame()
            card.setObjectName("card")
            card.setMinimumHeight(166)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)

            top = QHBoxLayout()
            top.setSpacing(10)
            top.addWidget(self._cover_thumb(track, 62))

            copy = QVBoxLayout()
            copy.setSpacing(4)
            badge = QLabel(f"SRC::{track.source.upper()}")
            badge.setObjectName("accent")
            copy.addWidget(badge)
            title = QLabel(track.title)
            title.setObjectName("trackTitle")
            title.setWordWrap(True)
            copy.addWidget(title)
            meta = QLabel(track.duration)
            meta.setObjectName("micro")
            copy.addWidget(meta)
            queue_state = self._track_queue_state(track)
            if queue_state:
                state = QLabel(queue_state)
                state.setObjectName("statusGood" if queue_state == "NOW" else "accent")
                copy.addWidget(state)
            actions = QHBoxLayout()
            actions.setSpacing(6)
            play = QPushButton(self._track_play_label(track))
            play.setObjectName("uvPug")
            play.setEnabled(self._can_play_library_track(track))
            play.clicked.connect(lambda _=False, track=track: self._play_library_track(track))
            actions.addWidget(play)
            add = QPushButton(self._track_add_label(track))
            add.setObjectName("uvSloth")
            add.setEnabled(self._can_add_library_track(track))
            add.clicked.connect(lambda _=False, track=track: self._add_library_track_to_queue(track))
            actions.addWidget(add)
            playlist = QPushButton(self._track_playlist_label(track))
            playlist.setObjectName("uvStingray")
            playlist.setEnabled(self._can_add_library_track_to_playlist(track))
            playlist.clicked.connect(lambda _=False, track=track: self._add_library_track_to_playlist(track))
            actions.addWidget(playlist)
            copy.addLayout(actions)
            top.addLayout(copy, 1)
            layout.addLayout(top)
            layout.addWidget(self._mini_meter((14, 30, 20, 42, 24, 34)))
            layout.addStretch(1)
            return card

        def _build_playerbar(self):
            bar = QFrame()
            bar.setObjectName("playerbar")
            bar.setFixedHeight(104)
            layout = QHBoxLayout(bar)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(14)

            track_data = self._now_summary()
            layout.addWidget(self._cover_thumb(track_data, 68, image_size=54))

            info = QVBoxLayout()
            info.setSpacing(4)
            title = QLabel(track_data.title)
            title.setObjectName("trackTitle")
            info.addWidget(title)
            artist = QLabel(f"{track_data.artist.upper()} // {track_data.source.upper()}")
            artist.setObjectName("micro")
            info.addWidget(artist)
            info.addWidget(self._mini_meter((10, 26, 18, 34, 22, 30, 14, 38)))
            layout.addLayout(info)

            controls = QHBoxLayout()
            controls.setSpacing(8)
            commands_enabled = self._commands_enabled()
            play_label = "PAUSE" if self.runtime.is_live and self.runtime.is_playing else "PLAY"
            for label, obj, action in (
                ("PREV", "uvDragonfly", "previous"),
                (play_label, "uvPug", "toggle_play"),
                ("NEXT", "uvDragonfly", "next"),
            ):
                btn = QPushButton(label)
                btn.setObjectName(obj)
                btn.setEnabled(commands_enabled)
                btn.clicked.connect(lambda _=False, command=action: self._send_command(command))
                controls.addWidget(btn)
            layout.addLayout(controls)

            current = QLabel(self._format_seconds(self.runtime.position if self.runtime.is_live else 0))
            current.setObjectName("timecode")
            layout.addWidget(current)

            progress = QSlider(Qt.Horizontal)
            progress.setRange(0, 100)
            progress.setValue(self._runtime_progress_percent())
            progress.setEnabled(commands_enabled and self.runtime.duration > 0)
            progress.sliderReleased.connect(lambda slider=progress: self._seek_to_percent(slider.value()))
            layout.addWidget(progress, 1)

            total = QLabel(self._format_seconds(self.runtime.duration) if self.runtime.is_live else "--:--")
            total.setObjectName("timecode")
            layout.addWidget(total)

            volume_label = QLabel(f"VOL {self._runtime_volume_percent():02d}")
            volume_label.setObjectName("timecode")
            layout.addWidget(volume_label)

            volume = QSlider(Qt.Horizontal)
            volume.setFixedWidth(120)
            volume.setRange(0, 100)
            volume.setValue(self._runtime_volume_percent())
            volume.setEnabled(commands_enabled)
            volume.sliderReleased.connect(lambda slider=volume: self._set_volume_percent(slider.value()))
            layout.addWidget(volume)
            return bar

        def _small_panel(self, label: str, value: str):
            panel = QFrame()
            panel.setObjectName("signalPanel")
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(10, 10, 10, 10)
            title = QLabel(label)
            title.setObjectName("accent")
            layout.addWidget(title)
            text = QLabel(value)
            text.setObjectName("micro")
            text.setWordWrap(True)
            layout.addWidget(text)
            return panel

        def _panel(self, title: str, caption: str = ""):
            panel = QFrame()
            panel.setObjectName("panel")
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(16, 16, 16, 16)
            layout.setSpacing(12)
            heading = QLabel(title)
            heading.setObjectName("section")
            layout.addWidget(heading)
            if caption:
                sub = QLabel(caption)
                sub.setObjectName("muted")
                sub.setWordWrap(True)
                layout.addWidget(sub)
            return panel, layout

        def _track_grid(self, tracks, *, columns: int):
            wrap = QWidget()
            grid = QGridLayout(wrap)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(12)
            items = tuple(tracks or ())
            if not items:
                empty = QLabel("NO TRACKS READY")
                empty.setObjectName("micro")
                grid.addWidget(empty, 0, 0)
                return wrap
            for i, track in enumerate(items):
                grid.addWidget(self._track_card(track), i // columns, i % columns)
            return wrap

        def _open_search(self, query: str):
            self._search_query = str(query or "").strip()
            self._set_page("Search")

        def _update_search_results(self, grid, status: QLabel, query: str):
            self._search_query = str(query or "")
            self._clear_layout(grid)
            results = self._search_tracks(self._search_query)
            if self._search_query.strip():
                status.setText(f"{len(results)} MATCHES")
            else:
                status.setText("RECENT AND LOCAL SIGNALS")
            if not results:
                empty = QLabel("NO SAVED MATCHES")
                empty.setObjectName("micro")
                grid.addWidget(empty, 0, 0)
                return
            for i, track in enumerate(results[:12]):
                grid.addWidget(self._track_card(track), i // 3, i % 3)

        def _search_tracks(self, query: str):
            tracks = self._searchable_tracks()
            needle = str(query or "").strip().casefold()
            if not needle:
                return tracks[:12]
            terms = [term for term in needle.split() if term]
            matches = []
            for track in tracks:
                haystack = " ".join(
                    (
                        track.title,
                        track.artist,
                        track.album,
                        track.source,
                        track.duration,
                        Path(track.path).stem if track.path else "",
                    )
                ).casefold()
                if all(term in haystack for term in terms):
                    matches.append(track)
            return tuple(matches[:24])

        def _searchable_tracks(self):
            tracks = []
            seen = set()
            for group in (self.snapshot.library_preview, self.snapshot.recent_tracks, self.snapshot.queue_preview):
                for track in group:
                    key = (
                        track.path,
                        track.title.casefold(),
                        track.artist.casefold(),
                        track.source.casefold(),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    tracks.append(track)
            return tuple(tracks)

        def _clear_layout(self, layout):
            while layout.count():
                item = layout.takeAt(0)
                child = item.widget()
                if child:
                    child.deleteLater()
                child_layout = item.layout()
                if child_layout:
                    self._clear_layout(child_layout)

        def _playlist_card(self, playlist):
            card = QFrame()
            card.setObjectName("card")
            card.setMinimumHeight(188)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(8)
            tag = QLabel(f"VAULT // {playlist.count} TRACKS")
            tag.setObjectName("accent" if playlist.count else "micro")
            layout.addWidget(tag)
            title = QLabel(playlist.name)
            title.setObjectName("trackTitle")
            title.setWordWrap(True)
            layout.addWidget(title)

            if playlist.tracks:
                for track in playlist.tracks:
                    layout.addLayout(self._queue_line(track))
            else:
                empty = QLabel("NO TRACKS SAVED")
                empty.setObjectName("micro")
                layout.addWidget(empty)

            layout.addWidget(self._mini_meter(self._playlist_meter_heights(playlist.count)))
            actions = QHBoxLayout()
            actions.setSpacing(6)
            play = QPushButton("PLAY")
            play.setObjectName("uvPug")
            play.setEnabled(self._commands_enabled() and playlist.count > 0)
            play.clicked.connect(lambda _=False, name=playlist.name: self._play_playlist(name))
            actions.addWidget(play)
            view = QPushButton("VIEW")
            view.setObjectName("uvStingray")
            view.clicked.connect(
                lambda _=False: self._set_action_message("PLAYLIST VIEW LATER PHASE", "stale")
            )
            actions.addWidget(view)
            layout.addLayout(actions)
            layout.addStretch(1)
            return card

        def _playlist_empty_card(self):
            card = QFrame()
            card.setObjectName("card")
            card.setMinimumHeight(146)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(8)
            tag = QLabel("EMPTY")
            tag.setObjectName("micro")
            layout.addWidget(tag)
            title = QLabel("No saved playlists")
            title.setObjectName("trackTitle")
            title.setWordWrap(True)
            layout.addWidget(title)
            layout.addWidget(self._mini_meter((10, 22, 16, 34, 18, 28)))
            action = QPushButton("CREATE")
            action.setObjectName("uvDragonfly")
            action.clicked.connect(
                lambda _=False: self._set_action_message("CREATE PLAYLIST IN LEGACY", "stale")
            )
            layout.addWidget(action)
            layout.addStretch(1)
            return card

        def _source_card(self, source):
            card = QFrame()
            card.setObjectName("card")
            card.setMinimumHeight(188)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(8)
            title = QLabel(source.name)
            title.setObjectName("section")
            layout.addWidget(title)
            state = QLabel(source.state)
            state.setObjectName("statusGood" if source.healthy else "statusWarn")
            layout.addWidget(state)
            detail = QLabel(getattr(source, "detail", "") or "Legacy source view is available.")
            detail.setObjectName("micro")
            detail.setWordWrap(True)
            layout.addWidget(detail)
            layout.addWidget(self._mini_meter((12, 24, 18, 38, 20, 30) if source.healthy else (8, 12, 10, 16, 12, 14)))
            view_key = self._source_view_key(source)
            action = QPushButton(getattr(source, "action", "") or "OPEN")
            action.setObjectName("uvStingray" if source.healthy else "uvDragonfly")
            action.setEnabled(bool(view_key) and self._commands_enabled())
            action.clicked.connect(lambda _=False, key=view_key: self._open_source_view(key))
            layout.addWidget(action)
            layout.addStretch(1)
            return card

        def _source_handoff_panel(self):
            panel, layout = self._panel("Source Search Handoff", "send a stream query to the legacy player")
            layout.addLayout(
                self._metric_row(
                    "BRIDGE",
                    "READY" if self._commands_enabled() else "OFFLINE",
                    "TARGETS",
                    "SC / YT / IA",
                )
            )
            query = QLineEdit()
            query.setPlaceholderText("type a song, artist, mix, tape, archive title")
            query.setText(self._source_query)
            query.textChanged.connect(lambda text: setattr(self, "_source_query", str(text or "")))
            query.returnPressed.connect(lambda field=query: self._source_search("youtube", field.text()))
            layout.addWidget(query)

            actions = QHBoxLayout()
            actions.setSpacing(8)
            for label, view_key, obj_name in (
                ("SOUNDCLOUD", "soundcloud", "uvStingray"),
                ("YOUTUBE", "youtube", "uvPug"),
                ("ARCHIVE", "archive", "uvSloth"),
            ):
                btn = QPushButton(label)
                btn.setObjectName(obj_name)
                btn.setEnabled(self._commands_enabled())
                btn.clicked.connect(lambda _=False, key=view_key, field=query: self._source_search(key, field.text()))
                actions.addWidget(btn)
            layout.addLayout(actions)
            hint = QLabel("Press Enter for YouTube, or choose a source button.")
            hint.setObjectName("micro")
            layout.addWidget(hint)
            return panel

        def _source_telemetry_panel(self):
            panel, layout = self._panel("Legacy Source Telemetry", "read-only status from the running player")
            self._source_status_labels = {}
            for key in (
                "source",
                "query",
                "results",
                "status",
            ):
                row = QLabel(self._source_status_label_text(key))
                row.setObjectName("micro")
                row.setWordWrap(True)
                self._source_status_labels[key] = row
                layout.addWidget(row)
            return panel

        def _source_results_panel(self):
            panel, layout = self._panel("Source Results", "legacy stream handoff")
            self._source_result_cards = []
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(10)
            for index in range(6):
                card, title, meta, badge, thumb, action = self._source_result_card(index)
                self._source_result_cards.append((card, title, meta, badge, thumb, action))
                grid.addWidget(card, index // 3, index % 3)
            layout.addLayout(grid)
            return panel

        def _source_result_card(self, index: int):
            card = QFrame()
            card.setObjectName("card")
            card.setMinimumHeight(156)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(7)
            top = QHBoxLayout()
            top.setSpacing(10)
            thumb = QLabel("")
            thumb.setObjectName("sourceResultThumb")
            thumb.setFixedSize(54, 54)
            thumb.setAlignment(Qt.AlignCenter)
            top.addWidget(thumb)
            copy = QVBoxLayout()
            copy.setSpacing(5)
            badge = QLabel("")
            badge.setObjectName("accent")
            copy.addWidget(badge)
            title = QLabel("")
            title.setObjectName("trackTitle")
            title.setWordWrap(True)
            copy.addWidget(title)
            top.addLayout(copy, 1)
            layout.addLayout(top)
            meta = QLabel("")
            meta.setObjectName("micro")
            meta.setWordWrap(True)
            layout.addWidget(meta)
            layout.addStretch(1)
            action = QPushButton("")
            action.setObjectName("uvPug")
            action.setEnabled(False)
            action.clicked.connect(lambda _=False, result_index=index: self._play_source_result(result_index))
            layout.addWidget(action)
            card.setVisible(False)
            self._set_source_result_card(card, title, meta, badge, thumb, action, index)
            return card, title, meta, badge, thumb, action

        def _source_view_key(self, source):
            key = str(getattr(source, "view_key", "") or "").strip().lower()
            if key:
                return key
            names = {
                "local": "library",
                "soundcloud": "soundcloud",
                "youtube": "youtube",
                "archive": "archive",
                "netstream": "netstream",
            }
            return names.get(str(getattr(source, "name", "") or "").strip().lower(), "")

        def _open_source_view(self, view_key: str):
            if not view_key:
                self._set_action_message("SOURCE VIEW LATER PHASE", "stale")
                return
            if self._send_command("open_legacy_view", {"view": view_key}):
                self._set_action_message("SOURCE OPEN SENT", "live", clear=False)

        def _source_search(self, view_key: str, query: str):
            query = str(query or "").strip()
            if not query:
                self._open_source_view(view_key)
                return
            self._source_query = query
            if self._send_command("open_legacy_view", {"view": view_key, "query": query, "search": True}):
                self._set_action_message(f"{view_key.upper()} SEARCH SENT", "live", clear=False)

        def _source_result_command_source(self, source: str):
            key = str(source or "").strip().lower()
            aliases = {
                "sc": "soundcloud",
                "sound cloud": "soundcloud",
                "soundcloud": "soundcloud",
                "yt": "youtube",
                "you tube": "youtube",
                "youtube": "youtube",
                "internet archive": "archive",
                "archive": "archive",
            }
            return aliases.get(key, "")

        def _play_source_result(self, index: int):
            if index >= len(self.runtime.source_results):
                self._set_action_message("SOURCE RESULT MISSING", "stale")
                return
            result = self.runtime.source_results[index]
            source = self._source_result_command_source(result.source)
            if not source:
                self._set_action_message("SOURCE RESULT UNSUPPORTED", "stale")
                return
            label = "SOURCE BROWSE SENT" if source == "archive" else "SOURCE PLAY SENT"
            if self._send_command("play_source_result", {"source": source, "index": index}):
                self._set_action_message(label, "live", clear=False)

        def _set_source_result_thumb(self, thumb: QLabel, result, fallback: str):
            thumb.clear()
            if result is not None:
                pixmap = self._cover_pixmap(result)
                if pixmap is not None:
                    thumb.setPixmap(
                        pixmap.scaled(
                            50,
                            50,
                            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                    return
            thumb.setText(self._source_initials(fallback))

        def _source_status_value(self, key: str):
            status = self.runtime.source_status
            if not self.runtime.is_live or status is None:
                defaults = {
                    "source": "OFFLINE",
                    "query": "NO QUERY",
                    "results": "0",
                    "status": "START LEGACY PLAYER",
                }
                return defaults.get(key, "")
            values = {
                "source": (status.source or "none").upper(),
                "query": status.query or "NO QUERY",
                "results": str(status.result_count),
                "status": status.status or "READY",
            }
            return values.get(key, "")

        def _source_status_label_text(self, key: str):
            labels = {
                "source": "ACTIVE",
                "query": "QUERY",
                "results": "RESULTS",
                "status": "STATUS",
            }
            return f"{labels.get(key, key.upper())}  {self._source_status_value(key)}"

        def _sync_source_status_labels(self):
            for key, label in self._source_status_labels.items():
                label.setText(self._source_status_label_text(key))

        def _set_source_result_card(
            self,
            card: QFrame,
            title: QLabel,
            meta: QLabel,
            badge: QLabel,
            thumb: QLabel,
            action: QPushButton,
            index: int,
        ):
            if not self.runtime.is_live:
                card.setVisible(index == 0)
                badge.setText("OFFLINE")
                title.setText("No live source results")
                meta.setText("Start the legacy player and run a source search.")
                self._set_source_result_thumb(thumb, None, "offline")
                action.setText("WAIT")
                action.setObjectName("uvStingray")
                action.setEnabled(False)
                return
            if index >= len(self.runtime.source_results):
                card.setVisible(index == 0)
                badge.setText("EMPTY")
                title.setText("No legacy results yet")
                meta.setText("Send a YouTube, SoundCloud, or Archive search.")
                self._set_source_result_thumb(thumb, None, "source")
                action.setText("SEARCH")
                action.setObjectName("uvSloth")
                action.setEnabled(False)
                return
            result = self.runtime.source_results[index]
            source = self._source_result_command_source(result.source)
            action_label = "BROWSE" if source == "archive" else "PLAY"
            card.setVisible(True)
            badge.setText(f"{result.source.upper()} // {result.duration}")
            title.setText(result.title)
            meta.setText(result.artist)
            self._set_source_result_thumb(thumb, result, result.source)
            action.setText(action_label)
            action.setObjectName("uvStingray" if source == "archive" else "uvPug")
            action.setEnabled(bool(source and self._commands_enabled()))

        def _sync_source_result_cards(self):
            for index, (card, title, meta, badge, thumb, action) in enumerate(self._source_result_cards):
                self._set_source_result_card(card, title, meta, badge, thumb, action, index)

        def _settings_card(self, label: str, value: str):
            card = QFrame()
            card.setObjectName("card")
            card.setMinimumHeight(118)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(8)
            title = QLabel(label.upper())
            title.setObjectName("micro")
            layout.addWidget(title)
            setting = QLabel(value)
            setting.setObjectName("section")
            setting.setWordWrap(True)
            layout.addWidget(setting)
            layout.addStretch(1)
            return card

        def _text_line(self, label: str, value: str):
            text = QLabel(f"{label}  {value}")
            text.setObjectName("micro")
            text.setWordWrap(True)
            return text

        def _chip(self, text: str, kind: str = ""):
            chip = QLabel(text)
            self._set_chip_kind(chip, kind)
            return chip

        def _set_chip_kind(self, chip: QLabel, kind: str = ""):
            names = {
                "live": "chipLive",
                "stale": "chipStale",
                "offline": "chipOffline",
            }
            chip.setObjectName(names.get(kind, "chip"))
            chip.style().unpolish(chip)
            chip.style().polish(chip)

        def _divider(self):
            divider = QFrame()
            divider.setObjectName("divider")
            return divider

        def _scanline(self):
            line = QFrame()
            line.setObjectName("scanline")
            return line

        def _metric_row(self, left_label: str, left_value: str, right_label: str, right_value: str):
            row = QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(self._metric(left_label, left_value))
            row.addWidget(self._metric(right_label, right_value))
            return row

        def _metric(self, label: str, value: str):
            wrap = QWidget()
            layout = QVBoxLayout(wrap)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            l = QLabel(label)
            l.setObjectName("micro")
            layout.addWidget(l)
            v = QLabel(value)
            v.setObjectName("mono")
            layout.addWidget(v)
            return wrap

        def _status_line(self, name: str, state: str, healthy: bool):
            row = QHBoxLayout()
            row.setSpacing(8)
            source = QLabel(name)
            source.setObjectName("mono")
            row.addWidget(source, 1)
            status = QLabel(state)
            status.setObjectName("statusGood" if healthy else "statusWarn")
            row.addWidget(status)
            return row

        def _queue_line(self, track: TrackSummary):
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(self._cover_thumb(track, 34, image_size=26, compact=True))
            title = QLabel(track.title)
            title.setObjectName("mono")
            row.addWidget(title, 1)
            meta = QLabel(f"{track.source.upper()} // {track.duration}")
            meta.setObjectName("micro")
            row.addWidget(meta)
            return row

        def _queue_item_line(self, item):
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(self._cover_thumb(item.track, 34, image_size=26, compact=True))
            marker = QLabel("NOW" if item.is_current else f"{item.position + 1:02d}")
            marker.setObjectName("statusGood" if item.is_current else "micro")
            row.addWidget(marker)
            title = QLabel(item.track.title)
            title.setObjectName("mono")
            row.addWidget(title, 1)
            meta = QLabel(item.track.artist.upper())
            meta.setObjectName("micro")
            row.addWidget(meta)
            play = QPushButton("PLAY")
            play.setObjectName("uvPug")
            play.setEnabled(self._commands_enabled() and not item.is_current)
            play.clicked.connect(
                lambda _=False, position=item.position: self._play_queue_position(position)
            )
            row.addWidget(play)
            drop = QPushButton("DROP")
            drop.setObjectName("uvEmu")
            drop.setEnabled(self._commands_enabled() and not item.is_current)
            drop.clicked.connect(
                lambda _=False, position=item.position: self._remove_queue_position(position)
            )
            row.addWidget(drop)
            return row

        def _playback_telemetry_panel(self):
            panel = QFrame()
            panel.setObjectName("telemetryPanel")
            layout = QHBoxLayout(panel)
            layout.setContentsMargins(12, 10, 12, 10)
            layout.setSpacing(14)

            percent = QLabel(f"{self._runtime_progress_percent():02d}%")
            percent.setObjectName("bigNumber")
            layout.addWidget(percent)

            meter_col = QVBoxLayout()
            meter_col.setSpacing(4)
            meter_col.addWidget(self._mini_meter(self._runtime_meter_heights(18)))
            meter_caption = QLabel("PLAYBACK SIGNAL")
            meter_caption.setObjectName("micro")
            meter_col.addWidget(meter_caption)
            layout.addLayout(meter_col, 1)

            facts = QVBoxLayout()
            facts.setSpacing(3)
            facts.addWidget(self._telemetry_line("LINK", self._runtime_link_label()))
            facts.addWidget(self._telemetry_line("SOURCE", self._runtime_mode()))
            facts.addWidget(self._telemetry_line("VOLUME", f"{self._runtime_volume_percent():02d}%"))
            facts.addWidget(self._telemetry_line("QUEUE", str(self.runtime.queue_count if self.runtime.is_live else len(self.snapshot.queue_preview))))
            layout.addLayout(facts)
            return panel

        def _telemetry_line(self, label: str, value: str):
            text = QLabel(f"{label}  {value}")
            text.setObjectName("micro")
            return text

        def _visualizer_panel(self, *, minimum_height: int = 156, title: str = "MONOCHROME WAVEFORM", mode: str = "spectrum"):
            panel = QFrame()
            panel.setObjectName("cyberPanel")
            panel.setMinimumHeight(minimum_height)
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(8)
            header = QHBoxLayout()
            title_label = QLabel(title)
            title_label.setObjectName("section")
            header.addWidget(title_label)
            header.addStretch(1)
            header.addWidget(self._chip("LIVE" if self.runtime.is_live else "OFFLINE", self._runtime_chip_kind()))
            layout.addLayout(header)
            layout.addWidget(CyberVisualizer(self.runtime, minimum_height=max(120, minimum_height - 58), mode=mode))
            return panel

        def _visualizer_mode_buttons(self):
            row = QHBoxLayout()
            row.setSpacing(8)
            for mode in ("spectrum", "scope", "ring", "radar", "circuit", "nodes", "burst"):
                btn = QPushButton(mode.upper())
                btn.setObjectName("uvSloth" if mode == self._visualizer_mode else "uvDragonfly")
                btn.clicked.connect(lambda _=False, mode=mode: self._set_visualizer_mode(mode))
                row.addWidget(btn)
            row.addStretch(1)
            return row

        def _set_visualizer_mode(self, mode: str):
            self._visualizer_mode = mode
            self._set_page("Visualizer")

        def _visualizer_mode_title(self, mode: str):
            titles = {
                "spectrum": "SPECTRUM SCOPE",
                "scope": "WAVEFORM SCOPE",
                "ring": "FREQUENCY RING",
                "radar": "RADAR SWEEP",
                "circuit": "CIRCUIT LINES",
                "nodes": "NODE GRAPH",
                "burst": "DATA BURST",
            }
            return titles.get(mode, "SPECTRUM SCOPE")

        def _bridge_activity_panel(self):
            panel, layout = self._panel("Command Bridge", "live command status and current Qt action surface")
            layout.addLayout(self._bridge_line("LINK", self._runtime_link_label(), self.runtime.is_live))
            layout.addLayout(self._bridge_line("SYSTEM", self._system_state_text(), self.runtime.is_live))
            layout.addLayout(self._bridge_line("PENDING", self._pending_command_label(), bool(self._pending_command_id)))
            layout.addLayout(self._bridge_line("LAST COMMAND", self._last_command_label(), self._last_command_ok()))
            layout.addWidget(self._divider())
            layout.addLayout(self._bridge_line("LOCAL PLAY", self._capability_state(self.runtime.is_live), self.runtime.is_live))
            layout.addLayout(self._bridge_line("LOCAL ADD", self._capability_state(self.runtime.is_live), self.runtime.is_live))
            layout.addLayout(self._bridge_line("PLAYLIST LIST", self._playlist_capability_state(), self.runtime.is_live and bool(self.snapshot.playlist_names)))
            layout.addLayout(self._bridge_line("QUEUE PLAY/DROP", self._capability_state(self.runtime.is_live), self.runtime.is_live))
            layout.addLayout(self._bridge_line("STREAM PLAYBACK", "LATER PHASE", False))
            return panel

        def _bridge_line(self, label: str, value: str, healthy: bool):
            row = QHBoxLayout()
            row.setSpacing(8)
            name = QLabel(label)
            name.setObjectName("mono")
            row.addWidget(name, 1)
            status = QLabel(value)
            status.setObjectName("statusGood" if healthy else "statusWarn")
            status.setWordWrap(True)
            row.addWidget(status, 2)
            return row

        def _pending_command_label(self):
            if not self._pending_command_id:
                return "NONE"
            return self._pending_command_action.replace("_", " ").upper()

        def _last_command_label(self):
            ack = self.runtime.last_command
            if ack is None:
                return "NONE"
            message = ack.message or self._ack_fallback_message(ack.action, ack.ok)
            age = self._age_label(ack.handled_at)
            action = ack.action.replace("_", " ").upper()
            if age:
                return f"{message} / {action} / {age}"
            return f"{message} / {action}"

        def _last_command_ok(self):
            ack = self.runtime.last_command
            return bool(ack and ack.ok)

        def _age_label(self, timestamp: float):
            if not timestamp:
                return ""
            age = max(0, int(time.time() - timestamp))
            if age < 2:
                return "JUST NOW"
            if age < 60:
                return f"{age}S AGO"
            return f"{age // 60}M AGO"

        def _capability_state(self, enabled: bool):
            return "READY" if enabled else "LEGACY OFFLINE"

        def _playlist_capability_state(self):
            if not self.runtime.is_live:
                return "LEGACY OFFLINE"
            if not self.snapshot.playlist_names:
                return "NO PLAYLISTS"
            return "READY"

        def _signal_strip(self):
            panel = QFrame()
            panel.setObjectName("signalPanel")
            panel.setFixedHeight(104)
            layout = QHBoxLayout(panel)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(16)

            left = QVBoxLayout()
            left.setSpacing(4)
            title = QLabel("VOIDNET SIGNAL BUS")
            title.setObjectName("section")
            left.addWidget(title)
            subtitle = QLabel("VAULT / STREAM RELAYS / QUEUE STACK / AUDIO CORE")
            subtitle.setObjectName("micro")
            left.addWidget(subtitle)
            left.addWidget(self._scanline())
            left.addStretch(1)
            layout.addLayout(left, 1)

            audio_heights = self._runtime_meter_heights(8, phase=0)
            cache_heights = self._runtime_meter_heights(8, phase=3, scale=0.65)
            queue_heights = self._queue_meter_heights(8)
            layout.addWidget(self._meter_block("AUDIO", audio_heights))
            layout.addWidget(self._meter_block("CACHE", cache_heights))
            layout.addWidget(self._meter_block("QUEUE", queue_heights))
            layout.addWidget(self._chip(self._runtime_status()))
            return panel

        def _threat_matrix_panel(self):
            panel = QFrame()
            panel.setObjectName("cyberPanel")
            panel.setFixedHeight(92)
            layout = QHBoxLayout(panel)
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(10)

            header = QVBoxLayout()
            header.setSpacing(4)
            title = QLabel("CYBER ROUTE MAP")
            title.setObjectName("section")
            header.addWidget(title)
            state = QLabel(self._system_state_text())
            state.setObjectName("accent" if self.runtime.is_live else "warningAccent")
            header.addWidget(state)
            header.addStretch(1)
            layout.addLayout(header, 1)

            cells = (
                ("RX", self._runtime_link_label(), self.runtime.is_live),
                ("SRC", self._runtime_mode(), self.runtime.is_live),
                ("Q", str(self.runtime.queue_count if self.runtime.is_live else len(self.snapshot.queue_preview)), bool(self.runtime.queue_count)),
                ("VOL", f"{self._runtime_volume_percent():02d}%", self.runtime.is_live),
                ("ACK", self._last_command_short(), self._last_command_ok()),
            )
            for label, value, good in cells:
                layout.addWidget(self._matrix_cell(label, value, good))
            return panel

        def _matrix_cell(self, label: str, value: str, good: bool):
            cell = QFrame()
            cell.setObjectName("matrixCell")
            cell.setFixedWidth(120)
            layout = QVBoxLayout(cell)
            layout.setContentsMargins(9, 8, 9, 8)
            layout.setSpacing(3)
            top = QLabel(label)
            top.setObjectName("micro")
            layout.addWidget(top)
            bottom = QLabel(value)
            bottom.setObjectName("accent" if good else "warningAccent")
            bottom.setWordWrap(True)
            layout.addWidget(bottom)
            return cell

        def _last_command_short(self):
            ack = self.runtime.last_command
            if ack is None:
                return "NONE"
            return (ack.message or self._ack_fallback_message(ack.action, ack.ok)).split(" ")[0]

        def _sidebar_meter(self):
            panel = QFrame()
            panel.setObjectName("signalPanel")
            panel.setFixedHeight(112)
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(6)
            label = QLabel("VOID LEVEL")
            label.setObjectName("accent")
            layout.addWidget(label)
            layout.addWidget(self._mini_meter((12, 26, 18, 44, 30, 22, 36, 16, 40, 24)))
            state = QLabel(
                f"{self._count_label(self.snapshot.library_count, 'TRACK')} / "
                f"{self._count_label(self.snapshot.playlist_count, 'LIST')}"
            )
            state.setObjectName("micro")
            layout.addWidget(state)
            return panel

        def _meter_block(self, label: str, heights: tuple[int, ...]):
            block = QWidget()
            layout = QVBoxLayout(block)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            title = QLabel(label)
            title.setObjectName("micro")
            layout.addWidget(title, alignment=Qt.AlignCenter)
            layout.addWidget(self._mini_meter(heights))
            return block

        def _mini_meter(self, heights: tuple[int, ...]):
            wrap = QWidget()
            layout = QHBoxLayout(wrap)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(3)
            layout.setAlignment(Qt.AlignBottom)
            for index, height in enumerate(heights):
                bar = QFrame()
                bar.setObjectName("meterBar" if index % 3 else "meterBarDim")
                bar.setFixedSize(5, height)
                layout.addWidget(bar, alignment=Qt.AlignBottom)
            return wrap

        def _now_summary(self):
            if self.runtime.is_live and self.runtime.track is not None:
                track = self.runtime.track
                return TrackSummary(
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                    source=track.source,
                    duration=self._format_seconds(self.runtime.duration),
                    path=track.path,
                    art_path=track.art_path,
                    art_url=track.art_url,
                )
            if self.snapshot.now_track is not None:
                return self.snapshot.now_track
            return TrackSummary(
                title="No Saved Track",
                artist="OTERNOS",
                album="Awaiting Library",
                source="Local Library",
                duration="--:--",
                path="",
                art_path="",
                art_url="",
            )

        def _recent_summaries(self):
            if self.snapshot.recent_tracks:
                return self.snapshot.recent_tracks[:5]
            return (
                TrackSummary(
                    title="Add music in the legacy player",
                    artist="OTERNOS",
                    album="No saved library yet",
                    source="Local Library",
                    duration="--:--",
                    path="",
                    art_path="",
                    art_url="",
                ),
            )

        def _runtime_status(self):
            if not self.runtime.data_file_exists:
                return "LEGACY OFFLINE"
            if not self.runtime.is_live:
                return "LEGACY STALE"
            if self.runtime.is_playing:
                return "PLAYING"
            if self.runtime.is_paused:
                return "PAUSED"
            return self.runtime.status.upper() if self.runtime.status else "IDLE"

        def _runtime_link_label(self):
            if self.runtime.is_live:
                return "LEGACY CONNECTED"
            if self.runtime.data_file_exists:
                return "LEGACY STALE"
            return "LEGACY OFFLINE"

        def _runtime_chip_kind(self):
            if self.runtime.is_live:
                return "live"
            if self.runtime.data_file_exists:
                return "stale"
            return "offline"

        def _commands_enabled(self):
            return bool(self.runtime.is_live)

        def _system_state_text(self):
            if self.snapshot.error:
                return "STATE ERROR"
            if self.runtime.is_live:
                return "LEGACY PLAYER CONNECTED"
            if self.runtime.data_file_exists:
                return "WAITING FOR LEGACY PLAYER"
            return "START LEGACY PLAYER FOR CONTROLS"

        def _runtime_mode(self):
            if self.runtime.is_live:
                return self.runtime.source.upper()
            if self.snapshot.flow_mode:
                return "FLOW"
            if self.snapshot.shuffle:
                return "SHUFFLE"
            return "DIRECT"

        def _runtime_progress_percent(self):
            if not self.runtime.is_live or self.runtime.duration <= 0:
                return 0
            return max(0, min(100, int((self.runtime.position / self.runtime.duration) * 100)))

        def _runtime_meter_heights(self, bars: int, *, phase: int = 0, scale: float = 1.0):
            if bars <= 0:
                return ()
            if not self.runtime.is_live:
                fallback = (12, 20, 14, 26, 16, 22, 10, 18)
                return tuple(max(8, int(fallback[i % len(fallback)] * scale)) for i in range(bars))
            seed = int(self.runtime.position * 10) + len(self._now_summary().title) + phase
            if self.runtime.is_paused:
                scale *= 0.55
            if not self.runtime.is_playing and not self.runtime.is_paused:
                scale *= 0.35
            heights = []
            for i in range(bars):
                raw = 12 + ((seed + i * 7 + (i % 3) * 11) % 48)
                if i % 5 == 0:
                    raw += 10
                heights.append(max(6, min(66, int(raw * scale))))
            return tuple(heights)

        def _queue_meter_heights(self, bars: int):
            count = self.runtime.queue_count if self.runtime.is_live else len(self.snapshot.queue_preview)
            base = max(1, count)
            return tuple(10 + ((base + i * 5) % 46) for i in range(max(0, bars)))

        def _playlist_meter_heights(self, count: int, bars: int = 6):
            base = max(1, int(count or 0))
            return tuple(10 + ((base * 3 + i * 7) % 38) for i in range(max(0, bars)))

        def _runtime_volume_percent(self):
            if not self.runtime.is_live:
                return 80
            return max(0, min(100, int(self.runtime.volume * 100)))

        def _format_seconds(self, value):
            seconds = max(0, int(value or 0))
            return f"{seconds // 60}:{seconds % 60:02d}"

        def _cover_pixmap(self, track):
            art_path = str(getattr(track, "art_path", "") or "")
            art_url = str(getattr(track, "art_url", "") or "")
            for path in (art_path, self._cached_cover_path(art_url)):
                if not path:
                    continue
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    return pixmap
            if art_url:
                self._request_remote_cover(art_url)
            return None

        def _cover_thumb(self, track, size: int, *, image_size: int | None = None, compact: bool = False):
            frame = QFrame()
            frame.setObjectName("queueThumb" if compact else "miniArt")
            frame.setFixedSize(size, size)
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(0, 0, 0, 0)

            pixmap = self._cover_pixmap(track)
            label = QLabel()
            if pixmap is not None:
                label.setObjectName("coverImage")
                target = image_size or max(20, size - 12)
                label.setPixmap(
                    pixmap.scaled(
                        target,
                        target,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            else:
                label.setText(self._source_initials(getattr(track, "source", "")))
                label.setObjectName("micro" if compact else "mono")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label, alignment=Qt.AlignCenter)
            return frame

        def _cached_cover_path(self, url: str):
            if not url:
                return ""
            return str(self._cover_cache_dir / self._cover_filename(url))

        def _cover_filename(self, url: str):
            digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
            suffix = Path(urlparse(url).path).suffix.lower()
            if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
                suffix = ".img"
            return f"{digest}{suffix}"

        def _request_remote_cover(self, url: str):
            if not url or url in self._cover_requests or url in self._cover_failures:
                return
            cache_path = Path(self._cached_cover_path(url))
            if cache_path.exists():
                return
            qurl = QUrl(url)
            if not qurl.isValid() or qurl.scheme() not in {"http", "https"}:
                self._cover_failures.add(url)
                return
            self._cover_requests.add(url)
            request = QNetworkRequest(qurl)
            request.setRawHeader(b"User-Agent", b"OTERNOS-Qt/0.2")
            reply = self._cover_manager.get(request)
            reply.finished.connect(
                lambda reply=reply, url=url, cache_path=cache_path: self._finish_cover_request(
                    reply,
                    url,
                    cache_path,
                )
            )

        def _finish_cover_request(self, reply, url: str, cache_path: Path):
            self._cover_requests.discard(url)
            try:
                error = reply.error()
                try:
                    has_error = int(error) != 0
                except TypeError:
                    has_error = getattr(error, "value", 0) != 0
                if has_error:
                    self._cover_failures.add(url)
                    return
                data = bytes(reply.readAll())
                if not data:
                    self._cover_failures.add(url)
                    return
                pixmap = QPixmap()
                if not pixmap.loadFromData(data):
                    self._cover_failures.add(url)
                    return
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(data)
            finally:
                reply.deleteLater()
            self._reload_snapshot(force=True, rebuild=False)

        def _remote_cover_state(self, url: str):
            if url in self._cover_requests:
                return "COVER LOADING"
            if url in self._cover_failures:
                return "COVER BLOCKED"
            if self._cached_cover_path(url) and Path(self._cached_cover_path(url)).exists():
                return "COVER CACHED"
            return "ART URL READY"

        def _remote_cover_hint(self, url: str):
            if url in self._cover_requests:
                return "REMOTE FETCH"
            if url in self._cover_failures:
                return "REMOTE FAILED"
            if self._cached_cover_path(url) and Path(self._cached_cover_path(url)).exists():
                return "REMOTE CACHED"
            return "REMOTE COVER"

        def _source_initials(self, source: str):
            words = [word for word in str(source or "OTERNOS").replace("/", " ").split() if word]
            if not words:
                return "OT"
            if len(words) == 1:
                return words[0][:2].upper()
            return "".join(word[0] for word in words[:2]).upper()

        def _send_command(self, action: str, payload: dict | None = None):
            if not self._commands_enabled():
                self._set_action_message("COMMAND OFFLINE", "offline")
                return False
            try:
                command = write_runtime_command(action, payload or {})
            except Exception:
                self._set_action_message("COMMAND FAILED", "offline")
                return False
            self._pending_command_id = command.command_id
            self._pending_command_action = command.action
            self._set_action_message("COMMAND SENT", "live", clear=False)
            self.runtime = load_runtime_snapshot()
            self._schedule_command_refresh()
            return True

        def _schedule_command_refresh(self):
            for delay_ms in (350, 900, 1500):
                QTimer.singleShot(delay_ms, lambda: self._reload_snapshot(force=True, rebuild=False))

        def _apply_command_ack(self):
            ack = self.runtime.last_command
            if not self._pending_command_id or ack is None:
                return
            if ack.command_id != self._pending_command_id:
                return
            message = ack.message or self._ack_fallback_message(ack.action, ack.ok)
            self._set_action_message(message, "live" if ack.ok else "offline")
            self._pending_command_id = ""
            self._pending_command_action = ""

        def _ack_fallback_message(self, action: str, ok: bool):
            if not ok:
                return "COMMAND REFUSED"
            labels = {
                "add_library_path_to_playlist": "PLAYLIST SAVED",
                "add_library_path_to_queue": "ADD HANDLED",
                "open_legacy_view": "SOURCE VIEW OPENED",
                "play_library_path": "PLAY HANDLED",
                "play_playlist": "PLAYLIST PLAY HANDLED",
                "play_queue_position": "QUEUE PLAY HANDLED",
                "play_source_result": "SOURCE RESULT HANDLED",
                "remove_queue_position": "DROP HANDLED",
                "seek_relative": "SEEK HANDLED",
                "set_volume": "VOLUME HANDLED",
                "toggle_play": "TOGGLE HANDLED",
                "next": "NEXT HANDLED",
                "previous": "PREV HANDLED",
            }
            return labels.get(action, "COMMAND HANDLED")

        def _set_action_message(self, message: str, kind: str = "live", *, clear: bool = True):
            self._action_message = message
            self._action_kind = kind
            if self._action_chip is not None:
                self._action_chip.setText(message)
                self._set_chip_kind(self._action_chip, kind)
            if clear:
                self._action_token += 1
                token = self._action_token
                QTimer.singleShot(2400, lambda token=token: self._clear_action_message(token))

        def _clear_action_message(self, token: int):
            if token != self._action_token:
                return
            self._action_message = self._default_action_message()
            self._action_kind = self._default_action_kind()
            if self._action_chip is not None:
                self._action_chip.setText(self._action_message)
                self._set_chip_kind(self._action_chip, self._action_kind)

        def _default_action_message(self):
            if self.runtime.is_live:
                return "CONTROLS READY"
            if self.runtime.data_file_exists:
                return "WAITING FOR PLAYER"
            return "START LEGACY PLAYER"

        def _default_action_kind(self):
            return self._runtime_chip_kind()

        def _action_is_idle(self):
            return self._action_message in {
                "READY",
                "CONTROLS READY",
                "WAITING FOR PLAYER",
                "START LEGACY PLAYER",
            }

        def _seek_to_percent(self, percent: int):
            if not self.runtime.is_live:
                self._set_action_message("SEEK OFFLINE", "offline")
                return
            if self.runtime.duration <= 0:
                self._set_action_message("NO DURATION", "stale")
                return
            target = (max(0, min(100, int(percent))) / 100.0) * self.runtime.duration
            delta = target - self.runtime.position
            self._send_command("seek_relative", {"seconds": delta})

        def _set_volume_percent(self, percent: int):
            volume = max(0.0, min(1.0, int(percent) / 100.0))
            self._send_command("set_volume", {"volume": volume})

        def _play_queue_position(self, position: int):
            if self._send_command("play_queue_position", {"position": int(position)}):
                self._set_action_message("QUEUE PLAY SENT", "live")

        def _play_playlist(self, name: str):
            if self._send_command("play_playlist", {"playlist": str(name)}):
                self._set_action_message("PLAYLIST PLAY SENT", "live")

        def _remove_queue_position(self, position: int):
            if self._send_command("remove_queue_position", {"position": int(position)}):
                self._set_action_message("DROP SENT", "stale")

        def _play_library_track(self, track: TrackSummary):
            if not self._can_play_library_track(track):
                return
            if self._send_command("play_library_path", {"path": track.path}):
                self._set_action_message("PLAY SENT", "live")

        def _add_library_track_to_queue(self, track: TrackSummary):
            if not self._can_add_library_track(track):
                return
            if self._send_command("add_library_path_to_queue", {"path": track.path}):
                self._set_action_message("ADD SENT", "live")

        def _add_library_track_to_playlist(self, track: TrackSummary):
            if not self._can_add_library_track_to_playlist(track):
                if not self.snapshot.playlist_names:
                    self._set_action_message("NO PLAYLISTS", "stale")
                return
            playlist = self._choose_playlist_name()
            if not playlist:
                return
            if self._send_command(
                "add_library_path_to_playlist",
                {"path": track.path, "playlist": playlist},
            ):
                self._set_action_message("LIST SENT", "live")

        def _can_play_library_track(self, track: TrackSummary):
            if not self._commands_enabled() or not track.path:
                return False
            lowered = track.path.lower()
            return not lowered.startswith(("http://", "https://"))

        def _can_add_library_track(self, track: TrackSummary):
            return self._can_play_library_track(track) and not self._track_queue_state(track)

        def _can_add_library_track_to_playlist(self, track: TrackSummary):
            return self._can_play_library_track(track) and bool(self.snapshot.playlist_names)

        def _track_play_label(self, track: TrackSummary):
            if not self._commands_enabled():
                return "LIVE OFF"
            if not track.path:
                return "NO PATH"
            if track.path.lower().startswith(("http://", "https://")):
                return "STREAM"
            return "PLAY"

        def _track_add_label(self, track: TrackSummary):
            state = self._track_queue_state(track)
            return state if state else "ADD"

        def _track_playlist_label(self, track: TrackSummary):
            if not self.snapshot.playlist_names:
                return "NO LIST"
            if not self._can_play_library_track(track):
                return "LIST"
            return "LIST"

        def _choose_playlist_name(self):
            names = tuple(name for name in self.snapshot.playlist_names if name)
            if not names:
                return ""
            if len(names) == 1:
                return names[0]

            dialog = QDialog(self)
            dialog.setWindowTitle("Add to Playlist")
            dialog.setModal(True)
            dialog.setMinimumWidth(320)
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(10)

            title = QLabel("Save Track To")
            title.setObjectName("section")
            layout.addWidget(title)
            hint = QLabel("Choose a saved playlist.")
            hint.setObjectName("micro")
            layout.addWidget(hint)

            playlist_list = QListWidget()
            for name in names:
                playlist_list.addItem(name)
            playlist_list.setCurrentRow(0)
            playlist_list.itemDoubleClicked.connect(lambda _item: dialog.accept())
            layout.addWidget(playlist_list)

            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() != QDialog.Accepted:
                return ""
            current = playlist_list.currentItem()
            if current is None:
                return ""
            return current.text()

        def _track_queue_state(self, track: TrackSummary):
            if not self.runtime.is_live or not track.path:
                return ""
            path = self._path_key(track.path)
            current = self.runtime.track
            if current is not None and self._path_key(current.path) == path:
                return "NOW"
            queued = {self._path_key(item) for item in self.runtime.queue_paths}
            if path in queued:
                return "QUEUED"
            return ""

        def _path_key(self, value: str):
            return str(value or "").replace("\\", "/").casefold()

        def _count_label(self, count: int, word: str):
            suffix = "" if count == 1 else "S"
            return f"{count} {word}{suffix}"

    win = Shell()
    win.show()
    return app.exec()

