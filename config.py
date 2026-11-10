"""ตั้งค่าหลักของแอป — แก้ที่นี่ที่เดียว"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # ปุ่มลัด (รูปแบบของไลบรารี `keyboard`)
    hotkey_translate: str = "ctrl+shift+t"
    hotkey_quit: str = "ctrl+shift+q"

    # ภาษาสำหรับ Windows OCR (language tag ของ Windows) เช่น "en-US", "ja", "ko", "zh-Hans-CN"
    # ต้องติดตั้ง language pack นั้นใน Windows ก่อน
    ocr_lang: str = "en-US"

    # ภาษาสำหรับ Google Translate (deep-translator) — src ใช้ "auto" ได้
    src_lang: str = "en"
    dst_lang: str = "th"

    # ขยายภาพก่อนส่ง OCR (ช่วยให้อ่านฟอนต์เล็กแม่นขึ้น)
    ocr_upscale: int = 2

    # Overlay ผลแปล
    overlay_timeout_ms: int = 8000
    overlay_font_px: int = 18