"""Overlay เต็มจอให้ลากเลือกพื้นที่ (freeze frame แบบ Snipping Tool)"""
from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget


def pil_to_qimage(img: Image.Image) -> QImage:
    rgb = img.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimg = QImage(
        data, rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888
    )
    return qimg.copy()  # copy เพื่อไม่ให้ผูกกับ buffer ของ data


class RegionSelector(QWidget):
    # (ภาพที่ crop แล้ว, กรอบที่เลือกในพิกัด global แบบ logical ของ Qt)
    selected = Signal(object, object)
    cancelled = Signal()
    closed = Signal()

    def __init__(self, screenshot: Image.Image, screen):
        super().__init__()
        self._shot = screenshot
        self._qimg = pil_to_qimage(screenshot)
        self._origin: QPoint | None = None
        self._rect = QRect()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setGeometry(screen.geometry())

    # --- แสดงผล ---
    def open(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def paintEvent(self, _event):
        p = QPainter(self)
        # พื้นหลัง = ภาพที่จับไว้ (ย่อ/ขยายให้พอดี logical size → รองรับ DPI scaling)
        p.drawImage(self.rect(), self._qimg)
        p.fillRect(self.rect(), QColor(0, 0, 0, 110))

        if not self._rect.isNull():
            r = self._rect.normalized()
            p.setClipRect(r)
            p.drawImage(self.rect(), self._qimg)  # ส่วนที่เลือกให้สว่างเหมือนเดิม
            p.setClipping(False)
            p.setPen(QPen(QColor("#00E5FF"), 2))
            p.drawRect(r)

        p.setPen(QColor("white"))
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        p.setFont(font)
        p.drawText(24, 36, "ลากเพื่อเลือกพื้นที่  •  Esc / คลิกขวา = ยกเลิก")

    # --- เมาส์ / คีย์บอร์ด ---
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self._cancel()
        elif e.button() == Qt.MouseButton.LeftButton:
            self._origin = e.position().toPoint()
            self._rect = QRect(self._origin, self._origin)
            self.update()

    def mouseMoveEvent(self, e):
        if self._origin is not None:
            self._rect = QRect(self._origin, e.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        self._origin = None
        r = self._rect.normalized()
        if r.width() < 8 or r.height() < 8:
            self._cancel()
            return

        # logical → physical pixel (คิดจากอัตราส่วนจริงของภาพ จึงถูกต้องทุก DPI scale)
        sx = self._shot.width / self.width()
        sy = self._shot.height / self.height()
        box = (
            round(r.left() * sx),
            round(r.top() * sy),
            round((r.left() + r.width()) * sx),
            round((r.top() + r.height()) * sy),
        )
        crop = self._shot.crop(box)
        anchor = QRect(self.mapToGlobal(r.topLeft()), r.size())
        self.selected.emit(crop, anchor)
        self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self._cancel()

    def _cancel(self):
        self.cancelled.emit()
        self.close()

    def closeEvent(self, e):
        self.closed.emit()
        super().closeEvent(e)