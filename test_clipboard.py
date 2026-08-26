import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from utils.clipboard import clipboard_contains_image, copy_image_to_clipboard


SCREENSHOTS_DIR = Path.home() / "Pictures" / "Screenshots"


def latest_screenshot() -> Path:
    screenshots = list(SCREENSHOTS_DIR.glob("*.png"))

    if not screenshots:
        raise FileNotFoundError(
            f"No PNG screenshots found in: {SCREENSHOTS_DIR}"
        )

    return max(screenshots, key=lambda path: path.stat().st_mtime)


def main() -> int:
    image_path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else latest_screenshot()

    print("Clipboard test image:")
    print(image_path)

    try:
        copy_image_to_clipboard(image_path)
    except Exception as error:
        print()
        print("CLIPBOARD TEST FAIL")
        print(error)
        return 1

    application = QGuiApplication.instance()
    application.processEvents()

    if not clipboard_contains_image():
        clipboard = application.clipboard()
        image = clipboard.image()

        print()
        print("CLIPBOARD TEST FAIL")
        print("The system clipboard does not contain a valid image.")
        print(f"Qt platform: {QGuiApplication.platformName()}")
        print(f"Owns clipboard: {clipboard.ownsClipboard()}")
        print(f"Clipboard MIME formats: {clipboard.mimeData().formats()}")
        print(f"Clipboard image is null: {image.isNull()}")
        return 1

    print()
    print("CLIPBOARD TEST PASS")
    print(f"Qt platform: {QGuiApplication.platformName()}")
    print("Clipboard image verified.")
    return 0


if __name__ == "__main__":
    application = QApplication(sys.argv)
    exit_code = 1

    def run_test() -> None:
        global exit_code

        exit_code = main()
        QTimer.singleShot(100, application.quit)

    QTimer.singleShot(100, run_test)
    application.exec()
    raise SystemExit(exit_code)
