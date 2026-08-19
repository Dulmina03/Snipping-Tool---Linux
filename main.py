import sys
import asyncio

from PySide6.QtWidgets import (
    QApplication,
    QPushButton,
    QComboBox,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from PySide6.QtGui import QImage

from capture.screenshot import ScreenshotCapture


class SnippingTool(QWidget):

    def __init__(self):

        super().__init__()

        # -------------------------
        # Window
        # -------------------------

        self.setWindowTitle(
            "AI Snipping Tool"
        )

        self.setFixedSize(
            420,
            80
        )

        # -------------------------
        # Screenshot engine
        # -------------------------

        self.capture = (
            ScreenshotCapture()
        )

        # -------------------------
        # Capture dropdown
        # -------------------------

        self.capture_dropdown = (
            QComboBox()
        )

        self.capture_dropdown.addItems(
            [
                "Full Screen",
                "Window",
                "Selected Area",
            ]
        )

        # -------------------------
        # Buttons
        # -------------------------

        self.screenshot_button = (
            QPushButton("Screenshot")
        )

        self.text_button = (
            QPushButton("Extract Text")
        )

        self.ai_button = (
            QPushButton("Ask AI")
        )

        # -------------------------
        # Layout
        # -------------------------

        main_layout = QVBoxLayout()

        main_layout.setContentsMargins(
            10,
            8,
            10,
            8,
        )

        main_layout.setSpacing(
            6
        )

        capture_layout = (
            QHBoxLayout()
        )

        capture_layout.addWidget(
            self.capture_dropdown
        )

        action_layout = (
            QHBoxLayout()
        )

        action_layout.setSpacing(
            6
        )

        action_layout.addWidget(
            self.screenshot_button
        )

        action_layout.addWidget(
            self.text_button
        )

        action_layout.addWidget(
            self.ai_button
        )

        main_layout.addLayout(
            capture_layout
        )

        main_layout.addLayout(
            action_layout
        )

        self.setLayout(
            main_layout
        )

        # -------------------------
        # Connections
        # -------------------------

        self.screenshot_button.clicked.connect(
            self.take_screenshot
        )

        self.text_button.clicked.connect(
            self.extract_text
        )

        self.ai_button.clicked.connect(
            self.ask_ai
        )

    # ==================================================
    # Screenshot
    # ==================================================

    def take_screenshot(self):

        mode = (
            self.capture_dropdown
            .currentText()
        )

        try:

            if mode == "Full Screen":

                path = asyncio.run(
                    self.capture
                    .capture_full_screen()
                )

            elif mode == "Window":

                path = asyncio.run(
                    self.capture
                    .capture_window()
                )

            elif mode == "Selected Area":

                path = asyncio.run(
                    self.capture
                    .capture_area()
                )

            else:

                raise RuntimeError(
                    "Unknown capture mode."
                )

            # Copy screenshot to clipboard
            self.copy_to_clipboard(
                path
            )

            print()
            print(
                "Screenshot saved:"
            )

            print(path)

            print(
                "Copied to clipboard."
            )

        except Exception as error:

            QMessageBox.critical(
                self,
                "Screenshot Error",
                str(error),
            )

            print(
                "Screenshot error:"
            )

            print(error)

    # ==================================================
    # Clipboard
    # ==================================================

    def copy_to_clipboard(
        self,
        path,
    ):

        image = QImage(
            str(path)
        )

        if image.isNull():

            raise RuntimeError(
                "Could not load screenshot "
                "for clipboard."
            )

        QApplication.clipboard().setImage(
            image
        )

    # ==================================================
    # Extract Text
    # ==================================================

    def extract_text(self):

        QMessageBox.information(
            self,
            "Extract Text",
            "OCR will be added next.",
        )

    # ==================================================
    # Ask AI
    # ==================================================

    def ask_ai(self):

        QMessageBox.information(
            self,
            "Ask AI",
            "AI functionality will be "
            "added later.",
        )


# ======================================================
# Start application
# ======================================================

app = QApplication(
    sys.argv
)

window = SnippingTool()

window.show()

sys.exit(
    app.exec()
)