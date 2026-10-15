from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from tiktok_publisher.config import AppSettings

logger = logging.getLogger(__name__)


async def onboard_screenshot(
    settings: AppSettings,
    page,
    phase: str,
    row_index: int | None = None,
) -> Path | None:
    log_dir = Path(settings.logging.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"row{row_index}_" if row_index else ""
    path = log_dir / f"onboard_{suffix}{phase}.png"
    try:
        await page.screenshot(path=str(path), full_page=True)
        return path
    except Exception as e:
        logger.warning("onboard screenshot %s: %s", phase, e)
        return None


async def fill_xpath_retry(
    page,
    xpath: str,
    value: str,
    *,
    attempts: int = 2,
    timeout_ms: int = 15000,
) -> None:
    last: Exception | None = None
    for i in range(attempts):
        try:
            await page.locator(f"xpath={xpath}").fill(value, timeout=timeout_ms)
            return
        except Exception as e:
            last = e
            await asyncio.sleep(1 + i)
    raise RuntimeError(f"fill failed xpath={xpath}: {last}")


async def click_xpath_retry(
    page,
    xpath: str,
    *,
    attempts: int = 2,
    timeout_ms: int = 15000,
) -> None:
    last: Exception | None = None
    for i in range(attempts):
        try:
            loc = page.locator(f"xpath={xpath}")
            if await loc.count() == 0:
                raise RuntimeError("element not found")
            await loc.first.click(timeout=timeout_ms)
            return
        except Exception as e:
            last = e
            await asyncio.sleep(1 + i)
    raise RuntimeError(f"click failed xpath={xpath}: {last}")


async def wait_xpath_visible(
    page,
    xpath: str,
    timeout_sec: float,
) -> bool:
    import time as _time

    deadline = _time.time() + timeout_sec
    while _time.time() < deadline:
        try:
            if await page.locator(f"xpath={xpath}").count() > 0:
                return True
        except Exception:
            pass
        await asyncio.sleep(1)
    return False


async def any_xpath_visible(page, xpaths: list[str], timeout_sec: float) -> bool:
    for xp in xpaths:
        if xp and await wait_xpath_visible(page, xp, timeout_sec):
            return True
    return False
