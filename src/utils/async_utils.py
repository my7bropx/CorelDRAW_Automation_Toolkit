"""
Async Utilities Module
Provides async operation support with progress reporting and cancellation.
"""

import logging
from typing import Callable, Any, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, Future
from functools import wraps

from PyQt5.QtCore import QObject, pyqtSignal, QThread

logger = logging.getLogger(__name__)


class AsyncWorker(QThread):
    """Worker thread for running long operations in background."""
    
    progress = pyqtSignal(int, int)  # current, total
    finished = pyqtSignal(object)  # result
    error = pyqtSignal(str)  # error message
    status = pyqtSignal(str)  # status message
    
    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False
        self._result = None
        
    def run(self):
        """Execute the function in background thread."""
        try:
            self._result = self._func(
                *self._args,
                progress_callback=self._report_progress,
                status_callback=self._report_status,
                cancel_callback=lambda: self._cancelled,
                **self._kwargs
            )
            self.finished.emit(self._result)
        except Exception as e:
            logger.error(f"Async worker error: {e}")
            self.error.emit(str(e))
    
    def _report_progress(self, current: int, total: int):
        """Report progress from worker."""
        self.progress.emit(current, total)
    
    def _report_status(self, message: str):
        """Report status from worker."""
        self.status.emit(message)
    
    def cancel(self):
        """Cancel the operation."""
        self._cancelled = True


class AsyncManager(QObject):
    """
    Manager for async operations with progress tracking.
    """
    
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
        
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._current_worker: Optional[AsyncWorker] = None
        
        logger.info("Async manager initialized")
    
    def run(
        self, 
        func: Callable, 
        on_progress: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        on_status: Optional[Callable] = None,
        *args, 
        **kwargs
    ) -> AsyncWorker:
        """
        Run a function asynchronously with progress tracking.
        
        Args:
            func: Function to run (should accept progress_callback and status_callback)
            on_progress: Callback for progress updates
            on_complete: Callback when complete
            on_error: Callback on error
            on_status: Callback for status messages
            *args, **kwargs: Arguments for the function
            
        Returns:
            AsyncWorker instance
        """
        # Cancel any existing operation
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.cancel()
            self._current_worker.wait()
        
        worker = AsyncWorker(func, *args, **kwargs)
        
        if on_progress:
            worker.progress.connect(on_progress)
        if on_complete:
            worker.finished.connect(on_complete)
        if on_error:
            worker.error.connect(on_error)
        if on_status:
            worker.status.connect(on_status)
            
        worker.start()
        self._current_worker = worker
        
        return worker
    
    def cancel_current(self):
        """Cancel the current operation."""
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.cancel()
            logger.info("Current async operation cancelled")
    
    def shutdown(self):
        """Shutdown the executor."""
        self._executor.shutdown(wait=True)
        logger.info("Async manager shutdown")


# Global instance
async_manager = AsyncManager()


def async_operation(progress_callback: Callable = None, status_callback: Callable = None, cancel_callback: Callable = None):
    """
    Decorator for async operations.
    
    Usage:
        @async_operation()
        def long_task(progress_callback, status_callback, cancel_callback):
            for i in range(100):
                if cancel_callback and cancel_callback():
                    break
                progress_callback(i, 100)
                status_callback(f"Processing {i}/100")
            return result
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return async_manager.run(
                func,
                *args,
                **kwargs
            )
        return wrapper
    return decorator
