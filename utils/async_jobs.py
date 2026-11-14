"""Cooperatively service asyncio I/O from Qt's main thread, without nested waits."""
import asyncio
import logging

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
        pending = asyncio.all_tasks(self.loop)
        for task in pending:
            task.cancel()
        if pending:
            self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        self.loop.run_until_complete(self.loop.shutdown_asyncgens())
        self.closed = True
        self.loop.close()
