"""Capture controller for the AI Snipping Tool.

Windows Snipping Tool UX:
1. Trigger (Alt+Shift+S or tray) immediately shows the fullscreen overlay.
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
from pathlib import Path
from urllib.parse import unquote
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from PIL import Image
from PySide6.QtCore import QRect, QRectF, Qt, QTimer, Signal, Slot
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
from ui.overlay import Overlay, SnipMode
from ui.display_overlay import DisplayOverlay, screen_fingerprint
from capture.display_mapping import (Rect, DisplayMappingError, compatibility_mapping, read_gnome_layout)
from utils.clipboard import copy_image_to_clipboard, copy_text_to_clipboard
from utils.capture_diagnostics import trace, image_trace, timed
from utils.capture_latency import CaptureLatency, active_capture
from utils.screenshot_files import copy_screenshot, save_png, cleanup_capture_source


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


@timed('rectangle_decode_crop_save')
def _crop_and_save(source: Path, x: float, y: float, w: float, h: float, mapping=None, canvas_size=None) -> Path:
    with Image.open(source) as img:
        if canvas_size is None and mapping is None and QGuiApplication.platformName() == 'wayland' and len(QGuiApplication.screens()) > 1:
            raise DisplayMappingError('A verified per-monitor mapping is required. Capture through main.py.')
        mapping = mapping or compatibility_mapping(canvas_size or _get_virtual_size(), img.size)
        if tuple(img.size) != mapping.image_size:
            raise DisplayMappingError('Screenshot dimensions changed after the overlay was created.')
        box = mapping.crop_box(Rect(x, y, w, h))
        with img.crop(box) as cropped:
            return save_png(cropped, SCREENSHOTS_DIR)


@timed('fullscreen_file_copy')
def _save_full(source: Path) -> Path:
    return copy_screenshot(source, SCREENSHOTS_DIR)


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
        self._operation_active = False
        self._permission_prompt = None
        self._clipboard_pending = None
        self.capture_engine    = ScreenshotCapture()
        self.last_capture_path: Path | None = None
        self.last_extracted_text: str | None = None
        self._overlay: Overlay | DisplayOverlay | None = None
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
        self.status_label = QLabel("", self)
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
        if self._shutting_down or self.busy or self._operation_active:
            return
        mode = self._selected_value(self.mode_group)
        self.capture_button.setEnabled(False)
        self.last_capture_path = None
        self.last_extracted_text = None
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

    # ── Main entry point (Alt+Shift+S → overlay immediately) ─────────────────

    @Slot()
    def show_from_global_shortcut(self) -> None:
        """Called by Alt+Shift+S or tray icon — launches the overlay directly."""
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
        self._capture_latency = CaptureLatency(getattr(self, "latency_listener", None))
        self.last_capture_path = None
        self.last_extracted_text = None
        self._clipboard_pending = None
        self._pending = self.jobs.submit(self._launch_overlay())

    @property
    def busy(self):
        return self._pending is not None and not self._pending.done()

    @timed('activation_to_overlay_prepare')
    async def _launch_overlay(self, permission_retry=False):
        latency = getattr(self, "_capture_latency", None) or CaptureLatency()
        latency_token = active_capture.set(latency)
        try:
            latency.mark("preparation_started")
            native_wayland = QGuiApplication.platformName() == 'wayland'
            layout_before = None
            mapping_error = None
            qt_before = screen_fingerprint(QGuiApplication.screens())
            if native_wayland:
                try:
                    latency.mark("layout_before_begin")
                    layout_before = await read_gnome_layout()
                    latency.mark("layout_before_done")
                except DisplayMappingError as error:
                    mapping_error = str(error)
            latency.mark("portal_request_begin")
            source_path = await asyncio.wait_for(_portal_screenshot(interactive=False), timeout=140)
            latency.mark("portal_returned")
            if permission_retry:
                # Discard the consent capture: it may include our permission
                # window. Recapture only after that real window has disappeared.
                self._dismiss_permission_prompt()
                self._cleanup_source(source_path)
                await asyncio.sleep(.2)
                latency.mark("portal_request_begin")
                source_path = await _portal_screenshot(interactive=False)
                latency.mark("portal_returned")
            image_trace('portal_source', source_path)
            self._src_path = source_path
            bg_pixmap = QPixmap(str(source_path))
            latency.mark("image_loaded")
            if bg_pixmap.isNull():
                raise RuntimeError("Portal returned an unreadable screenshot.")
            overlay = None
            if native_wayland and layout_before is not None:
                try:
                    layout_after = await read_gnome_layout()
                    latency.mark("layout_after_done")
                    if layout_before != layout_after or qt_before != screen_fingerprint(QGuiApplication.screens()):
                        raise DisplayMappingError('Display layout changed during capture. Capture again.')
                    with Image.open(source_path) as image:
                        mapping = layout_after.mapping(image.size, image.info.get('Software', ''))
                    bg_pixmap.setDevicePixelRatio(1.)  # PNG pixels, not output-DPR units.
                    latency.mark("mapping_completed")
                    overlay = DisplayOverlay(bg_pixmap, mapping)
                    overlay.mapping_failed.connect(self._on_mapping_failed)
                except DisplayMappingError as error:
                    mapping_error = str(error)
            if overlay is None:
                latency.mark("mapping_unverified" if native_wayland else "mapping_not_required")
                overlay = Overlay(bg_pixmap=bg_pixmap)
                if native_wayland:
                    # Keep server-side Full Screen and Window available, but do
                    # not let an unverified stretched preview produce a crop.
                    overlay._toolbar._buttons[SnipMode.RECTANGULAR].setEnabled(False)
                    overlay.bg_pixmap = None
                    overlay._mode = SnipMode.FULLSCREEN
                    overlay._toolbar.select_mode(SnipMode.FULLSCREEN)
                    primary = QGuiApplication.primaryScreen()
                    if primary is not None:
                        overlay._display_geometry = primary.geometry()
                        overlay.winId()
                        overlay.windowHandle().setScreen(primary)
                    overlay._rectangle_mapping_error = mapping_error or 'Rectangle display mapping is unavailable.'
            latency.mark("widgets_created")
            latency.observe(overlay)
            self._overlay = overlay
            overlay.area_selected.connect(
                lambda rect: self._on_area_selected(rect, source_path, overlay.capture_action))
            overlay.fullscreen_capture_requested.connect(
                lambda: self._on_fullscreen(source_path, overlay.capture_action))
            overlay.window_capture_requested.connect(
                lambda: self._on_window_requested(overlay.capture_action))
            overlay.cancelled.connect(self._on_cancelled)
            overlay.delivery_requested.connect(self._deliver_pending_clipboard)
            overlay.showFullScreenOverlay()
            latency.mark("show_returned")
            if mapping_error:
                self.status_label.setText(mapping_error)
                self._show_toast(mapping_error)
        except asyncio.CancelledError:
            latency.mark("capture_cancelled")
            raise
        except Exception as error:
            latency.mark("capture_failed")
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
            active_capture.reset(latency_token)
            if self._permission_prompt is not None:
                self._permission_prompt.continue_button.setEnabled(True)

    def _on_mapping_failed(self, message):
        self._on_cancelled()
        self.status_label.setText(message)
        self._show_toast(message)

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


    @timed('overlay_close_schedule')
    def _close_overlay(self):
        self._operation_active = False
        overlay, self._overlay = self._overlay, None
        if overlay is not None:
            overlay.close()
            overlay.deleteLater()

    def shutdown(self):
        self._shutting_down = True
        self._clipboard_pending = None
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

    def _on_area_selected(self, rect: QRect | QRectF, source_path: Path | None, action: str) -> None:
        if self._shutting_down or self._operation_active:
            return
        self._operation_active = True
        trace('capture_selected', action=action, mode='rectangle')
        if self._overlay is not None:
            self._overlay.set_processing()
        if source_path is None or not source_path.exists():
            self._close_overlay()
            self.status_label.setText("Capture failed: no backdrop screenshot.")
            self.capture_finished.emit()
            return
        try:
            mapping_error = getattr(self._overlay, '_rectangle_mapping_error', None)
            if mapping_error:
                raise DisplayMappingError(mapping_error)
            mapping = getattr(self._overlay, 'capture_mapping', None)
            if mapping is None and QGuiApplication.platformName() == 'wayland' and len(QGuiApplication.screens()) > 1:
                raise DisplayMappingError('A verified per-monitor mapping is required. Capture through main.py.')
            # Freeze all Qt-dependent geometry before submitting plain Pillow work.
            canvas_size = _get_virtual_size() if mapping is None else (1, 1)
            self._pending = self.jobs.submit(self._save_selected(source_path, action, 'Crop',
                _crop_and_save, rect.x(), rect.y(), rect.width(), rect.height(),
                mapping=mapping, canvas_size=canvas_size))
        except Exception as e:
            self._close_overlay()
            self.status_label.setText(f"Crop failed: {e}")
            self.capture_finished.emit()
            self._cleanup_source(source_path)
            self._src_path = None

    def _on_fullscreen(self, source_path: Path | None, action: str) -> None:
        if self._shutting_down or self._operation_active:
            return
        self._operation_active = True
        trace('capture_selected', action=action, mode='fullscreen')
        if self._overlay is not None:
            self._overlay.set_processing()
        if source_path is None or not source_path.exists():
            self._close_overlay()
            self.status_label.setText("Capture failed: no backdrop screenshot.")
            self.capture_finished.emit()
            return
        self._pending = self.jobs.submit(self._save_selected(source_path, action, 'Save', _save_full))

    async def _save_selected(self, source_path, action, operation, function, *args, **kwargs):
        # Ownership transfers from the controller to this coroutine. Cancellation
        # drains its one worker before the source is unlinked in finally.
        self._src_path = None
        try:
            out = await self.jobs.run_file(function, source_path, *args, **kwargs)
            if not self._shutting_down:
                self._handle_capture_result(out, action)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self._close_overlay()
            self.status_label.setText(f"{operation} failed: {e}")
            self.capture_finished.emit()
        finally:
            self._cleanup_source(source_path)

    def _on_window_requested(self, action: str) -> None:
        if self._shutting_down or self._operation_active:
            return
        self._operation_active = True
        trace('capture_selected', action=action, mode='window')
        if self._overlay is not None:
            self._overlay.set_processing()
            self._overlay.hide()
        self._cleanup_source(self._src_path)
        self._src_path = None
        self._pending = self.jobs.submit(self._capture_window(action))

    async def _capture_window(self, action):
        try:
            # Existing async backend calls clipboard on this Qt main thread.
            out = await asyncio.wait_for(capture_window(copy_to_clipboard=False), timeout=190)
            if out is None:
                self._close_overlay()
                self.status_label.setText("Window capture cancelled.")
                self.capture_finished.emit()
                return
            if self._overlay is not None:
                self._overlay.showFullScreenOverlay()
                await asyncio.sleep(.25)
            self._handle_capture_result(out, action)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._close_overlay()
            logger.exception("Window capture failed")
            self.status_label.setText(str(error) if isinstance(error, ScreenshotPortalError) else "Window capture failed or timed out.")
            self._show_toast(self.status_label.text())
            self.capture_finished.emit()

    def _on_cancelled(self) -> None:
        self._clipboard_pending = None
        if self.busy:
            self._pending.cancel()
        self._close_overlay()
        self._cleanup_source(self._src_path)
        self._src_path = None
        self.status_label.setText("Capture cancelled.")
        self.capture_finished.emit()

    def _handle_capture_result(self, path: Path, action: str) -> None:
        """Publish while the real capture window still owns Wayland focus."""
        image_trace('post_capture', path, action=action)
        self.last_capture_path = path
        if action in ('extract_text', 'ocr'):
            self.last_extracted_text = None
            self._pending = self.jobs.submit(self._recognize(path))
        else:
            self._clipboard_pending = ('image', path)
            self._deliver_pending_clipboard()

    @timed('clipboard_delivery')
    def _deliver_pending_clipboard(self):
        if self._shutting_down or self._clipboard_pending is None:
            return
        if (QGuiApplication.platformName() == 'wayland' and self._overlay is not None
                and not self._overlay.isActiveWindow()):
            self.status_label.setText('Result ready. Return to the capture overlay and click or press Enter to copy.')
            self._overlay.setCursor(Qt.ArrowCursor)
            self._show_toast(self.status_label.text())
            trace('clipboard_deferred', reason='capture_window_not_focused')
            return
        kind, value = self._clipboard_pending
        try:
            trace('clipboard_delivery', kind=kind, overlay_visible=self._overlay is not None and self._overlay.isVisible())
            if kind == 'image':
                copy_image_to_clipboard(value)
                message = f'Saved & copied: {value.name}'
            else:
                copy_text_to_clipboard(value)
                message = f'Text copied ({len(value)} chars)'
            self._clipboard_pending = None
            # setMimeData precedes surface teardown; QApplication remains alive
            # to serve requests from other clients after this window closes.
            self._close_overlay()
            self.status_label.setText(message)
            self._show_toast(message)
        except Exception as error:
            logger.exception('Clipboard delivery failed')
            self.status_label.setText(f'Clipboard copy failed: {error}')
            self._show_toast(self.status_label.text())
        self.capture_finished.emit()

    @timed('english_or_selected_ocr_job')
    async def _recognize(self, path):
        try:
            trace('ocr_started')
            text = await extract_text_async(path)
            self.last_extracted_text = text
            trace('ocr_returned', characters=len(text))
            if text:
                self._clipboard_pending = ('text', text)
                self._deliver_pending_clipboard()
            else:
                self._close_overlay()
                self.status_label.setText('No text detected.')
                self._show_toast(self.status_label.text())
                self.capture_finished.emit()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._close_overlay()
            logger.exception('Local OCR failed')
            self.status_label.setText(f'Local OCR failed: {error}')
            self._show_toast(self.status_label.text())
            if not self._shutting_down:
                self.capture_finished.emit()

    def _show_toast(self, message: str) -> None:
        try:
            self._toast = CaptureToast(message)
        except Exception as e:
            print(f"[TOAST ERROR] {e}", flush=True)

    @staticmethod
    def _cleanup_source(source_path: Path | None) -> None:
        cleanup_capture_source(source_path, SCREENSHOTS_DIR)

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
