"""Opt-in monotonic capture readiness timings; no image paths or contents."""
import itertools
from contextvars import ContextVar
import json
import logging
import os
import time

from PySide6.QtCore import QObject, QEvent, QTimer, Slot

_counter = itertools.count(1)
active_capture = ContextVar("active_capture_latency", default=None)


def signal_received():
    if os.environ.get('SNIPPING_LATENCY_DIAGNOSTICS') == '1':
        logging.getLogger('snipping.latency').info(json.dumps({
            'stage': 'shortcut_signal_received', 'monotonic_ns': time.monotonic_ns()}))


class CaptureLatency:
    def __init__(self, listener=None):
        self.listener = listener
        self.enabled = listener is not None or os.environ.get('SNIPPING_LATENCY_DIAGNOSTICS') == '1'
        self.started = time.monotonic_ns() if self.enabled else 0
        self.identifier = next(_counter) if self.enabled else None
        self.mark('callback_dispatched')

    def mark(self, stage):
        if not self.enabled:
            return
        now = time.monotonic_ns()
        row = {'capture': self.identifier, 'stage': stage, 'monotonic_ns': now,
               'elapsed_ms': (now - self.started) / 1_000_000}
        if self.listener is not None:
            self.listener(row)
        if os.environ.get('SNIPPING_LATENCY_DIAGNOSTICS') == '1':
            logging.getLogger('snipping.latency').info(json.dumps(row))

    def observe(self, overlay):
        if self.enabled:
            # Parent lifetime cancels pending timers on close/delete. Hold no
            # screenshot or controller reference after surface destruction.
            surface = getattr(overlay, 'primary', overlay)
            probe = ReadinessProbe(surface, overlay._toolbar, self.mark)
            surface._latency_probe = probe


class ReadinessProbe(QObject):
    def __init__(self, surface, toolbar, record):
        super().__init__(toolbar)
        self.surface, self.toolbar, self.record = surface, toolbar, record
        self.painted = self.complete = self.visible = self.interactive = False
        self.check = QTimer(self)
        self.check.setSingleShot(True)
        self.check.timeout.connect(self._after_event)
        surface.installEventFilter(self)
        toolbar.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.toolbar and event.type() == QEvent.Show and not self.visible:
            self.visible = True
            self.record('toolbar_visible')
        if watched is self.toolbar and event.type() == QEvent.Paint and not self.painted:
            self.painted = True
            self.record('toolbar_first_paint')
            self.check.start(0)
        if watched is self.surface and event.type() == QEvent.WindowActivate:
            self.check.start(0)
        return False

    @Slot()
    def _after_event(self):
        if self.painted and not self.complete:
            self.complete = True
            self.record('toolbar_paint_processed')
        if (self.complete and not self.interactive and self.surface.isActiveWindow()
                and self.toolbar.isVisible() and self.toolbar.isEnabled()):
            self.interactive = True
            self.record('overlay_interactive')
