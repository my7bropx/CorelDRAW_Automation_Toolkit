import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from PyQt5.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class OperationCancelled(RuntimeError):
    """Raised when a long-running tool operation is cancelled."""


@dataclass
class ProgressSnapshot:
    phase: str
    current: int
    total: int
    percent: float
    elapsed_seconds: float
    eta_seconds: Optional[float]


class ProgressController:
    """Track progress, elapsed time, ETA, and cancellation with throttled updates."""

    def __init__(
        self,
        snapshot_callback: Optional[Callable[[ProgressSnapshot], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        min_emit_interval: float = 0.08,
    ) -> None:
        self._snapshot_callback = snapshot_callback
        self._cancel_check = cancel_check
        self._min_emit_interval = max(0.01, float(min_emit_interval))
        self._operation_started = time.perf_counter()
        self._phase_started = self._operation_started
        self._phase = "Idle"
        self._current = 0
        self._total = 0
        self._last_emit = 0.0

    def is_cancelled(self) -> bool:
        return bool(self._cancel_check and self._cancel_check())

    def throw_if_cancelled(self) -> None:
        if self.is_cancelled():
            raise OperationCancelled("Operation cancelled.")

    def start_phase(self, phase: str, total: int = 0, current: int = 0, force: bool = True) -> None:
        self._phase = phase
        self._phase_started = time.perf_counter()
        self._current = max(0, int(current))
        self._total = max(0, int(total))
        self.emit(force=force)

    def update(self, current: int, total: Optional[int] = None, phase: Optional[str] = None, force: bool = False) -> None:
        if phase is not None and phase != self._phase:
            self._phase = phase
            self._phase_started = time.perf_counter()
        self._current = max(0, int(current))
        if total is not None:
            self._total = max(0, int(total))
        self.emit(force=force)

    def advance(self, step: int = 1, force: bool = False) -> None:
        self._current += int(step)
        self.emit(force=force)

    def complete(self, force: bool = True) -> None:
        if self._total > 0:
            self._current = self._total
        self.emit(force=force)

    def emit(self, force: bool = False) -> None:
        if self._snapshot_callback is None:
            return
        now = time.perf_counter()
        if not force and (now - self._last_emit) < self._min_emit_interval:
            return
        self._last_emit = now
        elapsed = max(0.0, now - self._operation_started)
        eta = None
        percent = 0.0
        if self._total > 0:
            percent = min(100.0, (self._current / max(1, self._total)) * 100.0)
            if self._current > 0:
                rate = elapsed / self._current
                eta = max(0.0, rate * max(0, self._total - self._current))
        self._snapshot_callback(
            ProgressSnapshot(
                phase=self._phase,
                current=self._current,
                total=self._total,
                percent=percent,
                elapsed_seconds=elapsed,
                eta_seconds=eta,
            )
        )

    def legacy_progress_callback(self, current: int, total: int) -> None:
        self.update(current, total)


class OperationWorker(QThread):
    """Generic worker for long-running drawing-tool operations."""

    snapshot = pyqtSignal(object)
    finished = pyqtSignal(object)
    cancelled = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, func: Callable[..., Any], *args, **kwargs) -> None:
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False
        self._label = getattr(func, "__name__", func.__class__.__name__)

    def cancel(self) -> None:
        self._cancelled = True
        logger.info("operation-worker cancel requested task=%s", self._label)

    def _emit_snapshot(self, snapshot: ProgressSnapshot) -> None:
        self.snapshot.emit(snapshot)

    def run(self) -> None:
        com_ready = False
        started = time.perf_counter()
        logger.info("operation-worker started task=%s", self._label)
        try:
            import pythoncom

            pythoncom.CoInitialize()
            com_ready = True
        except Exception as exc:
            logger.debug("Worker COM initialization skipped: %s", exc)

        controller = ProgressController(
            snapshot_callback=self._emit_snapshot,
            cancel_check=lambda: self._cancelled,
        )
        try:
            result = self._func(
                *self._args,
                progress_controller=controller,
                progress_callback=controller.legacy_progress_callback,
                cancel_callback=controller.is_cancelled,
                **self._kwargs,
            )
            if self._cancelled:
                logger.info("operation-worker cancelled task=%s elapsed=%.4fs", self._label, time.perf_counter() - started)
                self.cancelled.emit()
            else:
                logger.info("operation-worker finished task=%s elapsed=%.4fs", self._label, time.perf_counter() - started)
                self.finished.emit(result)
        except OperationCancelled:
            logger.info("operation-worker cancelled via exception task=%s elapsed=%.4fs", self._label, time.perf_counter() - started)
            self.cancelled.emit()
        except Exception as exc:
            logger.error("Operation worker failed: %s", exc)
            self.error.emit(str(exc))
        finally:
            if com_ready:
                try:
                    import pythoncom

                    pythoncom.CoUninitialize()
                except Exception:
                    pass
