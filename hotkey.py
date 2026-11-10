"""Global hotkey — callback ของ `keyboard` ทำงานคนละ thread กับ Qt
จึงส่งต่อผ่าน Signal เท่านั้น (ห้ามแตะ GUI ใน callback ตรงๆ)
"""
import keyboard
from PySide6.QtCore import QObject, Signal


class HotkeyManager(QObject):
    triggered = Signal(str)  # ส่งชื่อ action ที่ลงทะเบียนไว้

    def __init__(self, parent=None):
        super().__init__(parent)
        self._handles = []

    def register(self, name: str, combo: str) -> None:
        handle = keyboard.add_hotkey(combo, lambda n=name: self.triggered.emit(n))
        self._handles.append(handle)

    def unregister_all(self) -> None:
        for handle in self._handles:
            try:
                keyboard.remove_hotkey(handle)
            except (KeyError, ValueError):
                pass
        self._handles.clear()