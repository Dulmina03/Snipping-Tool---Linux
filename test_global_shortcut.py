"""MANUAL: real portal/key test. No synthetic shortcut signal is emitted.

Run in GNOME/Wayland, authorize the shortcut, focus another app and press the
assigned Ctrl+Shift+S within 90 seconds. This requests a real screenshot.
"""
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from main import acquire_instance_lock, configure_application, prepare_qt_environment


def main():
    prepare_qt_environment()
    app = QApplication(sys.argv)
    lock = acquire_instance_lock()
    if lock is None:
        print('NOT RUN: quit the existing app before this manual test.')
        return 1
    menu, shortcuts, tray, tray_menu = configure_application(app)
    observed = {'key': False, 'passed': False}
    shortcuts.shortcut_activated.connect(lambda: observed.update(key=True))
    shortcuts.registration_succeeded.connect(
        lambda trigger: print(f'Registered {trigger}; physically press it with another app focused.'))

    def check():
        if observed['key'] and menu._overlay is not None:
            observed['passed'] = not menu.isVisible() and menu._overlay.isVisible()
            app.quit()

    timer = QTimer()
    timer.timeout.connect(check)
    timer.start(50)
    QTimer.singleShot(90000, app.quit)
    try:
        shortcuts.start()
        app.exec()
    finally:
        menu.shutdown()
        menu.jobs.close()
        shortcuts.stop()
        tray.hide()
        lock.unlock()
    print('PASS: portal Activated reached the overlay; inspect desktop visually.' if observed['passed']
          else 'FAIL: no successful real shortcut/overlay within timeout.')
    return 0 if observed['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
