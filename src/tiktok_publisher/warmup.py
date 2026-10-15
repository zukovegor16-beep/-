from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from tiktok_publisher.browser_session import BrowserHandle
from tiktok_publisher.config import AppSettings
from tiktok_publisher.human_actions import human_delay, scroll_feed_step
from tiktok_publisher.outcomes import Outcome, OutcomeCode
from tiktok_publisher.publisher import _is_blocked_page

logger = logging.getLogger(__name__)


@dataclass
class WarmupResult:
    outcome: Outcome
    duration_sec: float
    likes: int
    scrolls: int


def _load_warmup_selectors(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


async def run_warmup_async(
    settings: AppSettings,
    handle: BrowserHandle | None,
    loop: asyncio.AbstractEventLoop,
) -> WarmupResult:
    cfg = settings.session.warmup
    started = time.time()
    if settings.dry_run or handle is None:
        await asyncio.sleep(0.05)
        return WarmupResult(
            Outcome.from_code(OutcomeCode.dry_run, "warmup dry-run"),
            time.time() - started,
            0,
            0,
        )

    sel = _load_warmup_selectors(settings.selectors_warmup_file)
    feed_url = sel.get("feed_url", "https://www.tiktok.com/foryou")
    like_sel = sel.get("like_button", '[data-e2e="like-icon"]')
    nav_ms = int((sel.get("timeouts") or {}).get("navigation_ms", 60000))

    page = await handle.get_page()
    await page.goto(feed_url, timeout=nav_ms, wait_until="domcontentloaded")
    body = (await page.content())[:8000]
    blocked = _is_blocked_page(page.url, body)
    if blocked:
        from tiktok_publisher.outcomes import classify_publish_error

        code = classify_publish_error(blocked)
        return WarmupResult(
            Outcome.from_code(code, blocked),
            time.time() - started,
            0,
            0,
        )

    scrolls = random.randint(cfg.scroll_count_min, cfg.scroll_count_max)
    likes = 0
    max_likes = random.randint(cfg.likes_min, cfg.likes_max)

    for _ in range(scrolls):
        if time.time() - started > cfg.max_duration_sec:
            break
        await scroll_feed_step(page)
        await human_delay(cfg.scroll_pause_sec.min * 1000, cfg.scroll_pause_sec.max * 1000)
        if likes < max_likes and random.random() < cfg.like_probability:
            try:
                btn = page.locator(like_sel).first
                if await btn.count() > 0:
                    await btn.click(timeout=5000)
                    likes += 1
            except Exception as e:
                logger.debug("like skip: %s", e)

    return WarmupResult(
        Outcome.from_code(OutcomeCode.warmup_ok, "warmup ok"),
        time.time() - started,
        likes,
        scrolls,
    )


def run_warmup(
    settings: AppSettings,
    handle: BrowserHandle | None,
    loop: asyncio.AbstractEventLoop,
) -> WarmupResult:
    return loop.run_until_complete(run_warmup_async(settings, handle, loop))
