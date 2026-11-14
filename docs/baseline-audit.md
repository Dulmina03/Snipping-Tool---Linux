# Source Baseline Audit — Awaiting Local Verification

**Repository:** https://github.com/Dulmina03/Snipping-Tool---Linux  
**Inspected GitHub branch:** `main`  
**HEAD from GitHub read (2026-11-14):** `ee0c132ece526748b876167c76f434886627f84d`  
**Last visible commit:** `2026-09-03`, `refactor: optimize overlay rendering logic to reduce UI flickering`  
**Audit status:** SOURCE REVIEW ONLY — no execution on the developer's Ubuntu machine yet.

## Source-confirmed inventory

| Area | Files | Source review status |
|---|---|---|
| Background/tray application | `main.py` | Qt application, tray, shortcut manager, `CaptureMenu` |
| Global shortcut | `shortcuts/global_shortcut.py` | Portal Registry + GlobalShortcuts integration present; physical shortcut requires local test |
| Capture overlay | `ui/overlay.py` | Screenshot/Extract Text dropdown; rectangular, window, full screen modes; freeform disabled |
| Controller | `ui/capture_menu.py` | Portal backdrop capture, crop/save, screenshot/OCR result handling, toast |
| Capture modules | `capture/screenshot.py`, `capture/window_capture.py`, `capture/selected_area.py` | Multiple portal capture flows |
| OCR | `ocr/ocr_engine.py` | Tesseract 3-pass recognition and PIL preprocessing; no explicit `sin+eng` selection |
| Clipboard | `utils/clipboard.py` | Qt image and UTF-8 text clipboard helpers |
| Tests | `test_*.py` | Mostly manual/UI-coupled scripts; modern automated suite missing |
| Desktop entry | `com.dulmina.aisnippingtool.desktop` | Hardcodes developer home path, launches `ui/capture_menu.py` rather than `main.py` |
| Legacy experiments | `capture/screen_capture.py`, `capture/native/`, `capture/portal_screenshot.py` | Experimental and/or duplicate source; do not delete without import/use audit |

## Confirmed code gaps and concerns requiring runtime reproduction

1. **Entry point mismatch:** `main.py` is the background tray daemon, while the desktop entry launches `ui/capture_menu.py`, which opens its overlay automatically. Source confirms mismatch; launch outcomes not tested here.
2. **Ghost controller risk:** `CaptureMenu.show_from_global_shortcut()` calls `self.show()` to satisfy an old `isVisible()` test, then launches overlay without clearly hiding the controller. Verify visually before change.
3. **Potential GUI freezing:** `CaptureMenu.launch_overlay()` calls `asyncio.run(_portal_screenshot(...))` in Qt signal path, `_on_window_requested()` similarly calls an async capture synchronously, and `_handle_capture_result()` calls Tesseract synchronously.
4. **Freeform:** explicitly disabled in `ui/overlay.py` (`enabled=False`, tooltip `coming soon`).
5. **Incomplete OCR language support:** `pytesseract.image_to_string(...)` calls do not specify `lang='sin+eng'`; check actual traineddata installed.
6. **OCR quality risk:** returns longest output of three passes; preprocessing uses a minimum-side-dependent upscaling factor that can grow excessively for a very thin crop.
7. **Mixed DPI/multi-monitor risk:** crop logic scales selection coordinates using the ratio of full screenshot pixels to unioned Qt screen geometry, which may not preserve per-screen mapping.
8. **Possible overwrite:** several outputs use only second-resolution timestamps without existence/unique-name handling.
9. **Test gap:** `test_global_shortcut.py` emits `shortcut_activated` itself and cannot prove a real keypress; `test_capture_menu.py` uses hidden compatibility radio controls and an old Ask AI placeholder test.
10. **Packaging gap:** no README/installer/release workflow in inspected Git tree; `.desktop` uses a developer-specific absolute path.
11. **Unfinished app capabilities:** no document/PDF extraction, annotated screenshot editor, settings, history, or functional Ask AI integration apparent in main tree.

## First local checks to perform

1. Confirm actual local branch/commit and any uncommitted work (which may be newer than GitHub).
2. Verify environment: session type, Python/Qt versions, portal backend, Tesseract and `tesseract --list-langs` including `sin` and `eng`.
3. Run static compilation and noninteractive tests, recording true outputs.
4. Manually test real shortcut, tray, region/window/fullscreen selection, cancellation, clipboard, OCR and shutdown.
5. Update this audit with observed behavior and the smallest Phase 1 fix recommendation.

**DO NOT mark any runtime feature PASS based solely on GitHub source or an earlier chat transcript.**
