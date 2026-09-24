import hashlib
import sys
import time
import urllib.request
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

sys.path.insert(0, str(Path(__file__).parent))
import flow_api

CACHE_DIR = Path(__file__).parent / ".thumb_cache"
WIDGET_SIZE = 120
POLL_MS = 1000


class CircularThumbnail(QWidget):
    """Frameless always-on-top circular artwork window."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(WIDGET_SIZE, WIDGET_SIZE)
        self._pixmap: QPixmap | None = None
        self._drag_pos: QPoint | None = None
        self._last_title = ""
        self._placeholder = self._make_placeholder()

    def _make_placeholder(self) -> QPixmap:
        pm = QPixmap(WIDGET_SIZE, WIDGET_SIZE)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(40, 40, 50))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, WIDGET_SIZE - 4, WIDGET_SIZE - 4)
        p.setPen(QColor(100, 100, 110))
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "♫")
        p.end()
        return pm

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pm = self._pixmap if self._pixmap else self._placeholder

        clip = QPainterPath()
        clip.addEllipse(2, 2, WIDGET_SIZE - 4, WIDGET_SIZE - 4)
        painter.setClipPath(clip)

        x = (WIDGET_SIZE - pm.width()) // 2
        y = (WIDGET_SIZE - pm.height()) // 2
        painter.drawPixmap(x, y, pm)

        painter.setClipping(False)
        painter.setPen(QColor(60, 60, 70, 180))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(2, 2, WIDGET_SIZE - 4, WIDGET_SIZE - 4)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
        elif event.button() == Qt.MouseButton.RightButton:
            QApplication.quit()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, _event):
        self._drag_pos = None

    def _load_thumb(self, source: str):
        CACHE_DIR.mkdir(exist_ok=True)

        if source.startswith("http://") or source.startswith("https://"):
            h = hashlib.md5(source.encode()).hexdigest()
            cache_file = CACHE_DIR / f"{h}.jpg"
            if not cache_file.exists():
                try:
                    urllib.request.urlretrieve(source, str(cache_file))
                except Exception:
                    return
            source = str(cache_file)

        pm = QPixmap(source)
        if pm.isNull():
            return

        self._pixmap = pm.scaled(
            WIDGET_SIZE,
            WIDGET_SIZE,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.update()

    def poll(self):
        track = flow_api.current_track()
        title = track.get("title", "")
        playing = track.get("playing", False)
        thumb = track.get("thumbnail", "")

        if not playing or not thumb:
            if self._pixmap is not None:
                self._pixmap = None
                self.update()
            self._last_title = ""
            return

        if title != self._last_title:
            self._last_title = title
            self._load_thumb(thumb)


def main():
    app = QApplication(sys.argv)
    widget = CircularThumbnail()
    widget.show()

    timer = QTimer()
    timer.timeout.connect(widget.poll)
    timer.start(POLL_MS)
    widget.poll()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
