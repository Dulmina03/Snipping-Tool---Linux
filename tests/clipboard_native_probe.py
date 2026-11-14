"""Opt-in native two-process clipboard probe; never a physical-input test.

Run from a real desktop session: .venv/bin/python tests/clipboard_native_probe.py
Uses public generated fixtures only. Does overwrite the session clipboard.
No GNOME settings changes. A missing focus grant is NOT RUN, not PASS.
"""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
import uuid
import hashlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from main import prepare_qt_environment
prepare_qt_environment()
from PySide6.QtCore import QThread, QTimer, QRect
from PySide6.QtGui import QImage, QColor, QTextDocument
from PySide6.QtWidgets import QApplication, QTextEdit
from utils.async_jobs import AsyncJobs
from utils.clipboard import copy_image_to_clipboard, copy_text_to_clipboard

PUBLIC_TEXT = 'Offline English 123. සිංහල ආයුබෝවන් ශ්‍රී ලංකාව \u200d\nSecond line.'


def reference_image(token=""):
    digest = hashlib.sha256(token.encode()).digest()
    image = QImage(73, 41, QImage.Format_ARGB32)
    image.fill(QColor('#124578'))
    image.setPixelColor(10, 9, QColor(*digest[:3], 255))
    return image


class ClipboardEditor(QTextEdit):
    # QTextEdit's default insertFromMimeData handles text, not standalone PNGs.
    def canInsertFromMimeData(self, source):
        return source.hasFormat('image/png') or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source):
        if source.hasFormat('image/png'):
            image = QImage.fromData(bytes(source.data('image/png')), 'PNG')
            if not image.isNull():
                from PySide6.QtCore import QUrl
                self.document().addResource(QTextDocument.ImageResource, QUrl('clipboard-image'), image)
                self.textCursor().insertImage('clipboard-image')
        else:
            super().insertFromMimeData(source)


def read_result(editor, mode, token=''):
    clipboard = QApplication.clipboard()
    mime = clipboard.mimeData()
    result = {'reader_active': editor.isActiveWindow(), 'retrieved': False,
              'gui_thread': QThread.currentThread() == QApplication.instance().thread()}
    if not result['reader_active'] or mime is None:
        return result
    result['formats'] = mime.formats()
    if mode == 'image':
        png = bytes(mime.data('image/png'))
        image = QImage.fromData(png, 'PNG')
        result['png_pixels_equal'] = (not image.isNull() and
            image.convertToFormat(QImage.Format_ARGB32) == reference_image(token))
        qt_image = clipboard.image()
        result['qt_size'] = [qt_image.width(), qt_image.height()]
        result['qt_pixels_equal'] = qt_image.convertToFormat(QImage.Format_ARGB32) == reference_image(token)
        editor.clear()
        editor.paste()
        result['paste_equal'] = '<img ' in editor.toHtml()
        result['retrieved'] = all(result.get(k) for k in ('png_pixels_equal', 'qt_pixels_equal', 'paste_equal'))
    else:
        result['utf8_bytes_equal'] = bytes(mime.data('text/plain;charset=utf-8')) == (PUBLIC_TEXT + token).encode('utf-8')
        result['qt_text_equal'] = clipboard.text() == PUBLIC_TEXT + token
        editor.clear()
        editor.paste()
        result['paste_equal'] = editor.toPlainText() == PUBLIC_TEXT + token
        result['retrieved'] = all(result[k] for k in ('utf8_bytes_equal', 'qt_text_equal', 'paste_equal'))
    return result


def reader(mode, token):
    app = QApplication([])
    editor = ClipboardEditor()
    editor.setWindowTitle('Public clipboard test reader')
    editor.resize(650, 240)
    editor.show()
    editor.activateWindow()
    tries = 0
    def poll():
        nonlocal tries
        tries += 1
        result = read_result(editor, mode, token)
        if result['retrieved'] or tries >= 45:
            print(json.dumps(result), flush=True)
            app.quit()
    timer = QTimer()
    timer.timeout.connect(poll)
    timer.start(100)
    app.exec()


def writer():
    from ui.capture_menu import CaptureMenu
    import ui.capture_menu as capture
    from unittest.mock import patch, AsyncMock
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    jobs = AsyncJobs()
    controller = CaptureMenu(jobs=jobs)
    window = QTextEdit('Public clipboard producer; no private text.')
    window.setWindowTitle('Public clipboard test owner')
    window.resize(650, 240)
    ledger = []
    beats = [0]
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: beats.__setitem__(0, beats[0] + 1))
    heartbeat.start(20)

    async def focus():
        # Remap between readers so the compositor can deliver a fresh pointer
        # enter serial. Keyboard focus alone does not refresh Qt's input serial.
        window.hide()
        await asyncio.sleep(.15)
        window.showMaximized()
        window.activateWindow()
        for _ in range(50):
            await asyncio.sleep(.05)
            if window.isActiveWindow():
                # Allow real Wayland keyboard.enter to be processed before hiding.
                await asyncio.sleep(.2)
                return True
        return False

    async def transfer(mode, token):
        process = await asyncio.create_subprocess_exec(sys.executable, __file__, '--reader', mode, token,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            data, _ = await asyncio.wait_for(process.communicate(), 8)
            return json.loads(data)
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    async def run():
        try:
            with tempfile.TemporaryDirectory(prefix='snipping-clipboard-') as scratch:
                path = Path(scratch) / 'public.png'
                reference_image().save(str(path), 'PNG')
                for scenario in ('never_focused', 'focused', 'closed', 'delayed', 'controller_image', 'controller_ocr'):
                    for mode in ('image', 'text') if scenario not in ('controller_image', 'controller_ocr') else (('image',) if scenario == 'controller_image' else ('text',)):
                        token = uuid.uuid4().hex
                        reference_image(token).save(str(path), 'PNG')
                        if scenario != 'never_focused' and not await focus():
                            ledger.append({'scenario': scenario, 'mode': mode, 'status': 'NOT RUN', 'reason': 'No native focus grant'})
                            continue
                        if scenario in ('closed', 'delayed', 'controller_image', 'controller_ocr'):
                            window.hide()
                            await asyncio.sleep(.2 if scenario != 'delayed' else 2)
                        before = beats[0]
                        if scenario == 'controller_image':
                            controller._handle_capture_result(path, 'screenshot')
                        elif scenario == 'controller_ocr':
                            with patch.object(capture, 'extract_text_async', new=AsyncMock(return_value=PUBLIC_TEXT + token)):
                                controller._handle_capture_result(path, 'extract_text')
                                await controller._pending
                        elif mode == 'image':
                            copy_image_to_clipboard(path)
                        else:
                            copy_text_to_clipboard(PUBLIC_TEXT + token)
                        owner = app.clipboard().ownsClipboard()
                        active = window.isActiveWindow()
                        await asyncio.sleep(.2)
                        result = await transfer(mode, token)
                        row = dict(scenario=scenario, mode=mode, status='PASS' if result['retrieved'] else 'FAIL',
                            writer_gui_thread=QThread.currentThread() == app.thread(), local_owns_clipboard=owner,
                            writer_active_at_write=active,
                            event_loop_alive=beats[0] > before, **result)
                        ledger.append(row)
                        print(json.dumps(row), flush=True)
                print(json.dumps({'physical': 'NOT RUN', 'ledger': ledger}), flush=True)
        except Exception as error:
            ledger.append({'scenario': 'harness', 'status': 'FAIL', 'error': type(error).__name__})
            print(json.dumps(ledger[-1]), flush=True)
        finally:
            app.quit()
    QTimer.singleShot(200, lambda: jobs.submit(run()))
    QTimer.singleShot(120000, app.quit)
    app.exec()
    controller.shutdown()
    jobs.close()
    if any(r['status'] == 'FAIL' and r['scenario'] != 'never_focused' for r in ledger):
        return 1
    return 2 if not ledger or any(r['status'] == 'NOT RUN' for r in ledger) else 0


if __name__ == '__main__':
    if '--reader' in sys.argv:
        reader(sys.argv[-2], sys.argv[-1])
    else:
        raise SystemExit(writer())
