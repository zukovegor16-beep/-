from __future__ import annotations

import asyncio
import random


async def human_delay(min_ms: int, max_ms: int) -> None:
    await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000.0)


async def human_delay_skewed(min_ms: int, max_ms: int) -> None:
    """Slightly longer tail — more human-like pauses."""
    lo, hi = min_ms / 1000.0, max_ms / 1000.0
    t = random.triangular(lo, hi, lo + (hi - lo) * 0.35)
    await asyncio.sleep(t)


async def mouse_jitter(page, width: int = 800, height: int = 600) -> None:
    try:
        x = random.randint(80, max(100, width - 80))
        y = random.randint(80, max(100, height - 80))
        await page.mouse.move(x, y, steps=random.randint(3, 8))
    except Exception:
        pass


async def wheel_scroll(page, delta_y: int) -> None:
    await page.mouse.wheel(0, delta_y)


async def scroll_feed_step(page, *, scroll_up_probability: float = 0.0) -> None:
    if random.random() < scroll_up_probability:
        delta = -random.randint(200, 500)
    else:
        delta = random.randint(400, 900)
    await wheel_scroll(page, delta)
    try:
        key = "ArrowUp" if delta < 0 else "ArrowDown"
        await page.keyboard.press(key)
    except Exception:
        pass
