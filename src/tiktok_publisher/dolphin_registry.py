from __future__ import annotations

import atexit
import logging
from threading import Lock

from tiktok_publisher.config import AppSettings

logger = logging.getLogger(__name__)

_lock = Lock()
_active_profile_ids: set[str] = set()
_client_factory = None


def set_client_factory(factory) -> None:
    global _client_factory
    _client_factory = factory


def register_profile(profile_id: str) -> None:
    with _lock:
        _active_profile_ids.add(str(profile_id))


def unregister_profile(profile_id: str) -> None:
    with _lock:
        _active_profile_ids.discard(str(profile_id))


def active_profiles() -> list[str]:
    with _lock:
        return sorted(_active_profile_ids)


def stop_all_profiles(settings: AppSettings | None = None) -> None:
    with _lock:
        ids = list(_active_profile_ids)
    if not ids:
        return
    if _client_factory is None and settings is None:
        logger.warning("dolphin cleanup skipped: no client (%s profiles)", len(ids))
        return
    try:
        from tiktok_publisher.dolphin_client import DolphinClient

        client = _client_factory() if _client_factory else DolphinClient(settings)  # type: ignore[arg-type]
        for pid in ids:
            try:
                client.stop_profile(pid)
            except Exception as e:
                logger.warning("cleanup stop %s: %s", pid, e)
            unregister_profile(pid)
    except Exception as e:
        logger.warning("dolphin cleanup failed: %s", e)


def _atexit_cleanup() -> None:
    stop_all_profiles(None)


atexit.register(_atexit_cleanup)
