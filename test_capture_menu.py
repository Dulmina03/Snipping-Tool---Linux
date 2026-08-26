"""Manual smoke test for the capture menu."""

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ui.capture_menu import CaptureMenu
from utils.clipboard import clipboard_contains_image, clipboard_contains_text


def main() -> int:
    application = QApplication(sys.argv)
    menu = CaptureMenu()

    if menu.mode_group.checkedButton() is None:
        print("CAPTURE MENU TEST FAIL: no default capture mode")
        return 1

    if menu.action_group.checkedButton() is None:
        print("CAPTURE MENU TEST FAIL: no default action")
        return 1

    if "--smoke" in sys.argv:
        menu.show()
        QTimer.singleShot(500, application.quit)
        application.exec()
        print("CAPTURE MENU SMOKE TEST PASS")
        return 0

    if "--cancel" in sys.argv:
        menu._capture = lambda mode: None
        menu.capture_finished.connect(
            lambda: application.exit(
                0
                if menu.status_label.text() == "Capture cancelled."
                and menu.capture_button.isEnabled()
                else 1
            )
        )
        menu.show()
        QTimer.singleShot(100, menu.start_capture)
        exit_code = application.exec()
        print(
            "CAPTURE MENU CANCELLATION TEST "
            f"{'PASS' if exit_code == 0 else 'FAIL'}"
        )
        return exit_code

    if "--ai" in sys.argv:
        messages = []
        menu.ai_radio.setChecked(True)
        menu._show_information = lambda title, message: messages.append((title, message))
        menu.start_capture()

        if messages == [("Ask AI", "AI integration is coming next.")]:
            print("CAPTURE MENU AI TEST PASS")
            return 0

        print("CAPTURE MENU AI TEST FAIL")
        return 1

    if "--run" in sys.argv:
        run_index = sys.argv.index("--run")

        try:
            mode, action = sys.argv[run_index + 1:run_index + 3]
        except ValueError:
            print("Usage: python test_capture_menu.py --run MODE ACTION")
            return 1

        mode_buttons = {
            "full_screen": menu.full_screen_radio,
            "window": menu.window_radio,
            "selected_area": menu.selected_area_radio,
        }
        action_buttons = {
            "screenshot": menu.screenshot_radio,
            "ocr": menu.ocr_radio,
        }

        if mode not in mode_buttons or action not in action_buttons:
            print("CAPTURE MENU TEST FAIL: unsupported mode or action")
            return 1

        mode_buttons[mode].setChecked(True)
        action_buttons[action].setChecked(True)
        menu._show_information = lambda title, message: print(f"{title}: {message}")
        menu._show_error = lambda title, message: print(f"{title}: {message}")

        def verify_result() -> None:
            path = menu.last_capture_path

            if path is None or not Path(path).is_file():
                print("CAPTURE MENU TEST FAIL: capture did not save a PNG")
                application.exit(1)
                return

            if action == "screenshot" and not clipboard_contains_image():
                print("CAPTURE MENU TEST FAIL: clipboard has no image")
                application.exit(1)
                return

            if action == "ocr":
                if not menu.last_extracted_text:
                    print("CAPTURE MENU TEST FAIL: OCR found no text")
                    application.exit(1)
                    return

                if not clipboard_contains_text(menu.last_extracted_text):
                    print("CAPTURE MENU TEST FAIL: clipboard text did not match OCR")
                    application.exit(1)
                    return

            print("CAPTURE MENU TEST PASS")
            application.exit(0)

        def start_capture() -> None:
            menu.start_capture()

        menu.show()
        menu.capture_finished.connect(verify_result)
        QTimer.singleShot(100, start_capture)
        return application.exec()

    menu.show()

    print("Capture menu launched.")
    print("Manually test Full Screen, Window, and Selected Area with Screenshot.")
    print("Then test Extract Text and cancel Selected Area with Escape.")
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
