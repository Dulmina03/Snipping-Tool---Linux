import asyncio
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from capture.screenshot import ScreenshotCapture
from utils.clipboard import clipboard_contains_image


async def main():

    print("Starting screenshot...")

    capture = ScreenshotCapture()

    path = await capture.capture_full_screen()

    if not path.is_file():
        raise RuntimeError(f"Screenshot file does not exist: {path}")

    if not clipboard_contains_image():
        raise RuntimeError("Clipboard does not contain an image.")

    print()
    print("Screenshot saved!")
    print(path)
    print("Clipboard image verified!")


if __name__ == "__main__":
    application = QApplication(sys.argv)
    exit_code = 1

    def run_test() -> None:
        global exit_code

        try:
            asyncio.run(main())
            exit_code = 0
        except Exception as error:
            print(f"TEST FAIL: {error}")
        finally:
            QTimer.singleShot(100, application.quit)

    QTimer.singleShot(100, run_test)
    application.exec()
    raise SystemExit(exit_code)
