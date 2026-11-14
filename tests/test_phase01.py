"""Headless lifecycle regression tests. Never assert a physical keyboard PASS."""
import asyncio
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import AsyncMock, patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
_scratch = tempfile.TemporaryDirectory(prefix='snipping-phase01-')
os.environ['HOME'] = _scratch.name
os.environ['XDG_DATA_HOME'] = _scratch.name + '/data'
os.environ['XDG_RUNTIME_DIR'] = _scratch.name

from PIL import Image
from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication

import main
from ui.capture_menu import CaptureMenu
from utils.desktop_entry import APP_ID, desktop_entry, ensure_desktop_entry
from shortcuts.global_shortcut import GlobalShortcutManager

app = QApplication.instance() or QApplication([])
app.setQuitOnLastWindowClosed(False)


def spin_until(predicate, seconds=3):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return
        time.sleep(.005)
    raise AssertionError('Timed out waiting for asynchronous state')


class FakeShortcuts(QObject):
    shortcut_activated = Signal()
    registration_succeeded = Signal(str)
    registration_failed = Signal(str)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.menu = CaptureMenu()
        self.toasts = []
        self.menu._show_toast = self.toasts.append
        self.source = Path(_scratch.name) / 'portal.png'
        Image.new('RGB', (100, 100), 'red').save(self.source)
        self.portal = patch('ui.capture_menu._portal_screenshot', new=AsyncMock(return_value=self.source))
        self.mock_portal = self.portal.start()

    def tearDown(self):
        self.menu.shutdown()
        self.menu.jobs.close()
        self.portal.stop()
        app.processEvents()

    def test_quiet_start_and_repeat_activation(self):
        self.assertFalse(self.menu.isVisible())
        self.assertIsNone(self.menu._overlay)
        self.menu.show_from_global_shortcut()
        self.menu.show_from_global_shortcut()
        spin_until(lambda: self.menu._overlay is not None)
        overlay = self.menu._overlay
        self.assertTrue(overlay.isVisible())
        self.assertFalse(self.menu.isVisible())
        self.menu.launch_overlay()
        self.assertIs(self.menu._overlay, overlay)
        self.assertEqual(self.mock_portal.await_count, 1)
        overlay.cancel_selection()
        self.assertIsNone(self.menu._overlay)
        self.assertFalse(self.menu.isVisible())
        self.assertFalse(self.source.exists())

    def test_denied_portal_keeps_controller_hidden_and_retry_works(self):
        self.mock_portal.side_effect = RuntimeError('denied')
        self.menu.launch_overlay()
        spin_until(lambda: not self.menu.busy)
        self.assertIsNone(self.menu._overlay)
        self.assertFalse(self.menu.isVisible())
        self.assertIn('denied', self.toasts[-1])
        self.mock_portal.side_effect = None
        self.menu.launch_overlay()
        spin_until(lambda: self.menu._overlay is not None)

    def test_slow_portal_heartbeat_and_shutdown(self):
        cancelled = []
        async def waiting(**kwargs):
            try:
                await asyncio.sleep(30)
            finally:
                cancelled.append(True)
        self.mock_portal.side_effect = waiting
        ticks = []
        timer = QTimer()
        timer.setInterval(5)
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start()
        self.menu.launch_overlay()
        spin_until(lambda: len(ticks) >= 8)
        self.assertTrue(self.menu.busy)
        self.assertFalse(self.menu.isVisible())
        self.menu.shutdown()
        self.menu.jobs.close()
        timer.stop()
        self.assertEqual(cancelled, [True])
        self.assertIsNone(self.menu._overlay)
        self.menu.launch_overlay()
        self.assertIsNone(self.menu._overlay)

    def test_window_portal_and_clipboard_remain_on_gui_thread(self):
        threads = []
        async def window():
            threads.append(QThread.currentThread())
            await asyncio.sleep(.03)
            return self.source
        with patch('ui.capture_menu.capture_window', window), \
             patch('ui.capture_menu.copy_image_to_clipboard', side_effect=lambda _: threads.append(QThread.currentThread())):
            self.menu._on_window_requested('screenshot')
            spin_until(lambda: not self.menu.busy)
        self.assertEqual(threads, [app.thread(), app.thread()])
        self.assertFalse(self.menu.isVisible())

    def test_ocr_keeps_gui_responsive_and_delivers_clipboard_on_main_thread(self):
        async def ocr(path):
            await asyncio.sleep(.08)
            return 'ශ්‍රී English'
        threads = []
        with patch('ui.capture_menu.extract_text_async', ocr), \
             patch('ui.capture_menu.copy_text_to_clipboard', side_effect=lambda _: threads.append(QThread.currentThread())):
            self.menu._handle_capture_result(self.source, 'extract_text')
            self.assertTrue(self.menu.busy)
            spin_until(lambda: not self.menu.busy)
        self.assertEqual(threads, [app.thread()])
        self.assertEqual(self.menu.last_extracted_text, 'ශ්‍රී English')

    def test_fullscreen_completion_closes_overlay(self):
        self.menu.launch_overlay()
        spin_until(lambda: self.menu._overlay is not None)
        saved = Path(_scratch.name) / 'saved.png'
        with patch('ui.capture_menu._save_full', return_value=saved), \
             patch('ui.capture_menu.copy_image_to_clipboard') as clipboard:
            self.menu._overlay._on_mode_changed(__import__('ui.overlay', fromlist=['SnipMode']).SnipMode.FULLSCREEN)
        clipboard.assert_called_once_with(saved)
        self.assertIsNone(self.menu._overlay)
        self.assertFalse(self.menu.isVisible())


class EntryTests(unittest.TestCase):
    def test_generated_launcher_and_custom_entry_preservation(self):
        with tempfile.TemporaryDirectory() as folder:
            apps = Path(folder)
            target = ensure_desktop_entry('/tmp/project with spaces', '/tmp/python with spaces', apps)
            text = target.read_text()
            self.assertIn('Exec="/tmp/python with spaces" "/tmp/project with spaces/main.py"', text)
            self.assertNotIn('capture_menu.py', text)
            result = subprocess.run(['desktop-file-validate', str(target)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            target.write_text('[Desktop Entry]\nName=My custom launcher\n')
            with self.assertRaises(RuntimeError):
                ensure_desktop_entry(applications_dir=apps)
            self.assertIn('My custom launcher', target.read_text())

    def test_migrate_legacy_launcher(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / f'{APP_ID}.desktop'
            target.write_text('[Desktop Entry]\nName=AI Snipping Tool\n'
                              f'StartupWMClass={APP_ID}\nExec=python /old/ui/capture_menu.py\n')
            ensure_desktop_entry(applications_dir=folder)
            self.assertIn('main.py', target.read_text())
            self.assertNotIn('/old/', target.read_text())

    def test_instance_lock(self):
        first = main.acquire_instance_lock()
        self.assertIsNotNone(first)
        try:
            self.assertIsNone(main.acquire_instance_lock())
        finally:
            first.unlock()
        next_lock = main.acquire_instance_lock()
        self.assertIsNotNone(next_lock)
        next_lock.unlock()

    def test_tray_and_shortcut_share_route_and_start_quietly(self):
        with patch('main.GlobalShortcutManager', FakeShortcuts):
            menu, shortcuts, tray, tray_menu = main.configure_application(app)
        menu._show_toast = lambda _: None
        try:
            self.assertFalse(menu.isVisible())
            self.assertIsNone(menu._overlay)
            self.assertEqual(app.desktopFileName(), APP_ID)
            with patch('ui.capture_menu._portal_screenshot', new=AsyncMock(side_effect=RuntimeError('denied'))) as portal:
                shortcuts.shortcut_activated.emit()
                spin_until(lambda: not menu.busy)
                tray_menu.actions()[0].trigger()
                spin_until(lambda: not menu.busy)
                self.assertEqual(portal.await_count, 2)
            self.assertFalse(menu.isVisible())
        finally:
            menu.shutdown()
            menu.jobs.close()
            tray.hide()
            app.aboutToQuit.disconnect(menu.shutdown)

    def test_old_standalone_entry_delegates(self):
        with patch('main.main', return_value=17) as canonical:
            from ui.capture_menu import main as compatibility_main
            self.assertEqual(compatibility_main(), 17)
            canonical.assert_called_once()

    def test_shutdown_during_shortcut_registration(self):
        manager = GlobalShortcutManager()
        entered = threading.Event()
        cancelled = threading.Event()
        async def waiting():
            entered.set()
            try:
                await asyncio.sleep(60)
            finally:
                cancelled.set()
        with patch.object(manager, '_register', waiting):
            self.assertTrue(manager.start())
            self.assertTrue(entered.wait(1))
            self.assertFalse(manager.start())
            started = time.monotonic()
            manager.stop()
        self.assertLess(time.monotonic() - started, 3)
        self.assertTrue(cancelled.is_set())
        self.assertFalse(manager._thread.is_alive())


if __name__ == '__main__':
    unittest.main()
