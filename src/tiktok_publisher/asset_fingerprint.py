from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1024 * 1024
_SMALL_FILE = 50 * 1024 * 1024


def file_fingerprint(path: Path) -> str:
    """Stable id for a video file (content + size)."""
    st = path.stat()
    size = st.st_size
    h = hashlib.sha256()
    h.update(str(size).encode())
    h.update(str(st.st_mtime_ns).encode())
    with path.open("rb") as f:
        if size <= _SMALL_FILE:
            while chunk := f.read(_CHUNK):
                h.update(chunk)
        else:
            h.update(f.read(_CHUNK))
    return h.hexdigest()
