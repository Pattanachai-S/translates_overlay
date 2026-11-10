"""LingoLens MVP — hotkey → ลากเลือกพื้นที่ → OCR → แปล → overlay

รัน:  python main.py
ออก:  Ctrl+Shift+Q (หรือ Ctrl+C ในหน้าต่างคอนโซล)
"""
import signal
import sys

from PySide6.QtCore import QObject, QRect, QRunnable, QThreadPool, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from capture import grab_primary_monitor, preprocess_for_ocr
from config import Config
from hotkey import HotkeyManager
from ocr import OCREngine, WindowsOCR
from region_selector import RegionSelector
from result_overlay import ResultOverlay
from translator import GoogleFreeTranslator, Translator


class TaskSignals(QObject):
    done = Signal(str, object)    # (ข้อความที่แปลแล้ว, anchor)
    failed = Signal(str, object)  # (ข้อความ error, anchor)


class PipelineTask(QRunnable):
    """OCR + แปล ทำใน worker thread เพื่อไม่ให้ UI/เกมค้าง"""

    def __init__(self, image, anchor, ocr: OCREngine, translator: Translator,
                 cfg: Config, signals: TaskSignals):
        super().__init__()
        self.image, self.anchor = image, anchor
        self.ocr, self.translator = ocr, translator
        self.cfg, self.signals = cfg, signals

    def run(self):
        try:
            prepared = preprocess_for_ocr(self.image, self.cfg.ocr_upscale)
            text = " ".join(self.ocr.read(prepared).split())  # รวมบรรทัดเป็นประโยคเดียว
            if not text:
                raise ValueError("อ่านข้อความไม่เจอ ลองเลือกพื้นที่ให้ครอบตัวหนังสือพอดีขึ้น")
            translated = self.translator.translate(text, self.cfg.src_lang, self.cfg.dst_lang)
            self.signals.done.emit(translated, self.anchor)
        except Exception as exc:  # noqa: BLE001 — แสดง error ให้ผู้ใช้เห็นแทนที่จะเงียบ
            self.signals.failed.emit(f"{type(exc).__name__}: {exc}", self.anchor)


class Controller(QObject):
    def __init__(self, app: QApplication, cfg: Config):
        super().__init__()
        self.app, self.cfg = app, cfg

        # ← จุดสลับ engine: เปลี่ยนสองบรรทัดนี้เมื่อเพิ่ม OCR/AI ตัวใหม่
        self.ocr: OCREngine = WindowsOCR(cfg.ocr_lang)
        self.translator: Translator = GoogleFreeTranslator()

        self.overlay = ResultOverlay(cfg.overlay_timeout_ms, cfg.overlay_font_px)
        self.pool = QThreadPool.globalInstance()
        self.signals = TaskSignals()
        self.signals.done.connect(self._on_done)
        self.signals.failed.connect(self._on_failed)

        self._selector: RegionSelector | None = None
        self._selecting = False  # กันกด hotkey ซ้ำระหว่างรอ/กำลังเลือก

        self.hotkeys = HotkeyManager(self)
        self.hotkeys.triggered.connect(self._on_hotkey)
        self.hotkeys.register("translate", cfg.hotkey_translate)
        self.hotkeys.register("quit", cfg.hotkey_quit)

    # --- hotkey ---
    def _on_hotkey(self, name: str):
        if name == "quit":
            self.hotkeys.unregister_all()
            self.app.quit()
        elif name == "translate" and not self._selecting:
            self._selecting = True
            self.overlay.hide()  # ซ่อนผลเก่า จะได้ไม่ติดไปในภาพที่จับ
            QTimer.singleShot(80, self._open_selector)

    def _open_selector(self):
        shot = grab_primary_monitor()
        screen = QGuiApplication.primaryScreen()
        selector = RegionSelector(shot, screen)
        selector.selected.connect(self._on_selected)
        selector.closed.connect(self._on_selector_closed)
        self._selector = selector
        selector.open()

    def _on_selector_closed(self):
        if self._selector is not None:
            self._selector.deleteLater()
        self._selector = None
        self._selecting = False

    # --- pipeline ---
    def _on_selected(self, image, anchor: QRect):
        self.overlay.show_text("กำลังแปล…", anchor, persistent=True)
        task = PipelineTask(image, anchor, self.ocr, self.translator, self.cfg, self.signals)
        self.pool.start(task)

    def _on_done(self, translated: str, anchor: QRect):
        self.overlay.show_text(translated, anchor)

    def _on_failed(self, message: str, anchor: QRect):
        self.overlay.show_text(f"⚠️ {message}", anchor)


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # overlay ปิด/ซ่อนบ่อย ห้ามให้แอปจบเอง

    # ให้ Ctrl+C ในคอนโซลใช้ได้ (Qt event loop จะกลืนสัญญาณถ้าไม่มี timer คอยปลุก)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    wake = QTimer()
    wake.start(300)
    wake.timeout.connect(lambda: None)

    cfg = Config()
    controller = Controller(app, cfg)  # noqa: F841 — ต้องถือ reference ไว้
    print(f"LingoLens พร้อมแล้ว — {cfg.hotkey_translate} = แปล, {cfg.hotkey_quit} = ออก")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())