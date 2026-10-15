from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator

from tiktok_publisher.browser_session import BrowserHandle, close_browser, open_browser
from tiktok_publisher.config import AppSettings
from tiktok_publisher.dolphin_client import DolphinClient, ProfileSession

logger = logging.getLogger(__name__)


@dataclass
class BrowserSession:
    settings: AppSettings
    profile_id: str
    loop: asyncio.AbstractEventLoop
    session: ProfileSession | None = None
    handle: BrowserHandle | None = None

    def start(self) -> None:
        if self.settings.dry_run:
            return
        dolphin = DolphinClient(self.settings)
        self.session = dolphin.start_profile(self.profile_id)
        self.handle = open_browser(self.session, self.loop)

    def stop(self) -> None:
        if self.settings.dry_run:
            return
        close_browser(self.handle)
        self.handle = None
        if self.session:
            DolphinClient(self.settings).stop_profile(self.profile_id)
            self.session = None


@contextmanager
def profile_browser_session(
    settings: AppSettings,
    profile_id: str,
    loop: asyncio.AbstractEventLoop,
) -> Generator[BrowserSession, None, None]:
    bs = BrowserSession(settings=settings, profile_id=profile_id, loop=loop)
    try:
        bs.start()
        yield bs
    finally:
        bs.stop()
