from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from tiktok_publisher.dolphin_client import ProfileSession

logger = logging.getLogger(__name__)


@dataclass
class BrowserHandle:
    """Patchright browser connected to a Dolphin profile."""

    browser: Any
    profile: ProfileSession
    loop: asyncio.AbstractEventLoop

    async def get_page(self):
        pages = self.browser.pages
        if asyncio.iscoroutine(pages):
            pages = await pages
        if pages:
            return pages[0]
        if self.browser.contexts:
            ctx = self.browser.contexts[0]
        else:
            ctx = await self.browser.new_context()
        return await ctx.new_page()

    async def disconnect(self) -> None:
        try:
            await self.browser.disconnect()
        except Exception as e:
            logger.warning("browser disconnect: %s", e)


async def connect_profile(session: ProfileSession) -> Any:
    import pyanty as dolphin  # type: ignore

    return await dolphin.get_browser(
        session.ws_endpoint,
        session.port,
        core="patchright",
    )


def open_browser(session: ProfileSession, loop: asyncio.AbstractEventLoop) -> BrowserHandle:
    browser = loop.run_until_complete(connect_profile(session))
    return BrowserHandle(browser=browser, profile=session, loop=loop)


def close_browser(handle: BrowserHandle | None) -> None:
    if handle is None:
        return
    handle.loop.run_until_complete(handle.disconnect())
