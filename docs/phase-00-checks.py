"""Reproduce isolated Phase 0 probes; never contacts a portal or downloads models.

Run: QT_QPA_PLATFORM=offscreen .venv/bin/python docs/phase-00-checks.py
These checks describe the current baseline, including known defects; they are
not release acceptance tests. Temporary HOME and clipboard are process-local.
"""
import importlib
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

with tempfile.TemporaryDirectory(prefix='snipping-phase00-') as scratch:
    os.environ['HOME'] = scratch
    from PIL import Image, ImageDraw, ImageFont
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    modules = ('main', 'ui.capture_menu', 'ui.overlay', 'ui.selection_overlay',
               'capture.screenshot', 'capture.selected_area', 'capture.window_capture',
               'capture.portal_screenshot', 'capture.screen_capture',
               'shortcuts.global_shortcut', 'ocr.ocr_engine', 'utils.clipboard')
    for name in modules:
        importlib.import_module(name)
    print('PASS: 12 production-module imports (no entry points invoked)')

    from ui.capture_menu import CaptureMenu, _save_full
    from ui.overlay import Overlay, SnipMode
    from utils.clipboard import (copy_image_to_clipboard, copy_text_to_clipboard,
                                 clipboard_contains_image, clipboard_contains_text)
    import ocr.ocr_engine as engine

    menu = CaptureMenu()
    print(f'OBSERVED: controller isVisible={menu.isVisible()}, size={menu.width()}x{menu.height()}')
    overlay = Overlay()
    assert not overlay._toolbar._buttons[SnipMode.FREEFORM].isEnabled()
    overlay.start_point, overlay.end_point = QPoint(10, 20), QPoint(40, 60)
    received = []
    overlay.area_selected.connect(received.append)
    overlay.confirm_selection()
    assert len(received) == 1 and received[0] == overlay.selected_rect
    print('PASS: synthetic rectangle selection signal; freeform disabled confirmed')

    image = Image.new('RGB', (900, 160), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 36)
    expected = 'Offline English screenshot test 123.'
    draw.text((30, 55), expected, fill='black', font=font)
    copy_image_to_clipboard(image)
    assert clipboard_contains_image()
    assert bytes(app.clipboard().mimeData().data('image/png')).startswith(b'\x89PNG\r\n\x1a\n')
    text = '\u0dc1\u0dca\u200d\u0dbb\u0dd3 English 123\n\u0dc3\u0dd2\u0d82\u0dc4\u0dbd'
    copy_text_to_clipboard(text)
    assert clipboard_contains_text(text)
    assert bytes(app.clipboard().mimeData().data('text/plain;charset=utf-8')) == text.encode('utf-8')
    print('PASS: offscreen PNG MIME and Sinhala/English/ZWJ UTF-8 clipboard round-trip')

    # Existing OCR setup can download models: replace it, prohibit network.
    tessdata = ROOT / 'ocr/tessdata'
    with patch.object(engine, '_setup_tessdata_dir', return_value=tessdata), \
         patch.object(engine.urllib.request, 'urlopen', side_effect=AssertionError('Network prohibited')):
        actual = engine.extract_text(image, lang='eng')
        def distance(a, b):
            row = list(range(len(b) + 1))
            for i, x in enumerate(a, 1):
                nxt = [i]
                for j, y in enumerate(b, 1):
                    nxt.append(min(nxt[-1] + 1, row[j] + 1, row[j-1] + (x != y)))
                row = nxt
            return row[-1]
        print(f'OBSERVED: single synthetic English fixture CER={distance(expected, actual)/len(expected):.4f}, '
              f'WER={distance(expected.split(), actual.split())/len(expected.split()):.4f}; '
              'raw strings compared, no normalization, not a release benchmark')
        # Model loading only, no Sinhala recognition accuracy claim.
        engine.pytesseract.image_to_string(image, lang='sin', config=engine._build_config())
        print('PASS: local sin model loads in Tesseract; Sinhala accuracy NOT RUN')

    source = Path(scratch) / 'source.png'
    image.save(source)
    with patch('ui.capture_menu.time.strftime', return_value='fixed'):
        first = _save_full(source)
        second = _save_full(source)
    print(f'OBSERVED: two same-second full saves reuse pathname={first == second}')
    print(f'OBSERVED: OCR punctuation cleanup {engine._post_process_text("- item")!r} from "- item"')
    app.clipboard().clear()
    menu.close()
    overlay.close()
