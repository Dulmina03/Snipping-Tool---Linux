"""Clipboard MIME/thread/lifetime regressions, not compositor acceptance."""
import asyncio
from pathlib import Path
import unittest
from unittest.mock import patch

from PySide6.QtCore import QThread
from PySide6.QtGui import QImage
from test_phase01 import app, spin_until
from clipboard_native_probe import PUBLIC_TEXT, reference_image, ClipboardEditor
from ui.capture_menu import CaptureMenu
from utils.clipboard import copy_image_to_clipboard, copy_text_to_clipboard


class ClipboardTests(unittest.TestCase):
    def tearDown(self):
        # Dispose Python-created MIME objects before interpreter/Qt teardown.
        app.clipboard().clear()
        if app.clipboard().supportsSelection():
            from PySide6.QtGui import QClipboard
            app.clipboard().clear(QClipboard.Selection)
        app.processEvents()

    def test_png_bytes_decode_to_exact_pixels(self):
        image = reference_image()
        copy_image_to_clipboard(image)
        mime = app.clipboard().mimeData()
        for name in ('image/png', 'image/x-png'):
            decoded = QImage.fromData(bytes(mime.data(name)), 'PNG')
            self.assertEqual(decoded.convertToFormat(QImage.Format_ARGB32), image)
        self.assertEqual(app.clipboard().image().convertToFormat(QImage.Format_ARGB32), image)

    def test_sinhala_zwj_and_english_exact_utf8_formats(self):
        copy_text_to_clipboard(PUBLIC_TEXT)
        mime = app.clipboard().mimeData()
        self.assertEqual(app.clipboard().text(), PUBLIC_TEXT)
        for name in ('text/plain', 'text/plain;charset=utf-8', 'UTF8_STRING'):
            self.assertEqual(bytes(mime.data(name)), PUBLIC_TEXT.encode('utf-8'))

    def test_reader_supports_png_paste_and_fresh_reference(self):
        image = reference_image('fresh-public-token')
        self.assertNotEqual(image, reference_image('old-public-token'))
        copy_image_to_clipboard(image)
        editor = ClipboardEditor()
        editor.paste()
        self.assertIn('<img ', editor.toHtml())
        editor.close()

    def test_clipboard_survives_overlay_cancel_and_controller_shutdown(self):
        menu = CaptureMenu()
        try:
            copy_text_to_clipboard(PUBLIC_TEXT)
            menu._on_cancelled()
            menu.shutdown()
            spin_until(lambda: not menu.busy)
            self.assertEqual(app.clipboard().text(), PUBLIC_TEXT)
            self.assertIs(app.instance(), app)
        finally:
            menu.jobs.close()

    def test_image_and_async_ocr_deliver_on_gui_thread(self):
        menu = CaptureMenu()
        threads = []
        async def extract(path):
            await asyncio.sleep(.02)
            return PUBLIC_TEXT
        def copy(value):
            threads.append(QThread.currentThread())
        try:
            with patch('ui.capture_menu.copy_image_to_clipboard', copy), \
                 patch('ui.capture_menu.copy_text_to_clipboard', copy), \
                 patch('ui.capture_menu.extract_text_async', extract), \
                 patch.object(menu, '_show_toast'):
                menu._handle_capture_result(Path('public.png'), 'screenshot')
                menu._handle_capture_result(Path('public.png'), 'extract_text')
                spin_until(lambda: not menu.busy)
            self.assertEqual(threads, [app.thread(), app.thread()])
            self.assertEqual(menu.last_extracted_text, PUBLIC_TEXT)
        finally:
            menu.shutdown()
            menu.jobs.close()

    def test_shutdown_prevents_late_async_clipboard_write(self):
        menu = CaptureMenu()
        started = []
        async def delayed(path):
            started.append(True)
            await asyncio.sleep(60)
            return PUBLIC_TEXT
        try:
            with patch('ui.capture_menu.extract_text_async', delayed), \
                 patch('ui.capture_menu.copy_text_to_clipboard') as copy:
                menu._handle_capture_result(Path('public.png'), 'extract_text')
                spin_until(lambda: bool(started))
                menu.shutdown()
                menu.jobs.close()
                copy.assert_not_called()
        finally:
            menu.jobs.close()
