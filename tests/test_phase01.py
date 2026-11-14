"""Headless lifecycle regression tests. Never assert a physical keyboard PASS."""
import asyncio
import os
from pathlib import Path
import subprocess
import sys
import signal
import tempfile
import threading
import time
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

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
from shortcuts.global_shortcut import GlobalShortcutManager, PREFERRED_TRIGGER

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
    preferred_trigger = PREFERRED_TRIGGER
    shortcut_activated = Signal()
    registration_succeeded = Signal(str)
    registration_failed = Signal(str)
    assignment_changed = Signal(str, str, str)
    identity_changed = Signal(str)
    configuration_available_changed = Signal(bool)
    configuration_message = Signal(str)
    def request_configuration(self):
        return False


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
        async def window(**kwargs):
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

    def test_shutdown_cancels_ocr_before_any_clipboard_delivery(self):
        cancelled = []
        async def ocr(path):
            try:
                await asyncio.sleep(60)
            finally:
                cancelled.append(True)
        with patch('ui.capture_menu.extract_text_async', ocr), \
             patch('ui.capture_menu.copy_text_to_clipboard') as clipboard:
            self.menu._handle_capture_result(self.source, 'extract_text')
            spin_until(lambda: len(asyncio.all_tasks(self.menu.jobs.loop)) > 0)
            # Ensure the OCR coroutine has entered before cancelling it.
            self.menu.jobs.tick()
            self.menu.shutdown()
            self.menu.jobs.close()
            self.assertEqual(cancelled, [True])
            clipboard.assert_not_called()


    def test_fullscreen_completion_closes_overlay(self):
        self.menu.launch_overlay()
        spin_until(lambda: self.menu._overlay is not None)
        saved = Path(_scratch.name) / 'saved.png'
        with patch('ui.capture_menu._save_full', return_value=saved), \
             patch('ui.capture_menu.copy_image_to_clipboard') as clipboard:
            self.menu._overlay._on_mode_changed(__import__('ui.overlay', fromlist=['SnipMode']).SnipMode.FULLSCREEN)
            spin_until(lambda: not self.menu.busy)
        clipboard.assert_called_once_with(saved)
        self.assertIsNone(self.menu._overlay)
        self.assertFalse(self.menu.isVisible())

    def test_window_cancel_does_not_report_success(self):
        with patch('ui.capture_menu.capture_window', new=AsyncMock(return_value=None)), \
             patch('ui.capture_menu.copy_image_to_clipboard') as clipboard:
            self.menu._on_window_requested('screenshot')
            spin_until(lambda: not self.menu.busy)
            clipboard.assert_not_called()
            self.assertEqual(self.menu.status_label.text(), 'Window capture cancelled.')

    def test_rectangle_completion_keeps_overlay_until_clipboard(self):
        self.menu.launch_overlay()
        spin_until(lambda: self.menu._overlay is not None)
        from PySide6.QtCore import QPoint
        overlay = self.menu._overlay
        overlay.start_point, overlay.end_point = QPoint(10, 10), QPoint(40, 40)
        with patch('ui.capture_menu.copy_image_to_clipboard',
                   side_effect=lambda _: self.assertIs(self.menu._overlay, overlay)):
            overlay.confirm_selection()
            spin_until(lambda: not self.menu.busy)
        self.assertFalse(self.menu.isVisible())
        self.assertTrue(self.menu.last_capture_path.is_file())

    def test_real_ocr_process_boundary_error_and_cancel(self):
        from utils.ocr_process import extract_text_async
        # Real worker protocol error is generic and does not expose document text.
        task = self.menu.jobs.submit(extract_text_async('/nonexistent/phase01.png'))
        spin_until(task.done)
        with self.assertRaises(RuntimeError):
            task.result()
        # Replace the worker command with a real long-running process group.
        real_spawn = asyncio.create_subprocess_exec
        pid_file = Path(_scratch.name) / 'worker.pid'
        code = f"import os,time; from pathlib import Path; Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(60)"
        async def spawn(*args, **kwargs):
            return await real_spawn(sys.executable, '-c', code, **kwargs)
        with patch('utils.ocr_process.asyncio.create_subprocess_exec', side_effect=spawn):
            task = self.menu.jobs.submit(extract_text_async(self.source))
            spin_until(pid_file.exists)
            pid = int(pid_file.read_text())
            self.menu.shutdown()
            self.menu.jobs.close()
            self.assertTrue(task.cancelled())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)



class EntryTests(unittest.TestCase):
    def test_gnome_theme_fallback_and_explicit_preference(self):
        with patch.dict(os.environ, {'XDG_CURRENT_DESKTOP': 'ubuntu:GNOME'}, clear=True):
            with patch('main.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='overrides\n')):
                main.prepare_qt_environment()
            self.assertEqual(os.environ['QT_QPA_PLATFORMTHEME'], 'generic')
            os.environ['QT_QPA_PLATFORMTHEME'] = 'user-theme'
            with patch('main.subprocess.run') as probe:
                main.prepare_qt_environment()
                probe.assert_not_called()
            self.assertEqual(os.environ['QT_QPA_PLATFORMTHEME'], 'user-theme')

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

    def test_actual_main_duplicate_start_signal_shutdown_and_restart(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            env = dict(os.environ, HOME=folder, XDG_DATA_HOME=folder + '/data',
                       XDG_RUNTIME_DIR=folder, DBUS_SESSION_BUS_ADDRESS='unix:path=/nonexistent/phase01-bus')
            for attempt in range(2):
                process = subprocess.Popen([sys.executable, str(root / 'main.py')], env=env,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    lock = Path(folder) / f'{APP_ID}.lock'
                    spin_until(lambda: lock.exists() or process.poll() is not None)
                    self.assertIsNone(process.poll())
                    second = subprocess.run([sys.executable, str(root / 'main.py')], env=env,
                                            capture_output=True, timeout=5)
                    self.assertEqual(second.returncode, 0)
                    self.assertIn(b'already running', second.stderr)
                    process.send_signal(signal.SIGTERM)
                    _, errors = process.communicate(timeout=5)
                    self.assertEqual(process.returncode, 0, errors)
                    self.assertFalse(lock.exists())
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.communicate()



class PortalCleanupTests(unittest.TestCase):
    def test_cancel_during_bus_connect_disconnects(self):
        from ui.capture_menu import _portal_screenshot
        from utils.async_jobs import AsyncJobs
        bus = SimpleNamespace(started=False, closed=False)
        async def connect():
            bus.started = True
            await asyncio.sleep(60)
        bus.connect = connect
        bus.disconnect = lambda: setattr(bus, 'closed', True)
        jobs = AsyncJobs()
        try:
            with patch('capture.screenshot_portal_request.MessageBus', return_value=bus):
                task = jobs.submit(_portal_screenshot())
                spin_until(lambda: bus.started)
                task.cancel()
                spin_until(task.done)
            self.assertTrue(task.cancelled())
            self.assertTrue(bus.closed)
        finally:
            jobs.close()

    def test_early_response_and_cancel_cleanup(self):
        from dbus_next import MessageType, Variant
        from ui.capture_menu import _portal_screenshot
        from utils.async_jobs import AsyncJobs

        class Bus:
            unique_name = ':1.900'
            def __init__(self, delay=False):
                self.handler = None
                self.delay = delay
                self.closed = False
                self.request_closed = False
                self.started = False
            async def connect(self):
                return self
            def add_message_handler(self, handler):
                self.handler = handler
            def remove_message_handler(self, handler):
                self.handler = None
            def disconnect(self):
                self.closed = True
            async def call(self, message):
                if message.member == 'Register':
                    return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=[])
                if message.member == 'Get':
                    return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=[Variant('u', 2)])
                if message.member == 'Close':
                    self.request_closed = True
                    return SimpleNamespace(message_type=MessageType.METHOD_RETURN)
                self.started = True
                if self.delay:
                    await asyncio.sleep(60)
                token = message.body[1]['handle_token'].value
                path = '/org/freedesktop/portal/desktop/request/1_900/' + token
                # Signal can arrive before Screenshot method reply.
                self.handler(SimpleNamespace(message_type=MessageType.SIGNAL,
                    interface='org.freedesktop.portal.Request', member='Response',
                    path=path, body=[0, {'uri': Variant('s', 'file:///tmp/synthetic.png')}]))
                return SimpleNamespace(message_type=MessageType.METHOD_RETURN, body=[path])

        for cancelled in (False, True):
            bus = Bus(delay=cancelled)
            jobs = AsyncJobs()
            try:
                with patch('capture.screenshot_portal_request.MessageBus', return_value=bus):
                    task = jobs.submit(_portal_screenshot())
                    spin_until(lambda: bus.started)
                    if cancelled:
                        task.cancel()
                    spin_until(task.done)
                    if cancelled:
                        self.assertTrue(task.cancelled())
                        self.assertTrue(bus.request_closed)
                    else:
                        self.assertEqual(task.result(), Path('/tmp/synthetic.png'))
                self.assertTrue(bus.closed)
                self.assertIsNone(bus.handler)
            finally:
                jobs.close()



if __name__ == '__main__':
    unittest.main()
