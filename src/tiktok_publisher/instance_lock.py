from __future__ import annotations

import os
from pathlib import Path


class InstanceLockError(RuntimeError):
    pass


class InstanceLock:
    def __init__(self, path: Path):
        self.path = path
        self._fd: int | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import fcntl

            fd = os.open(str(self.path), os.O_CREAT | os.O_RDWR, 0o644)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.ftruncate(fd, 0)
            os.write(fd, str(os.getpid()).encode())
            self._fd = fd
        except ImportError:
            if self.path.exists():
                try:
                    old = int(self.path.read_text(encoding="utf-8").strip())
                    os.kill(old, 0)
                    raise InstanceLockError(
                        f"Уже запущен другой экземпляр (PID {old}). Закройте его или удалите {self.path}"
                    )
                except (OSError, ValueError):
                    pass
            self.path.write_text(str(os.getpid()), encoding="utf-8")
        except BlockingIOError:
            raise InstanceLockError(
                f"Уже запущен другой экземпляр. Закройте его или удалите {self.path}"
            ) from None

    def release(self) -> None:
        if self._fd is not None:
            try:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except ImportError:
                pass
            self._fd = None
        if self.path.is_file():
            try:
                if self.path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                    self.path.unlink(missing_ok=True)
            except OSError:
                pass
