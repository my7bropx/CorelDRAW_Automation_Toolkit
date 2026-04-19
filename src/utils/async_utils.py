"""
Async utilities backed by the shared drawing-tool worker/progress pipeline.
"""

import logging
from functools import wraps
from typing import Callable, Optional

from PyQt5.QtCore import QObject

from ..tools.common.progress_controller import OperationWorker

logger = logging.getLogger(__name__)


class AsyncManager(QObject):
    """Thin compatibility wrapper around the shared OperationWorker."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        super().__init__()
        self._current_worker: Optional[OperationWorker] = None
        logger.info("Async manager initialized")

    def run(
        self,
        func: Callable,
        on_progress: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_status: Optional[Callable] = None,
        *args,
        **kwargs,
    ) -> OperationWorker:
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.cancel()
            self._current_worker.wait()

        worker = OperationWorker(func, *args, **kwargs)

        if on_progress:
            worker.snapshot.connect(lambda snapshot: on_progress(snapshot.current, snapshot.total))
        if on_status:
            worker.snapshot.connect(lambda snapshot: on_status(snapshot.phase))
        if on_complete:
            worker.finished.connect(on_complete)
        if on_error:
            worker.error.connect(on_error)

        worker.start()
        self._current_worker = worker
        return worker

    def cancel_current(self):
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.cancel()
            logger.info("Current async operation cancelled")

    def shutdown(self):
        logger.info("Async manager shutdown")


async_manager = AsyncManager()


def async_operation(progress_callback: Callable = None, status_callback: Callable = None, cancel_callback: Callable = None):
    """Compatibility decorator for background operations."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return async_manager.run(func, *args, **kwargs)

        return wrapper

    return decorator
