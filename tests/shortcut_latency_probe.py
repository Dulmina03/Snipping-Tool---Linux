"""Cold/warm production-path timings; injected signal is NOT a physical key.

--native uses real host Screenshot/DisplayConfig portals and ephemeral images.
Default uses public PNGs/offscreen Qt; no permissions or desktop capture.
"""
import argparse
import gc
import importlib.util
import asyncio
import json
import math
from pathlib import Path
import shutil
import statistics
import sys
import tempfile
import threading
import time
from types import SimpleNamespace as NS
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
main.prepare_qt_environment()
from PIL import Image, ImageDraw
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from dbus_next import MessageType
from shortcuts.global_shortcut import GlobalShortcutManager, GLOBAL_SHORTCUTS_INTERFACE
import ui.capture_menu as capture


def resource_counts():
    return {'fds':len(list(Path('/proc/self/fd').iterdir())),
            'python_threads':[t.name for t in threading.enumerate()]}


def run(output, count=21, native=False, scheduler_source=None):
    app=QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    if scheduler_source is not None:
        spec=importlib.util.spec_from_file_location('latency_original_jobs',scheduler_source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        capture.AsyncJobs=module.AsyncJobs
    menu=capture.CaptureMenu()
    manager=GlobalShortcutManager()
    manager._session_handle='/latency/probe'
    manager.shortcut_activated.connect(menu.launch_overlay)
    records=[]
    menu.latency_listener=lambda row:records.append(dict(row))
    samples=[]
    before=resource_counts()
    def spin(predicate, timeout=145):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            app.processEvents()
            if predicate():return
            if menu._pending is not None and menu._pending.done() and menu._overlay is None:
                raise RuntimeError('Capture did not produce an overlay: '+menu.status_label.text())
            time.sleep(.0005)
        raise TimeoutError('Readiness checkpoint not observed: '+menu.status_label.text())
    def events_for(duration):
        deadline=time.monotonic()+duration
        while time.monotonic()<deadline:
            app.processEvents();time.sleep(.0005)
    try:
        with tempfile.TemporaryDirectory(prefix='snipping-latency-') as scratch:
            folder=Path(scratch)
            fixture=folder/'public.png'
            image=Image.new('RGB',(1920,1080),'#eeeeee')
            draw=ImageDraw.Draw(image)
            for i in range(400):
                x=(i*137)%1800;y=(i*71)%1000
                draw.rectangle((x,y,x+100,y+70),fill=((i*29)%256,(i*43)%256,(i*61)%256))
            image.save(fixture)
            async def fake_portal(**kwargs):
                await asyncio.sleep(.005)
                target=folder/f'source-{len(samples)}.png'
                shutil.copyfile(fixture,target)
                return target
            context=patch.object(capture,'_portal_screenshot',fake_portal) if not native else __import__('contextlib').nullcontext()
            with context:
                for index in range(count):
                    records.clear()
                    sent=[]
                    def activate():
                        sent.append(time.monotonic_ns())
                        manager._message_handler(NS(message_type=MessageType.SIGNAL,
                            interface=GLOBAL_SHORTCUTS_INTERFACE,member='Activated',
                            body=['/latency/probe',manager.shortcut_id]))
                    thread=threading.Thread(target=activate,name='injected-shortcut')
                    thread.start();thread.join()
                    spin(lambda:any(r['stage']=='toolbar_paint_processed' for r in records))
                    events_for(.04)
                    stages={r['stage']:(r['monotonic_ns']-sent[0])/1e6 for r in records}
                    assert menu._overlay is not None
                    row={'index':index,'cold':index==0,'stages_ms':stages,
                         'active':menu._overlay.isActiveWindow(),'controls_enabled':menu._overlay._toolbar.isEnabled()}
                    samples.append(row)
                    menu._on_cancelled()
                    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
                    events_for(.06)
                    assert menu._overlay is None
                    assert not menu.jobs.tasks
    finally:
        menu.shutdown();menu.jobs.close()
    uncollected=resource_counts()
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    app.processEvents()
    gc.collect()
    names=sorted({key for row in samples[1:] for key in row['stages_ms']})
    aggregates={}
    for name in names:
        values=sorted(row['stages_ms'][name] for row in samples[1:] if name in row['stages_ms'])
        aggregates[name]={'n':len(values),'median':statistics.median(values),
                          'p95':values[math.ceil(.95*len(values))-1]}
    result={'kind':'native portals/programmatic signal' if native else 'public fixture/offscreen/programmatic signal',
            'samples':samples,'warm_summary_ms':aggregates,'resources_before':before,
            'resources_after_shutdown_uncollected':uncollected,
            'resources_after_shutdown':resource_counts(), 'scheduler_source':str(scheduler_source), 'pending_tasks':len(menu.jobs.tasks)}
    Path(output).write_text(json.dumps(result,indent=2))
    print(json.dumps({'output':str(output),'count':len(samples),'summary':aggregates}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--count',type=int,default=21)
    parser.add_argument('--native',action='store_true')
    parser.add_argument('--scheduler-source',type=Path,help='Read-only baseline module snapshot for serialized A/B comparisons')
    args=parser.parse_args()
    run(args.output,args.count,args.native,args.scheduler_source)
