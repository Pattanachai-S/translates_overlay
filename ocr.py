"""OCR engines — interface กลาง + Windows OCR (winsdk)

เพิ่ม engine ใหม่ (RapidOCR, Cloud Vision ฯลฯ) ได้โดย subclass OCREngine
"""
import asyncio
import io
from abc import ABC, abstractmethod

from PIL import Image


class OCREngine(ABC):
    @abstractmethod
    def read(self, image: Image.Image) -> str:
        """รับภาพ คืนข้อความที่อ่านได้"""


class WindowsOCR(OCREngine):
    def __init__(self, lang: str = "en-US"):
        self.lang = lang

    def read(self, image: Image.Image) -> str:
        # เรียกจาก worker thread เท่านั้น (ห้ามเรียกจาก thread ของ Qt)
        return asyncio.run(self._read_async(image))

    async def _read_async(self, image: Image.Image) -> str:
        # import ตรงนี้ เพื่อให้โมดูลนี้ถูก import ได้แม้ไม่ใช่ Windows
        from winrt.windows.globalization import Language
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import (
            DataWriter,
            InMemoryRandomAccessStream,
        )

        engine = OcrEngine.try_create_from_language(Language(self.lang))
        if engine is None:
            available = [
                lang.language_tag for lang in OcrEngine.available_recognizer_languages
            ]
            raise RuntimeError(
                f"Windows OCR ไม่รองรับภาษา '{self.lang}' ในเครื่องนี้ "
                f"(ติดตั้ง language pack ใน Settings > Time & Language > Language) "
                f"ภาษาที่มี: {available}"
            )

        # Windows OCR จำกัดขนาดภาพสูงสุด ถ้าใหญ่เกินให้ย่อลง
        max_dim = OcrEngine.max_image_dimension
        if max(image.size) > max_dim:
            ratio = max_dim / max(image.size)
            image = image.resize(
                (int(image.width * ratio), int(image.height * ratio)),
                Image.Resampling.LANCZOS,
            )

        buf = io.BytesIO()
        image.save(buf, format="PNG")

        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(buf.getvalue())
        await writer.store_async()
        await writer.flush_async()
        writer.detach_stream()
        stream.seek(0)

        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(bitmap)
        return result.text