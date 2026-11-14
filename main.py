"""Main entry point for AI Snipping Tool background daemon."""

import sys
import os
import subprocess
import signal
from pathlib import Path

from utils.desktop_entry import APP_ID, ensure_desktop_entry

from PySide6.QtCore import QLockFile, QStandardPaths, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from shortcuts.global_shortcut import GlobalShortcutManager
from ui.capture_menu import CaptureMenu


def create_tray_icon() -> QIcon:
    """Create a high-resolution tray icon or load from theme."""
    icon = QIcon.fromTheme("camera-photo")
    if not icon.isNull():
        return icon

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    # Rounded background badge
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(30, 144, 255))
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)

    # Snipping tool camera / crosshair symbol
    painter.setPen(QPen(QColor(255, 255, 255), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawRoundedRect(14, 18, 36, 28, 6, 6)
    painter.drawEllipse(24, 24, 16, 16)
    painter.drawPoint(42, 22)
    painter.end()

    return QIcon(pixmap)


def prepare_qt_environment():
    """Avoid the observed Qt GTK theme abort on GNOME without XSettings keys.

    Respect an explicitly selected theme. This only selects a Qt fallback;
    it does not modify GNOME settings or installed schemas.
    """
    if os.environ.get("QT_QPA_PLATFORMTHEME") or "gnome" not in os.environ.get("XDG_CURRENT_DESKTOP", "").lower():
        return
    try:
        result = subprocess.run(
            ["gsettings", "list-keys", "org.gnome.settings-daemon.plugins.xsettings"],
            capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.TimeoutExpired):
        return
    if result.returncode == 0 and "antialiasing" not in result.stdout.splitlines():
        os.environ["QT_QPA_PLATFORMTHEME"] = "generic"


def acquire_instance_lock():
    runtime = QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation)
    lock = QLockFile(str(Path(runtime) / f"{APP_ID}.lock"))
    if not lock.tryLock(0):
        return None
    return lock


def configure_application(application):
    """Build a quiet background app; expose owned objects for lifecycle tests."""
    application.setQuitOnLastWindowClosed(False)
    application.setApplicationName(APP_ID)
    application.setDesktopFileName(APP_ID)
    menu = CaptureMenu()
    shortcut_manager = GlobalShortcutManager()

    # System Tray setup
    tray_icon = QSystemTrayIcon(create_tray_icon(), application)
    tray_icon.setToolTip("AI Snipping Tool\nPress Ctrl+Shift+S to capture")

    tray_menu = QMenu()
    capture_action = tray_menu.addAction("Capture (Ctrl+Shift+S)")
    capture_action.triggered.connect(menu.launch_overlay)

    tray_menu.addSeparator()

    quit_action = tray_menu.addAction("Quit")
    quit_action.triggered.connect(application.quit)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.activated.connect(
        lambda reason: menu.launch_overlay()
        if reason == QSystemTrayIcon.Trigger
        else None
    )
    tray_icon.show()

    # Wire global shortcut signals
    shortcut_manager.shortcut_activated.connect(menu.launch_overlay)
    shortcut_manager.registration_succeeded.connect(
        menu.set_global_shortcut_registered
    )
    shortcut_manager.registration_failed.connect(menu.set_global_shortcut_error)
    application.aboutToQuit.connect(menu.shutdown)

    return menu, shortcut_manager, tray_icon, tray_menu


def main() -> int:
    if "--install-desktop" in sys.argv:
        try:
            print(ensure_desktop_entry())
            return 0
        except (OSError, RuntimeError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 1
    prepare_qt_environment()
    application = QApplication(sys.argv)
    lock = acquire_instance_lock()
    if lock is None:
        print("AI Snipping Tool is already running, or its runtime lock is unavailable.", file=sys.stderr)
        return 0
    menu, shortcut_manager, tray_icon, tray_menu = configure_application(application)
    previous_handlers = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[sig] = signal.signal(sig, lambda *_: application.quit())
    try:
        shortcut_manager.start()
        return application.exec()
    finally:
        menu.shutdown()
        menu.jobs.close()
        shortcut_manager.stop()
        tray_icon.hide()
        lock.unlock()
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    sys.exit(main())
