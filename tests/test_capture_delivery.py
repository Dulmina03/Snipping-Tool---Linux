"""Regression coverage for production-handler focus/clipboard ordering."""
import asyncio
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import AsyncMock,patch

from PIL import Image
from PySide6.QtCore import QPoint,QThread
from test_phase01 import app,spin_until
from ui.capture_menu import CaptureMenu
from utils.clipboard import copy_text_to_clipboard
from clipboard_native_probe import PUBLIC_TEXT


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.scratch=tempfile.TemporaryDirectory()
        self.source=Path(self.scratch.name)/'source.png'
        Image.new('RGB',(1920,1080),'white').save(self.source)
        self.menu=CaptureMenu();self.menu._show_toast=lambda _:None
        self.geometry=patch('ui.capture_menu._get_virtual_size',return_value=(1920,1080));self.geometry.start()
        self.directory=patch('ui.capture_menu.SCREENSHOTS_DIR',Path(self.scratch.name)/'saved');self.directory.start()
        with patch('ui.capture_menu._portal_screenshot',new=AsyncMock(return_value=self.source)):
            self.menu.launch_overlay();spin_until(lambda:self.menu._overlay is not None)
        self.overlay=self.menu._overlay
    def tearDown(self):
        self.menu.shutdown();self.menu.jobs.close();self.directory.stop();self.geometry.stop();self.scratch.cleanup();app.processEvents()
    def select(self,action='screenshot'):
        self.overlay._toolbar.set_action(action)
        self.overlay.start_point=QPoint(50,300);self.overlay.end_point=QPoint(400,500)
        self.overlay.confirm_selection()
        if action == 'screenshot':
            spin_until(lambda: not self.menu.busy)

    def test_rectangular_image_is_copied_before_surface_teardown(self):
        observations=[]
        def copy(path):
            observations.append((self.overlay.isVisible(),QThread.currentThread()==app.thread()))
            with Image.open(path) as saved:self.assertEqual(saved.size,(351,201))
        with patch('ui.capture_menu.copy_image_to_clipboard',copy):self.select()
        self.assertEqual(observations,[(True,True)])
        self.assertIsNone(self.menu._overlay)
        self.assertTrue(self.menu.last_capture_path.is_file())

    def test_async_ocr_retains_surface_through_text_delivery(self):
        started=[];copied=[]
        async def ocr(path):
            started.append(True);await asyncio.sleep(.1);return PUBLIC_TEXT
        def copy(text):
            copied.append((text,self.overlay.isVisible(),QThread.currentThread()==app.thread()))
        with patch('ui.capture_menu.extract_text_async',ocr),patch('ui.capture_menu.copy_text_to_clipboard',copy):
            self.select('extract_text');spin_until(lambda:bool(started))
            self.assertTrue(self.overlay.isVisible())
            self.assertTrue(self.overlay._processing)
            spin_until(lambda:not self.menu.busy)
        self.assertEqual(copied,[(PUBLIC_TEXT,True,True)])
        self.assertIsNone(self.menu._overlay)

    def test_unfocused_ocr_defers_until_genuine_delivery_action(self):
        async def ocr(path):return PUBLIC_TEXT
        with patch('ui.capture_menu.QGuiApplication.platformName',return_value='wayland'), \
             patch.object(self.overlay,'isActiveWindow',return_value=False), \
             patch('ui.capture_menu.extract_text_async',ocr), \
             patch('ui.capture_menu.copy_text_to_clipboard') as copy:
            self.select('extract_text');spin_until(lambda:not self.menu.busy)
            copy.assert_not_called()
            self.assertIn('press Enter',self.menu.status_label.text())
            self.assertEqual(self.menu._clipboard_pending,('text',PUBLIC_TEXT))
        with patch('ui.capture_menu.copy_text_to_clipboard') as copy:
            self.overlay.delivery_requested.emit()
            copy.assert_called_once_with(PUBLIC_TEXT)
        self.assertIsNone(self.menu._overlay)

    def test_escape_during_ocr_cancels_and_never_delivers_late_text(self):
        started=[]
        async def ocr(path):
            started.append(True);await asyncio.sleep(60);return PUBLIC_TEXT
        with patch('ui.capture_menu.extract_text_async',ocr),patch('ui.capture_menu.copy_text_to_clipboard') as copy:
            self.select('extract_text');spin_until(lambda:bool(started))
            self.overlay.cancel_selection();spin_until(lambda:not self.menu.busy)
            copy.assert_not_called()
            self.assertIsNone(self.menu._overlay)
            self.assertIsNone(self.menu._clipboard_pending)

    def test_failed_copy_does_not_report_success_or_destroy_retry_surface(self):
        with patch('ui.capture_menu.copy_image_to_clipboard',side_effect=RuntimeError('test copy failure')):
            self.select()
        self.assertIn('Clipboard copy failed',self.menu.status_label.text())
        self.assertIs(self.menu._overlay,self.overlay)
        self.assertIsNotNone(self.menu._clipboard_pending)

    def test_worker_thread_clipboard_call_rejected_without_qt_write(self):
        failures=[]
        def worker():
            try:copy_text_to_clipboard(PUBLIC_TEXT)
            except RuntimeError as error:failures.append(str(error))
        thread=threading.Thread(target=worker);thread.start();thread.join()
        self.assertEqual(failures,['Clipboard operations must run on the Qt GUI thread.'])

    def test_window_result_restores_surface_before_single_copy(self):
        window=Path(self.scratch.name)/'window.png'
        Image.new('RGB',(300,200),'blue').save(window)
        observed=[]
        with patch('ui.capture_menu.capture_window',new=AsyncMock(return_value=window)) as backend, \
             patch('ui.capture_menu.copy_image_to_clipboard',side_effect=lambda path:observed.append((path,self.overlay.isVisible()))):
            self.menu._on_window_requested('screenshot');spin_until(lambda:not self.menu.busy)
        backend.assert_awaited_once_with(copy_to_clipboard=False)
        self.assertEqual(observed,[(window,True)])
        self.assertIsNone(self.menu._overlay)

    def test_window_cancellation_cleans_retained_surface_without_copy(self):
        with patch('ui.capture_menu.capture_window',new=AsyncMock(return_value=None)), \
             patch('ui.capture_menu.copy_image_to_clipboard') as copy:
            self.menu._on_window_requested('screenshot');spin_until(lambda:not self.menu.busy)
            copy.assert_not_called()
        self.assertIsNone(self.menu._overlay)
