from __future__ import annotations

import logging
from collections import deque
from threading import Lock

_lock = Lock()
_lines: deque[str] = deque(maxlen=500)


class RingBufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        with _lock:
            _lines.append(msg)


def get_log_tail(n: int = 50) -> list[str]:
    with _lock:
        return list(_lines)[-n:]


def setup_logging(log_dir: str | None = None) -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler = RingBufferHandler()
    handler.setFormatter(fmt)
    root.addHandler(handler)
    if log_dir:
        from pathlib import Path

        Path(log_dir).mkdir(parents=True, exist_ok=True)
        from logging.handlers import RotatingFileHandler

        fh = RotatingFileHandler(
            Path(log_dir) / "tiktok-publisher.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)
