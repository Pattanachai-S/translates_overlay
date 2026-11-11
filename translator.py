"""Translators — interface กลาง + Google ฟรี (มี retry / fallback / cache)

GoogleFreeTranslator จะลองตามลำดับนี้ ตัวไหนโดน 429 หรือพัง จะข้ามไปตัวถัดไปเอง:
  1. translate.googleapis.com (client=gtx)  — endpoint เบา โดนจำกัดน้อยกว่า
  2. deep-translator (translate.google.com/m)
  3. MyMemory — ผู้ให้บริการคนละเจ้า ใช้เมื่อ Google จำกัด IP ของเรา

ภายหลังเพิ่ม AITranslator (Claude/GPT ฯลฯ) ได้โดย subclass Translator
"""
from __future__ import annotations

import html
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict

import requests

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_TIMEOUT = 8  # วินาที


class Translator(ABC):
    @abstractmethod
    def translate(self, text: str, src: str, dst: str) -> str:
        """แปลข้อความจากภาษา src เป็น dst"""


class RateLimitedError(Exception):
    """ผู้ให้บริการจำกัดความถี่ (HTTP 429)"""


def _check(resp: requests.Response) -> None:
    if resp.status_code == 429:
        raise RateLimitedError("HTTP 429")
    resp.raise_for_status()


def _chunks(text: str, limit: int):
    """แบ่งข้อความยาวเป็นท่อนไม่เกิน limit ตัวอักษร (ตัดที่ช่องว่างถ้ามี)"""
    text = text.strip()
    while len(text) > limit:
        cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        yield text[:cut]
        text = text[cut:].lstrip()
    if text:
        yield text


# ---------- providers: (text, src, dst) -> translated ----------

def _google_gtx(text: str, src: str, dst: str) -> str:
    resp = requests.get(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": src, "tl": dst, "dt": "t", "q": text},
        headers={"User-Agent": _UA},
        timeout=_TIMEOUT,
    )
    _check(resp)
    data = resp.json()
    return "".join(seg[0] for seg in data[0] if seg and seg[0])


def _google_deep(text: str, src: str, dst: str) -> str:
    from deep_translator import GoogleTranslator
    from deep_translator.exceptions import TooManyRequests

    try:
        return GoogleTranslator(source=src, target=dst).translate(text)
    except TooManyRequests as exc:
        raise RateLimitedError(str(exc)) from exc


def _mymemory(text: str, src: str, dst: str) -> str:
    pair = f"{'Autodetect' if src == 'auto' else src}|{dst}"
    resp = requests.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text, "langpair": pair},
        headers={"User-Agent": _UA},
        timeout=_TIMEOUT,
    )
    _check(resp)
    data = resp.json()
    status = str(data.get("responseStatus"))
    if status == "429":
        raise RateLimitedError("MyMemory 429")
    if status != "200":
        raise RuntimeError(data.get("responseDetails") or f"MyMemory status {status}")
    return html.unescape(data["responseData"]["translatedText"])


_RETRYABLE = (RateLimitedError, requests.Timeout, requests.ConnectionError)


class GoogleFreeTranslator(Translator):
    """Google Translate ฟรีแบบไม่เป็นทางการ + ช่องทางสำรอง

    cooldown: โดน 429 แล้วพักตัวนั้นกี่วินาที (ระหว่างพักจะข้ามไปใช้ตัวสำรองเลย ไม่เสียเวลารอ)
    """

    def __init__(self, retries: int = 1, backoff: float = 0.8,
                 cooldown: float = 60.0, cache_size: int = 128):
        # (ชื่อ, ฟังก์ชัน, ความยาวสูงสุดต่อ request)
        self._providers = [
            ("Google (gtx)", _google_gtx, 800),
            ("Google (deep-translator)", _google_deep, 4500),
            ("MyMemory", _mymemory, 450),
        ]
        self._retries, self._backoff, self._cooldown = retries, backoff, cooldown
        self._blocked_until: dict[str, float] = {}
        self._cache: OrderedDict[tuple, str] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()

    def translate(self, text: str, src: str, dst: str) -> str:
        text = text.strip()
        key = (text, src, dst)

        with self._lock:
            if key in self._cache:  # ข้อความเดิม ไม่ต้องยิงซ้ำ
                self._cache.move_to_end(key)
                return self._cache[key]
            now = time.monotonic()
            candidates = [p for p in self._providers
                          if self._blocked_until.get(p[0], 0) <= now]
            if not candidates:  # พักครบทุกตัว → ลองใหม่หมดดีกว่าไม่ลองเลย
                candidates = list(self._providers)

        errors: list[str] = []
        for name, fn, limit in candidates:
            try:
                result = self._call(fn, text, src, dst, limit)
            except RateLimitedError:
                with self._lock:
                    self._blocked_until[name] = time.monotonic() + self._cooldown
                errors.append(f"{name}: โดนจำกัดความถี่ (429)")
                continue
            except Exception as exc:  # noqa: BLE001 — ลองตัวถัดไป
                errors.append(f"{name}: {type(exc).__name__}: {exc}")
                continue

            with self._lock:
                self._cache[key] = result
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
            return result

        raise RuntimeError("แปลไม่สำเร็จ — " + " | ".join(errors))

    def _call(self, fn, text: str, src: str, dst: str, limit: int) -> str:
        parts = []
        for piece in _chunks(text, limit):
            for attempt in range(self._retries + 1):
                try:
                    parts.append(fn(piece, src, dst))
                    break
                except _RETRYABLE:
                    if attempt >= self._retries:
                        raise
                    time.sleep(self._backoff * (attempt + 1))
        result = " ".join(p.strip() for p in parts if p and p.strip())
        if not result:
            raise RuntimeError("ผลลัพธ์ว่าง")
        return result