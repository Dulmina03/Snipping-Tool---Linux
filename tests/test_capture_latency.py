"""Active Qt scheduling/readiness regressions; no physical keyboard claims."""
import asyncio
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QCoreApplication, QEvent, QThread, QTimer
from test_phase01 import app, spin_until
import ui.capture_menu as capture
from utils.async_jobs import AsyncJobs
from utils.capture_latency import CaptureLatency


class SchedulingTests(unittest.TestCase):
    def setUp(self):
        self.jobs = AsyncJobs()
        self.addCleanup(self.jobs.close)

    def test_idle_has_no_wakeups_and_active_jobs_return_to_idle(self):
        self.assertFalse(self.jobs.timer.isActive())
        async def operation():
            for _ in range(15):
                await asyncio.sleep(0)
            return QThread.currentThread() == app.thread()
        task=self.jobs.submit(operation())
        self.assertTrue(self.jobs.timer.isActive())
        spin_until(lambda:task.done() and not self.jobs.tasks)
        self.assertTrue(task.result())
        self.assertFalse(self.jobs.timer.isActive())
        second=self.jobs.submit(operation())
        spin_until(lambda:second.done() and not self.jobs.tasks)
        self.assertTrue(second.result())

    def test_first_completion_does_not_stop_other_owned_jobs(self):
        release=asyncio.Event()
        async def pending():
            await release.wait()
        async def short():
            await asyncio.sleep(0)
        slow=self.jobs.submit(pending());fast=self.jobs.submit(short())
        spin_until(lambda:fast.done() and fast not in self.jobs.tasks)
        self.assertTrue(self.jobs.timer.isActive())
        self.assertFalse(slow.done())
        release.set()
        spin_until(lambda:not self.jobs.tasks)
        self.assertFalse(self.jobs.timer.isActive())

    def test_completion_callback_can_submit_next_job_after_idle_transition(self):
        rows=[]
        async def operation(number):
            await asyncio.sleep(0)
            rows.append(number)
        first=self.jobs.submit(operation(1))
        first.add_done_callback(lambda task:self.jobs.submit(operation(2)))
        spin_until(lambda:rows==[1,2] and not self.jobs.tasks)
        self.assertFalse(self.jobs.timer.isActive())

    def test_suspended_io_keeps_qt_responsive_and_does_not_reenter_asyncio(self):
        beats=[]
        timer=QTimer();timer.timeout.connect(lambda:beats.append(time.monotonic()));timer.start(2)
        async def operation():
            self.jobs.tick()  # Explicit nested invocation is ignored.
            app.processEvents()
            await asyncio.sleep(.05)
        try:
            task=self.jobs.submit(operation())
            spin_until(lambda:task.done() and not self.jobs.tasks)
            self.assertIsNone(task.result())
            self.assertGreater(len(beats),3)
        finally:
            timer.stop()

    def test_close_during_suspended_io_cancels_once_and_stops_timer(self):
        entered=[];cancelled=[]
        async def operation():
            entered.append(True)
            try:await asyncio.sleep(60)
            finally:cancelled.append(True)
        self.jobs.submit(operation());spin_until(lambda:bool(entered))
        self.jobs.close()
        self.assertEqual(cancelled,[True])
        self.assertFalse(self.jobs.timer.isActive())
        self.assertTrue(self.jobs.loop.is_closed())


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.scratch=tempfile.TemporaryDirectory(prefix='snipping-readiness-')
        self.addCleanup(self.scratch.cleanup)
        self.menu=capture.CaptureMenu()
        self.rows=[];self.menu.latency_listener=self.rows.append
        self.counter=0
    def tearDown(self):
        self.menu.shutdown();self.menu.jobs.close()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    def launch(self):
        self.counter+=1
        source=Path(self.scratch.name)/f'fresh-{self.counter}.png'
        Image.new('RGB',(80,60),(self.counter,25,30)).save(source)
        async def portal(**kwargs):
            await asyncio.sleep(.002)
            return source
        with patch.object(capture,'_portal_screenshot',portal):
            self.menu.launch_overlay()
            spin_until(lambda:any(row['stage']=='overlay_interactive' for row in self.rows))
        return source

    def test_actual_handlers_report_ordered_fresh_readiness_and_preserve_pixels(self):
        source=self.launch()
        stages=[row['stage'] for row in self.rows]
        for earlier,later in (('callback_dispatched','portal_request_begin'),
                              ('portal_returned','image_loaded'),('image_loaded','widgets_created'),
                              ('widgets_created','toolbar_first_paint'),
                              ('toolbar_first_paint','toolbar_paint_processed'),
                              ('toolbar_paint_processed','overlay_interactive')):
            self.assertLess(stages.index(earlier),stages.index(later))
        self.assertEqual(self.menu._overlay.bg_pixmap.toImage().pixelColor(0,0).red(),1)
        self.assertTrue(all(set(row)=={'capture','stage','monotonic_ns','elapsed_ms'} for row in self.rows))
        self.assertTrue(source.exists())
        old_id=self.rows[0]['capture']
        self.menu._on_cancelled();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        self.rows.clear();self.launch()
        self.assertNotEqual(self.rows[0]['capture'],old_id)
        self.assertEqual(self.menu._overlay.bg_pixmap.toImage().pixelColor(0,0).red(),2)

    def test_cancel_after_creation_destroys_probe_without_late_readiness(self):
        self.launch();self.menu._on_cancelled()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
        count=len(self.rows)
        for _ in range(5):app.processEvents()
        self.assertEqual(len(self.rows),count)
        self.assertIsNone(self.menu._overlay)

    def test_disabled_diagnostics_do_not_attach_qt_probe(self):
        with patch.dict('os.environ',{'SNIPPING_LATENCY_DIAGNOSTICS':'0'}):
            run=CaptureLatency()
        self.assertFalse(run.enabled)
        self.assertIsNone(run.identifier)
