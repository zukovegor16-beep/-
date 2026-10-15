from __future__ import annotations

from pathlib import Path


class UploadLock:
    """Marker file while a video is being uploaded."""

    def __init__(self, video: Path):
        self.video = video
        self.marker = video.with_name(video.name + ".uploading")

    def acquire(self) -> bool:
        try:
            if self.marker.exists():
                return False
            self.marker.write_text("1", encoding="utf-8")
            return True
        except OSError:
            return True

    def release(self) -> None:
        try:
            self.marker.unlink(missing_ok=True)
        except OSError:
            pass

    def __enter__(self) -> UploadLock:
        if not self.acquire():
            raise RuntimeError(f"Файл уже загружается: {self.video.name}")
        return self

    def __exit__(self, *args) -> None:
        self.release()
