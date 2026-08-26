"""Integration test for the XDG GlobalShortcuts portal registration."""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from shortcuts.global_shortcut import GlobalShortcutManager, PREFERRED_TRIGGER
from ui.capture_menu import CaptureMenu


def main() -> int:
    application = QApplication(sys.argv)
    menu = CaptureMenu()
    shortcut_manager = GlobalShortcutManager()
    activation_count = 0
    result = {"exit_code": 1}

    def on_activated() -> None:
        nonlocal activation_count

        activation_count += 1
        menu.show_from_global_shortcut()

    def finish(exit_code: int) -> None:
        shortcut_manager.stop()
        result["exit_code"] = exit_code
        application.quit()

    def on_registered(trigger: str) -> None:
        print(f"Registered shortcut: {trigger}")

        if trigger != PREFERRED_TRIGGER or not shortcut_manager.is_registered:
            print("GLOBAL SHORTCUT TEST FAIL: registration is not active")
            finish(1)
            return

        # Exercise the same Qt signal path used by a portal Activated signal.
        shortcut_manager.shortcut_activated.emit()

        QTimer.singleShot(100, verify_activation)

    def verify_activation() -> None:
        if activation_count != 1 or not menu.isVisible():
            print("GLOBAL SHORTCUT TEST FAIL: activation did not reach the menu")
            finish(1)
            return

        if not shortcut_manager.is_registered:
            print("GLOBAL SHORTCUT TEST FAIL: registration did not remain active")
            finish(1)
            return

        print("GLOBAL SHORTCUT TEST PASS")
        finish(0)

    def on_failed(error: str) -> None:
        print("GLOBAL SHORTCUT TEST FAIL")
        print(error)
        finish(1)

    shortcut_manager.shortcut_activated.connect(on_activated)
    shortcut_manager.registration_succeeded.connect(on_registered)
    shortcut_manager.registration_failed.connect(on_failed)

    if not shortcut_manager.start():
        print("GLOBAL SHORTCUT TEST FAIL: duplicate registration attempt")
        return 1

    application.exec()
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
