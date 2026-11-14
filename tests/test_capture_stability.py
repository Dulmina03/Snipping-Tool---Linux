"""Controlled production workflows: worker ownership/cancellation and long runs.

No physical input, actual GNOME permission UI or external paste is asserted.
"""
import asyncio
import json
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, QRect, QThread, QTimer
from PySide6.QtGui import QImage
from test_phase01 import app, spin_until
import test_repeated_capture as repeated
import ui.capture_menu as capture
from capture.screenshot_portal_request import ScreenshotPortalError
from utils.capture_diagnostics import timed


class CaptureStabilityTests(unittest.TestCase):
    setUp = repeated.RepeatedCaptureTests.setUp
    tearDown = repeated.RepeatedCaptureTests.tearDown
    launch = repeated.RepeatedCaptureTests.launch
    finish = repeated.RepeatedCaptureTests.finish
    portal = repeated.RepeatedCaptureTests.portal

    def test_slow_save_keeps_gui_alive_coalesces_requests_and_delivers_on_gui(self):
        entered, release = threading.Event(), threading.Event()
        original = capture.save_png
        worker_threads, gui_threads = [], []
        def save(*args):
            worker_threads.append(QThread.currentThread() == app.thread())
            entered.set()
            if not release.wait(3):
                raise TimeoutError('Test worker was not released')
            return original(*args)
        original_copy = capture.copy_image_to_clipboard
        def copy(path):
            gui_threads.append(QThread.currentThread() == app.thread())
            self.assertIsNotNone(self.menu._overlay)
            original_copy(path)
        self.launch()
        try:
            with patch.object(capture, 'save_png', save), patch.object(capture, 'copy_image_to_clipboard', copy):
                self.menu._on_area_selected(QRect(10, 10, 20, 15), self.menu._src_path, 'screenshot')
                spin_until(entered.is_set)
                beats = len(self.heartbeats)
                for _ in range(20):
                    self.menu.launch_overlay()
                    self.menu._on_fullscreen(self.sources[-1], 'screenshot')
                    self.menu._on_window_requested('screenshot')
                    app.processEvents()
                    time.sleep(.002)
                self.assertEqual(self.counter, 1)
                self.assertGreater(len(self.heartbeats), beats)
                self.assertTrue(self.sources[-1].exists())
                release.set()
                spin_until(lambda: not self.menu.busy and not self.menu.jobs.tasks)
        finally:
            release.set()
        self.assertEqual(worker_threads, [False])
        self.assertEqual(gui_threads, [True])
        self.assertEqual(len(list(self.saved.glob('*.png'))), 1)
        self.assertFalse(list(self.saved.glob('.capture-*')))
        self.assertIsNone(self.menu._overlay)

    def test_cancel_running_write_drains_before_retry_without_late_clipboard(self):
        entered, release = threading.Event(), threading.Event()
        original = capture.save_png
        def save(*args):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('Test worker was not released')
            return original(*args)
        capture.copy_text_to_clipboard('previous සිංහල ශ්‍රී\u200d — !')
        self.launch()
        try:
            with patch.object(capture, 'save_png', save):
                self.menu._on_area_selected(QRect(10, 10, 20, 15), self.menu._src_path, 'screenshot')
                spin_until(entered.is_set)
                task = self.menu._pending
                self.menu._on_cancelled()
                app.processEvents()
                self.menu.jobs.tick()
                task.cancel()  # Repeated cancellation must not abandon the thread.
                self.menu.launch_overlay()
                self.assertEqual(self.counter, 1)
                self.assertTrue(self.menu.busy)
                self.assertTrue(self.sources[-1].exists())
                release.set()
                spin_until(lambda: not self.menu.jobs.tasks)
                self.assertTrue(task.cancelled())
        finally:
            release.set()
        self.assertEqual(app.clipboard().text(), 'previous සිංහල ශ්‍රී\u200d — !')
        self.assertIsNone(self.menu.last_capture_path)
        self.assertIsNone(self.menu._clipboard_pending)
        self.assertFalse(self.sources[-1].exists())
        # A completed atomic save is preserved even if cancellation arrived while encoding.
        previous = list(self.saved.glob('*.png'))
        self.assertEqual(len(previous), 1)
        snapshot = previous[0].read_bytes()
        self.launch(); self.finish()
        self.assertEqual(previous[0].read_bytes(), snapshot)
        self.assertFalse(asyncio.all_tasks(self.menu.jobs.loop))

    def test_shutdown_during_file_work_joins_thread_cleans_source_and_never_copies(self):
        entered, release = threading.Event(), threading.Event()
        original = capture.save_png
        def save(*args):
            entered.set()
            if not release.wait(3):
                raise TimeoutError('Test worker was not released')
            return original(*args)
        self.launch()
        timer = None
        try:
            with patch.object(capture, 'save_png', save), patch.object(capture, 'copy_image_to_clipboard') as copy:
                self.menu._on_area_selected(QRect(10, 10, 20, 15), self.menu._src_path, 'screenshot')
                spin_until(entered.is_set)
                timer = threading.Timer(.05, release.set); timer.start()
                self.menu.shutdown(); self.menu.jobs.close()
                copy.assert_not_called()
                self.assertTrue(self.menu.jobs.closed)
                self.assertFalse(self.menu.jobs.file_executor._threads & set(threading.enumerate()))
        finally:
            release.set()
            if timer is not None: timer.join()
        self.assertFalse(self.sources[-1].exists())
        self.assertIsNone(self.menu._overlay)
        self.assertIsNone(self.menu.last_capture_path)
        self.assertFalse(list(self.saved.glob('.capture-*')))

    def test_cancel_before_save_coroutine_starts_cleans_source_and_allows_retry(self):
        self.launch()
        self.menu._on_area_selected(QRect(10, 10, 20, 15), self.menu._src_path, 'screenshot')
        self.menu._on_cancelled()
        spin_until(lambda: not self.menu.jobs.tasks)
        self.assertFalse(self.sources[-1].exists())
        self.assertFalse(self.saved.exists())
        self.assertIsNone(self.menu.last_capture_path)
        self.launch(); self.finish()

    def test_fifty_rapid_open_cancel_cycles_leave_no_overlay_source_or_jobs(self):
        starting_fds = len(list(Path('/proc/self/fd').iterdir()))
        for _ in range(50):
            overlay = self.launch()
            self.menu.launch_overlay()
            overlay.cancel_selection()
            spin_until(lambda: not self.menu.jobs.tasks)
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            self.assertIsNone(self.menu._overlay)
            self.assertFalse(self.sources[-1].exists())
            self.assertFalse(asyncio.all_tasks(self.menu.jobs.loop))
        self.assertEqual(self.counter, 50)
        self.assertLessEqual(len(list(Path('/proc/self/fd').iterdir())), starting_fds + 1)
        self.assertFalse(self.saved.exists())

    def test_twenty_window_backend_results_and_cancellations_are_fresh(self):
        async def window_portal(**kwargs):
            if self.counter % 3 == 0:
                raise ScreenshotPortalError('cancelled', 'Controlled portal cancellation', 1)
            return await self.portal(**kwargs)
        completed = []
        with patch('capture.window_capture.request_screenshot', side_effect=window_portal), \
             patch('capture.window_capture.OUTPUT_DIR', self.saved):
            for _ in range(20):
                overlay = self.launch()
                self.menu._on_window_requested('screenshot')
                self.menu.launch_overlay()
                spin_until(lambda: not self.menu.busy and not self.menu.jobs.tasks)
                self.assertIsNone(self.menu._overlay)
                if self.menu.last_capture_path:
                    path = self.menu.last_capture_path
                    self.assertNotIn(path, completed)
                    completed.append(path)
                    with Image.open(path) as image:
                        copied = QImage.fromData(bytes(app.clipboard().mimeData().data('image/png')), 'PNG')
                        self.assertEqual(copied.pixelColor(0, 0).red(), image.getpixel((0, 0))[0])
                else:
                    self.assertEqual(self.menu.status_label.text(), 'Window capture cancelled.')
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        self.assertGreater(len(completed), 0)
        self.assertFalse(any(path.exists() for path in self.sources))
        self.assertFalse(list(self.saved.glob('.capture-*')))
        self.assertFalse(asyncio.all_tasks(self.menu.jobs.loop))

    def test_repeated_portal_failure_and_timeout_preserve_clipboard_and_recover(self):
        capture.copy_text_to_clipboard('preserve clipboard')
        for kind in ('timeout', 'unavailable', 'cancelled', 'unexpected') * 3:
            async def fail(**kwargs):
                raise ScreenshotPortalError(kind, 'Controlled ' + kind)
            with patch.object(capture, '_portal_screenshot', side_effect=fail):
                self.menu.launch_overlay()
                spin_until(lambda: not self.menu.busy and not self.menu.jobs.tasks)
            self.assertIsNone(self.menu._overlay)
            self.assertFalse(asyncio.all_tasks(self.menu.jobs.loop))
            self.assertEqual(app.clipboard().text(), 'preserve clipboard')
        self.launch(); self.finish()

    def test_busy_legacy_activation_cannot_clear_active_results(self):
        self.launch()
        self.menu.last_extracted_text = 'current result'
        self.menu._operation_active = True
        self.menu.start_capture()
        self.assertEqual(self.menu.last_extracted_text, 'current result')

    def test_cancelled_worker_failure_is_consumed_without_result_or_orphan(self):
        entered, release = threading.Event(), threading.Event()
        def fail(*args):
            entered.set()
            release.wait(3)
            raise OSError('Controlled failed write after cancellation')
        self.launch()
        try:
            with patch.object(capture, 'save_png', fail), patch.object(capture, 'copy_image_to_clipboard') as copy:
                self.menu._on_area_selected(QRect(10, 10, 20, 15), self.menu._src_path, 'screenshot')
                spin_until(entered.is_set)
                self.menu._on_cancelled()
                release.set()
                spin_until(lambda: not self.menu.jobs.tasks)
                copy.assert_not_called()
        finally:
            release.set()
        self.assertIsNone(self.menu.last_capture_path)
        self.assertFalse(self.sources[-1].exists())
        self.assertFalse(asyncio.all_tasks(self.menu.jobs.loop))

    def test_idle_shutdown_is_idempotent_and_rejects_new_work(self):
        self.menu.shutdown(); self.menu.jobs.close()
        self.menu.shutdown(); self.menu.jobs.close()
        self.menu.launch_overlay()
        self.assertIsNone(self.menu._overlay)
        self.assertEqual(self.counter, 0)
        async def forbidden():
            self.fail('Closed executor accepted work')
        with self.assertRaisesRegex(RuntimeError, 'shutting down'):
            self.menu.jobs.submit(forbidden())

    def test_opt_in_monotonic_duration_diagnostics_contain_no_returned_text(self):
        @timed('public_ocr_fixture')
        async def operation():
            return 'private result must not be logged'
        with patch.dict('os.environ', {'SNIPPING_DIAGNOSTICS': '1'}), \
             self.assertLogs('snipping.diagnostics', level='INFO') as logged:
            task = self.menu.jobs.submit(operation())
            spin_until(task.done)
        self.assertEqual(task.result(), 'private result must not be logged')
        payload = json.loads(logged.records[0].message)
        self.assertEqual(payload['operation'], 'public_ocr_fixture')
        self.assertGreaterEqual(payload['milliseconds'], 0)
        self.assertNotIn('private result', logged.output[0])
