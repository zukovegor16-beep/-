from __future__ import annotations

import asyncio
import random


async def human_delay(min_ms: int, max_ms: int) -> None:
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000.0)


async def wheel_scroll(page, delta_y: int) -> None:
    await page.mouse.wheel(0, delta_y)


async def scroll_feed_step(page) -> None:
    delta = random.randint(400, 900)
    await wheel_scroll(page, delta)
    try:
        await page.keyboard.press("ArrowDown")
    except Exception:
        pass
