"""Main entry point for AI Snipping Tool background daemon."""

import sys
import os
import subprocess
import logging
import signal
from pathlib import Path

from utils.desktop_entry import APP_ID, ensure_desktop_entry

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication

from shortcuts.global_shortcut import GlobalShortcutManager
from ui.capture_menu import CaptureMenu
from utils.capture_diagnostics import trace


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
    if os.environ.get('SNIPPING_DIAGNOSTICS') == '1':
        heartbeat = QTimer(menu)
        heartbeat.setInterval(1000)
        heartbeat.timeout.connect(lambda: trace('event_loop_heartbeat',
            clipboard_owned=application.clipboard().ownsClipboard(),
            application_alive=QApplication.instance() is application,
            capture_jobs=len(menu.jobs.tasks)))
        heartbeat.start()

    # No tray/status window: the service owns background lifetime and control.
    shortcut_manager.shortcut_activated.connect(menu.launch_overlay)
    shortcut_manager.identity_changed.connect(
        lambda status: logging.getLogger(__name__).info('Application identity: %s', status))
    shortcut_manager.registration_failed.connect(
        lambda error: logging.getLogger(__name__).error('Shortcut registration failed: %s', error))
    application.aboutToQuit.connect(
        lambda: logging.getLogger(__name__).info('QApplication aboutToQuit emitted'))
    application.aboutToQuit.connect(menu.shutdown)

    return menu, shortcut_manager


def main() -> int:
    if "--install-desktop" in sys.argv:
        try:
            print(ensure_desktop_entry())
            return 0
        except (OSError, RuntimeError, ValueError) as error:
            print(str(error), file=sys.stderr)
            return 1
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    prepare_qt_environment()
    application = QApplication(sys.argv)
    lock = acquire_instance_lock()
    if lock is None:
        print("AI Snipping Tool is already running, or its runtime lock is unavailable.", file=sys.stderr)
        return 0
    menu, shortcut_manager = configure_application(application)
    previous_handlers = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[sig] = signal.signal(sig, lambda *_: application.quit())
    try:
        shortcut_manager.start()
        return application.exec()
    finally:
        logging.getLogger(__name__).info('Shutdown: stopping capture jobs')
        menu.shutdown()
        menu.jobs.close()
        logging.getLogger(__name__).info('Shutdown: closing shortcut portal session')
        shortcut_manager.stop()
        lock.unlock()
        logging.getLogger(__name__).info('Shutdown complete')
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    sys.exit(main())
