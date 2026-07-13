from __future__ import annotations

import logging
import threading
from pathlib import Path

from qingluo_console.collector_runner import run_collectors_once

logger = logging.getLogger(__name__)


class CollectionScheduler:
    def __init__(self, *, db_path: str | Path, interval_seconds: int = 60):
        self.db_path = Path(db_path)
        self.interval_seconds = max(10, interval_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="ai-console-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                run_collectors_once(db_path=self.db_path)
            except Exception:
                logger.exception("Scheduled collection failed")
            self._stop_event.wait(self.interval_seconds)
