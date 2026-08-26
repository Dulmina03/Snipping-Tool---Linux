import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ocr.ocr_engine import extract_text, tesseract_version
from utils.clipboard import copy_text_to_clipboard, clipboard_contains_text


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

    print("OCR engine status:")

    try:
        print(f"Tesseract {tesseract_version()}")
        print()
        print("Image used:")
        print(image_path)

        text = extract_text(image_path)
    except Exception as error:
        print()
        print("OCR TEST FAIL")
        print(error)
        return 1

    print()
    print("Extracted text:")
    print(text if text else "(No text detected.)")

    if text:
        try:
            copy_text_to_clipboard(text)
        except Exception as error:
            print()
            print("OCR TEST FAIL")
            print(f"Could not copy extracted text to the clipboard: {error}")
            return 1

        if not clipboard_contains_text(text):
            print()
            print("OCR TEST FAIL")
            print("Clipboard text does not match the extracted text.")
            return 1

        print()
        print("Extracted text copied to clipboard.")
    else:
        print()
        print("No text was copied because OCR found no text.")

    print()
    print("OCR TEST PASS")
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
