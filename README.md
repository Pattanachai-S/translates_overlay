# translates_overlay
Windows overlay app that translates in-game

## Tech Stack

| Purpose | Tool |
|---|---|
| Language | Python 3.10+ |
| GUI | PySide6  |
| Screen capture | `mss` |
| OCR | Windows OCR |
| Translate (MVP) | deep-translator (Google) |
| Global hotkey | `keyboard` |


Phase 1 (MVP): Hotkey → Select an area by dragging → Capture screenshot → OCR → Translate to Thai using Google Translate → Display the result in an overlay.