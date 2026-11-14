"""Opt-in local Phase 1 diagnostics; never records pixels or extracted text."""
import json
import logging
import os
import functools
import inspect
import time
from pathlib import Path


def timed(event):
    """Opt-in monotonic durations; never includes pixels or OCR contents."""
    def decorate(function):
        if inspect.iscoroutinefunction(function):
            @functools.wraps(function)
            async def asynchronous(*args, **kwargs):
                start = time.monotonic()
                try:
                    return await function(*args, **kwargs)
                finally:
                    trace('duration', operation=event, milliseconds=(time.monotonic()-start)*1000)
            return asynchronous
        @functools.wraps(function)
        def synchronous(*args, **kwargs):
            start = time.monotonic()
            try:
                return function(*args, **kwargs)
            finally:
                trace('duration', operation=event, milliseconds=(time.monotonic()-start)*1000)
        return synchronous
    return decorate


def trace(event, **fields):
    if os.environ.get('SNIPPING_DIAGNOSTICS') == '1':
        logging.getLogger('snipping.diagnostics').info(json.dumps({'event': event, **fields}, default=str))


def image_trace(event, path, **fields):
    if os.environ.get('SNIPPING_DIAGNOSTICS') != '1':
        return
    from PySide6.QtGui import QImage
    path = Path(path)
    image = QImage(str(path))
    trace(event, path=str(path), exists=path.is_file(), valid=not image.isNull(),
          dimensions=[image.width(), image.height()],
          bytes=path.stat().st_size if path.is_file() else None, **fields)
