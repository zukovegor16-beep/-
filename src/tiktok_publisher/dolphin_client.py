from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from tiktok_publisher.config import AppSettings

logger = logging.getLogger(__name__)


@dataclass
class ProfileSession:
    profile_id: str
    port: int
    ws_endpoint: str


class DolphinClient:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._api = None

    def ping(self) -> tuple[bool, str]:
        base = self.settings.dolphin.api_base.rstrip("/")
        try:
            r = httpx.get(f"{base}/v1.0/browser_profiles", timeout=5.0)
            if r.status_code == 401:
                return True, "API доступен (требуется авторизация)"
            if r.status_code < 500:
                return True, f"API ответ: {r.status_code}"
            return False, f"HTTP {r.status_code}"
        except httpx.HTTPError as e:
            return False, str(e)

    def start_profile(self, profile_id: str) -> ProfileSession:
        try:
            import pyanty as dolphin  # type: ignore
            from pyanty import DolphinAPI  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "Установите Dolphin support: pip install 'tiktok-publisher[dolphin]'"
            ) from e

        token = self.settings.dolphin.api_token
        api = DolphinAPI(api_key=token) if token else DolphinAPI()
        self._api = api
        run_info = dolphin.run_profile(profile_id)
        automation = run_info.get("automation") or {}
        port = automation.get("port")
        ws = automation.get("wsEndpoint") or automation.get("ws_endpoint")
        if not port or not ws:
            raise RuntimeError(f"Не удалось запустить профиль {profile_id}: {run_info}")
        logger.info("Dolphin profile %s started on port %s", profile_id, port)
        return ProfileSession(profile_id=profile_id, port=int(port), ws_endpoint=str(ws))

    def stop_profile(self, profile_id: str) -> None:
        try:
            import pyanty as dolphin  # type: ignore
        except ImportError:
            return
        try:
            dolphin.close_profile(profile_id)
            logger.info("Dolphin profile %s stopped", profile_id)
        except Exception as e:
            logger.warning("stop profile %s: %s", profile_id, e)
