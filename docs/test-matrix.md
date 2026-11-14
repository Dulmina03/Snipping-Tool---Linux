# Baseline Test Matrix — Execute on Ubuntu with Codex

**Test environment:** NOT RECORDED. All rows start **NOT RUN** until Codex actually runs them in the local project.

| ID | Test | How | Status | Notes / evidence |
|---|---|---|---|---|
| E01 | Python/Qt dependencies | `python --version`; `python -m pip check` | NOT RUN | |
| E02 | Source syntax | `python -m compileall -q main.py capture ui ocr shortcuts utils` | NOT RUN | |
| E03 | Desktop session | `echo $XDG_SESSION_TYPE`; `echo $XDG_CURRENT_DESKTOP` | NOT RUN | |
| E04 | Tesseract languages | `tesseract --version`; `tesseract --list-langs` | NOT RUN | Confirm `eng`, `sin` |
| C01 | Full-screen screenshot | `python test_screenshot.py` | NOT RUN | Opens portal; interactive environment |
| C02 | Selected region | `python test_area.py` | NOT RUN | Drag a region; inspect crop |
| C03 | Window capture | `python test_window.py` | NOT RUN | Choose window in portal |
| C04 | Actual global shortcut | `python main.py`, then physically Ctrl+Shift+S while another app is focused | NOT RUN | Signal-emission tests do not count |
| C05 | Clipboard image | `python test_clipboard.py` | NOT RUN | Paste in at least one other GUI app |
| C06 | English OCR | `python test_ocr.py PATH_TO_ENGLISH_FIXTURE.png` | NOT RUN | Compare to reference text, not merely nonempty |
| C07 | Sinhala OCR | to be built | NOT RUN | Required labeled Sinhala sample and CER/WER |
| C08 | Mixed Sinhala/English OCR | to be built | NOT RUN | Required labeled mixed sample and CER/WER |
| C09 | OCR clipboard | `python test_ocr.py PATH_TO_FIXTURE.png` | NOT RUN | Unicode copy/paste |
| C10 | Tray/background/quit | `python main.py` | NOT RUN | Check tray, close, no duplicate process |
| C11 | Cancel / deny portal | manual with `python main.py` | NOT RUN | No stray outputs or stuck overlay |
| C12 | Multi-monitor / mixed DPI | manual with two monitors if available | NOT RUN | Check offsets/scaling; mark unavailable if no hardware |
| C13 | Fast repeated screenshots | manual capture several times in one second | NOT RUN | No overwritten output |
| D01 | Text-layer PDF | feature not implemented | NOT RUN | Future Phase 4/6 |
| D02 | Scanned PDF Sinhala/English | feature not implemented | NOT RUN | Future Phase 5/6 |
| D03 | JPEG/PNG/WebP/BMP/TIFF input | feature incomplete | NOT RUN | Future import compatibility matrix |
| R01 | Package installation | feature incomplete | NOT RUN | Future Phase 12 |

## Rules

- Use **PASS**, **FAIL**, **NOT RUN**, or **BLOCKED**; note why.
- Existing files beginning with `test_` may be interactive scripts rather than automated unit tests.
- Never mark a GUI/portal test PASS solely because code compiles.
- Record command output and screenshot/image integrity where possible, but do not commit personal screenshots without permission.
- Record initial failure before fixing a bug, and retest after.
