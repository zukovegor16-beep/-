from __future__ import annotations

import shutil
from pathlib import Path

from tiktok_publisher.config import AppSettings


POSTED_DIRNAME = "posted"


def list_pending_videos(folder: Path, settings: AppSettings) -> list[Path]:
    if not folder.is_dir():
        return []
    exts = {e.lower() for e in settings.queue.extensions}
    files = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in exts
    ]
    if settings.queue.sort_by == "name":
        files.sort(key=lambda p: p.name.lower())
    else:
        files.sort(key=lambda p: p.stat().st_mtime)
    return files


def next_video(folder: Path, settings: AppSettings) -> Path | None:
    pending = list_pending_videos(folder, settings)
    return pending[0] if pending else None


def move_to_posted(video: Path) -> Path:
    posted_dir = video.parent / POSTED_DIRNAME
    posted_dir.mkdir(parents=True, exist_ok=True)
    dest = posted_dir / video.name
    if dest.exists():
        dest = posted_dir / f"{video.stem}_{video.stat().st_mtime_ns}{video.suffix}"
    shutil.move(str(video), str(dest))
    return dest
