"""จับภาพหน้าจอ + preprocess ก่อนส่ง OCR

หมายเหตุ: ต้องเรียกหลังสร้าง QApplication แล้ว เพื่อให้โปรเซสเป็น DPI-aware
(Qt6 ตั้งให้เอง) ไม่งั้น mss อาจได้พิกัดที่ถูกย่อตาม DPI scaling
"""
import mss
from PIL import Image, ImageOps


def grab_primary_monitor() -> Image.Image:
    """จับภาพจอหลักทั้งจอ (physical pixels) เป็น PIL Image (RGB)"""
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # 0 = ทุกจอรวมกัน, 1 = จอหลัก
        shot = sct.grab(monitor)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def preprocess_for_ocr(img: Image.Image, scale: int = 2) -> Image.Image:
    """ขยาย + ขาวดำ + ปรับ contrast ให้ OCR อ่านง่ายขึ้น"""
    gray = img.convert("L")
    if scale > 1:
        gray = gray.resize(
            (gray.width * scale, gray.height * scale),
            Image.Resampling.LANCZOS,
        )
    return ImageOps.autocontrast(gray)