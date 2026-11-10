"""กล่องแสดงผลแปล — ลอยเหนือเกม, คลิกทะลุได้, ไม่แย่งโฟกัสจากเกม"""
from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ResultOverlay(QWidget):
    def __init__(self, timeout_ms: int = 8000, font_px: int = 18):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
            | Qt.WindowType.WindowTransparentForInput  # คลิกทะลุไปที่เกม
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._label = QLabel()
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            f"""
            QLabel {{
                background-color: rgba(20, 20, 28, 225);
                color: #FFFFFF;
                border: 1px solid rgba(0, 229, 255, 160);
                border-radius: 10px;
                padding: 10px 14px;
                font-size: {font_px}px;
            }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self._timeout_ms = timeout_ms

    def show_text(self, text: str, anchor: QRect, persistent: bool = False) -> None:
        """แสดงข้อความใกล้กรอบ anchor (พิกัด global) — persistent=True คือไม่ซ่อนอัตโนมัติ"""
        self._label.setText(text)
        self._label.setMaximumWidth(max(anchor.width(), 380))
        self.adjustSize()

        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()

        x = min(max(anchor.left(), geo.left()), geo.right() - self.width())
        y = anchor.bottom() + 8
        if y + self.height() > geo.bottom():  # ไม่พอข้างล่าง → ย้ายไปไว้เหนือกรอบ
            y = anchor.top() - self.height() - 8
        y = min(max(y, geo.top()), geo.bottom() - self.height())

        self.move(x, y)
        self.show()
        self.raise_()

        self._timer.stop()
        if not persistent:
            self._timer.start(self._timeout_ms)