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

CONTRIBUTOR_ENTRIES = (
    {
        "source": "React Bits",
        "creator": "David Haz",
        "component": "Faulty Terminal",
        "link": "https://www.reactbits.dev/backgrounds/faulty-terminal",
        "usage": "background motion surface reference",
    },
    {
        "source": "React Bits",
        "creator": "David Haz",
        "component": "Click Spark",
        "link": "https://www.reactbits.dev/animations/click-spark",
        "usage": "click feedback interaction reference",
    },
    {
        "source": "React Bits",
        "creator": "David Haz",
        "component": "Elastic Slider",
        "link": "https://www.reactbits.dev/components/elastic-slider",
        "usage": "volume control interaction reference",
    },
    {
        "source": "React Bits",
        "creator": "David Haz",
        "component": "Text Type",
        "link": "https://www.reactbits.dev/text-animations/text-type",
        "usage": "animated typing placeholder reference",
    },
    {
        "source": "React Bits",
        "creator": "David Haz",
        "component": "Target Cursor",
        "link": "https://www.reactbits.dev/animations/target-cursor",
        "usage": "toggleable cursor-lock mode reference",
    },
    {
        "source": "React Bits",
        "creator": "David Haz",
        "component": "Blur Text",
        "link": "https://www.reactbits.dev/text-animations/blur-text",
        "usage": "typed-letter blur resolve feedback reference",
    },
    {
        "source": "React Bits",
        "creator": "David Haz",
        "component": "Scroll Reveal",
        "link": "https://www.reactbits.dev/text-animations/scroll-reveal",
        "usage": "scroll-position text reveal reference",
    },
    {
        "source": "Magic UI",
        "creator": "Build UI / Ritesh Bucha",
        "component": "Dock",
        "link": "https://magicui.design/docs/components/dock",
        "usage": "sidebar dock navigation reference",
    },
    {
        "source": "Cult UI",
        "creator": "Cult UI",
        "component": "Family Button",
        "link": "https://www.cult-ui.com/docs/components/family-button",
        "usage": "expandable source handoff button reference",
    },
    {
        "source": "UIVerse",
        "creator": "OnCloud125252",
        "component": "angry-dragonfly-77",
        "link": "https://uiverse.io/OnCloud125252/angry-dragonfly-77",
        "usage": "button silhouette reference",
    },
    {
        "source": "UIVerse",
        "creator": "tirth_5172",
        "component": "yellow-pug-84",
        "link": "https://uiverse.io/tirth_5172/yellow-pug-84",
        "usage": "primary button silhouette reference",
    },
    {
        "source": "UIVerse",
        "creator": "zjssun",
        "component": "tidy-sloth-40",
        "link": "https://uiverse.io/zjssun/tidy-sloth-40",
        "usage": "button silhouette reference",
    },
    {
        "source": "UIVerse",
        "creator": "xopc333",
        "component": "modern-stingray-68",
        "link": "https://uiverse.io/xopc333/modern-stingray-68",
        "usage": "button silhouette reference",
    },
    {
        "source": "UIVerse",
        "creator": "Galahhad",
        "component": "ancient-emu-61",
        "link": "https://uiverse.io/Galahhad/ancient-emu-61",
        "usage": "button silhouette reference",
    },
)


STYLE = """
* {
    font-family: "Segoe UI", "Inter", Arial, sans-serif;
    letter-spacing: 0;
}
QMainWindow {
    background: #000000;
    color: #f0f0f0;
}
QWidget {
    background: #000000;
    color: #f0f0f0;
}
QWidget#root,
QWidget#main,
QWidget#scrollContent,
QWidget#pageWrap,
QWidget#headerWrap {
    background: transparent;
}
QWidget#clickSparkOverlay {
    background: transparent;
}
QSlider#elasticSlider {
    background: transparent;
}
QLabel {
    background: transparent;
}
QScrollArea, QScrollArea::viewport {
    background: transparent;
}
QFrame#sidebar {
    background: #050505;
    border-right: 1px solid #222222;
}
QFrame#dockNavRail {
    background: #000000;
    border: 1px solid #222222;
    border-radius: 8px;
}
QPushButton#dockNavButton {
    background: transparent;
    border: none;
    padding: 0;
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
    background: #141414;
    color: #ffffff;
    border-color: #ffffff;
    border-left-color: #ffffff;
}
QPushButton#uvDragonfly:pressed {
    background: #000000;
    color: #ffffff;
    border-color: #ffffff;
}
QPushButton#uvPug {
    background: #050505;
    color: #f0f0f0;
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
    background: #181818;
    color: #ffffff;
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
    background: #000000;
    color: #ffffff;
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
    background: #000000;
    color: #ffffff;
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
    background: #141414;
    color: #ffffff;
    border-color: #ffffff;
    border-right-color: #ffffff;
}
QPushButton#uvEmu:pressed {
    background: #141414;
    color: #ffffff;
}
QPushButton#primaryControl {
    background: #050505;
    color: #f0f0f0;
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
    background: #050505;
    color: #f0f0f0;
    border: 1px solid #ffffff;
    border-radius: 3px;
    padding: 9px 12px;
    text-align: center;
    min-width: 56px;
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-weight: 900;
}
QPushButton#uvPlay:hover {
    background: #141414;
    color: #ffffff;
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
    background: #000000;
    color: #ffffff;
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
    background: #050505;
    border: none;
    min-height: 18px;
    max-height: 18px;
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
        from PySide6.QtCore import QEasingCurve, QEvent, QObject, QRectF, QUrl, Qt, QTimer, QVariantAnimation, Signal
        from PySide6.QtGui import QColor, QCursor, QDesktopServices, QPainter, QPainterPath, QPen, QPixmap
        from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest
        from PySide6.QtWidgets import (
            QApplication,
            QDialog,
            QDialogButtonBox,
            QFrame,
            QGridLayout,
            QGraphicsBlurEffect,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QMainWindow,
            QPushButton,
            QScrollArea,
            QSizePolicy,
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

    class ClickSparkOverlay(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("clickSparkOverlay")
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAutoFillBackground(False)
            self.setStyleSheet("background: transparent; border: none;")
            self._sparks: list[dict] = []
            self._timer = QTimer(self)
            self._timer.setInterval(16)
            self._timer.timeout.connect(self._tick)
            self.hide()

        def spark(self, x: int, y: int):
            now = time.monotonic()
            self._sparks.append(
                {
                    "x": float(x),
                    "y": float(y),
                    "start": now,
                    "duration": 0.46,
                    "count": 10,
                    "radius": 15.0,
                    "size": 3.0,
                }
            )
            self.show()
            self.raise_()
            if not self._timer.isActive():
                self._timer.start()
            self.update()

        def _tick(self):
            now = time.monotonic()
            self._sparks = [
                spark for spark in self._sparks if now - spark["start"] <= spark["duration"]
            ]
            if not self._sparks:
                self._timer.stop()
                self.hide()
            self.update()

        def paintEvent(self, _event):
            if not self._sparks:
                return
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            now = time.monotonic()
            for spark in self._sparks:
                raw_t = max(0.0, min(1.0, (now - spark["start"]) / spark["duration"]))
                t = 1.0 - (1.0 - raw_t) * (1.0 - raw_t)
                alpha = int(220 * (1.0 - raw_t))
                if alpha <= 0:
                    continue
                pen = QPen(QColor(240, 240, 240, alpha))
                pen.setWidth(max(1, int(2 - raw_t)))
                painter.setPen(pen)
                count = int(spark["count"])
                radius = float(spark["radius"])
                size = float(spark["size"])
                for index in range(count):
                    angle = (math.pi * 2.0 * index / count) + 0.16
                    inner = radius * 0.25 * t
                    outer = radius * (0.45 + 0.75 * t)
                    x1 = int(spark["x"] + math.cos(angle) * inner)
                    y1 = int(spark["y"] + math.sin(angle) * inner)
                    x2 = int(spark["x"] + math.cos(angle) * (outer + size * (1.0 - raw_t)))
                    y2 = int(spark["y"] + math.sin(angle) * (outer + size * (1.0 - raw_t)))
                    painter.drawLine(x1, y1, x2, y2)

    class BlurTextOverlay(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("blurTextOverlay")
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAutoFillBackground(False)
            self.setStyleSheet("background: transparent; border: none;")
            self._items: list[dict] = []
            self._timer = QTimer(self)
            self._timer.setInterval(16)
            self._timer.timeout.connect(self._tick)
            self.hide()

        def burst(self, field: QLineEdit, text: str):
            text = (text or "").strip("\r\n")
            if not text:
                return
            cursor_rect = field.cursorRect()
            text = text[-4:]
            text_width = max(8, field.fontMetrics().horizontalAdvance(text))
            point = field.mapTo(self.parentWidget(), cursor_rect.topLeft())
            font = field.font()
            self._items.append(
                {
                    "text": text,
                    "x": float(point.x()),
                    "y": float(point.y() + cursor_rect.height() - 3),
                    "mask_x": float(point.x() - text_width - 1),
                    "mask_y": float(point.y() + 2),
                    "mask_w": float(text_width + 4),
                    "mask_h": float(cursor_rect.height() - 3),
                    "start": time.monotonic(),
                    "duration": 0.42,
                    "font": font,
                }
            )
            self.show()
            self.raise_()
            if not self._timer.isActive():
                self._timer.start()
            self.update()

        def _tick(self):
            now = time.monotonic()
            self._items = [
                item for item in self._items if now - item["start"] <= item["duration"]
            ]
            if not self._items:
                self._timer.stop()
                self.hide()
            self.update()

        def paintEvent(self, _event):
            if not self._items:
                return
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            now = time.monotonic()
            for item in self._items:
                raw_t = max(0.0, min(1.0, (now - item["start"]) / item["duration"]))
                settle = 1.0 - (1.0 - raw_t) * (1.0 - raw_t)
                fade = 1.0 - max(0.0, (raw_t - 0.58) / 0.42)
                alpha = int(220 * fade)
                if alpha <= 0:
                    continue
                x = float(item["x"])
                y = float(item["y"]) - (1.0 - settle) * 13.0
                blur = (1.0 - settle) * 7.0
                mask_alpha = int(245 * max(0.0, 1.0 - raw_t / 0.64))
                if mask_alpha > 0:
                    painter.fillRect(
                        QRectF(item["mask_x"], item["mask_y"], item["mask_w"], item["mask_h"]),
                        QColor(5, 5, 5, mask_alpha),
                    )
                painter.setFont(item["font"])
                for dx, dy, weight in (
                    (-blur, 0.0, 0.18),
                    (blur, 0.0, 0.18),
                    (0.0, -blur, 0.14),
                    (0.0, blur, 0.14),
                    (-blur * 0.6, -blur * 0.6, 0.12),
                    (blur * 0.6, blur * 0.6, 0.12),
                ):
                    painter.setPen(QPen(QColor(240, 240, 240, int(alpha * weight))))
                    painter.drawText(int(x + dx), int(y + dy), item["text"])
                painter.setPen(QPen(QColor(240, 240, 240, int(alpha * (0.55 + settle * 0.45)))))
                painter.drawText(int(x), int(y), item["text"])

    class FaultyTerminalSurface(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("root")
            self._phase = 0
            self._mouse_x = 0.5
            self._mouse_y = 0.5
            self._white_colors = tuple(QColor(240, 240, 240, alpha) for alpha in range(256))
            self._black_colors = tuple(QColor(0, 0, 0, alpha) for alpha in range(256))
            self._frame_current: QPixmap | None = None
            self._frame_previous: QPixmap | None = None
            self._frame_cache_size: tuple[int, int] = (0, 0)
            self._frame_started_at = 0.0
            self._frame_interval = 0.11
            self._frame_fade = 0.16
            self._render_scale = 0.46
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self.setAutoFillBackground(False)
            self.setMouseTracking(True)
            self._timer = QTimer(self)
            self._timer.setInterval(33)
            self._timer.timeout.connect(self._advance)
            self._timer.start()

        def _advance(self):
            self.update()

        def mouseMoveEvent(self, event):
            pos = event.position() if hasattr(event, "position") else event.pos()
            width = max(1, self.width())
            height = max(1, self.height())
            self._mouse_x = max(0.0, min(1.0, pos.x() / width))
            self._mouse_y = max(0.0, min(1.0, pos.y() / height))
            super().mouseMoveEvent(event)

        def paintEvent(self, _event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            rect = self.rect()
            width = max(1, rect.width())
            height = max(1, rect.height())
            current, previous, fade = self._render_cached_frame(width, height)
            painter.drawPixmap(rect, current, current.rect())
            if previous is not None and fade < 1.0:
                painter.setOpacity(1.0 - fade)
                painter.drawPixmap(rect, previous, previous.rect())
                painter.setOpacity(1.0)

        def _render_cached_frame(self, width: int, height: int):
            cache_width = max(240, int(width * self._render_scale))
            cache_height = max(160, int(height * self._render_scale))
            cache_size = (cache_width, cache_height)
            now = time.monotonic()
            needs_first_frame = self._frame_current is None
            needs_resize = self._frame_cache_size != cache_size
            needs_next_frame = now - self._frame_started_at >= self._frame_interval
            if needs_first_frame or needs_resize or needs_next_frame:
                if needs_resize:
                    self._frame_previous = None
                else:
                    self._frame_previous = self._frame_current
                self._phase = (self._phase + 2) % 10000
                self._frame_current = self._build_terminal_frame(cache_width, cache_height)
                self._frame_cache_size = cache_size
                self._frame_started_at = now
            fade = min(1.0, max(0.0, (now - self._frame_started_at) / self._frame_fade))
            return self._frame_current, self._frame_previous, fade

        def _build_terminal_frame(self, cache_width: int, cache_height: int):
            frame = QPixmap(cache_width, cache_height)
            frame.fill(QColor("#000000"))
            frame_painter = QPainter(frame)
            frame_painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            phase = self._phase
            self._paint_digit_field(frame_painter, cache_width, cache_height, phase)
            self._paint_displacement_bands(frame_painter, cache_width, cache_height, phase)
            self._paint_shader_scanlines(frame_painter, cache_width, cache_height, phase)
            self._paint_dither(frame_painter, cache_width, cache_height, phase)
            self._paint_vignette(frame_painter, cache_width, cache_height)
            frame_painter.end()
            return frame

        def _paint_digit_field(self, painter: QPainter, width: int, height: int, phase: int):
            cell = 26
            dot = 3
            gap = 1
            cols = width // cell + 4
            rows = height // cell + 4
            time_value = phase * 0.021
            load_rows = min(rows, int((phase / 32.0) * rows) + 1)

            for row in range(-1, rows):
                if row > load_rows:
                    continue
                y = row * cell - int((phase * 0.19) % cell)
                if y < -cell or y > height + cell:
                    continue
                scan = 0.82 + 0.18 * math.sin((y / max(1, height)) * math.pi * 34 + time_value * 20)
                for col in range(-1, cols):
                    x = col * cell
                    if x < -cell or x > width + cell:
                        continue
                    warped_x, warped_y = self._barrel_point(x, y, width, height)
                    intensity = self._cell_intensity(col, row, time_value)
                    mouse = self._mouse_influence(col, row, cols, rows, time_value)
                    intensity = max(0.0, min(1.0, intensity + mouse))
                    flicker = 0.74 + 0.26 * self._hash(col * 13.7 + phase * 0.41, row * 9.1)
                    intensity *= scan * flicker
                    if intensity < 0.16:
                        continue
                    self._paint_digit_cell(painter, int(warped_x), int(warped_y), cell, dot, gap, intensity, col, row, phase)

        def _paint_digit_cell(
            self,
            painter: QPainter,
            x: int,
            y: int,
            cell: int,
            dot: int,
            gap: int,
            intensity: float,
            col: int,
            row: int,
            phase: int,
        ):
            matrix = 5
            block = dot + gap
            start_x = x + 2
            start_y = y + 2
            threshold = 1.16 - intensity * 1.5
            for py in range(matrix):
                for px in range(matrix):
                    dx = px - 2
                    dy = py - 2
                    radial = (dx * dx + dy * dy) * 0.0625
                    noise = self._hash(col * 31.0 + px * 7.0 + phase * 0.13, row * 29.0 + py * 11.0)
                    value = intensity - radial + noise * 0.26
                    if value <= threshold:
                        continue
                    shade = 0.35 + (1.0 - py / 4.0) * 0.45 + (px / 4.0) * 0.2
                    alpha = max(0, min(98, int(104 * value * shade)))
                    if alpha <= 4:
                        continue
                    painter.fillRect(start_x + px * block, start_y + py * block, dot, dot, self._white_colors[alpha])
            if intensity > 0.74:
                alpha = int(28 * min(1.0, intensity))
                painter.fillRect(x, y, cell - 2, 1, self._white_colors[alpha])
                painter.fillRect(x, y + cell - 3, cell - 2, 1, self._white_colors[alpha // 2])

        def _paint_displacement_bands(self, painter: QPainter, width: int, height: int, phase: int):
            time_value = phase * 0.033
            for band in range(4):
                y_norm = (phase * 0.006 * (band + 1) + band * 0.173) % 1.0
                window = 1.0 / (1.0 + 48.0 * (y_norm - 0.5) * (y_norm - 0.5))
                y = int(y_norm * height)
                displacement = int(math.sin(y_norm * 20.0 + time_value) * 24 * window)
                alpha = 10 + int(22 * window)
                painter.fillRect(max(0, displacement), y, width, 1, self._white_colors[alpha])
                if band % 2 == phase % 2:
                    band_h = 3 + ((phase + band) % 5)
                    block_w = max(120, width // (3 + band % 3))
                    x = int((self._hash(phase * 0.17, band * 19.0) * max(1, width - block_w)))
                    painter.fillRect(x + displacement, y + 3, block_w, band_h, self._white_colors[alpha // 2])
                    painter.fillRect(max(0, x + displacement - 34), y + band_h + 5, min(width, block_w + 68), 1, self._black_colors[165])

        def _paint_shader_scanlines(self, painter: QPainter, width: int, height: int, phase: int):
            drift = int((phase * 0.5) % 5)
            for y in range(-5 + drift, height, 4):
                if y >= 0:
                    painter.fillRect(0, y, width, 1, self._white_colors[9])
            bar_y = int(((phase * 0.012) % 1.0) * height)
            painter.fillRect(0, bar_y, width, max(1, height // 180), self._white_colors[22])

        def _paint_dither(self, painter: QPainter, width: int, height: int, phase: int):
            spacing = 22
            for y in range((phase % spacing), height, spacing):
                for x in range((phase * 3) % spacing, width, spacing * 3):
                    alpha = int(4 + self._hash(x * 0.7 + phase, y * 1.3) * 10)
                    painter.fillRect(x, y, 1, 1, self._white_colors[alpha])

        def _paint_vignette(self, painter: QPainter, width: int, height: int):
            edge = max(24, min(width, height) // 12)
            painter.fillRect(0, 0, width, edge, self._black_colors[86])
            painter.fillRect(0, height - edge, width, edge, self._black_colors[96])
            painter.fillRect(0, 0, edge, height, self._black_colors[76])
            painter.fillRect(width - edge, 0, edge, height, self._black_colors[76])

        def _cell_intensity(self, col: int, row: int, time_value: float):
            x = col * 0.09
            y = row * 0.14
            wave = math.sin(x * 10.0 + time_value * 0.7) * math.sin(y * (3.0 + math.sin(time_value * 0.09)))
            fbm = 0.0
            amp = 0.52
            px = x + math.sin(time_value * 0.08)
            py = y + math.cos(time_value * 0.05)
            for octave in range(2):
                fbm += amp * (
                    math.sin(px * (2.7 + octave) + time_value * (0.7 + octave * 0.33))
                    * math.sin(py * (3.9 + octave) - time_value * (0.5 + octave * 0.21))
                )
                px, py = py * 1.7 + 0.13, px * 1.9 - 0.07
                amp *= 0.46
            hashed = self._hash(col * 1.77 + math.floor(time_value * 2.0), row * 1.31)
            return max(0.0, min(1.0, 0.28 + wave * 0.18 + fbm * 0.46 + hashed * 0.32))

        def _mouse_influence(self, col: int, row: int, cols: int, rows: int, time_value: float):
            mx = self._mouse_x * cols
            my = self._mouse_y * rows
            dx = col - mx
            dy = row - my
            dist2 = dx * dx + dy * dy
            if dist2 > 144.0:
                return 0.0
            dist = math.sqrt(dist2)
            influence = math.exp(-dist * 0.28) * 0.26
            ripple = math.sin(dist * 1.75 - time_value * 5.0) * 0.08 * influence
            return influence + ripple

        def _barrel_point(self, x: float, y: float, width: int, height: int):
            cx = (x / width) * 2.0 - 1.0
            cy = (y / height) * 2.0 - 1.0
            r2 = cx * cx + cy * cy
            curve = 0.055
            cx *= 1.0 + curve * r2
            cy *= 1.0 + curve * r2
            return (cx * 0.5 + 0.5) * width, (cy * 0.5 + 0.5) * height

        def _hash(self, x: float, y: float):
            return math.modf(math.sin(x * 12.9898 + y * 78.233) * 43758.5453)[0] % 1.0

    class ElasticSlider(QWidget):
        valueChanged = Signal(int)
        elasticReleased = Signal(int)

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("elasticSlider")
            self.setMouseTracking(True)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setFixedHeight(34)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self._minimum = 0
            self._maximum = 100
            self._value = 50
            self._elastic_pad = 32.0
            self._hover_amount = 0.0
            self._overflow = 0.0
            self._region = "middle"
            self._pressing = False
            self._hover_animation = None
            self._overflow_animation = None

        def setRange(self, minimum: int, maximum: int):
            self._minimum = int(minimum)
            self._maximum = max(self._minimum, int(maximum))
            self.setValue(self._value)

        def setValue(self, value: int):
            next_value = max(self._minimum, min(self._maximum, int(value)))
            if next_value == self._value:
                self.update()
                return
            self._value = next_value
            self.valueChanged.emit(self._value)
            self.update()

        def value(self):
            return self._value

        def minimum(self):
            return self._minimum

        def maximum(self):
            return self._maximum

        def enterEvent(self, event):
            self._animate_hover(1.0)
            super().enterEvent(event)

        def leaveEvent(self, event):
            if not self._pressing:
                self._animate_hover(0.0)
            super().leaveEvent(event)

        def mousePressEvent(self, event):
            if not self.isEnabled() or event.button() != Qt.MouseButton.LeftButton:
                return super().mousePressEvent(event)
            self._pressing = True
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.grabMouse()
            self._animate_hover(1.0)
            self._set_value_from_x(self._event_x(event))
            self._set_overflow_from_x(self._event_x(event))
            event.accept()

        def mouseMoveEvent(self, event):
            if self._pressing:
                x = self._event_x(event)
                self._set_value_from_x(x)
                self._set_overflow_from_x(x)
                event.accept()
                return
            super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event):
            if self._pressing and event.button() == Qt.MouseButton.LeftButton:
                x = self._event_x(event)
                self._pressing = False
                try:
                    self.releaseMouse()
                except Exception:
                    pass
                self._set_value_from_x(x)
                self._animate_overflow(0.0)
                self.elasticReleased.emit(self.value())
                local = event.position().toPoint() if hasattr(event, "position") else event.pos()
                if not self.rect().contains(local):
                    self._animate_hover(0.0)
                event.accept()
                return
            super().mouseReleaseEvent(event)

        def keyPressEvent(self, event):
            if event.key() in {Qt.Key.Key_Left, Qt.Key.Key_Down}:
                self.setValue(self.value() - 2)
                self.elasticReleased.emit(self.value())
                event.accept()
                return
            if event.key() in {Qt.Key.Key_Right, Qt.Key.Key_Up}:
                self.setValue(self.value() + 2)
                self.elasticReleased.emit(self.value())
                event.accept()
                return
            super().keyPressEvent(event)

        def paintEvent(self, _event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

            base_track = self._base_track_rect()
            track = QRectF(base_track)
            stretch = self._overflow * 0.55
            if self._region == "left":
                track.setLeft(track.left() - stretch)
            elif self._region == "right":
                track.setRight(track.right() + stretch)

            groove = QColor(240, 240, 240, 34 if self.isEnabled() else 14)
            fill = QColor(240, 240, 240, 226 if self.isEnabled() else 90)
            handle_fill = QColor(240, 240, 240, 244 if self.isEnabled() else 100)
            handle_cut = QColor(0, 0, 0, 210 if self.isEnabled() else 120)
            text_color = QColor(240, 240, 240, 156 if self.isEnabled() else 70)

            marker_scale = 1.0 + min(0.35, self._overflow / 70.0)
            marker_shift = self._overflow * 0.24
            left_shift = -marker_shift if self._region == "left" else 0.0
            right_shift = marker_shift if self._region == "right" else 0.0
            self._draw_marker(painter, "-", 15.0 + left_shift, self.height() / 2.0, marker_scale if self._region == "left" else 1.0, text_color)
            self._draw_marker(painter, "+", self.width() - 15.0 + right_shift, self.height() / 2.0, marker_scale if self._region == "right" else 1.0, text_color)

            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.setBrush(groove)
            radius = track.height() / 2.0
            painter.drawRoundedRect(track, radius, radius)

            handle_center = track.left() + self._ratio() * track.width()
            fill_rect = QRectF(track.left(), track.top(), max(track.height(), handle_center - track.left()), track.height())
            painter.setBrush(fill)
            painter.drawRoundedRect(fill_rect, radius, radius)

            handle_width = 12.0 + self._hover_amount * 3.0 + self._overflow * 0.08
            handle_height = 12.0 + self._hover_amount * 3.0 - min(2.4, self._overflow * 0.025)
            handle_rect = QRectF(
                handle_center - handle_width / 2.0,
                self.height() / 2.0 - handle_height / 2.0,
                handle_width,
                handle_height,
            )
            painter.setBrush(handle_fill)
            painter.drawRoundedRect(handle_rect, handle_height / 2.0, handle_height / 2.0)
            painter.setBrush(handle_cut)
            cut_rect = QRectF(
                handle_rect.center().x() - max(1.0, handle_width * 0.09),
                handle_rect.top() + 3.0,
                max(2.0, handle_width * 0.18),
                max(2.0, handle_rect.height() - 6.0),
            )
            painter.drawRoundedRect(cut_rect, 1.2, 1.2)

            if self._hover_amount > 0.08 or self._pressing:
                painter.setPen(QPen(QColor(240, 240, 240, int(150 + self._hover_amount * 70))))
                bubble = QRectF(handle_center - 16.0, 0.0, 32.0, 12.0)
                painter.drawText(bubble, Qt.AlignmentFlag.AlignCenter, f"{self.value():02d}")

        def _event_x(self, event):
            if hasattr(event, "position"):
                return float(event.position().x())
            return float(event.pos().x())

        def _ratio(self):
            span = max(1, self.maximum() - self.minimum())
            return (self.value() - self.minimum()) / span

        def _base_track_rect(self):
            track_height = max(6.0, 6.0 + self._hover_amount * 5.0 - min(2.0, self._overflow * 0.04))
            pad = self._elastic_pad
            return QRectF(pad, (self.height() - track_height) / 2.0, max(36.0, self.width() - pad * 2.0), track_height)

        def _set_value_from_x(self, x: float):
            track = self._base_track_rect()
            ratio = 0.0 if track.width() <= 0 else (x - track.left()) / track.width()
            ratio = max(0.0, min(1.0, ratio))
            span = max(0, self.maximum() - self.minimum())
            value = int(round(self.minimum() + ratio * span))
            self.setValue(value)

        def _set_overflow_from_x(self, x: float):
            track = self._base_track_rect()
            overflow = 0.0
            region = "middle"
            if x < track.left():
                region = "left"
                overflow = self._decay(track.left() - x, 38.0)
            elif x > track.right():
                region = "right"
                overflow = self._decay(x - track.right(), 38.0)
            self._region = region
            self._overflow = overflow
            self.update()

        def _animate_hover(self, target: float):
            current = self._hover_amount
            animation = self._hover_animation
            if animation is not None:
                animation.stop()
            animation = QVariantAnimation(self)
            animation.setStartValue(current)
            animation.setEndValue(target)
            animation.setDuration(170 if target > current else 220)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic if target > current else QEasingCurve.Type.InOutSine)
            animation.valueChanged.connect(lambda value: self._set_hover(float(value)))
            self._hover_animation = animation
            animation.start()

        def _animate_overflow(self, target: float):
            current = self._overflow
            animation = self._overflow_animation
            if animation is not None:
                animation.stop()
            animation = QVariantAnimation(self)
            animation.setStartValue(current)
            animation.setEndValue(target)
            animation.setDuration(320)
            animation.setEasingCurve(QEasingCurve.Type.OutBack)
            animation.valueChanged.connect(lambda value: self._set_overflow(float(value)))
            animation.finished.connect(lambda: self._finish_overflow(target))
            self._overflow_animation = animation
            animation.start()

        def _set_hover(self, value: float):
            self._hover_amount = max(0.0, min(1.0, value))
            self.update()

        def _set_overflow(self, value: float):
            self._overflow = max(0.0, value)
            self.update()

        def _finish_overflow(self, target: float):
            self._overflow = target
            if target <= 0.0:
                self._region = "middle"
            self.update()

        def _draw_marker(self, painter: QPainter, label: str, x: float, y: float, scale: float, color: QColor):
            painter.save()
            painter.translate(x, y)
            painter.scale(scale, scale)
            painter.setPen(color)
            painter.drawText(QRectF(-8.0, -8.0, 16.0, 16.0), Qt.AlignmentFlag.AlignCenter, label)
            painter.restore()

        def _decay(self, value: float, maximum: float):
            if maximum <= 0:
                return 0.0
            entry = value / maximum
            sigmoid = 2.0 * (1.0 / (1.0 + math.exp(-entry)) - 0.5)
            return sigmoid * maximum

    class TextTypePlaceholder(QObject):
        def __init__(self, field: QLineEdit, texts: tuple[str, ...], parent=None):
            super().__init__(parent or field)
            self._field = field
            self._texts = tuple(text for text in texts if text)
            self._text_index = 0
            self._char_index = 0
            self._deleting = False
            self._pause_until = time.monotonic() + 0.25
            self._cursor_on = True
            self._cursor_tick = 0
            self._timer = QTimer(self)
            self._timer.setInterval(48)
            self._timer.timeout.connect(self._tick)
            self._timer.start()
            field.textChanged.connect(lambda _text: self._render())
            self._render()

        def _tick(self):
            if not self._texts:
                return
            self._cursor_tick = (self._cursor_tick + 1) % 12
            if self._cursor_tick in {0, 6}:
                self._cursor_on = not self._cursor_on
            now = time.monotonic()
            if self._field.text():
                return
            if now < self._pause_until:
                self._render()
                return

            text = self._texts[self._text_index]
            if self._deleting:
                self._char_index = max(0, self._char_index - 1)
                if self._char_index == 0:
                    self._deleting = False
                    self._text_index = (self._text_index + 1) % len(self._texts)
                    self._pause_until = now + 0.18
                self._timer.setInterval(30)
            else:
                self._char_index = min(len(text), self._char_index + 1)
                if self._char_index >= len(text):
                    self._deleting = True
                    self._pause_until = now + 1.15
                self._timer.setInterval(54 + (self._char_index % 4) * 10)
            self._render()

        def _render(self):
            if not self._texts or self._field.text():
                return
            text = self._texts[self._text_index]
            cursor = "|" if self._cursor_on else " "
            self._field.setPlaceholderText(text[: self._char_index] + cursor)

    class BlurTextInputFeedback(QObject):
        def __init__(self, field: QLineEdit, window, parent=None):
            super().__init__(parent or field)
            self._field = field
            self._window = window
            self._last_text = field.text()
            field.textEdited.connect(self._on_text_edited)

        def _on_text_edited(self, text: str):
            typed = ""
            if len(text) > len(self._last_text):
                if text.startswith(self._last_text):
                    typed = text[len(self._last_text) :]
                else:
                    typed = text[-1:]
            self._last_text = text
            if not typed:
                return
            overlay = getattr(self._window, "_typing_blur_overlay", None)
            if overlay is not None:
                overlay.burst(self._field, typed)

    class TargetCursorOverlay(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("targetCursorOverlay")
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAutoFillBackground(False)
            self.setStyleSheet("background: transparent; border: none;")
            self._enabled = False
            self._pressed = False
            self._cursor_x = 0.0
            self._cursor_y = 0.0
            self._rotation = 0.0
            self._target = None
            self._corners: list[tuple[float, float]] = []
            self._timer = QTimer(self)
            self._timer.setInterval(16)
            self._timer.timeout.connect(self._tick)
            self.hide()

        def set_enabled(self, enabled: bool):
            self._enabled = bool(enabled)
            self._target = None
            self._corners = []
            if self._enabled:
                self.show()
                self.raise_()
                if not self._timer.isActive():
                    self._timer.start()
            else:
                self._timer.stop()
                self.hide()
            self.update()

        def set_pressed(self, pressed: bool):
            if not self._enabled:
                return
            self._pressed = bool(pressed)
            self.update()

        def _tick(self):
            if not self._enabled:
                return
            global_pos = QCursor.pos()
            local = self.mapFromGlobal(global_pos)
            if not self.rect().contains(local):
                self._target = None
                self.update()
                return
            target_x = float(local.x())
            target_y = float(local.y())
            if self._cursor_x == 0.0 and self._cursor_y == 0.0:
                self._cursor_x = target_x
                self._cursor_y = target_y
            else:
                self._cursor_x += (target_x - self._cursor_x) * 0.42
                self._cursor_y += (target_y - self._cursor_y) * 0.42
            self._target = self._target_widget(global_pos)
            self._rotation = (self._rotation + 0.045) % (math.pi * 2.0)
            desired = self._desired_corners()
            if len(self._corners) != 4:
                self._corners = desired
            else:
                strength = 0.28 if self._target is not None else 0.18
                self._corners = [
                    (x + (tx - x) * strength, y + (ty - y) * strength)
                    for (x, y), (tx, ty) in zip(self._corners, desired)
                ]
            self.update()

        def _target_widget(self, global_pos):
            widget = QApplication.widgetAt(global_pos)
            while widget is not None:
                if widget is self or widget.objectName() in {"targetCursorOverlay", "clickSparkOverlay"}:
                    widget = widget.parentWidget()
                    continue
                if widget.window() is not self.window():
                    return None
                if self._is_target(widget):
                    return widget
                widget = widget.parentWidget()
            return None

        def _is_target(self, widget):
            if isinstance(widget, (QPushButton, QLineEdit, QSlider, ElasticSlider)):
                return widget.isEnabled()
            return bool(widget.property("cursorTarget"))

        def _desired_corners(self):
            if self._target is not None:
                top_left = self.mapFromGlobal(self._target.mapToGlobal(self._target.rect().topLeft()))
                bottom_right = self.mapFromGlobal(self._target.mapToGlobal(self._target.rect().bottomRight()))
                rect = QRectF(
                    float(top_left.x()),
                    float(top_left.y()),
                    float(bottom_right.x() - top_left.x() + 1),
                    float(bottom_right.y() - top_left.y() + 1),
                ).normalized()
                rect = rect.adjusted(-4.0, -4.0, 4.0, 4.0)
                size = 13.0
                return [
                    (rect.left(), rect.top()),
                    (rect.right() - size, rect.top()),
                    (rect.right() - size, rect.bottom() - size),
                    (rect.left(), rect.bottom() - size),
                ]
            radius = 18.0
            size = 13.0
            positions = []
            for base_x, base_y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                x = base_x * radius
                y = base_y * radius
                rotated_x = x * math.cos(self._rotation) - y * math.sin(self._rotation)
                rotated_y = x * math.sin(self._rotation) + y * math.cos(self._rotation)
                positions.append((self._cursor_x + rotated_x - size / 2.0, self._cursor_y + rotated_y - size / 2.0))
            return positions

        def paintEvent(self, _event):
            if not self._enabled:
                return
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            scale = 0.82 if self._pressed else 1.0
            dot_radius = 2.2 * scale
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.setBrush(QColor(240, 240, 240, 230))
            painter.drawEllipse(QRectF(self._cursor_x - dot_radius, self._cursor_y - dot_radius, dot_radius * 2.0, dot_radius * 2.0))

            pen = QPen(QColor(240, 240, 240, 220))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for index, (x, y) in enumerate(self._corners):
                self._draw_corner(painter, index, x, y, 13.0 * scale)

        def _draw_corner(self, painter: QPainter, index: int, x: float, y: float, size: float):
            if index == 0:
                painter.drawLine(int(x), int(y), int(x + size), int(y))
                painter.drawLine(int(x), int(y), int(x), int(y + size))
            elif index == 1:
                painter.drawLine(int(x), int(y), int(x + size), int(y))
                painter.drawLine(int(x + size), int(y), int(x + size), int(y + size))
            elif index == 2:
                painter.drawLine(int(x + size), int(y), int(x + size), int(y + size))
                painter.drawLine(int(x), int(y + size), int(x + size), int(y + size))
            else:
                painter.drawLine(int(x), int(y), int(x), int(y + size))
                painter.drawLine(int(x), int(y + size), int(x + size), int(y + size))

    class ButtonGlowFilter(QObject):
        def eventFilter(self, obj, event):
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonPress:
                self._emit_click_spark(obj, event)
                self._emit_target_cursor_press(obj, True)
            elif event_type == QEvent.Type.MouseButtonRelease:
                self._emit_target_cursor_press(obj, False)
            if isinstance(obj, QPushButton):
                if obj.objectName() in {"dockNavButton", "sourceFamilyButton"}:
                    return False
                if event_type == QEvent.Type.Enter:
                    obj._glow_hovering = True
                    if not getattr(obj, "_glow_pressing", False):
                        self._animate_glow(obj, 1.0)
                elif event_type == QEvent.Type.Leave:
                    obj._glow_hovering = False
                    if not getattr(obj, "_glow_pressing", False):
                        self._animate_glow(obj, 0.0)
                elif event_type == QEvent.Type.MouseButtonPress and obj.isEnabled():
                    try:
                        if event.button() != Qt.MouseButton.LeftButton:
                            return False
                    except Exception:
                        pass
                    obj._glow_pressing = True
                    self._animate_glow(obj, 1.55, duration=95, easing=QEasingCurve.Type.OutQuad)
                elif event_type == QEvent.Type.MouseButtonRelease:
                    obj._glow_pressing = False
                    target = 1.0 if getattr(obj, "_glow_hovering", False) and obj.isEnabled() else 0.0
                    self._animate_glow(obj, target, duration=330, easing=QEasingCurve.Type.OutCubic)
                elif event_type == QEvent.Type.EnabledChange and not obj.isEnabled():
                    obj._glow_pressing = False
                    obj._glow_hovering = False
                    self._animate_glow(obj, 0.0)
            return False

        def _emit_click_spark(self, widget: QWidget, event):
            if not isinstance(widget, QWidget):
                return
            if widget.objectName() == "clickSparkOverlay":
                return
            try:
                if event.button() != Qt.MouseButton.LeftButton:
                    return
            except Exception:
                pass
            try:
                local = event.position().toPoint()
            except Exception:
                try:
                    local = event.pos()
                except Exception:
                    local = widget.rect().center()
            window = widget.window()
            overlay = getattr(window, "_spark_overlay", None)
            if overlay is None:
                return
            point = widget.mapTo(window, local)
            overlay.spark(point.x(), point.y())

        def _emit_target_cursor_press(self, widget: QWidget, pressed: bool):
            if not isinstance(widget, QWidget):
                return
            window = widget.window()
            overlay = getattr(window, "_target_cursor_overlay", None)
            if overlay is not None:
                overlay.set_pressed(pressed)

        def _animate_glow(self, button: QPushButton, target: float, *, duration: int | None = None, easing=None):
            if not button.isEnabled():
                target = 0.0
            current = float(getattr(button, "_glow_level", 0.0) or 0.0)
            animation = getattr(button, "_glow_animation", None)
            if animation is not None:
                animation.stop()
            self._set_glow(button, current)
            animation = QVariantAnimation(button)
            animation.setStartValue(current)
            animation.setEndValue(target)
            animation.setDuration(duration if duration is not None else (280 if target > current else 420))
            animation.setEasingCurve(easing if easing is not None else (QEasingCurve.Type.OutCubic if target > current else QEasingCurve.Type.InOutSine))
            animation.valueChanged.connect(lambda value, button=button: self._set_glow(button, float(value)))
            animation.finished.connect(lambda button=button, target=target: self._finish_glow(button, target))
            button._glow_animation = animation
            animation.start()

        def _set_glow(self, button: QPushButton, amount: float):
            amount = max(0.0, min(1.55, amount))
            button._glow_level = amount
            if not hasattr(button, "_base_style_sheet"):
                button._base_style_sheet = button.styleSheet()
            if amount <= 0.01:
                button.setStyleSheet(button._base_style_sheet)
                return
            border = min(255, int(105 + amount * 95))
            fill = min(28, int(5 + amount * 10))
            color = min(255, int(220 + amount * 20))
            button.setStyleSheet(
                button._base_style_sheet
                + (
                    "\n"
                    "QPushButton {"
                    f"background: rgb({fill}, {fill}, {fill});"
                    f"color: rgb({color}, {color}, {color});"
                    f"border-color: rgb({border}, {border}, {border});"
                    "}"
                )
            )

        def _finish_glow(self, button: QPushButton, target: float):
            if target <= 0.0:
                button._glow_level = 0.0
                if getattr(button, "_glow_animation", None) is not None:
                    button._glow_animation = None
                QTimer.singleShot(90, lambda button=button: self._clear_glow(button))

        def _clear_glow(self, button: QPushButton):
            if float(getattr(button, "_glow_level", 0.0) or 0.0) > 0.0:
                return
            button.setStyleSheet(getattr(button, "_base_style_sheet", ""))

    button_glow_filter = ButtonGlowFilter(app)
    app.installEventFilter(button_glow_filter)
    app._button_glow_filter = button_glow_filter

    class DockNavButton(QPushButton):
        def __init__(self, page: str, badge: str, parent=None):
            super().__init__(page, parent)
            self.setObjectName("dockNavButton")
            self.setProperty("pageName", page)
            self.setProperty("active", False)
            self.setToolTip(page)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setStyleSheet("background: transparent; border: none;")
            self._page = page
            self._badge = badge
            self._active = False
            self._dock_level = 0.0
            self._dock_animation: QVariantAnimation | None = None
            self._apply_dock_level(0.0)

        def set_active(self, active: bool):
            self._active = bool(active)
            self.setProperty("active", self._active)
            self.setToolTip(f"{self._page} // ACTIVE" if self._active else self._page)
            target = max(self._dock_level, 0.48) if self._active else min(self._dock_level, 0.0)
            self.set_dock_level(target, animated=True)
            self.update()

        def set_dock_level(self, level: float, *, animated: bool = True):
            target = max(0.0, min(1.0, float(level)))
            if self._active:
                target = max(target, 0.48)
            if not animated:
                self._apply_dock_level(target)
                return
            animation = self._dock_animation
            if animation is not None:
                animation.stop()
            if abs(target - self._dock_level) <= 0.015:
                self._apply_dock_level(target)
                return
            animation = QVariantAnimation(self)
            animation.setStartValue(self._dock_level)
            animation.setEndValue(target)
            animation.setDuration(170 if target > self._dock_level else 240)
            animation.setEasingCurve(
                QEasingCurve.Type.OutCubic if target > self._dock_level else QEasingCurve.Type.InOutSine
            )
            animation.valueChanged.connect(lambda value: self._apply_dock_level(float(value)))
            animation.finished.connect(lambda: setattr(self, "_dock_animation", None))
            self._dock_animation = animation
            animation.start()

        def _apply_dock_level(self, level: float):
            self._dock_level = max(0.0, min(1.0, float(level)))
            display = max(self._dock_level, 0.48 if self._active else 0.0)
            width = int(50 + display * 116)
            height = int(36 + display * 14)
            if self.width() != width or self.height() != height:
                self.setFixedSize(width, height)
            self.update()

        def enterEvent(self, event):
            self._sync_parent_dock()
            super().enterEvent(event)

        def mouseMoveEvent(self, event):
            self._sync_parent_dock()
            super().mouseMoveEvent(event)

        def leaveEvent(self, event):
            QTimer.singleShot(20, self._sync_parent_dock)
            super().leaveEvent(event)

        def _sync_parent_dock(self):
            rail = self.parentWidget()
            if hasattr(rail, "update_hover_from_global"):
                rail.update_hover_from_global(QCursor.pos())

        def paintEvent(self, _event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            level = max(self._dock_level, 0.48 if self._active else 0.0)
            rect = QRectF(1.0, 1.0, float(self.width() - 2), float(self.height() - 2))

            if self._active:
                fill = QColor(240, 240, 240, 232)
                border = QColor(255, 255, 255, 238)
                text = QColor(0, 0, 0, 245)
                badge_fill = QColor(0, 0, 0, 235)
                badge_text = QColor(255, 255, 255, 245)
            else:
                shade = min(28, int(8 + level * 22))
                fill = QColor(shade, shade, shade, int(160 + level * 55))
                border = QColor(130, 130, 130, int(80 + level * 135))
                text = QColor(235, 235, 235, int(80 + level * 165))
                badge_fill = QColor(238, 238, 238, int(185 + level * 50))
                badge_text = QColor(0, 0, 0, 235)

            painter.setPen(QPen(border, 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 8.0, 8.0)

            if level > 0.05 and not self._active:
                glow = QColor(255, 255, 255, int(28 + level * 58))
                painter.setPen(QPen(glow, 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect.adjusted(2.0, 2.0, -2.0, -2.0), 7.0, 7.0)

            badge_size = min(30.0 + level * 5.0, rect.height() - 8.0)
            badge = QRectF(rect.left() + 6.0, rect.center().y() - badge_size / 2.0, badge_size, badge_size)
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.setBrush(badge_fill)
            painter.drawRoundedRect(badge, 8.0, 8.0)

            font = painter.font()
            font.setFamily("Cascadia Mono")
            font.setBold(True)
            font.setPointSize(8)
            painter.setFont(font)
            painter.setPen(QPen(badge_text))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, self._badge)

            if self.width() >= 92:
                label_alpha = min(245, int((level - 0.18) / 0.82 * 245)) if not self._active else 245
                painter.setPen(QPen(QColor(text.red(), text.green(), text.blue(), max(0, label_alpha))))
                font.setPointSize(9)
                painter.setFont(font)
                label_rect = QRectF(badge.right() + 8.0, rect.top(), rect.width() - badge.width() - 16.0, rect.height())
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._page.upper())

    class DockNavRail(QFrame):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setObjectName("dockNavRail")
            self.setMouseTracking(True)
            self._buttons: list[DockNavButton] = []
            self._layout = QVBoxLayout(self)
            self._layout.setContentsMargins(6, 6, 6, 6)
            self._layout.setSpacing(5)

        def add_nav_button(self, button: DockNavButton):
            self._buttons.append(button)
            self._layout.addWidget(button, 0, Qt.AlignmentFlag.AlignHCenter)

        def update_hover_from_global(self, global_pos):
            local = self.mapFromGlobal(global_pos)
            if not self.rect().contains(local):
                self.reset_magnification()
                return
            self._apply_magnification(float(local.y()))

        def reset_magnification(self):
            for button in self._buttons:
                button.set_dock_level(0.48 if button.property("active") else 0.0)

        def sync_active(self):
            cursor = self.mapFromGlobal(QCursor.pos())
            if self.rect().contains(cursor):
                self._apply_magnification(float(cursor.y()))
            else:
                self.reset_magnification()

        def mouseMoveEvent(self, event):
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            self._apply_magnification(float(pos.y()))
            super().mouseMoveEvent(event)

        def leaveEvent(self, event):
            QTimer.singleShot(20, self._reset_if_cursor_left)
            super().leaveEvent(event)

        def _reset_if_cursor_left(self):
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                self.reset_magnification()

        def _apply_magnification(self, hover_y: float):
            distance_limit = 118.0
            for button in self._buttons:
                center = button.y() + button.height() / 2.0
                distance = abs(hover_y - center)
                raw = max(0.0, 1.0 - distance / distance_limit)
                eased = raw * raw * (3.0 - 2.0 * raw)
                button.set_dock_level(eased, animated=False)

    class SourceFamilyButton(QPushButton):
        def __init__(self, source_key: str, label: str, code: str, detail: str, parent=None):
            super().__init__(label, parent)
            self.setObjectName("sourceFamilyButton")
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setMouseTracking(True)
            self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.setFixedHeight(124)
            self.setStyleSheet("background: transparent; border: none; padding: 0;")
            self._source_key = source_key
            self._label = label
            self._code = code
            self._detail = detail
            self._expanded = 0.0
            self._pressed_level = 0.0
            self._family_animation: QVariantAnimation | None = None
            self._press_animation: QVariantAnimation | None = None

        def enterEvent(self, event):
            self._animate_expand(1.0)
            super().enterEvent(event)

        def leaveEvent(self, event):
            if not self.hasFocus():
                self._animate_expand(0.0)
            super().leaveEvent(event)

        def focusInEvent(self, event):
            self._animate_expand(1.0)
            super().focusInEvent(event)

        def focusOutEvent(self, event):
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                self._animate_expand(0.0)
            super().focusOutEvent(event)

        def mousePressEvent(self, event):
            self._animate_press(1.0)
            super().mousePressEvent(event)

        def mouseReleaseEvent(self, event):
            self._animate_press(0.0)
            super().mouseReleaseEvent(event)

        def _animate_expand(self, target: float):
            animation = self._family_animation
            if animation is not None:
                animation.stop()
            animation = QVariantAnimation(self)
            animation.setStartValue(self._expanded)
            animation.setEndValue(max(0.0, min(1.0, target)))
            animation.setDuration(260 if target > self._expanded else 330)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic if target > self._expanded else QEasingCurve.Type.InOutSine)
            animation.valueChanged.connect(lambda value: self._set_expanded(float(value)))
            animation.finished.connect(lambda: setattr(self, "_family_animation", None))
            self._family_animation = animation
            animation.start()

        def _animate_press(self, target: float):
            animation = self._press_animation
            if animation is not None:
                animation.stop()
            animation = QVariantAnimation(self)
            animation.setStartValue(self._pressed_level)
            animation.setEndValue(max(0.0, min(1.0, target)))
            animation.setDuration(90 if target > self._pressed_level else 180)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.valueChanged.connect(lambda value: self._set_pressed_level(float(value)))
            animation.finished.connect(lambda: setattr(self, "_press_animation", None))
            self._press_animation = animation
            animation.start()

        def _set_expanded(self, value: float):
            self._expanded = max(0.0, min(1.0, value))
            self.update()

        def _set_pressed_level(self, value: float):
            self._pressed_level = max(0.0, min(1.0, value))
            self.update()

        def paintEvent(self, _event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            press_inset = 1.5 * self._pressed_level
            level = self._expanded
            visual_height = 76.0 + level * 46.0
            rect = QRectF(
                1.0 + press_inset,
                1.0 + press_inset,
                self.width() - 2.0 - press_inset * 2.0,
                visual_height - 2.0 - press_inset * 2.0,
            )
            fill = int(5 + level * 14)
            border_alpha = int(95 + level * 135)
            painter.setPen(QPen(QColor(235, 235, 235, border_alpha), 1))
            painter.setBrush(QColor(fill, fill, fill, 232))
            painter.drawRoundedRect(rect, 8.0, 8.0)

            painter.setPen(QPen(QColor(255, 255, 255, int(24 + level * 76)), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(4.0, 4.0, -4.0, -4.0), 6.0, 6.0)

            icon_size = 38.0 + level * 10.0
            icon_rect = QRectF(rect.left() + 12.0, rect.top() + 13.0, icon_size, icon_size)
            self._draw_source_icon(painter, icon_rect)

            font = painter.font()
            font.setFamily("Cascadia Mono")
            font.setBold(True)
            font.setPointSize(10)
            painter.setFont(font)
            painter.setPen(QPen(QColor(242, 242, 242, 238)))
            title_rect = QRectF(icon_rect.right() + 12.0, rect.top() + 12.0, rect.width() - icon_rect.width() - 28.0, 24.0)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self._label.upper())

            font.setPointSize(8)
            painter.setFont(font)
            painter.setPen(QPen(QColor(170, 170, 170, 205)))
            painter.drawText(
                QRectF(icon_rect.right() + 12.0, rect.top() + 36.0, rect.width() - icon_rect.width() - 28.0, 18.0),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"{self._code} // HANDOFF",
            )

            if level > 0.02:
                alpha = int(level * 215)
                painter.setPen(QPen(QColor(215, 215, 215, alpha)))
                font.setPointSize(8)
                painter.setFont(font)
                detail_rect = QRectF(rect.left() + 12.0, rect.top() + 72.0, rect.width() - 24.0, 32.0)
                painter.drawText(detail_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, self._detail)

                painter.setPen(QPen(QColor(255, 255, 255, int(level * 185)), 1))
                y = rect.bottom() - 13.0
                painter.drawLine(int(rect.left() + 12.0), int(y), int(rect.right() - 12.0), int(y))

        def _draw_source_icon(self, painter: QPainter, rect: QRectF):
            painter.save()
            painter.setClipRect(rect.adjusted(-1.0, -1.0, 1.0, 1.0))
            painter.setPen(QPen(QColor(245, 245, 245, 232), 2))
            painter.setBrush(QColor(245, 245, 245, 226))
            key = self._source_key
            if key == "youtube":
                box = rect.adjusted(1.0, 7.0, -1.0, -7.0)
                painter.drawRoundedRect(box, 8.0, 8.0)
                painter.setBrush(QColor(0, 0, 0, 245))
                painter.setPen(QPen(Qt.PenStyle.NoPen))
                path = QPainterPath()
                path.moveTo(box.left() + box.width() * 0.42, box.top() + box.height() * 0.28)
                path.lineTo(box.left() + box.width() * 0.42, box.bottom() - box.height() * 0.28)
                path.lineTo(box.right() - box.width() * 0.25, box.center().y())
                path.closeSubpath()
                painter.drawPath(path)
            elif key == "soundcloud":
                painter.setBrush(QColor(245, 245, 245, 226))
                w = rect.width()
                h = rect.height()
                base_y = rect.top() + h * 0.77
                for index, height_ratio in enumerate((0.26, 0.38, 0.52, 0.42)):
                    x = rect.left() + w * (0.06 + index * 0.08)
                    bar_w = max(1.6, w * 0.045)
                    bar_h = h * height_ratio
                    painter.drawRoundedRect(QRectF(x, base_y - bar_h, bar_w, bar_h), bar_w / 2.0, bar_w / 2.0)
                cloud = QPainterPath()
                cloud.addEllipse(QRectF(rect.left() + w * 0.31, rect.top() + h * 0.37, w * 0.28, h * 0.28))
                cloud.addEllipse(QRectF(rect.left() + w * 0.48, rect.top() + h * 0.22, w * 0.35, h * 0.35))
                cloud.addEllipse(QRectF(rect.left() + w * 0.73, rect.top() + h * 0.43, w * 0.20, h * 0.20))
                cloud.addRoundedRect(
                    QRectF(rect.left() + w * 0.35, rect.top() + h * 0.58, w * 0.58, h * 0.17),
                    4.0,
                    4.0,
                )
                painter.drawPath(cloud.simplified())
            elif key == "archive":
                roof = QPainterPath()
                roof.moveTo(rect.left() + rect.width() * 0.12, rect.top() + rect.height() * 0.34)
                roof.lineTo(rect.center().x(), rect.top() + rect.height() * 0.12)
                roof.lineTo(rect.right() - rect.width() * 0.12, rect.top() + rect.height() * 0.34)
                roof.closeSubpath()
                painter.drawPath(roof)
                painter.drawRect(QRectF(rect.left() + rect.width() * 0.16, rect.top() + rect.height() * 0.38, rect.width() * 0.68, 3.0))
                for index in range(4):
                    x = rect.left() + rect.width() * (0.22 + index * 0.15)
                    painter.drawRect(QRectF(x, rect.top() + rect.height() * 0.48, rect.width() * 0.07, rect.height() * 0.26))
                painter.drawRect(QRectF(rect.left() + rect.width() * 0.14, rect.top() + rect.height() * 0.78, rect.width() * 0.72, 3.0))
            else:
                painter.drawRoundedRect(rect.adjusted(4.0, 4.0, -4.0, -4.0), 8.0, 8.0)
                painter.setPen(QPen(QColor(0, 0, 0, 245)))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._code[:2])
            painter.restore()

    class SmoothScrollArea(QScrollArea):
        viewportChanged = Signal()

        def __init__(self, parent=None):
            super().__init__(parent)
            self._scroll_target = 0.0
            self._scroll_animation: QVariantAnimation | None = None
            app_instance = QApplication.instance()
            if app_instance is not None:
                app_instance.installEventFilter(self)

        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.Wheel and self._should_handle_wheel_target(obj):
                if self._handle_wheel(event):
                    return True
            return super().eventFilter(obj, event)

        def viewportEvent(self, event):
            if event.type() == QEvent.Type.Wheel and self._handle_wheel(event):
                return True
            return super().viewportEvent(event)

        def resizeEvent(self, event):
            super().resizeEvent(event)
            self.viewportChanged.emit()

        def showEvent(self, event):
            super().showEvent(event)
            self.viewportChanged.emit()

        def wheelEvent(self, event):
            if self._handle_wheel(event):
                return
            super().wheelEvent(event)

        def _should_handle_wheel_target(self, obj):
            if not self.isVisible() or not isinstance(obj, QWidget):
                return False
            if obj is self.verticalScrollBar() or isinstance(obj, (QSlider, ElasticSlider)):
                return False
            widget = self.widget()
            viewport = self.viewport()
            return (
                obj is self
                or obj is viewport
                or obj is widget
                or (widget is not None and widget.isAncestorOf(obj))
                or viewport.isAncestorOf(obj)
            )

        def _handle_wheel(self, event):
            bar = self.verticalScrollBar()
            if bar is None or bar.maximum() <= 0:
                return False
            pixel_delta = event.pixelDelta().y()
            angle_delta = event.angleDelta().y()
            delta = float(pixel_delta if pixel_delta else angle_delta / 120.0 * 92.0)
            if abs(delta) < 0.5:
                return False
            current = float(bar.value())
            base = self._scroll_target if self._scroll_animation is not None else current
            target = max(float(bar.minimum()), min(float(bar.maximum()), base - delta))
            self._scroll_target = target
            animation = self._scroll_animation
            if animation is not None:
                animation.stop()
            animation = QVariantAnimation(self)
            animation.setStartValue(current)
            animation.setEndValue(target)
            animation.setDuration(430)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.valueChanged.connect(lambda value, bar=bar: bar.setValue(int(round(float(value)))))
            animation.finished.connect(lambda: setattr(self, "_scroll_animation", None))
            self._scroll_animation = animation
            animation.start()
            event.accept()
            return True

    class CyberVisualizer(QWidget):
        def __init__(self, runtime, *, minimum_height: int = 132, mode: str = "spectrum", parent=None):
            super().__init__(parent)
            self.setMinimumHeight(minimum_height)
            self._mode = mode
            self._phase = 0
            self._crt_phase = 0
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

        def sync_runtime(self, runtime) -> None:
            """Refresh cached playback/visualizer state without rebuilding the widget tree."""
            self._is_live = bool(runtime.is_live)
            self._is_playing = bool(runtime.is_playing)
            self._position = float(runtime.position or 0.0)
            self._duration = float(runtime.duration or 0.0)
            self._bars = tuple(float(value) for value in getattr(runtime, "visualizer_bars", ())[:48])
            self._clock_started = time.monotonic()

        def _advance(self):
            self._crt_phase += 1
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

            self._paint_crt_overlay(painter, width, height)

            painter.setPen(QPen(QColor("#aaaaaa")))
            status = "LIVE SIGNAL" if self._is_live else "OFFLINE TRACE"
            painter.drawText(12, 18, f"{self._mode.upper()} // {status}")
            painter.drawText(12, height - 6, f"POS {int(playhead):04d}s / DUR {int(self._duration):04d}s")

        def _paint_crt_overlay(self, painter: QPainter, width: int, height: int):
            drift = self._crt_phase % 8
            for y in range(-8 + drift, height, 4):
                if y < 0:
                    continue
                alpha = 18 if (y // 4) % 2 else 9
                painter.fillRect(0, y, width, 1, QColor(240, 240, 240, alpha))
            for y in range(-8 + drift, height, 8):
                if y < 0:
                    continue
                painter.fillRect(0, y + 2, width, 1, QColor(0, 0, 0, 54))
            shimmer = int((self._crt_phase * 2) % max(1, height))
            painter.fillRect(0, shimmer, width, 1, QColor(240, 240, 240, 8))

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

    class CRTScanlineStrip(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setFixedHeight(18)
            self._phase = 0
            self._timer = QTimer(self)
            self._timer.setInterval(90)
            self._timer.timeout.connect(self._advance)
            self._timer.start()

        def _advance(self):
            self._phase += 1
            self.update()

        def paintEvent(self, _event):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            rect = self.rect()
            width = max(1, rect.width())
            height = max(1, rect.height())
            painter.fillRect(rect, QColor("#050505"))
            drift = self._phase % 8
            for y in range(-8 + drift, height, 4):
                if y < 0:
                    continue
                painter.fillRect(0, y, width, 1, QColor(240, 240, 240, 28))
            for y in range(-8 + drift, height, 8):
                if y + 2 < 0:
                    continue
                painter.fillRect(0, y + 2, width, 1, QColor(0, 0, 0, 108))
            shimmer = (self._phase * 2) % max(1, height)
            painter.fillRect(0, shimmer, width, 1, QColor(240, 240, 240, 12))
            painter.fillRect(0, 0, width, 1, QColor(240, 240, 240, 18))
            painter.fillRect(0, height - 1, width, 1, QColor(240, 240, 240, 12))

    class Shell(QMainWindow):
        def __init__(self):
            super().__init__()
            self.snapshot = load_app_snapshot()
            self.runtime = load_runtime_snapshot()
            self._app_state_marker = snapshot_file_marker()
            self._runtime_state_marker = runtime_file_marker()
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
            self._target_cursor_enabled = False
            self._target_cursor_cursor_hidden = False
            self._target_cursor_toggle_button: QPushButton | None = None
            self._defer_page_rebuild = False
            self._state_timer: QTimer | None = None
            self._playerbar_seek: QSlider | None = None
            self._playerbar_time_current: QLabel | None = None
            self._playerbar_time_total: QLabel | None = None
            self._playerbar_play_button: QPushButton | None = None
            self._playerbar_volume_label: QLabel | None = None
            self._home_seek: QSlider | None = None
            self._home_pos_time: QLabel | None = None
            self._home_dur_time: QLabel | None = None
            self._home_status_value: QLabel | None = None
            self._home_mode_value: QLabel | None = None
            self._home_telemetry_percent: QLabel | None = None
            self._home_telemetry_link: QLabel | None = None
            self._home_telemetry_source: QLabel | None = None
            self._home_telemetry_volume: QLabel | None = None
            self._home_telemetry_queue: QLabel | None = None
            self._cover_cache_dir = Path.home() / ".voidplayer_cache" / "art"
            self._cover_manager = QNetworkAccessManager(self)
            self._cover_requests: set[str] = set()
            self._cover_failures: set[str] = set()
            self._text_type_effects: list[TextTypePlaceholder] = []
            self._typing_blur_effects: list[BlurTextInputFeedback] = []
            self.setWindowTitle("OTERNOS // Qt Prototype")
            self.resize(1180, 820)
            self.setMinimumSize(960, 660)
            self._nav_buttons: list[QPushButton] = []
            self._dock_nav_rail: DockNavRail | None = None
            self._page_title: QLabel | None = None
            self._page_caption: QLabel | None = None
            self._content_stack: QVBoxLayout | None = None
            self._main_scroll: QScrollArea | None = None
            self._action_chip: QLabel | None = None
            self._scroll_reveal_items: list[tuple[QLabel, QGraphicsBlurEffect]] = []
            self._source_status_labels: dict[str, QLabel] = {}
            self._source_result_cards: list[tuple[QFrame, QLabel, QLabel, QLabel, QLabel, QPushButton]] = []
            self._build()
            self._spark_overlay = ClickSparkOverlay(self)
            self._spark_overlay.setGeometry(self.rect())
            self._spark_overlay.raise_()
            self._typing_blur_overlay = BlurTextOverlay(self)
            self._typing_blur_overlay.setGeometry(self.rect())
            self._typing_blur_overlay.raise_()
            self._target_cursor_overlay = TargetCursorOverlay(self)
            self._target_cursor_overlay.setGeometry(self.rect())
            self._target_cursor_overlay.set_enabled(self._target_cursor_enabled)
            self._target_cursor_overlay.raise_()
            self._start_state_timer()

        def resizeEvent(self, event):
            super().resizeEvent(event)
            overlay = getattr(self, "_spark_overlay", None)
            if overlay is not None:
                overlay.setGeometry(self.rect())
                overlay.raise_()
            blur_overlay = getattr(self, "_typing_blur_overlay", None)
            if blur_overlay is not None:
                blur_overlay.setGeometry(self.rect())
                blur_overlay.raise_()
            target_overlay = getattr(self, "_target_cursor_overlay", None)
            if target_overlay is not None:
                target_overlay.setGeometry(self.rect())
                target_overlay.raise_()

        def _build(self):
            self._nav_buttons = []
            self._dock_nav_rail = None
            self._content_stack = None
            self._main_scroll = None
            self._scroll_reveal_items = []
            self._text_type_effects = []
            self._typing_blur_effects = []
            self._target_cursor_toggle_button = None
            self._playerbar_seek = None
            self._playerbar_time_current = None
            self._playerbar_time_total = None
            self._playerbar_play_button = None
            self._playerbar_volume_label = None
            self._home_seek = None
            self._home_pos_time = None
            self._home_dur_time = None
            self._home_status_value = None
            self._home_mode_value = None
            self._home_telemetry_percent = None
            self._home_telemetry_link = None
            self._home_telemetry_source = None
            self._home_telemetry_volume = None
            self._home_telemetry_queue = None
            root = FaultyTerminalSurface()
            root.setObjectName("root")
            self.setCentralWidget(root)

            layout = QHBoxLayout(root)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            layout.addWidget(self._build_sidebar())
            layout.addWidget(self._build_main(), 1)
            self._set_page(self._current_page)
            overlay = getattr(self, "_spark_overlay", None)
            if overlay is not None:
                overlay.raise_()
            blur_overlay = getattr(self, "_typing_blur_overlay", None)
            if blur_overlay is not None:
                blur_overlay.raise_()
            target_overlay = getattr(self, "_target_cursor_overlay", None)
            if target_overlay is not None:
                target_overlay.raise_()

        def _start_state_timer(self):
            self._state_timer = QTimer(self)
            self._state_timer.setInterval(self._state_timer_interval())
            self._state_timer.timeout.connect(lambda: self._reload_snapshot())
            self._state_timer.start()

        def _build_sidebar(self):
            side = QFrame()
            side.setObjectName("sidebar")
            side.setFixedWidth(204)

            layout = QVBoxLayout(side)
            layout.setContentsMargins(14, 18, 14, 16)
            layout.setSpacing(10)

            brand = QLabel("OTERNOS//VOID")
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

            nav_rail = DockNavRail()
            self._dock_nav_rail = nav_rail
            nav_items = (
                ("Home", "HM"),
                ("Search", "SR"),
                ("Library", "LB"),
                ("Playlists", "PL"),
                ("Sources", "SC"),
                ("Now Playing", "NP"),
                ("Visualizer", "VZ"),
                ("Queue", "Q"),
                ("Settings", "ST"),
                ("Contributors", "CR"),
            )
            for name, badge in nav_items:
                btn = DockNavButton(name, badge, nav_rail)
                btn.setProperty("pageName", name)
                btn.clicked.connect(lambda _=False, page=name: self._set_page(page))
                self._nav_buttons.append(btn)
                nav_rail.add_nav_button(btn)

            layout.addWidget(nav_rail)
            QTimer.singleShot(0, self._refresh_dock_nav)

            layout.addStretch(1)

            layout.addWidget(self._sidebar_meter())
            state = self._system_state_text()
            status = self._small_panel("SYSTEM", state)
            layout.addWidget(status)
            return side

        def _build_main(self):
            main = QWidget()
            main.setObjectName("main")
            main.setAutoFillBackground(False)
            outer = QVBoxLayout(main)
            outer.setContentsMargins(16, 16, 16, 16)
            outer.setSpacing(12)

            outer.addLayout(self._build_topbar())

            scroll = SmoothScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.verticalScrollBar().valueChanged.connect(lambda _=0: self._update_scroll_reveal())
            scroll.viewportChanged.connect(self._update_scroll_reveal)
            self._main_scroll = scroll
            scroll_content = QWidget()
            scroll_content.setObjectName("scrollContent")
            scroll_content.setAutoFillBackground(False)
            self._content_stack = QVBoxLayout(scroll_content)
            self._content_stack.setContentsMargins(0, 0, 0, 0)
            self._content_stack.setSpacing(16)
            scroll.setWidget(scroll_content)
            outer.addWidget(scroll, 1)

            outer.addWidget(self._build_playerbar())
            return main

        def _build_topbar(self):
            wrap = QVBoxLayout()
            wrap.setSpacing(8)

            row = QHBoxLayout()
            row.setSpacing(8)

            back = QPushButton("[ BACK ]")
            back.setObjectName("uvDragonfly")
            back.setEnabled(bool(self._page_history))
            back.clicked.connect(lambda _=False: self._go_back())
            row.addWidget(back)

            forward = QPushButton("[ FWD ]")
            forward.setObjectName("uvDragonfly")
            forward.setEnabled(bool(self._page_forward))
            forward.clicked.connect(lambda _=False: self._go_forward())
            row.addWidget(forward)

            search = QLineEdit()
            self._install_text_type_placeholder(
                search,
                (
                    "scan local vault",
                    "search SoundCloud",
                    "search YouTube",
                    "search Archive",
                ),
            )
            search.returnPressed.connect(lambda field=search: self._open_search(field.text()))
            row.addWidget(search, 1)

            refresh = QPushButton("[ SYNC ]")
            refresh.setObjectName("uvStingray")
            refresh.clicked.connect(lambda _=False: self._reload_snapshot(force=True))
            row.addWidget(refresh)

            wrap.addLayout(row)

            status_row = QHBoxLayout()
            status_row.setSpacing(8)
            status_row.addWidget(self._chip("CORE//ONLINE", "live"))
            status_row.addWidget(self._chip(f"VAULT//{self.snapshot.library_count}"))
            status_row.addWidget(self._chip(self._runtime_link_label(), self._runtime_chip_kind()))
            self._action_chip = self._chip(self._action_message, self._action_kind)
            status_row.addWidget(self._action_chip, 1)

            profile = QPushButton("ROOT")
            profile.setObjectName("uvEmu")
            profile.clicked.connect(
                lambda _=False: self._set_action_message("PROFILE LATER PHASE", "stale")
            )
            status_row.addWidget(profile)
            wrap.addLayout(status_row)

            return wrap

        def _set_page(self, page: str, *, record_history: bool = True):
            if page != self._current_page and record_history:
                self._page_history.append(self._current_page)
                self._page_forward.clear()
            self._current_page = page
            self._sync_state_timer_interval()
            for btn in self._nav_buttons:
                active = btn.property("pageName") == page
                if hasattr(btn, "set_active"):
                    btn.set_active(active)
                else:
                    btn.setProperty("active", active)
                    btn.style().unpolish(btn)
                    btn.style().polish(btn)
            self._refresh_dock_nav()

            if not self._content_stack:
                return
            while self._content_stack.count():
                item = self._content_stack.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()

            header = QWidget()
            header.setObjectName("headerWrap")
            header.setAutoFillBackground(False)
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

            body = self._page_body(page)
            self._content_stack.addWidget(body)
            self._content_stack.addStretch(1)
            self._install_scroll_reveal(header, body)
            QTimer.singleShot(0, self._update_scroll_reveal)

        def _refresh_dock_nav(self):
            rail = self._dock_nav_rail
            if rail is not None:
                rail.sync_active()

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
            app_marker = snapshot_file_marker()
            runtime_marker = runtime_file_marker()
            if app_marker != self._app_state_marker or runtime_marker != self._runtime_state_marker:
                self._reload_snapshot(force=True, app_marker=app_marker, runtime_marker=runtime_marker)

        def _reload_snapshot(
            self,
            *,
            force: bool = False,
            app_marker=None,
            runtime_marker=None,
            rebuild: bool | None = None,
        ):
            app_marker = snapshot_file_marker() if app_marker is None else app_marker
            runtime_marker = runtime_file_marker() if runtime_marker is None else runtime_marker
            if (
                not force
                and app_marker == self._app_state_marker
                and runtime_marker == self._runtime_state_marker
                and not self._defer_page_rebuild
            ):
                return
            app_changed = app_marker != self._app_state_marker
            if rebuild is None:
                on_structural_page = self._current_page not in {"Search", "Sources"}
                should_rebuild = force or (app_changed and on_structural_page)
            else:
                should_rebuild = rebuild
            action_was_idle = self._action_is_idle()
            self.snapshot = load_app_snapshot()
            self.runtime = load_runtime_snapshot()
            self._apply_command_ack()
            if action_was_idle and not self._pending_command_id:
                self._action_message = self._default_action_message()
                self._action_kind = self._default_action_kind()
            self._app_state_marker = app_marker
            self._runtime_state_marker = runtime_marker
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

        def _install_text_type_placeholder(self, field: QLineEdit, texts: tuple[str, ...]):
            effect = TextTypePlaceholder(field, texts)
            blur = BlurTextInputFeedback(field, self)
            self._text_type_effects.append(effect)
            self._typing_blur_effects.append(blur)
            return field

        def _install_scroll_reveal(self, *roots: QWidget):
            self._scroll_reveal_items = []
            for root in roots:
                for label in root.findChildren(QLabel):
                    if not self._scroll_reveal_enabled_for(label):
                        continue
                    effect = QGraphicsBlurEffect(label)
                    effect.setBlurRadius(14.0)
                    label.setGraphicsEffect(effect)
                    label.setProperty("scrollReveal", True)
                    label.setProperty("scrollRevealDone", False)
                    self._scroll_reveal_items.append((label, effect))

        def _scroll_reveal_enabled_for(self, label: QLabel):
            text = str(label.text() or "").strip()
            if not text:
                return False
            object_name = label.objectName()
            if object_name in {"sourceResultThumb", "timecode", "micro", "statusGood", "statusWarn", "coverImage"}:
                return False
            reveal_names = {
                "accent",
                "bigNumber",
                "heroTitle",
                "mono",
                "muted",
                "section",
                "title",
                "trackTitle",
                "warningAccent",
            }
            return object_name in reveal_names and len(text) > 2

        def _update_scroll_reveal(self):
            scroll = self._main_scroll
            if scroll is None or not self._scroll_reveal_items:
                return
            viewport = scroll.viewport()
            viewport_height = max(1, viewport.height())
            reveal_start = viewport_height * 0.88
            for label, effect in tuple(self._scroll_reveal_items):
                if label is None or effect is None:
                    continue
                try:
                    top = label.mapTo(viewport, label.rect().topLeft()).y()
                    bottom = label.mapTo(viewport, label.rect().bottomLeft()).y()
                except RuntimeError:
                    continue
                if bottom < -40:
                    self._finish_scroll_reveal(label, effect)
                elif top > viewport_height + 120:
                    self._reset_scroll_reveal(label, effect)
                elif top <= reveal_start and bottom >= -12:
                    self._animate_scroll_reveal(label, effect)
                else:
                    if not bool(label.property("scrollRevealDone")):
                        effect.setBlurRadius(14.0)

        def _animate_scroll_reveal(self, label: QLabel, effect: QGraphicsBlurEffect):
            if bool(label.property("scrollRevealDone")):
                return
            label.setProperty("scrollRevealDone", True)
            animation = getattr(label, "_scroll_reveal_animation", None)
            if animation is not None:
                animation.stop()
            start = max(10.0, float(effect.blurRadius()))
            animation = QVariantAnimation(label)
            animation.setStartValue(start)
            animation.setEndValue(0.0)
            animation.setDuration(680)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            animation.valueChanged.connect(lambda value, effect=effect: effect.setBlurRadius(float(value)))
            animation.finished.connect(lambda label=label: setattr(label, "_scroll_reveal_animation", None))
            label._scroll_reveal_animation = animation
            animation.start()

        def _reset_scroll_reveal(self, label: QLabel, effect: QGraphicsBlurEffect):
            if not bool(label.property("scrollRevealDone")) and effect.blurRadius() >= 13.5:
                return
            animation = getattr(label, "_scroll_reveal_animation", None)
            if animation is not None:
                animation.stop()
                label._scroll_reveal_animation = None
            label.setProperty("scrollRevealDone", False)
            effect.setBlurRadius(14.0)

        def _finish_scroll_reveal(self, label: QLabel, effect: QGraphicsBlurEffect):
            animation = getattr(label, "_scroll_reveal_animation", None)
            if animation is not None:
                animation.stop()
                label._scroll_reveal_animation = None
            label.setProperty("scrollRevealDone", True)
            effect.setBlurRadius(0.0)

        def _sync_live_widgets(self):
            if self._action_chip is not None:
                self._action_chip.setText(self._action_message)
                self._set_chip_kind(self._action_chip, self._action_kind)
            self._sync_source_status_labels()
            self._sync_source_result_cards()
            self._sync_state_timer_interval()
            self._sync_runtime_dependent_widgets()

        def _sync_runtime_dependent_widgets(self):
            for vis in self.findChildren(CyberVisualizer):
                vis.sync_runtime(self.runtime)
            if self._playerbar_seek is not None:
                self._playerbar_seek.blockSignals(True)
                self._playerbar_seek.setValue(self._runtime_progress_percent())
                self._playerbar_seek.setEnabled(self._commands_enabled() and self.runtime.duration > 0)
                self._playerbar_seek.blockSignals(False)
            if self._playerbar_time_current is not None:
                self._playerbar_time_current.setText(
                    self._format_seconds(self.runtime.position if self.runtime.is_live else 0)
                )
            if self._playerbar_time_total is not None:
                self._playerbar_time_total.setText(
                    self._format_seconds(self.runtime.duration) if self.runtime.is_live else "--:--"
                )
            if self._playerbar_play_button is not None:
                label = "PAUSE" if self.runtime.is_live and self.runtime.is_playing else "PLAY"
                self._playerbar_play_button.setText(label)
            if self._playerbar_volume_label is not None:
                self._playerbar_volume_label.setText(f"VOL {self._runtime_volume_percent():02d}")
            if self._home_seek is not None:
                self._home_seek.blockSignals(True)
                self._home_seek.setValue(self._runtime_progress_percent())
                self._home_seek.setEnabled(self._commands_enabled() and self.runtime.duration > 0)
                self._home_seek.blockSignals(False)
            if self._home_pos_time is not None:
                self._home_pos_time.setText(
                    self._format_seconds(self.runtime.position if self.runtime.is_live else 0)
                )
            if self._home_dur_time is not None:
                dur = self._format_seconds(self.runtime.duration) if self.runtime.is_live else self._now_summary().duration
                self._home_dur_time.setText(dur)
            if self._home_status_value is not None:
                self._home_status_value.setText(self._runtime_status())
            if self._home_mode_value is not None:
                self._home_mode_value.setText(self._runtime_mode())
            if self._home_telemetry_percent is not None:
                self._home_telemetry_percent.setText(f"{self._runtime_progress_percent():02d}%")
            if self._home_telemetry_link is not None:
                self._home_telemetry_link.setText(f"LINK  {self._runtime_link_label()}")
            if self._home_telemetry_source is not None:
                self._home_telemetry_source.setText(f"SOURCE  {self._runtime_mode()}")
            if self._home_telemetry_volume is not None:
                self._home_telemetry_volume.setText(f"VOLUME  {self._runtime_volume_percent():02d}%")
            if self._home_telemetry_queue is not None:
                q = self.runtime.queue_count if self.runtime.is_live else len(self.snapshot.queue_preview)
                self._home_telemetry_queue.setText(f"QUEUE  {q}")

        def _restore_scroll(self, value: int):
            if not self._main_scroll:
                return
            bar = self._main_scroll.verticalScrollBar()
            bar.setValue(max(0, min(value, bar.maximum())))

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
                "Contributors": "credit ledger for borrowed interactions, component references, and linked creators",
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
                "Contributors": self._build_contributors_page,
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
            wrapper.setObjectName("pageWrap")
            wrapper.setAutoFillBackground(False)
            grid = QGridLayout(wrapper)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            search_panel, search_layout = self._panel("Packet Search", "local vault and stream relays")
            search = QLineEdit()
            self._install_text_type_placeholder(
                search,
                (
                    "scan tracks",
                    "scan artists",
                    "scan albums",
                    "scan stream relays",
                ),
            )
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
            grid.addWidget(results_panel, 1, 0)
            grid.setColumnStretch(0, 1)
            return wrapper

        def _build_library_page(self):
            wrapper = QWidget()
            wrapper.setObjectName("pageWrap")
            wrapper.setAutoFillBackground(False)
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
            body.addWidget(self._track_grid(self.snapshot.library_preview or self._recent_summaries(), columns=2))
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
                    grid.addWidget(self._playlist_card(playlist), i // 2, i % 2)
            else:
                grid.addWidget(self._playlist_empty_card(), 0, 0)
            layout.addLayout(grid)
            return panel

        def _build_sources_page(self):
            wrapper = QWidget()
            wrapper.setObjectName("pageWrap")
            wrapper.setAutoFillBackground(False)
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
                grid.addWidget(self._source_card(source), i // 2, i % 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            layout.addLayout(grid)
            layout.addWidget(self._now_panel("Sources"))
            return wrapper

        def _build_now_playing_page(self):
            wrapper = QWidget()
            wrapper.setObjectName("pageWrap")
            wrapper.setAutoFillBackground(False)
            grid = QGridLayout(wrapper)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            grid.addWidget(self._now_panel("Now Playing"), 0, 0, 1, 2)
            grid.addWidget(self._queue_panel(), 1, 0, 1, 2)
            grid.addWidget(self._shelf_panel(), 2, 0, 1, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            return wrapper

        def _build_visualizer_page(self):
            wrapper = QWidget()
            wrapper.setObjectName("pageWrap")
            wrapper.setAutoFillBackground(False)
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
            grid.addWidget(visual, 0, 0, 1, 2)

            modes, modes_layout = self._panel("Legacy Modes", "ported visualizer language")
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="RADAR SWEEP", mode="radar"))
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="FREQUENCY RING", mode="ring"))
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="CIRCUIT LINES", mode="circuit"))
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="NODE GRAPH", mode="nodes"))
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="DATA BURST", mode="burst"))
            modes_layout.addWidget(self._visualizer_panel(minimum_height=140, title="WAVEFORM SCOPE", mode="scope"))
            grid.addWidget(modes, 1, 0, 1, 2)

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
            grid.addWidget(signal, 2, 0, 1, 2)

            grid.addWidget(self._bridge_activity_panel(), 3, 0, 1, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            return wrapper

        def _build_queue_page(self):
            wrapper = QWidget()
            wrapper.setObjectName("pageWrap")
            wrapper.setAutoFillBackground(False)
            grid = QGridLayout(wrapper)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            grid.addWidget(self._queue_panel(), 0, 0, 1, 2)
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
            grid.addWidget(controls, 1, 0, 1, 2)
            grid.addWidget(self._shelf_panel(), 2, 0, 1, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            return wrapper

        def _build_settings_page(self):
            wrapper = QWidget()
            wrapper.setObjectName("pageWrap")
            wrapper.setAutoFillBackground(False)
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
                ("Target Cursor", self._target_cursor_state()),
            )
            for i, (label, value) in enumerate(cards):
                grid.addWidget(self._settings_card(label, value), i // 2, i % 2)

            grid.addWidget(self._interface_modes_panel(), 4, 0, 1, 2)

            state, state_layout = self._panel("State Files", "read-only bridge files")
            state_layout.addWidget(self._text_line("SAVED", self.snapshot.data_file))
            state_layout.addWidget(self._text_line("RUNTIME", self.runtime.data_file))
            state_layout.addWidget(self._text_line("SYSTEM", self._system_state_text()))
            grid.addWidget(state, 5, 0, 1, 2)

            grid.addWidget(self._bridge_activity_panel(), 6, 0, 1, 2)
            return wrapper

        def _interface_modes_panel(self):
            panel, layout = self._panel("Interface Modes", "optional shell-wide visual modes")
            layout.addLayout(self._metric_row("TARGET CURSOR", self._target_cursor_state(), "DEFAULT CURSOR", "HIDDEN" if self._target_cursor_enabled else "VISIBLE"))
            hint = QLabel("Locks four cursor corners onto buttons, inputs, and sliders.")
            hint.setObjectName("muted")
            hint.setWordWrap(True)
            layout.addWidget(hint)
            row = QHBoxLayout()
            row.setSpacing(8)
            toggle = QPushButton("DISABLE TARGET CURSOR" if self._target_cursor_enabled else "ENABLE TARGET CURSOR")
            toggle.setObjectName("uvPug" if self._target_cursor_enabled else "uvStingray")
            toggle.clicked.connect(lambda _=False: self._toggle_target_cursor())
            self._target_cursor_toggle_button = toggle
            row.addWidget(toggle)
            row.addStretch(1)
            layout.addLayout(row)
            return panel

        def _target_cursor_state(self):
            return "ON" if self._target_cursor_enabled else "OFF"

        def _toggle_target_cursor(self):
            self._target_cursor_enabled = not self._target_cursor_enabled
            self._sync_target_cursor_mode()
            self._set_action_message(
                "TARGET CURSOR ON" if self._target_cursor_enabled else "TARGET CURSOR OFF",
                "live" if self._target_cursor_enabled else "stale",
            )
            if self._current_page == "Settings":
                self._set_page("Settings", record_history=False)

        def _sync_target_cursor_mode(self):
            overlay = getattr(self, "_target_cursor_overlay", None)
            if overlay is not None:
                overlay.setGeometry(self.rect())
                overlay.set_enabled(self._target_cursor_enabled)
                overlay.raise_()
            if self._target_cursor_enabled and not self._target_cursor_cursor_hidden:
                QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
                self._target_cursor_cursor_hidden = True
            elif not self._target_cursor_enabled and self._target_cursor_cursor_hidden:
                QApplication.restoreOverrideCursor()
                self._target_cursor_cursor_hidden = False
            if self._target_cursor_toggle_button is not None:
                self._target_cursor_toggle_button.setText(
                    "DISABLE TARGET CURSOR" if self._target_cursor_enabled else "ENABLE TARGET CURSOR"
                )

        def _build_contributors_page(self):
            wrapper = QWidget()
            wrapper.setObjectName("pageWrap")
            wrapper.setAutoFillBackground(False)
            grid = QGridLayout(wrapper)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            entries = self._contributors_entries()
            sources = len({entry["source"] for entry in entries})
            react_bits = sum(1 for entry in entries if entry["source"] == "React Bits")
            uiverse = sum(1 for entry in entries if entry["source"] == "UIVerse")
            magic_ui = sum(1 for entry in entries if entry["source"] == "Magic UI")
            cult_ui = sum(1 for entry in entries if entry["source"] == "Cult UI")
            intro, intro_layout = self._panel("Credit Ledger", "linked sources behind the shell's borrowed interactions")
            intro_layout.addLayout(self._metric_row("ENTRIES", str(len(entries)), "SOURCES", str(sources)))
            intro_layout.addLayout(self._metric_row("UIVERSE", str(uiverse), "REACT BITS", str(react_bits)))
            intro_layout.addLayout(self._metric_row("MAGIC UI", str(magic_ui), "CULT UI", str(cult_ui)))
            intro_layout.addWidget(self._text_line("NOTE", "new borrowed pieces land here as soon as they enter the shell"))
            grid.addWidget(intro, 0, 0, 1, 2)

            cards = QGridLayout()
            cards.setHorizontalSpacing(12)
            cards.setVerticalSpacing(12)
            for index, entry in enumerate(entries):
                cards.addWidget(self._contributor_card(entry), index // 2, index % 2)
            grid.addLayout(cards, 1, 0, 1, 2)
            return wrapper

        def _build_dashboard(self, page: str):
            wrapper = QWidget()
            wrapper.setObjectName("pageWrap")
            wrapper.setAutoFillBackground(False)
            grid = QGridLayout(wrapper)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(14)

            grid.addWidget(self._signal_strip(), 0, 0, 1, 2)
            grid.addWidget(self._threat_matrix_panel(), 1, 0, 1, 2)
            grid.addWidget(self._now_panel(page), 2, 0, 1, 2)
            grid.addWidget(self._source_panel(), 3, 0, 1, 1)
            grid.addWidget(self._queue_panel(), 3, 1, 1, 1)

            shelves = self._shelf_panel()
            grid.addWidget(shelves, 4, 0, 1, 2)

            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
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
            track.setMinimumWidth(0)
            track.setWordWrap(True)
            track.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            copy.addWidget(track)
            artist = QLabel(f"{track_data.artist} / {track_data.album}")
            artist.setObjectName("muted")
            artist.setMinimumWidth(0)
            artist.setWordWrap(True)
            artist.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            copy.addWidget(artist)
            desc = QLabel(self._caption_for(page))
            desc.setWordWrap(True)
            desc.setObjectName("muted")
            copy.addWidget(desc)
            copy.addWidget(self._visualizer_panel())
            copy.addWidget(self._playback_telemetry_panel(install_home_refs=True))
            copy.addWidget(self._divider())

            copy.addLayout(self._metric_row("SOURCE", track_data.source.upper(), "LIBRARY", str(self.snapshot.library_count)))
            copy.addLayout(self._metric_row("PLAYLISTS", str(self.snapshot.playlist_count), "REPEAT", self.snapshot.repeat_mode.upper()))
            mode = self._runtime_mode()
            status_row = QHBoxLayout()
            status_row.setSpacing(10)
            s_wrap, self._home_status_value = self._metric_with_value_ref("STATUS", self._runtime_status())
            m_wrap, self._home_mode_value = self._metric_with_value_ref("MODE", mode)
            status_row.addWidget(s_wrap)
            status_row.addWidget(m_wrap)
            copy.addLayout(status_row)
            copy.addSpacing(4)

            progress = QSlider(Qt.Horizontal)
            self._home_seek = progress
            progress.setRange(0, 100)
            progress.setValue(self._runtime_progress_percent())
            progress.setEnabled(self._commands_enabled() and self.runtime.duration > 0)
            progress.sliderReleased.connect(lambda slider=progress: self._seek_to_percent(slider.value()))
            copy.addWidget(progress)
            pos_row = QHBoxLayout()
            pos_row.setSpacing(10)
            pos_wrap, self._home_pos_time = self._metric_flipped(
                self._format_seconds(self.runtime.position if self.runtime.is_live else 0),
                "POSITION",
            )
            dur_wrap, self._home_dur_time = self._metric_flipped(
                self._format_seconds(self.runtime.duration) if self.runtime.is_live else track_data.duration,
                "DURATION",
            )
            pos_row.addWidget(pos_wrap)
            pos_row.addWidget(dur_wrap)
            copy.addLayout(pos_row)
            copy.addStretch(1)

            layout.addLayout(copy, 1)
            return panel

        def _art_panel(self, track: TrackSummary):
            art = QFrame()
            art.setObjectName("art")
            art.setFixedSize(188, 188)
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
                        142,
                        142,
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
                cards.addWidget(self._track_card(track), i // 2, i % 2)
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
            title.setMinimumWidth(0)
            title.setWordWrap(True)
            title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            info.addWidget(title)
            artist = QLabel(f"{track_data.artist.upper()} // {track_data.source.upper()}")
            artist.setObjectName("micro")
            artist.setMinimumWidth(0)
            artist.setWordWrap(True)
            artist.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            info.addWidget(artist)
            info.addWidget(self._mini_meter((10, 26, 18, 34, 22, 30, 14, 38)))
            layout.addLayout(info, 1)

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
                if action == "toggle_play":
                    self._playerbar_play_button = btn
            layout.addLayout(controls)

            current = QLabel(self._format_seconds(self.runtime.position if self.runtime.is_live else 0))
            current.setObjectName("timecode")
            self._playerbar_time_current = current
            layout.addWidget(current)

            progress = QSlider(Qt.Horizontal)
            self._playerbar_seek = progress
            progress.setRange(0, 100)
            progress.setValue(self._runtime_progress_percent())
            progress.setEnabled(commands_enabled and self.runtime.duration > 0)
            progress.sliderReleased.connect(lambda slider=progress: self._seek_to_percent(slider.value()))
            layout.addWidget(progress, 1)

            total = QLabel(self._format_seconds(self.runtime.duration) if self.runtime.is_live else "--:--")
            total.setObjectName("timecode")
            self._playerbar_time_total = total
            layout.addWidget(total)

            volume_label = QLabel(f"VOL {self._runtime_volume_percent():02d}")
            volume_label.setObjectName("timecode")
            self._playerbar_volume_label = volume_label
            layout.addWidget(volume_label)

            volume = ElasticSlider()
            volume.setFixedWidth(156)
            volume.setRange(0, 100)
            volume.setValue(self._runtime_volume_percent())
            volume.setEnabled(True)
            volume.valueChanged.connect(lambda value, label=volume_label: label.setText(f"VOL {int(value):02d}"))
            volume.elasticReleased.connect(self._set_volume_percent)
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
                grid.addWidget(self._track_card(track), i // 2, i % 2)

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
            self._install_text_type_placeholder(
                query,
                (
                    "type a song",
                    "type an artist",
                    "type a mix",
                    "type an archive title",
                ),
            )
            query.setText(self._source_query)
            query.textChanged.connect(lambda text: setattr(self, "_source_query", str(text or "")))
            query.returnPressed.connect(lambda field=query: self._source_search("youtube", field.text()))
            layout.addWidget(query)

            actions = QGridLayout()
            actions.setContentsMargins(0, 0, 0, 0)
            actions.setHorizontalSpacing(10)
            actions.setVerticalSpacing(10)
            for index, (label, view_key, code, detail) in enumerate(
                (
                    ("SoundCloud", "soundcloud", "SC", "send the query to the legacy SoundCloud tab"),
                    ("YouTube", "youtube", "YT", "open YouTube search through the running player bridge"),
                    ("Archive", "archive", "IA", "scan Internet Archive records and browse source results"),
                )
            ):
                btn = SourceFamilyButton(view_key, label, code, detail)
                btn.setEnabled(self._commands_enabled())
                btn.clicked.connect(lambda _=False, key=view_key, field=query: self._source_search(key, field.text()))
                actions.addWidget(btn, 0, index)
            for column in range(3):
                actions.setColumnStretch(column, 1)
            layout.addLayout(actions)
            hint = QLabel("Press Enter for YouTube, or expand a source tile and click.")
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
                grid.addWidget(card, index // 2, index % 2)
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

        def _contributors_entries(self):
            return CONTRIBUTOR_ENTRIES

        def _contributor_card(self, entry: dict[str, str]):
            card = QFrame()
            card.setObjectName("card")
            card.setMinimumHeight(164)
            layout = QVBoxLayout(card)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(8)

            badge = QLabel(entry["source"].upper())
            badge.setObjectName("accent")
            layout.addWidget(badge)

            title = QLabel(entry["component"])
            title.setObjectName("trackTitle")
            title.setWordWrap(True)
            layout.addWidget(title)

            creator = QLabel(f"BY {entry['creator']}")
            creator.setObjectName("micro")
            layout.addWidget(creator)

            usage = QLabel(entry["usage"])
            usage.setObjectName("muted")
            usage.setWordWrap(True)
            layout.addWidget(usage)

            domain = QLabel(entry["link"].replace("https://", ""))
            domain.setObjectName("micro")
            domain.setWordWrap(True)
            layout.addWidget(domain)

            row = QHBoxLayout()
            row.setSpacing(8)
            state = QLabel("CREDITED")
            state.setObjectName("statusGood")
            row.addWidget(state)
            row.addStretch(1)

            open_link = QPushButton("OPEN LINK")
            open_link.setObjectName("uvStingray")
            open_link.clicked.connect(lambda _=False, url=entry["link"]: self._open_external_link(url))
            row.addWidget(open_link)
            layout.addLayout(row)
            return card

        def _text_line(self, label: str, value: str):
            text = QLabel(f"{label}  {value}")
            text.setObjectName("micro")
            text.setWordWrap(True)
            return text

        def _chip(self, text: str, kind: str = ""):
            chip = QLabel(text)
            chip.setMinimumWidth(0)
            chip.setWordWrap(True)
            chip.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
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
            return CRTScanlineStrip()

        def _metric_row(self, left_label: str, left_value: str, right_label: str, right_value: str):
            row = QHBoxLayout()
            row.setSpacing(10)
            row.addWidget(self._metric(left_label, left_value))
            row.addWidget(self._metric(right_label, right_value))
            return row

        def _metric(self, label: str, value: str):
            wrap = QWidget()
            wrap.setMinimumWidth(0)
            layout = QVBoxLayout(wrap)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            l = QLabel(label)
            l.setObjectName("micro")
            layout.addWidget(l)
            v = QLabel(value)
            v.setObjectName("mono")
            v.setMinimumWidth(0)
            v.setWordWrap(True)
            v.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            layout.addWidget(v)
            return wrap

        def _metric_with_value_ref(self, label: str, value: str):
            wrap = QWidget()
            wrap.setMinimumWidth(0)
            layout = QVBoxLayout(wrap)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            l = QLabel(label)
            l.setObjectName("micro")
            layout.addWidget(l)
            v = QLabel(value)
            v.setObjectName("mono")
            v.setMinimumWidth(0)
            v.setWordWrap(True)
            v.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            layout.addWidget(v)
            return wrap, v

        def _metric_flipped(self, value_top: str, caption_bottom: str):
            wrap = QWidget()
            wrap.setMinimumWidth(0)
            layout = QVBoxLayout(wrap)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            top = QLabel(value_top)
            top.setObjectName("micro")
            layout.addWidget(top)
            bottom = QLabel(caption_bottom)
            bottom.setObjectName("mono")
            bottom.setMinimumWidth(0)
            bottom.setWordWrap(True)
            bottom.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            layout.addWidget(bottom)
            return wrap, top

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

        def _playback_telemetry_panel(self, *, install_home_refs: bool = False):
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
            link_line = self._telemetry_line("LINK", self._runtime_link_label())
            source_line = self._telemetry_line("SOURCE", self._runtime_mode())
            vol_line = self._telemetry_line("VOLUME", f"{self._runtime_volume_percent():02d}%")
            queue_line = self._telemetry_line(
                "QUEUE",
                str(self.runtime.queue_count if self.runtime.is_live else len(self.snapshot.queue_preview)),
            )
            facts.addWidget(link_line)
            facts.addWidget(source_line)
            facts.addWidget(vol_line)
            facts.addWidget(queue_line)
            layout.addLayout(facts)
            if install_home_refs:
                self._home_telemetry_percent = percent
                self._home_telemetry_link = link_line
                self._home_telemetry_source = source_line
                self._home_telemetry_volume = vol_line
                self._home_telemetry_queue = queue_line
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
            row = QGridLayout()
            row.setHorizontalSpacing(8)
            row.setVerticalSpacing(8)
            for index, mode in enumerate(("spectrum", "scope", "ring", "radar", "circuit", "nodes", "burst")):
                btn = QPushButton(mode.upper())
                btn.setObjectName("uvSloth" if mode == self._visualizer_mode else "uvDragonfly")
                btn.clicked.connect(lambda _=False, mode=mode: self._set_visualizer_mode(mode))
                row.addWidget(btn, index // 4, index % 4)
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
            name.setMinimumWidth(0)
            row.addWidget(name, 1)
            status = QLabel(value)
            status.setObjectName("statusGood" if healthy else "statusWarn")
            status.setMinimumWidth(0)
            status.setWordWrap(True)
            status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
            subtitle = QLabel("VAULT / STREAMS / QUEUE / CORE")
            subtitle.setObjectName("micro")
            subtitle.setWordWrap(True)
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
            state.setMinimumWidth(0)
            state.setWordWrap(True)
            state.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
            cell.setFixedWidth(82)
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

        def _open_external_link(self, url: str):
            qurl = QUrl(url)
            if not qurl.isValid() or qurl.scheme() not in {"http", "https"}:
                self._set_action_message("CREDIT LINK INVALID", "stale")
                return
            if QDesktopServices.openUrl(qurl):
                self._set_action_message("CREDIT LINK OPEN", "live")
            else:
                self._set_action_message("CREDIT LINK FAILED", "stale")

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

