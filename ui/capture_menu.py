"""Capture controller for the AI Snipping Tool.

Windows Snipping Tool UX:
1. Trigger (Ctrl+Shift+S or tray) immediately shows the fullscreen overlay.
2. The overlay has a top-center pill toolbar with an action dropdown
   ("Screenshot" vs "Extract Text") and mode buttons (Rectangular, Freeform, Window, Full Screen).
3. Once captured, the action runs automatically with NO post-capture action popup:
   - "Screenshot": image is saved to ~/Pictures/Screenshots/ AND copied to clipboard.
   - "Extract Text": OCR is executed and extracted text is copied to clipboard.
4. A brief, non-blocking floating toast confirms completion and auto-dismisses.
"""

from __future__ import annotations

import asyncio
import os
import inspect
import logging
import time
from pathlib import Path
from urllib.parse import unquote
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from PIL import Image
from PySide6.QtCore import QRect, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QWidget,
)

from capture.screenshot import ScreenshotCapture
from capture.window_capture import take_screenshot as capture_window
from utils.async_jobs import AsyncJobs
from utils.ocr_process import extract_text_async
from ui.overlay import Overlay
from utils.clipboard import copy_image_to_clipboard, copy_text_to_clipboard


SCREENSHOTS_DIR = Path.home() / "Pictures" / "Screenshots"


# ─────────────────────────────────────────────────────────────────────────────
#  Portal screenshot helper
# ─────────────────────────────────────────────────────────────────────────────

from capture.screenshot_portal_request import request_screenshot as _portal_screenshot, ScreenshotPortalError

logger = logging.getLogger(__name__)


def _get_virtual_size() -> tuple[int, int]:
    total = QRect()
    for s in QGuiApplication.screens():
        total = total.united(s.geometry())
    return total.width() or 1920, total.height() or 1080


def _crop_and_save(source: Path, x: int, y: int, w: int, h: int) -> Path:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    out = SCREENSHOTS_DIR / f"Screenshot_{time.strftime('%Y-%m-%d_%H-%M-%S')}.png"
    with Image.open(source) as img:
        sw, sh = _get_virtual_size()
        sx, sy = img.width / sw, img.height / sh
        left   = max(0, round(x * sx))
        top    = max(0, round(y * sy))
        right  = min(img.width,  round((x + w) * sx))
        bottom = min(img.height, round((y + h) * sy))
        img.crop((left, top, right, bottom)).save(out, "PNG")
    return out


def _save_full(source: Path) -> Path:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    out = SCREENSHOTS_DIR / f"Screenshot_{time.strftime('%Y-%m-%d_%H-%M-%S')}.png"
    import shutil
    shutil.copy2(source, out)
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  Non-blocking Toast Confirmation
# ─────────────────────────────────────────────────────────────────────────────

class CaptureToast(QWidget):
    """Small non-blocking floating notification that auto-dismisses without clicks."""

    def __init__(self, message: str, parent: QWidget | None = None, duration_ms: int = 1700):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        frame = QFrame()
        frame.setObjectName("toast_frame")
        frame.setStyleSheet("""
            QFrame#toast_frame {
                background: rgba(18, 18, 28, 0.94);
                border: 1.5px solid rgba(255, 255, 255, 0.18);
                border-radius: 14px;
            }
        """)

        inner = QHBoxLayout(frame)
        inner.setContentsMargins(18, 10, 18, 10)

        lbl = QLabel(message)
        lbl.setStyleSheet("""
            color: #FFFFFF;
            font-size: 13px;
            font-weight: 700;
            background: transparent;
        """)
        inner.addWidget(lbl)
        outer.addWidget(frame)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 200))
        self.setGraphicsEffect(shadow)

        self.adjustSize()
        self._position()
        self.show()

        QTimer.singleShot(duration_ms, self.close)

    def _position(self) -> None:
        screen = QGuiApplication.primaryScreen()
        sg = screen.geometry() if screen else QRect(0, 0, 1920, 1080)
        x = sg.center().x() - self.width() // 2
        y = sg.bottom() - self.height() - 70
        self.move(max(10, x), max(10, y))


# ─────────────────────────────────────────────────────────────────────────────
#  CaptureMenu — background controller + tray / test compatibility object
# ─────────────────────────────────────────────────────────────────────────────

class CaptureMenu(QWidget):
    """
    Background capture controller.

    ``show_from_global_shortcut()`` immediately launches the fullscreen overlay
    (no separate launcher popup).  The overlay handles mode selection via its
    built-in pill toolbar.  When capture completes, it automatically executes
    the selected action (save+copy image or OCR text to clipboard) without
    any post-capture modal or action menu.

    Hidden ``action_group`` / ``mode_group`` attributes are kept for
    test-harness backward compatibility.
    """

    capture_finished = Signal()

    def __init__(self, jobs=None):
        super().__init__()
        self.jobs = jobs if jobs is not None else AsyncJobs(self)
        self._pending = None
        self._shutting_down = False
        self._permission_prompt = None
        self.capture_engine    = ScreenshotCapture()
        self.last_capture_path: Path | None = None
        self.last_extracted_text: str | None = None
        self._overlay: Overlay | None = None
        self._toast: CaptureToast | None = None
        self._src_path: Path | None = None

        # Kept invisible — for test_capture_menu.py compatibility
        self._compat_hidden_init()

        self.setWindowTitle("AI Snipping Tool")
        self.hide()  # Controller never owns a visible production window.

    # ── Test-harness compatibility stubs ─────────────────────────────────────

    def _compat_hidden_init(self) -> None:
        """Create hidden groups/radios so existing test code can introspect them."""
        self.mode_group = QButtonGroup(self)
        self.full_screen_radio    = self._hidden_radio(self.mode_group, "full_screen", True)
        self.window_radio         = self._hidden_radio(self.mode_group, "window")
        self.selected_area_radio  = self._hidden_radio(self.mode_group, "selected_area")

        self.action_group = QButtonGroup(self)
        self.screenshot_radio = self._hidden_radio(self.action_group, "screenshot", True)
        self.ocr_radio        = self._hidden_radio(self.action_group, "ocr")
        self.ai_radio         = self._hidden_radio(self.action_group, "ai")

        # Minimal status_label for test assertions
        self.status_label = QLabel("")
        self.status_label.hide()

        # Minimal capture_button for --cancel test
        self.capture_button = QPushButton("Capture")
        self.capture_button.hide()

    @staticmethod
    def _hidden_radio(group: QButtonGroup, value: str, checked: bool = False) -> QRadioButton:
        r = QRadioButton()
        r.setProperty("value", value)
        r.setChecked(checked)
        r.setVisible(False)
        group.addButton(r)
        return r

    # ── Legacy start_capture for --cancel / --run test modes ─────────────────

    def start_capture(self) -> None:
        """Used by test_capture_menu.py --cancel and --run test modes."""
        mode = self._selected_value(self.mode_group)
        self.capture_button.setEnabled(False)
        self.last_capture_path = None
        self.last_extracted_text = None
        if self._shutting_down or self.busy:
            return
        self.status_label.setText("Preparing…")
        self._pending = self.jobs.submit(self._legacy_run(mode))

    async def _legacy_run(self, mode: str) -> None:
        try:
            path = self._capture(mode)
            if inspect.isawaitable(path):
                path = await path
        except asyncio.CancelledError:
            raise
        except Exception:
            self.capture_button.setEnabled(True)
            self.status_label.setText("Capture failed.")
            self.capture_finished.emit()
            return
        self.capture_button.setEnabled(True)
        if path is None:
            self.status_label.setText("Capture cancelled.")
            self.capture_finished.emit()
            return
        self._handle_capture_result(path, self._selected_value(self.action_group))

    def _capture(self, mode):
        """Compatibility backend; all production selection goes through the overlay."""
        if mode == "full_screen":
            return self.capture_engine.capture_full_screen()
        if mode == "window":
            return capture_window()
        raise ValueError("Use the production overlay for rectangular selection.")

    @staticmethod
    def _selected_value(group: QButtonGroup) -> str:
        btn = group.checkedButton()
        return btn.property("value") if btn else ""

    # ── Main entry point (Ctrl+Shift+S → overlay immediately) ─────────────────

    @Slot()
    def show_from_global_shortcut(self) -> None:
        """Called by Ctrl+Shift+S or tray icon — launches the overlay directly."""
        print("[CAPTURE MENU] Overlay launched via shortcut/tray", flush=True)
        self.launch_overlay()

    @Slot()
    def launch_overlay(self) -> None:
        """Coalesce activation while a portal request, overlay or OCR job is active."""
        if self._permission_prompt is not None:
            self._permission_prompt.show()
            self._permission_prompt.raise_()
            self._permission_prompt.activateWindow()
            return
        if self._shutting_down or self._overlay is not None or self.busy:
            return
        self._pending = self.jobs.submit(self._launch_overlay())

    @property
    def busy(self):
        return self._pending is not None and not self._pending.done()

    async def _launch_overlay(self, permission_retry=False):
        try:
            source_path = await asyncio.wait_for(_portal_screenshot(interactive=False), timeout=140)
            if permission_retry:
                # Discard the consent capture: it may include our permission
                # window. Recapture only after that real window has disappeared.
                self._dismiss_permission_prompt()
                self._cleanup_source(source_path)
                await asyncio.sleep(.2)
                source_path = await _portal_screenshot(interactive=False)
            self._src_path = source_path
            bg_pixmap = QPixmap(str(source_path))
            if bg_pixmap.isNull():
                raise RuntimeError("Portal returned an unreadable screenshot.")
            overlay = Overlay(bg_pixmap=bg_pixmap)
            self._overlay = overlay
            overlay.area_selected.connect(
                lambda rect: self._on_area_selected(rect, source_path, overlay.capture_action))
            overlay.fullscreen_capture_requested.connect(
                lambda: self._on_fullscreen(source_path, overlay.capture_action))
            overlay.window_capture_requested.connect(
                lambda: self._on_window_requested(overlay.capture_action))
            overlay.cancelled.connect(self._on_cancelled)
            overlay.showFullScreenOverlay()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._cleanup_source(self._src_path)
            self._src_path = None
            if isinstance(error, ScreenshotPortalError):
                self.status_label.setText(str(error))
                logger.warning('Capture failed: kind=%s response=%s detail=%s',
                               error.kind, error.response_code, error)
                if error.kind == 'permission' or error.response_code == 2:
                    self._show_permission_prompt()
                elif self._permission_prompt is not None:
                    self._permission_prompt.message.setText(str(error))
            else:
                logger.exception('Unexpected capture failure')
                self.status_label.setText(f'Screenshot failed: {error}')
            self._show_toast(self.status_label.text())
            self.capture_finished.emit()
        finally:
            if self._permission_prompt is not None:
                self._permission_prompt.continue_button.setEnabled(True)

    def _show_permission_prompt(self):
        if self._permission_prompt is not None or self._shutting_down:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Screenshot permission — AI Snipping Tool')
        layout = QVBoxLayout(dialog)
        dialog.message = QLabel(
            'GNOME could not complete the screenshot request. It may require this app '
            'to be focused before showing its permission dialog.\n'
            'Click Continue here, then choose Allow or Deny in GNOME. '
            'No screenshot permission is changed automatically.')
        dialog.message.setWordWrap(True)
        layout.addWidget(dialog.message)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        dialog.continue_button = buttons.addButton('Continue', QDialogButtonBox.ActionRole)
        layout.addWidget(buttons)
        buttons.rejected.connect(dialog.reject)
        dialog.continue_button.clicked.connect(self._retry_screenshot_permission)
        dialog.finished.connect(lambda _: self._permission_prompt_closed(dialog))
        self._permission_prompt = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _retry_screenshot_permission(self):
        if self._shutting_down or self.busy or self._permission_prompt is None:
            return
        # An explicit click gives GNOME a genuine focused app, not a forged
        # activation token or an invisible controller impersonating a parent.
        self._permission_prompt.continue_button.setEnabled(False)
        self._pending = self.jobs.submit(self._launch_overlay(permission_retry=True))

    def _permission_prompt_closed(self, dialog):
        if self._permission_prompt is dialog:
            self._permission_prompt = None
            if self.busy:
                self._pending.cancel()
            self.status_label.setText('Screenshot permission request closed.')
        dialog.deleteLater()

    def _dismiss_permission_prompt(self):
        dialog, self._permission_prompt = self._permission_prompt, None
        if dialog is not None:
            dialog.close()


    def _close_overlay(self):
        overlay, self._overlay = self._overlay, None
        if overlay is not None:
            overlay.close()
            overlay.deleteLater()

    def shutdown(self):
        self._shutting_down = True
        if self.busy:
            self._pending.cancel()
        self._close_overlay()
        self._dismiss_permission_prompt()
        self._cleanup_source(self._src_path)
        self._src_path = None
        if self._toast is not None:
            try:
                self._toast.close()
            except RuntimeError:
                pass  # WA_DeleteOnClose toast may already have expired.
            self._toast = None
        self.hide()

    # ── Capture result handlers ───────────────────────────────────────────────

    def _on_area_selected(self, rect: QRect, source_path: Path | None, action: str) -> None:
        self._close_overlay()
        self._src_path = None
        if source_path is None or not source_path.exists():
            self.status_label.setText("Capture failed: no backdrop screenshot.")
            self.capture_finished.emit()
            return
        try:
            out = _crop_and_save(source_path, rect.x(), rect.y(), rect.width(), rect.height())
        except Exception as e:
            self.status_label.setText(f"Crop failed: {e}")
            self.capture_finished.emit()
            return
        finally:
            self._cleanup_source(source_path)

        self._handle_capture_result(out, action)

    def _on_fullscreen(self, source_path: Path | None, action: str) -> None:
        self._close_overlay()
        self._src_path = None
        if source_path is None or not source_path.exists():
            self.status_label.setText("Capture failed: no backdrop screenshot.")
            self.capture_finished.emit()
            return
        try:
            out = _save_full(source_path)
        except Exception as e:
            self.status_label.setText(f"Save failed: {e}")
            self.capture_finished.emit()
            return
        finally:
            self._cleanup_source(source_path)

        self._handle_capture_result(out, action)

    def _on_window_requested(self, action: str) -> None:
        self._close_overlay()
        self._cleanup_source(self._src_path)
        self._src_path = None
        self._pending = self.jobs.submit(self._capture_window(action))

    async def _capture_window(self, action):
        try:
            # Existing async backend calls clipboard on this Qt main thread.
            out = await asyncio.wait_for(capture_window(), timeout=190)
            if out is None:
                self.status_label.setText("Window capture cancelled.")
                self.capture_finished.emit()
                return
            self._handle_capture_result(out, action)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.exception("Window capture failed")
            self.status_label.setText(str(error) if isinstance(error, ScreenshotPortalError) else "Window capture failed or timed out.")
            self._show_toast(self.status_label.text())
            self.capture_finished.emit()

    def _on_cancelled(self) -> None:
        self._close_overlay()
        self._cleanup_source(self._src_path)
        self._src_path = None
        self.status_label.setText("Capture cancelled.")
        self.capture_finished.emit()

    def _handle_capture_result(self, path: Path, action: str) -> None:
        """Handle post-capture automatic behavior: Screenshot vs Extract Text."""
        self.last_capture_path = path
        is_ocr = (action == "extract_text" or action == "ocr")

        if is_ocr:
            self._pending = self.jobs.submit(self._recognize(path))
            return
        else:
            # Default "Screenshot" mode: BOTH save to disk AND copy to clipboard
            try:
                copy_image_to_clipboard(path)
                self.status_label.setText(f"Saved & copied: {path.name}")
                self._show_toast("✓ Saved & copied to clipboard!")
            except Exception as e:
                print(f"[CLIPBOARD ERROR] {e}", flush=True)
                self.status_label.setText(f"Clipboard copy failed: {e}")
                self._show_toast(f"✓ Saved: {path.name}")

        QApplication.processEvents()
        self.capture_finished.emit()

    async def _recognize(self, path):
        try:
            text = await extract_text_async(path)
            self.last_extracted_text = text
            if text:
                copy_text_to_clipboard(text)
                self.status_label.setText(f"Text copied ({len(text)} chars)")
            else:
                self.status_label.setText("No text detected.")
            self._show_toast(self.status_label.text())
        except asyncio.CancelledError:
            raise
        except Exception:
            self.status_label.setText("Local OCR failed or timed out.")
            self._show_toast(self.status_label.text())
        finally:
            if not self._shutting_down:
                self.capture_finished.emit()

    def _show_toast(self, message: str) -> None:
        try:
            self._toast = CaptureToast(message)
        except Exception as e:
            print(f"[TOAST ERROR] {e}", flush=True)

    @staticmethod
    def _cleanup_source(source_path: Path | None) -> None:
        if source_path and source_path.exists():
            try:
                source_path.unlink()
            except OSError:
                pass

    # ── Slots wired by main.py ────────────────────────────────────────────────

    @Slot(str)
    def set_global_shortcut_registered(self, trigger: str) -> None:
        self.status_label.setText(f"Global shortcut registered: {trigger}")

    @Slot(str)
    def set_global_shortcut_error(self, error: str) -> None:
        self.status_label.setText("Global shortcut unavailable; use the tray Capture action.")
        if not self._shutting_down:
            self._show_toast(self.status_label.text())


# ─────────────────────────────────────────────────────────────────────────────
#  Standalone entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    """Compatibility invocation delegates to the canonical background application."""
    from main import main as application_main
    return application_main()


if __name__ == "__main__":
    sys.exit(main())
