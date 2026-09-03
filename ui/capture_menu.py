"""Capture menu and post-selection action toolbar for the AI Snipping Tool."""

import asyncio
from datetime import datetime
from pathlib import Path
import sys
import threading

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from capture.screenshot import ScreenshotCapture
from capture.selected_area import main as capture_selected_area
from capture.window_capture import take_screenshot as capture_window
from ocr.ocr_engine import extract_text
from shortcuts.global_shortcut import GlobalShortcutManager
from utils.clipboard import copy_image_to_clipboard, copy_text_to_clipboard


SCREENSHOTS_DIR = Path.home() / "Pictures" / "Screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Shared stylesheet tokens ──────────────────────────────────────────────────
_ACCENT = "#6C63FF"        # violet
_ACCENT_HOVER = "#857DFF"
_ACCENT_PRESS = "#524BC7"
_SURFACE = "#1E1E2E"       # dark navy base
_SURFACE_RAISED = "#28283E"
_TEXT = "#E0E0F8"
_TEXT_DIM = "#9090B0"
_DANGER = "#E06C75"
_DANGER_HOVER = "#F07880"
_SUCCESS = "#98C379"

_BASE_STYLE = f"""
QWidget {{
    background-color: {_SURFACE};
    color: {_TEXT};
    font-family: 'Inter', 'Segoe UI', 'SF Pro Display', sans-serif;
    font-size: 13px;
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
#  ActionMenu — small floating toolbar shown AFTER a capture selection
# ─────────────────────────────────────────────────────────────────────────────

class ActionMenu(QWidget):
    """
    Compact floating action toolbar that appears after an area/screen/window
    capture is complete.  Presents four choices:
        • Copy to Clipboard  — copy image pixels
        • Extract Text (OCR) — run Tesseract and copy text
        • Save as Image      — save PNG to ~/Pictures/Screenshots/
        • Cancel             — discard the capture
    Closes automatically after any action is taken.
    """

    def __init__(
        self,
        captured_path: Path,
        near_rect: QRect | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._path = captured_path
        self._near_rect = near_rect

        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._build_ui()
        self._apply_shadow()
        self._position_near_selection()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet(f"""
            QFrame#card {{
                background-color: {_SURFACE_RAISED};
                border-radius: 14px;
                border: 1px solid rgba(255,255,255,0.08);
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(8)

        # ── Header row ────────────────────────────────────────────────────────
        header = QLabel("📸  Capture ready")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 700;
            color: {_TEXT};
            padding-bottom: 4px;
            letter-spacing: 0.3px;
        """)
        card_layout.addWidget(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background: rgba(255,255,255,0.07); min-height:1px; max-height:1px; border: none;")
        card_layout.addWidget(sep)
        card_layout.addSpacing(4)

        # ── Action buttons ────────────────────────────────────────────────────
        self._copy_btn    = self._make_btn("📋  Copy to Clipboard",      _ACCENT, _ACCENT_HOVER)
        self._ocr_btn     = self._make_btn("🔍  Extract Text (OCR)",     "#4ECDC4", "#66D9D1")
        self._save_btn    = self._make_btn("💾  Save as Image",          "#56B4D3", "#74C6E0")
        self._cancel_btn  = self._make_btn("✕   Cancel",                 "#444460", "#55556E", small=True)

        self._copy_btn.clicked.connect(self._action_copy_image)
        self._ocr_btn.clicked.connect(self._action_ocr)
        self._save_btn.clicked.connect(self._action_save)
        self._cancel_btn.clicked.connect(self._action_cancel)

        for btn in (self._copy_btn, self._ocr_btn, self._save_btn):
            card_layout.addWidget(btn)

        card_layout.addSpacing(4)
        card_layout.addWidget(self._cancel_btn)

        # ── Status label ──────────────────────────────────────────────────────
        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setWordWrap(True)
        self._status.setStyleSheet(f"font-size: 11px; color: {_TEXT_DIM}; padding-top: 4px;")
        self._status.setVisible(False)
        card_layout.addWidget(self._status)

        outer.addWidget(card)
        self.setStyleSheet(_BASE_STYLE)

    @staticmethod
    def _make_btn(text: str, color: str, hover: str, small: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        size = 32 if small else 40
        radius = 8 if small else 10
        font_size = 12 if small else 13
        btn.setMinimumHeight(size)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {'#FFFFFF' if color != "#444460" else _TEXT_DIM};
                border: none;
                border-radius: {radius}px;
                padding: 0 16px;
                font-size: {font_size}px;
                font-weight: {'600' if not small else '500'};
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {hover};
                color: #FFFFFF;
            }}
            QPushButton:pressed {{
                background-color: {color};
            }}
            QPushButton:disabled {{
                background-color: rgba(255,255,255,0.06);
                color: {_TEXT_DIM};
            }}
        """)
        return btn

    def _apply_shadow(self) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.setGraphicsEffect(shadow)

    # ── Positioning ───────────────────────────────────────────────────────────

    def _position_near_selection(self) -> None:
        self.adjustSize()
        w, h = self.width() or 280, self.height() or 280

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.move(80, 80)
            return

        sg = screen.geometry()

        if self._near_rect and not self._near_rect.isEmpty():
            # Place below the selection, right-aligned with its right edge
            x = self._near_rect.right() - w
            y = self._near_rect.bottom() + 16
        else:
            # Centre-bottom of the primary screen
            x = sg.center().x() - w // 2
            y = sg.bottom() - h - 60

        # Clamp to screen bounds with margin
        margin = 12
        x = max(sg.left() + margin, min(x, sg.right() - w - margin))
        y = max(sg.top() + margin, min(y, sg.bottom() - h - margin))

        self.move(x, y)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _set_busy(self, message: str) -> None:
        for btn in (self._copy_btn, self._ocr_btn, self._save_btn, self._cancel_btn):
            btn.setEnabled(False)
        self._status.setText(message)
        self._status.setVisible(True)
        QApplication.processEvents()

    def _finish(self, message: str = "", close: bool = True) -> None:
        if message:
            self._status.setText(message)
            self._status.setStyleSheet(f"font-size: 11px; color: {_SUCCESS}; padding-top: 4px;")
            self._status.setVisible(True)
        if close:
            QTimer.singleShot(1200, self.close)

    def _error(self, title: str, message: str) -> None:
        for btn in (self._copy_btn, self._ocr_btn, self._save_btn, self._cancel_btn):
            btn.setEnabled(True)
        self._status.setText(f"⚠ {message}")
        self._status.setStyleSheet(f"font-size: 11px; color: {_DANGER}; padding-top: 4px;")
        self._status.setVisible(True)
        QMessageBox.critical(self, title, message)

    @Slot()
    def _action_copy_image(self) -> None:
        self._set_busy("Copying image to clipboard…")
        try:
            copy_image_to_clipboard(self._path)
            self._finish("✓ Image copied to clipboard!")
        except Exception as e:
            self._error("Clipboard error", str(e))

    @Slot()
    def _action_ocr(self) -> None:
        self._set_busy("Running OCR — please wait…")
        try:
            text = extract_text(self._path)
            if not text:
                self._error("No text found", "Tesseract found no readable text in the selected area.")
                return
            copy_text_to_clipboard(text)
            self._finish(f"✓ Text copied! ({len(text)} chars)")
        except Exception as e:
            self._error("OCR error", str(e))

    @Slot()
    def _action_save(self) -> None:
        self._set_busy("Saving image…")
        try:
            # Image was already saved to SCREENSHOTS_DIR by capture flow;
            # just confirm the path exists and show user.
            if self._path.exists():
                self._finish(f"✓ Saved:\n{self._path.name}")
            else:
                self._error("Save error", f"File not found: {self._path}")
        except Exception as e:
            self._error("Save error", str(e))

    @Slot()
    def _action_cancel(self) -> None:
        self.close()


# ─────────────────────────────────────────────────────────────────────────────
#  CaptureMenu — initial mode-picker launcher (shown on Ctrl+Shift+S)
# ─────────────────────────────────────────────────────────────────────────────

class CaptureMenu(QWidget):
    """Styled launcher for selecting capture mode; triggers ActionMenu after capture."""

    capture_finished = Signal()

    # Slots expected by main.py
    _shortcut_registered_signal = Signal(str)
    _shortcut_error_signal = Signal(str)

    def __init__(self):
        super().__init__()

        self.capture = ScreenshotCapture()
        self.last_capture_path: Path | None = None
        self.last_extracted_text: str | None = None
        self._action_menu: ActionMenu | None = None

        self.setWindowTitle("AI Snipping Tool")
        self.setFixedWidth(310)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setStyleSheet(_BASE_STYLE + f"""
            QWidget {{
                background-color: {_SURFACE};
            }}
            QPushButton#capture {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {_ACCENT}, stop:1 {_ACCENT_HOVER});
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                padding: 10px 0;
                font-size: 14px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
            QPushButton#capture:hover {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {_ACCENT_HOVER}, stop:1 #9B94FF);
            }}
            QPushButton#capture:pressed {{
                background: {_ACCENT_PRESS};
            }}
            QPushButton#capture:disabled {{
                background: rgba(108,99,255,0.35);
                color: rgba(255,255,255,0.4);
            }}
            QRadioButton {{
                color: {_TEXT};
                spacing: 8px;
                padding: 4px 2px;
                font-size: 13px;
            }}
            QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 2px solid rgba(255,255,255,0.25);
                background: transparent;
            }}
            QRadioButton::indicator:checked {{
                background: {_ACCENT};
                border-color: {_ACCENT};
            }}
            QRadioButton:hover {{
                color: #FFFFFF;
            }}
            QLabel#section {{
                color: {_TEXT_DIM};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.2px;
                text-transform: uppercase;
                padding-top: 8px;
            }}
            QFrame#sep {{
                background: rgba(255,255,255,0.06);
                min-height: 1px;
                max-height: 1px;
                border: none;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(6)

        # ── Title ─────────────────────────────────────────────────────────────
        title_row = QHBoxLayout()
        icon_lbl = QLabel("✂")
        icon_lbl.setStyleSheet(f"font-size: 22px; color: {_ACCENT}; padding-right: 6px;")
        title_lbl = QLabel("Snipping Tool")
        title_lbl.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {_TEXT}; letter-spacing: 0.3px;")
        title_row.addWidget(icon_lbl)
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        root.addLayout(title_row)

        root.addSpacing(8)
        self._add_sep(root)
        root.addSpacing(4)

        # ── Capture mode ──────────────────────────────────────────────────────
        section_mode = QLabel("CAPTURE MODE")
        section_mode.setObjectName("section")
        root.addWidget(section_mode)

        self.mode_group = QButtonGroup(self)
        self.full_screen_radio = self._add_radio(root, self.mode_group, "🖥  Full Screen", "full_screen", True)
        self.window_radio      = self._add_radio(root, self.mode_group, "🪟  Window",      "window")
        self.selected_area_radio = self._add_radio(root, self.mode_group, "✂  Selected Area", "selected_area")

        root.addSpacing(6)
        self._add_sep(root)
        root.addSpacing(4)

        # ── Action selector (hidden; kept for test-harness compatibility) ─────
        # The visible per-capture action choice happens in ActionMenu after
        # selection.  These radio buttons are hidden but wired so that the
        # --run test mode and --ai test mode still work.
        self.action_group = QButtonGroup(self)
        self.screenshot_radio = self._make_hidden_radio(self.action_group, "screenshot", checked=True)
        self.ocr_radio        = self._make_hidden_radio(self.action_group, "ocr")
        self.ai_radio         = self._make_hidden_radio(self.action_group, "ai")

        root.addSpacing(6)
        self._add_sep(root)
        root.addSpacing(4)

        # ── Capture button ────────────────────────────────────────────────────
        self.capture_button = QPushButton("  Capture")
        self.capture_button.setObjectName("capture")
        self.capture_button.setMinimumHeight(44)
        self.capture_button.setCursor(Qt.PointingHandCursor)
        self.capture_button.clicked.connect(self.start_capture)
        root.addWidget(self.capture_button)

        # ── Status label ──────────────────────────────────────────────────────
        self.status_label = QLabel("Choose a capture mode and click Capture.")
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"font-size: 11px; color: {_TEXT_DIM}; padding-top: 6px;")
        root.addWidget(self.status_label)

    @staticmethod
    def _make_hidden_radio(group: QButtonGroup, value: str, checked: bool = False) -> QRadioButton:
        """Create a hidden QRadioButton used only for test-harness compatibility."""
        radio = QRadioButton()
        radio.setProperty("value", value)
        radio.setChecked(checked)
        radio.setVisible(False)
        group.addButton(radio)
        return radio

    @staticmethod
    def _add_sep(layout: QVBoxLayout) -> None:
        sep = QFrame()
        sep.setObjectName("sep")
        layout.addWidget(sep)

    @staticmethod
    def _add_radio(
        layout: QVBoxLayout,
        group: QButtonGroup,
        text: str,
        value: str,
        checked: bool = False,
    ) -> QRadioButton:
        radio = QRadioButton(text)
        radio.setProperty("value", value)
        radio.setChecked(checked)
        group.addButton(radio)
        layout.addWidget(radio)
        return radio

    @staticmethod
    def _selected_value(group: QButtonGroup) -> str:
        btn = group.checkedButton()
        return btn.property("value")

    # ── Capture flow ──────────────────────────────────────────────────────────

    def start_capture(self) -> None:
        # If the hidden action_group has "ai" selected (test mode), handle it inline.
        if self._selected_value(self.action_group) == "ai":
            QMessageBox.information(self, "Ask AI", "AI integration is coming next.")
            return

        self.capture_button.setEnabled(False)
        self.last_capture_path = None
        self.last_extracted_text = None
        self.status_label.setText("Preparing…")
        self.hide()
        # Short delay so the menu window disappears before the portal fires.
        QTimer.singleShot(120, self._run_capture)

    def _run_capture(self) -> None:
        mode = self._selected_value(self.mode_group)
        try:
            path = self._capture(mode)
        except Exception as error:
            self._on_capture_done(None, error)
            return
        self._on_capture_done(path, None)

    def _capture(self, mode: str) -> Path | None:
        if mode == "full_screen":
            return asyncio.run(self.capture.capture_full_screen())
        if mode == "window":
            return asyncio.run(capture_window())
        if mode == "selected_area":
            return asyncio.run(capture_selected_area())
        raise ValueError(f"Unknown capture mode: {mode}")

    def _on_capture_done(self, path: Path | None, error: Exception | None) -> None:
        self.capture_button.setEnabled(True)

        if error is not None:
            self.status_label.setText(f"Capture failed: {error}")
            self.show()
            self.raise_()
            self.activateWindow()
            self.capture_finished.emit()
            QMessageBox.critical(self, "Capture failed", str(error))
            return

        if path is None:
            self.status_label.setText("Capture cancelled.")
            self.show()
            self.raise_()
            self.activateWindow()
            self.capture_finished.emit()
            return

        self.last_capture_path = path
        self.status_label.setText(f"Saved: {path.name}")
        self.capture_finished.emit()

        # Show action menu; don't re-show the mode picker until it's done
        self._show_action_menu(path)


    def _show_action_menu(self, path: Path) -> None:
        if self._action_menu is not None:
            try:
                self._action_menu.close()
            except RuntimeError:
                pass
            self._action_menu = None

        menu = ActionMenu(captured_path=path)
        self._action_menu = menu
        # When the action menu closes, bring the capture mode picker back
        menu.destroyed.connect(self._on_action_menu_closed)
        menu.show()
        menu.raise_()
        menu.activateWindow()

    def _on_action_menu_closed(self) -> None:
        self._action_menu = None
        self.show()
        self.raise_()
        self.activateWindow()

    # ── Slots wired by main.py ────────────────────────────────────────────────

    @Slot()
    def show_from_global_shortcut(self) -> None:
        """Bring the capture mode picker forward after Ctrl+Shift+S."""
        print("[CAPTURE MENU] Opened via shortcut or tray", flush=True)
        self.show()
        self.raise_()
        self.activateWindow()

    @Slot(str)
    def set_global_shortcut_registered(self, trigger: str) -> None:
        self.status_label.setText(f"Global shortcut registered: {trigger}")

    @Slot(str)
    def set_global_shortcut_error(self, error: str) -> None:
        self.status_label.setText(f"Global shortcut unavailable: {error}")


# ─────────────────────────────────────────────────────────────────────────────
#  Standalone entry point (used by tests and legacy desktop entry)
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    application = QApplication(sys.argv)
    application.setQuitOnLastWindowClosed(False)
    menu = CaptureMenu()
    shortcut_manager = GlobalShortcutManager()

    shortcut_manager.shortcut_activated.connect(menu.show_from_global_shortcut)
    shortcut_manager.registration_succeeded.connect(menu.set_global_shortcut_registered)
    shortcut_manager.registration_failed.connect(menu.set_global_shortcut_error)
    application.aboutToQuit.connect(shortcut_manager.stop)

    shortcut_manager.start()
    menu.show()
    sys.exit(application.exec())


if __name__ == "__main__":
    main()
