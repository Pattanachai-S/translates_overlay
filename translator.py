"""Translators — interface กลาง + Google (deep-translator)

ภายหลังเพิ่ม AITranslator (Claude/GPT ฯลฯ) ได้โดย subclass Translator
"""
from abc import ABC, abstractmethod


class Translator(ABC):
    @abstractmethod
    def translate(self, text: str, src: str, dst: str) -> str:
        """แปลข้อความจากภาษา src เป็น dst"""


class GoogleFreeTranslator(Translator):
    """Google Translate แบบไม่เป็นทางการ (ฟรี แต่ยิงถี่เกินอาจโดนบล็อกชั่วคราว)"""

    def translate(self, text: str, src: str, dst: str) -> str:
        from deep_translator import GoogleTranslator

        return GoogleTranslator(source=src, target=dst).translate(text)