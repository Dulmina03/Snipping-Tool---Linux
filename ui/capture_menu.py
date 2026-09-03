"""Capture menu for screenshots, OCR, and the future AI action."""

import asyncio
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from capture.screenshot import ScreenshotCapture
from capture.selected_area import main as capture_selected_area
from capture.window_capture import take_screenshot as capture_window
from ocr.ocr_engine import extract_text
from shortcuts.global_shortcut import GlobalShortcutManager
from utils.clipboard import copy_text_to_clipboard


class CaptureMenu(QWidget):
    """Small launcher for the project's established capture workflows."""

    capture_finished = Signal()

    def __init__(self):
        super().__init__()

        self.capture = ScreenshotCapture()
        self.last_capture_path = None
        self.last_extracted_text = None

        self.setWindowTitle("AI Snipping Tool")
        self.setFixedWidth(300)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("Capture")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        layout.addWidget(QLabel("Capture Mode"))

        self.mode_group = QButtonGroup(self)
        self.full_screen_radio = self._add_radio_button(
            layout, self.mode_group, "Full Screen", "full_screen", True
        )
        self.window_radio = self._add_radio_button(
            layout, self.mode_group, "Window", "window"
        )
        self.selected_area_radio = self._add_radio_button(
            layout, self.mode_group, "Selected Area", "selected_area"
        )

        layout.addSpacing(8)
        layout.addWidget(QLabel("Action"))

        self.action_group = QButtonGroup(self)
        self.screenshot_radio = self._add_radio_button(
            layout, self.action_group, "Screenshot", "screenshot", True
        )
        self.ocr_radio = self._add_radio_button(
            layout, self.action_group, "Extract Text", "ocr"
        )
        self.ai_radio = self._add_radio_button(
            layout, self.action_group, "Ask AI", "ai"
        )

        self.capture_button = QPushButton("Capture")
        self.capture_button.clicked.connect(self.start_capture)
        layout.addWidget(self.capture_button)

        self.status_label = QLabel("Choose a capture mode and action.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    @staticmethod
    def _add_radio_button(
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
        button = group.checkedButton()
        return button.property("value")

    def start_capture(self) -> None:
        action = self._selected_value(self.action_group)

        if action == "ai":
            self._show_information("Ask AI", "AI integration is coming next.")
            return

        self.capture_button.setEnabled(False)
        self.last_capture_path = None
        self.last_extracted_text = None
        self.status_label.setText("Preparing capture...")
        self.hide()

        # Let the menu hide before it can appear in a full-screen capture.
        QTimer.singleShot(100, self._run_capture)

    def _run_capture(self) -> None:
        mode = self._selected_value(self.mode_group)
        action = self._selected_value(self.action_group)

        try:
            path = self._capture(mode)

            if path is None:
                self.status_label.setText("Capture cancelled.")
                return

            self.last_capture_path = path

            if action == "ocr":
                self._extract_text(path)
            else:
                self.status_label.setText(f"Screenshot copied to clipboard:\n{path}")
                self._show_information(
                    "Screenshot captured",
                    f"Saved and copied to the clipboard:\n{path}",
                )
        except Exception as error:
            self.status_label.setText(f"Capture failed: {error}")
            self._show_error("Capture failed", str(error))
        finally:
            self.capture_button.setEnabled(True)
            self.show()
            self.raise_()
            self.activateWindow()
            self.capture_finished.emit()

    def _capture(self, mode: str):
        if mode == "full_screen":
            return asyncio.run(self.capture.capture_full_screen())

        if mode == "window":
            return asyncio.run(capture_window())

        if mode == "selected_area":
            # The existing Tk overlay must run on the main thread.
            return asyncio.run(capture_selected_area())

        raise ValueError(f"Unknown capture mode: {mode}")

    def _extract_text(self, image_path) -> None:
        text = extract_text(image_path)
        self.last_extracted_text = text

        if not text:
            self.status_label.setText("Capture saved, but no text was detected.")
            self._show_information(
                "No text detected",
                "The capture was saved, but Tesseract found no text to copy.",
            )
            return

        copy_text_to_clipboard(text)
        self.status_label.setText("Extracted text copied to clipboard.")
        self._show_information(
            "Text extracted",
            "Extracted text was copied to the clipboard.",
        )

    def _show_information(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    @Slot()
    def show_from_global_shortcut(self) -> None:
        """Bring the existing capture menu forward after Ctrl+Shift+S."""
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


def main() -> None:
    application = QApplication(sys.argv)
    menu = CaptureMenu()
    shortcut_manager = GlobalShortcutManager()

    shortcut_manager.shortcut_activated.connect(menu.show_from_global_shortcut)
    shortcut_manager.registration_succeeded.connect(
        menu.set_global_shortcut_registered
    )
    shortcut_manager.registration_failed.connect(menu.set_global_shortcut_error)
    application.aboutToQuit.connect(shortcut_manager.stop)

    shortcut_manager.start()
    menu.show()
    sys.exit(application.exec())


if __name__ == "__main__":
    main()
