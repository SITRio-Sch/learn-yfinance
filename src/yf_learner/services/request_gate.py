"""Thread-safe pacing gate for provider requests."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class RequestGate:
    """Serializes provider operations and enforces a minimum interval between starts."""

    def __init__(
        self,
        min_interval_seconds: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self._min_interval = min_interval_seconds
        self._clock = clock
        self._sleep = sleep_func
        self._lock = threading.Lock()
        self._last_start_time: float = 0.0

    def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Acquires the lock, paces based on the last start time, and executes func."""
        with self._lock:
            now = self._clock()
            elapsed = now - self._last_start_time
            if elapsed < self._min_interval:
                to_sleep = self._min_interval - elapsed
                self._sleep(to_sleep)

            # Record start time
            self._last_start_time = self._clock()
            return func(*args, **kwargs)
