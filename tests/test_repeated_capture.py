"""Production controller repetition with public fixtures and real offscreen Qt MIME.

The portal/OCR replies are controlled fixtures; these are not physical Wayland
keyboard, permission, recognition-accuracy or external-paste acceptance tests.
"""
import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, QRect, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from test_phase01 import app, spin_until
from ui.capture_menu import CaptureMenu
from ui.overlay import Overlay
from utils import screenshot_files as files


class RepeatedCaptureTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = Path(self.scratch.name)
        self.saved = self.root / 'saved'
        self.menu = CaptureMenu()
        self.messages = []
        self.menu._show_toast = self.messages.append
        self.counter = 0
        self.sources = []
        self.heartbeats = []
        self.heartbeat = QTimer(self.menu)
        self.heartbeat.setInterval(1)
        self.heartbeat.timeout.connect(lambda: self.heartbeats.append(1))
        self.heartbeat.start()
        self.patches = [patch('ui.capture_menu.SCREENSHOTS_DIR', self.saved),
                        patch('ui.capture_menu._get_virtual_size', return_value=(80, 60)),
                        patch.object(files.time, 'strftime', return_value='2099-01-02_03-04-05'),
                        patch('ui.capture_menu._portal_screenshot', side_effect=self.portal)]
        for item in self.patches:
            item.start()

    async def portal(self, **kwargs):
        self.counter += 1
        path = self.root / f'portal-{self.counter}.png'
        Image.new('RGB', (80, 60), (self.counter % 255, 70, 100)).save(path)
        self.sources.append(path)
        return path

    def tearDown(self):
        self.menu.shutdown()
        self.menu.jobs.close()
        self.menu.deleteLater()
        # Qt's offscreen plugin otherwise crashes at interpreter teardown even
        # for a standalone QMimeData text owner; dispose test-owned MIME now.
        app.clipboard().clear()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        for item in reversed(self.patches):
            item.stop()
        self.scratch.cleanup()
        app.processEvents()

    def launch(self):
        self.menu.launch_overlay()
        spin_until(lambda: self.menu._overlay is not None and not self.menu.busy)
        self.assertIsNone(self.menu.last_capture_path)
        self.assertIsNone(self.menu.last_extracted_text)
        self.assertEqual(sum(isinstance(w, Overlay) and w.isVisible()
                             for w in QApplication.topLevelWidgets()), 1)
        self.assertFalse(self.menu.isVisible())
        return self.menu._overlay

    def finish(self, action='screenshot', full=False):
        if full:
            self.menu._on_fullscreen(self.menu._src_path, action)
        else:
            self.menu._on_area_selected(QRect(10, 10, 20, 15), self.menu._src_path, action)
        spin_until(lambda: not self.menu.busy and not self.menu.jobs.tasks)
        self.assertIsNone(self.menu._overlay)
        self.assertIsNone(self.menu._src_path)
        self.assertIsNone(self.menu._clipboard_pending)
        self.assertFalse(any(path.exists() for path in self.sources))
        return self.menu.last_capture_path

    def test_one_hundred_consecutive_screenshots_keep_pixels_and_clipboard_fresh(self):
        snapshots = {}
        for index in range(100):
            overlay = self.launch()
            self.menu.launch_overlay()
            self.assertIs(self.menu._overlay, overlay)
            self.assertEqual(self.counter, index + 1)
            path = self.finish(full=bool(index % 2))
            self.assertNotIn(path, snapshots)
            snapshots[path] = path.read_bytes()
            expected = (self.counter % 255, 70, 100)
            with Image.open(path) as image:
                self.assertEqual(image.size, (80, 60) if index % 2 else (20, 15))
                self.assertEqual(image.getpixel((2, 2)), expected)
            png = bytes(app.clipboard().mimeData().data('image/png'))
            copied = QImage.fromData(png, 'PNG')
            self.assertFalse(copied.isNull())
            color = copied.pixelColor(2, 2)
            self.assertEqual((color.red(), color.green(), color.blue()), expected)
        self.assertEqual(len(list(self.saved.glob('*.png'))), 100)
        self.assertTrue(all(path.read_bytes() == data for path, data in snapshots.items()))
        self.assertFalse(list(self.saved.glob('.capture-*')))
        self.assertFalse(asyncio.all_tasks(self.menu.jobs.loop))
        self.assertGreater(len(self.heartbeats), 10)

    def test_consecutive_ocr_callbacks_clear_previous_text_and_deliver_new_unicode(self):
        async def recognize(path):
            await asyncio.sleep(.01)
            return f'English සිංහල ශ්‍රී\u200d — {path.name}'
        paths = set()
        with patch('ui.capture_menu.extract_text_async', side_effect=recognize):
            for _ in range(10):
                self.launch()
                path = self.finish('extract_text')
                self.assertNotIn(path, paths)
                paths.add(path)
                expected = f'English සිංහල ශ්‍රී\u200d — {path.name}'
                self.assertEqual(self.menu.last_extracted_text, expected)
                self.assertEqual(app.clipboard().text(), expected)
        self.assertFalse(asyncio.all_tasks(self.menu.jobs.loop))

    def test_cancel_before_selection_preserves_saved_image_and_clipboard(self):
        self.launch()
        previous = self.finish()
        snapshot = previous.read_bytes()
        clipboard = bytes(app.clipboard().mimeData().data('image/png'))
        overlay = self.launch()
        overlay.cancel_selection()
        spin_until(lambda: not self.menu.jobs.tasks)
        self.assertIsNone(self.menu._overlay)
        self.assertIsNone(self.menu.last_capture_path)
        self.assertIsNone(self.menu.last_extracted_text)
        self.assertEqual(list(self.saved.glob('*.png')), [previous])
        self.assertEqual(previous.read_bytes(), snapshot)
        self.assertEqual(bytes(app.clipboard().mimeData().data('image/png')), clipboard)
        self.assertFalse(self.sources[-1].exists())
        self.launch()
        self.assertNotEqual(self.finish(), previous)

    def test_failed_write_closes_overlay_preserves_previous_and_can_retry(self):
        self.launch()
        previous = self.finish()
        snapshot = previous.read_bytes()
        clipboard = bytes(app.clipboard().mimeData().data('image/png'))
        self.launch()
        with patch.object(files.os, 'link', side_effect=PermissionError('simulated write denied')):
            result = self.finish()
        self.assertIsNone(result)
        self.assertIn('Crop failed', self.menu.status_label.text())
        self.assertEqual(previous.read_bytes(), snapshot)
        self.assertEqual(list(self.saved.glob('*.png')), [previous])
        self.assertFalse(list(self.saved.glob('.capture-*')))
        self.assertEqual(bytes(app.clipboard().mimeData().data('image/png')), clipboard)
        self.launch()
        self.assertNotEqual(self.finish(), previous)

    def test_cancel_ocr_then_capture_has_no_late_text_or_orphan_task(self):
        started = []
        cancelled = []
        async def recognize(path):
            started.append(True)
            try:
                await asyncio.sleep(60)
                return 'stale result'
            finally:
                cancelled.append(True)
        overlay = self.launch()
        with patch('ui.capture_menu.extract_text_async', side_effect=recognize):
            self.menu._on_area_selected(QRect(10, 10, 20, 15), self.menu._src_path, 'extract_text')
            spin_until(lambda: bool(started))
            saved = self.menu.last_capture_path
            before = saved.read_bytes()
            self.menu.launch_overlay()
            self.assertIs(self.menu._overlay, overlay)
            overlay.cancel_selection()
            spin_until(lambda: not self.menu.busy and not self.menu.jobs.tasks)
        self.assertEqual(cancelled, [True])
        self.assertIsNone(self.menu.last_extracted_text)
        self.assertIsNone(self.menu._clipboard_pending)
        self.assertEqual(saved.read_bytes(), before)
        self.launch()
        self.finish()
        self.assertFalse(asyncio.all_tasks(self.menu.jobs.loop))
        self.assertNotEqual(app.clipboard().text(), 'stale result')

    def test_cancel_delayed_portal_then_next_capture_remains_usable(self):
        entered = []
        ended = []
        async def delayed(**kwargs):
            entered.append(True)
            try:
                await asyncio.sleep(60)
            finally:
                ended.append(True)
        with patch('ui.capture_menu._portal_screenshot', side_effect=delayed):
            self.menu.launch_overlay()
            spin_until(lambda: bool(entered))
            self.menu._on_cancelled()
            spin_until(lambda: not self.menu.jobs.tasks)
        self.assertEqual(ended, [True])
        self.assertFalse(asyncio.all_tasks(self.menu.jobs.loop))
        self.assertFalse(self.saved.exists())
        self.launch()
        self.finish()

    def test_saved_screenshot_used_as_portal_source_is_not_deleted_on_cancel(self):
        self.launch()
        previous = self.finish()
        snapshot = previous.read_bytes()
        with patch('ui.capture_menu._portal_screenshot', return_value=previous):
            self.launch().cancel_selection()
            spin_until(lambda: not self.menu.jobs.tasks)
        self.assertEqual(previous.read_bytes(), snapshot)
        self.assertIsNone(self.menu.last_capture_path)
