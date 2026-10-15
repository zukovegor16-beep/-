from __future__ import annotations

import random
import secrets
from pathlib import Path

from tiktok_publisher.config import AppSettings


def resolve_avatar_path(
    settings: AppSettings,
    *,
    login: str,
    column_path: Path,
) -> Path | None:
    pick = settings.onboard.avatar_pick
    if pick == "column" and column_path.is_file():
        return column_path

    lib = settings.avatar_library_path
    if not lib.is_dir():
        if column_path.is_file():
            return column_path
        return None

    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    files = [p for p in lib.iterdir() if p.is_file() and p.suffix.lower() in exts]
    if not files:
        return column_path if column_path.is_file() else None

    if pick == "by_login":
        key = login.strip().lower()
        for p in files:
            if p.stem.lower() == key:
                return p
        for p in files:
            if key in p.name.lower():
                return p
        return column_path if column_path.is_file() else None

    if pick == "random":
        return secrets.choice(files)

    return column_path if column_path.is_file() else random.choice(files) if files else None
