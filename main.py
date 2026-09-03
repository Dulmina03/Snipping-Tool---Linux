"""Main entry point for AI Snipping Tool background daemon."""

import sys

from PySide6.QtCore import Qt
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


def main() -> int:
    application = QApplication(sys.argv)
    application.setQuitOnLastWindowClosed(False)

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
    shortcut_manager.shortcut_activated.connect(menu.show_from_global_shortcut)
    shortcut_manager.registration_succeeded.connect(
        menu.set_global_shortcut_registered
    )
    shortcut_manager.registration_failed.connect(menu.set_global_shortcut_error)
    application.aboutToQuit.connect(shortcut_manager.stop)

    print("AI Snipping Tool started in background.")
    print("Press Ctrl+Shift+S to capture or use the system tray icon.")

    shortcut_manager.start()

    # Start quietly in the background without opening menu/overlay
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())