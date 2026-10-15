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

    async def _context(self):
        if self.browser.contexts:
            return self.browser.contexts[0]
        return await self.browser.new_context()

    async def get_page(self):
        pages = self.browser.pages
        if asyncio.iscoroutine(pages):
            pages = await pages
        if pages:
            return pages[0]
        ctx = await self._context()
        return await ctx.new_page()

    async def new_page(self):
        ctx = await self._context()
        return await ctx.new_page()

    async def disconnect(self) -> None:
        try:
            await self.browser.disconnect()
        except Exception as e:
            logger.warning("browser disconnect: %s", e)

    async def is_healthy(self) -> bool:
        try:
            page = await self.get_page()
            url = page.url
            if not url or url == "about:blank":
                return False
            await page.title()
            return True
        except Exception:
            return False


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
