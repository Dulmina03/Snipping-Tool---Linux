"""Cooperatively service asyncio I/O from Qt's main thread, without nested waits."""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from PySide6.QtCore import QObject, QTimer


class AsyncJobs(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = asyncio.new_event_loop()
        self.timer = QTimer(self)
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.tasks = set()
        self.closed = False
        self.file_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='snipping-file')

    async def run_file(self, function, *args, **kwargs):
        """Only plain file/Pillow work; never pass Qt GUI objects here.

        A running filesystem write cannot safely be interrupted. Drain it on
        cancellation so source cleanup, retry and shutdown cannot race it.
        """
        if self.closed:
            raise RuntimeError('Application is shutting down')
        future = self.file_executor.submit(partial(function, *args, **kwargs))
        cancelled = False
        # Poll one concurrent future on our already-cooperative asyncio loop.
        # Do not depend on cross-thread asyncio future callbacks: the target
        # Python runtime stalled at shutdown in that implementation's regression.
        while not future.done():
            try:
                await asyncio.sleep(.01)
            except asyncio.CancelledError:
                cancelled = True
        if cancelled:
            future.exception()  # Consume a failure after cancellation; never publish it.
            raise asyncio.CancelledError
        return future.result()

    def submit(self, coroutine):
        if self.closed:
            coroutine.close()
            raise RuntimeError('Application is shutting down')
        task = self.loop.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self._finished)
        return task

    def _finished(self, task):
        self.tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logging.getLogger(__name__).error('Background operation failed: %s', task.exception())

    def tick(self):
        # Clipboard helpers process Qt events; prevent re-entering asyncio there.
        if self.closed or self.loop.is_running():
            return
        self.loop.call_soon(self.loop.stop)
        self.loop.run_forever()

    def close(self):
        """Called after Qt exec returns; cancel I/O and reap child processes."""
        if self.closed:
            return
        self.timer.stop()
        # Cancel owned roots first: their finally blocks reap subprocesses.
        # Cancelling shielded spawn tasks directly can orphan a child.
        pending = set(self.tasks)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        remaining = asyncio.all_tasks(self.loop)
        for task in remaining:
            task.cancel()
        if remaining:
            self.loop.run_until_complete(asyncio.gather(*remaining, return_exceptions=True))
        self.loop.run_until_complete(self.loop.shutdown_asyncgens())
        self.file_executor.shutdown(wait=True, cancel_futures=True)
        self.closed = True
        self.loop.close()
