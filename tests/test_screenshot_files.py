"""Filesystem and save-path regressions; never touch the user's screenshots."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image
from dbus_next import MessageType, Variant
from test_phase01 import app
from utils import screenshot_files as files

STAMP = '2099-01-02_03-04-05'


class ScreenshotFileTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = Path(self.scratch.name)
        self.saved = self.root / 'saved'
        self.source = self.root / 'source.png'
        Image.new('RGB', (40, 30), 'blue').save(self.source)
        self.original = self.source.read_bytes()
        self.clock = patch.object(files.time, 'strftime', return_value=STAMP)
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.scratch.cleanup()

    def assert_no_staging(self):
        self.assertEqual(list(self.saved.glob('.capture-*')), [])

    def test_one_hundred_copies_within_identical_second(self):
        paths = [files.copy_screenshot(self.source, self.saved) for _ in range(100)]
        self.assertEqual(len(set(paths)), 100)
        self.assertEqual(paths[0].name, f'Screenshot_{STAMP}.png')
        self.assertEqual(paths[-1].name, f'Screenshot_{STAMP}_099.png')
        for path in paths:
            self.assertEqual(path.read_bytes(), self.original)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assert_no_staging()

    def test_existing_file_directory_and_broken_symlink_preserved(self):
        self.saved.mkdir()
        previous = self.saved / f'Screenshot_{STAMP}.png'
        previous.write_bytes(b'previous screenshot bytes')
        directory = self.saved / f'Screenshot_{STAMP}_001.png'
        directory.mkdir()
        symlink = self.saved / f'Screenshot_{STAMP}_002.png'
        symlink.symlink_to(self.saved / 'missing-target')
        result = files.copy_screenshot(self.source, self.saved)
        self.assertEqual(result.name, f'Screenshot_{STAMP}_003.png')
        self.assertEqual(previous.read_bytes(), b'previous screenshot bytes')
        self.assertTrue(directory.is_dir())
        self.assertTrue(symlink.is_symlink())
        self.assertFalse(symlink.exists())
        self.assert_no_staging()

    def test_atomic_collision_between_selection_and_publication(self):
        real_link = os.link
        collided = []
        def link(source, destination):
            if not collided:
                destination.write_bytes(b'another writer won')
                collided.append(destination)
            return real_link(source, destination)
        with patch.object(files.os, 'link', side_effect=link):
            result = files.copy_screenshot(self.source, self.saved)
        self.assertEqual(collided[0].read_bytes(), b'another writer won')
        self.assertEqual(result.read_bytes(), self.original)
        self.assertNotEqual(result, collided[0])
        self.assert_no_staging()

    def test_threads_publish_distinct_complete_images(self):
        def save(index):
            return files.save_png(Image.new('RGB', (12, 9), (index, 50, 70)), self.saved)
        with ThreadPoolExecutor(max_workers=8) as pool:
            paths = list(pool.map(save, range(40)))
        self.assertEqual(len(set(paths)), 40)
        for index, path in enumerate(paths):
            with Image.open(path) as image:
                self.assertEqual(image.getpixel((3, 3)), (index, 50, 70))
        self.assert_no_staging()

    def test_separate_processes_cannot_overwrite_each_other(self):
        code = '''import sys
from pathlib import Path
from utils import screenshot_files as files
files.time.strftime = lambda *args: '2099-01-02_03-04-05'
for _ in range(8): files.copy_screenshot(Path(sys.argv[1]), Path(sys.argv[2]))
'''
        children = [subprocess.Popen([sys.executable, '-c', code, str(self.source), str(self.saved)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
        try:
            for child in children:
                _, stderr = child.communicate(timeout=15)
                self.assertEqual(child.returncode, 0, stderr.decode())
        finally:
            for child in children:
                if child.poll() is None:
                    child.kill()
                child.wait()
        paths = list(self.saved.glob('*.png'))
        self.assertEqual(len(paths), 32)
        self.assertTrue(all(p.read_bytes() == self.original for p in paths))
        self.assert_no_staging()

    def test_no_public_partial_file_before_writer_finishes(self):
        def writer(stream):
            stream.write(b'in progress')
            self.assertFalse(list(self.saved.glob('*.png')))
            stream.write(b' complete')
        result = files.write_screenshot(self.saved, writer)
        self.assertEqual(result.read_bytes(), b'in progress complete')
        self.assert_no_staging()

    def test_failed_encode_does_not_publish_or_damage_previous_image(self):
        previous = files.copy_screenshot(self.source, self.saved)
        def broken(stream):
            stream.write(b'partial')
            raise OSError('simulated disk full')
        with self.assertRaisesRegex(OSError, 'disk full'):
            files.write_screenshot(self.saved, broken)
        self.assertEqual(list(self.saved.glob('*.png')), [previous])
        self.assertEqual(previous.read_bytes(), self.original)
        self.assert_no_staging()

    def test_permission_or_link_failure_cleans_staging_and_allows_retry(self):
        with patch.object(files.os, 'link', side_effect=PermissionError('publish denied')):
            with self.assertRaises(PermissionError):
                files.copy_screenshot(self.source, self.saved)
        self.assertFalse(list(self.saved.glob('*.png')))
        self.assert_no_staging()
        self.assertEqual(files.copy_screenshot(self.source, self.saved).read_bytes(), self.original)

    def test_missing_source_and_invalid_directory_fail_without_artifacts(self):
        with self.assertRaises(FileNotFoundError):
            files.copy_screenshot(self.root / 'missing.png', self.saved)
        self.assert_no_staging()
        invalid = self.root / 'not-a-directory'
        invalid.write_bytes(b'keep this file')
        with self.assertRaises(FileExistsError):
            files.copy_screenshot(self.source, invalid)
        self.assertEqual(invalid.read_bytes(), b'keep this file')

    def test_cleanup_never_removes_saved_source_or_saved_symlink(self):
        saved = files.copy_screenshot(self.source, self.saved)
        symlink = self.saved / 'saved-link.png'
        symlink.symlink_to(self.source)
        files.cleanup_capture_source(saved, self.saved)
        files.cleanup_capture_source(symlink, self.saved)
        self.assertEqual(saved.read_bytes(), self.original)
        self.assertTrue(symlink.is_symlink())
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_production_fullscreen_and_rectangle_save_paths_share_safe_names(self):
        import ui.capture_menu as capture
        with patch.object(capture, 'SCREENSHOTS_DIR', self.saved), \
             patch.object(capture, '_get_virtual_size', return_value=(40, 30)):
            full = capture._save_full(self.source)
            rect = capture._crop_and_save(self.source, 3, 4, 12, 9)
            full_again = capture._save_full(self.source)
        self.assertEqual(len({full, rect, full_again}), 3)
        self.assertEqual(full.read_bytes(), self.original)
        self.assertEqual(full_again.read_bytes(), self.original)
        with Image.open(rect) as image:
            self.assertEqual(image.size, (12, 9))
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 255))
        self.assert_no_staging()

    def test_legacy_engine_and_area_paths_do_not_overwrite(self):
        from capture.screenshot import ScreenshotCapture
        import capture.selected_area as area
        engine = ScreenshotCapture()
        engine.screenshot_folder = self.saved
        with patch.object(engine, '_request', new=AsyncMock(return_value={'uri': Variant('s', self.source.as_uri())})), \
             patch('capture.screenshot.copy_image_to_clipboard'):
            first = asyncio.run(engine.capture_full_screen())
            second = asyncio.run(engine.capture_full_screen())
        with patch.object(area, 'SCREENSHOTS_DIR', self.saved), \
             patch.object(area, 'get_screen_size', return_value=(40, 30)), contextlib.redirect_stdout(io.StringIO()):
            third = area.crop_screenshot(self.source, 0, 0, 20, 15)
        self.assertEqual(len({first, second, third}), 3)
        self.assertEqual(first.read_bytes(), self.original)
        self.assertEqual(second.read_bytes(), self.original)
        self.assert_no_staging()

    def test_legacy_portal_save_path_does_not_overwrite(self):
        from capture.portal_screenshot import PortalScreenshot
        async def run():
            interface = SimpleNamespace(on_response=lambda callback: callback(0, {'uri': Variant('s', self.source.as_uri())}))
            proxy = SimpleNamespace(get_interface=lambda _: interface)
            portal = PortalScreenshot()
            portal.bus = SimpleNamespace(call=AsyncMock(return_value=SimpleNamespace(
                message_type=MessageType.METHOD_RETURN, body=['/request/test'])),
                introspect=AsyncMock(return_value=None), get_proxy_object=lambda *args: proxy)
            return [Path(await portal.screenshot()), Path(await portal.screenshot())]
        with patch('capture.portal_screenshot.Path.home', return_value=self.root), contextlib.redirect_stdout(io.StringIO()):
            paths = asyncio.run(run())
        self.assertNotEqual(*paths)
        self.assertTrue(all(path.read_bytes() == self.original for path in paths))

    def test_window_save_cancel_failure_and_preserved_source(self):
        import capture.window_capture as window
        from capture.screenshot_portal_request import ScreenshotPortalError
        self.saved.mkdir()
        source = self.saved / 'already-saved.png'
        source.write_bytes(self.original)
        with patch.object(window, 'OUTPUT_DIR', self.saved), \
             patch.object(window, 'request_screenshot', new=AsyncMock(return_value=source)), \
             patch.object(window, 'copy_image_to_clipboard') as copy, contextlib.redirect_stdout(io.StringIO()):
            first = asyncio.run(window.take_screenshot())
            second = asyncio.run(window.take_screenshot())
        self.assertNotEqual(first, second)
        self.assertEqual(copy.call_count, 2)
        self.assertEqual(source.read_bytes(), self.original)
        before = set(self.saved.iterdir())
        with patch.object(window, 'OUTPUT_DIR', self.saved), \
             patch.object(window, 'request_screenshot', new=AsyncMock(side_effect=ScreenshotPortalError('cancelled', 'cancelled', 1))), \
             patch.object(window, 'copy_image_to_clipboard') as copy:
            self.assertIsNone(asyncio.run(window.take_screenshot()))
            copy.assert_not_called()
        with patch.object(window, 'OUTPUT_DIR', self.saved), \
             patch.object(window, 'request_screenshot', new=AsyncMock(return_value=self.source)), \
             patch.object(files.os, 'link', side_effect=OSError('disk failure')), \
             patch.object(window, 'copy_image_to_clipboard') as copy:
            with self.assertRaises(OSError):
                asyncio.run(window.take_screenshot())
            copy.assert_not_called()
        self.assertEqual(set(self.saved.iterdir()), before)
        self.assertEqual(source.read_bytes(), self.original)
        self.assertFalse(self.source.exists())
        self.assert_no_staging()
