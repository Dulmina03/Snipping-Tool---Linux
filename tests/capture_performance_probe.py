"""Repeatable public-fixture benchmark, NOT physical GNOME acceptance.

Run QT_QPA_PLATFORM=offscreen .venv/bin/python tests/capture_performance_probe.py OUTPUT.json
No private screenshots/text, system permissions, or shortcuts are accessed.
"""
import asyncio
from collections import defaultdict
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
main.prepare_qt_environment()
from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QCoreApplication, QEvent, QRect, QTimer
from PySide6.QtWidgets import QApplication
import ui.capture_menu as capture
from utils.ocr_process import extract_text_async


def resources():
    fields = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    return {'rss_kib': int(fields['VmRSS'].split()[0]),
            'threads': int(fields['Threads']), 'fds': len(list(Path('/proc/self/fd').iterdir()))}


def main_probe(output):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    metrics = defaultdict(list)
    def timed(name, function):
        def wrapped(*args, **kwargs):
            start = time.monotonic()
            try:
                return function(*args, **kwargs)
            finally:
                metrics[name].append((time.monotonic() - start) * 1000)
        return wrapped
    def spin(predicate, timeout=15):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            app.processEvents()
            if predicate():
                return
            time.sleep(.001)
        raise TimeoutError('Benchmark operation did not complete')
    with tempfile.TemporaryDirectory(prefix='snipping-performance-') as scratch:
        root = Path(scratch)
        fixture = root / 'public-noise.png'
        Image.frombytes('RGB', (1600, 900), random.Random(42).randbytes(1600*900*3)).save(fixture)
        english = root / 'public-english.png'
        image = Image.new('RGB', (1100, 160), 'white')
        ImageDraw.Draw(image).text((25, 45), 'Offline English screenshot test 123.', fill='black',
                                  font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 40))
        image.save(english)
        menu = capture.CaptureMenu()
        menu._show_toast = lambda message: None  # Toast rendering excluded explicitly.
        previous = [time.monotonic()]
        gaps = []
        def beat():
            now = time.monotonic()
            gaps.append((now - previous[0])*1000)
            previous[0] = now
        timer = QTimer(); timer.setInterval(1); timer.timeout.connect(beat); timer.start()
        async def portal(**kwargs):
            start = time.monotonic()
            await asyncio.sleep(.01)  # Controlled portal delay, NOT measured GNOME latency.
            path = root / 'portal.png'
            shutil.copyfile(fixture, path)
            metrics['fixture_portal_wait_ms'].append((time.monotonic()-start)*1000)
            return path
        patches = [patch.object(capture, 'SCREENSHOTS_DIR', root/'saved'),
                   patch.object(capture, '_get_virtual_size', return_value=(1600, 900)),
                   patch.object(capture, '_portal_screenshot', side_effect=portal)]
        for name, attribute in [('crop_total_ms', '_crop_and_save'), ('png_save_ms', 'save_png'),
                                ('fullscreen_copy_ms', '_save_full'), ('clipboard_publish_ms', 'copy_image_to_clipboard')]:
            patches.append(patch.object(capture, attribute, timed(name, getattr(capture, attribute))))
        patches.append(patch.object(menu, '_close_overlay', timed('overlay_close_ms', menu._close_overlay)))
        for item in patches: item.start()
        observations = []
        try:
            for index in range(53):  # Three warmups, then 50 measured alternating operations.
                if index == 3:
                    metrics.clear(); gaps.clear(); observations.append({'after_captures': 0, **resources()})
                start = time.monotonic()
                menu.launch_overlay()
                spin(lambda: menu._overlay is not None and not menu.busy)
                metrics['activation_to_overlay_ms'].append((time.monotonic()-start)*1000)
                start = time.monotonic()
                if index % 2:
                    menu._on_fullscreen(menu._src_path, 'screenshot')
                else:
                    menu._on_area_selected(QRect(100, 100, 1200, 700), menu._src_path, 'screenshot')
                spin(lambda: not menu.busy and not menu.jobs.tasks)
                metrics['selection_to_delivery_ms'].append((time.monotonic()-start)*1000)
                assert menu._overlay is None and menu.last_capture_path.is_file()
                assert not list((root/'saved').glob('.capture-*'))
                QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
                if index in (12, 52):
                    observations.append({'after_captures': index-2, **resources()})
            async def ocr():
                start = time.monotonic()
                text = await extract_text_async(english)
                assert 'English' in text and '123' in text
                metrics['english_ocr_ms'].append((time.monotonic()-start)*1000)
            for _ in range(3):
                menu.jobs.submit(ocr()); spin(lambda: not menu.jobs.tasks, timeout=60)
            assert not asyncio.all_tasks(menu.jobs.loop)
            assert len(list((root/'saved').glob('*.png'))) == 53
            worker_threads_before_close = resources()['threads']
        finally:
            timer.stop(); menu.shutdown(); menu.jobs.close()
            for item in reversed(patches): item.stop()
            app.clipboard().clear()  # Only this isolated offscreen test owns the clipboard.
            menu.deleteLater(); QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        def summary(values):
            values = sorted(values)
            return {'n': len(values), 'median': round(statistics.median(values), 3),
                    'p95': round(values[max(0, __import__('math').ceil(len(values)*.95)-1)], 3),
                    'max': round(max(values), 3)}
        report = {'kind': 'offscreen public production-handler fixture; no physical input',
                  'fixture': '1600x900 seeded RGB noise; rectangle 1200x700; 50 alternating captures after 3 warmups',
                  'metrics_ms': {key: summary(value) for key, value in metrics.items() if value},
                  'qt_heartbeat_gap_ms': summary(gaps), 'resource_observations': observations,
                  'threads_before_close': worker_threads_before_close, 'resources_after_close': resources(),
                  'limitations': ['Portal delay is synthetic, not native latency or permission time.',
                    'No physical shortcut, compositor frame presentation, focus change or external paste.',
                    'Toast rendering excluded. OCR is real Tesseract on a public English fixture.',
                    'PNG save is contained in crop_total; do not sum those overlapping metrics.']}
        Path(output).write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main_probe(sys.argv[1])
