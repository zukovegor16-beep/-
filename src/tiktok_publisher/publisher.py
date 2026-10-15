from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from tiktok_publisher.config import AppSettings, load_selectors
from tiktok_publisher.dolphin_client import ProfileSession

logger = logging.getLogger(__name__)


async def publish_video_async(
    settings: AppSettings,
    session: ProfileSession | None,
    video_path: Path,
    caption: str,
) -> tuple[bool, str]:
    if settings.dry_run or session is None:
        logger.info("[dry-run] upload %s caption=%r", video_path.name, caption[:80])
        await asyncio.sleep(0.05)
        return True, ""

    selectors = load_selectors(settings.selectors_file)
    upload_url = selectors.get("upload_url", "https://www.tiktok.com/upload")
    timeouts = selectors.get("timeouts") or {}

    try:
        import pyanty as dolphin  # type: ignore
    except ImportError as e:
        return False, str(e)

    browser = None
    try:
        browser = await dolphin.get_browser(
            session.ws_endpoint,
            session.port,
            core="patchright",
        )
        pages = browser.pages if hasattr(browser, "pages") else []
        if asyncio.iscoroutine(pages):
            pages = await pages
        if pages:
            page = pages[0]
        else:
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()

        nav_ms = int(timeouts.get("navigation_ms", 60000))
        await page.goto(upload_url, timeout=nav_ms)

        dismiss = selectors.get("split_window_dismiss")
        if dismiss:
            try:
                btn = page.locator(f"xpath={dismiss}")
                if await btn.count() > 0:
                    await btn.first.click(timeout=3000)
            except Exception:
                pass

        file_sel = selectors.get("upload_video_input", "//input[@type='file']")
        await page.locator(f"xpath={file_sel}").set_input_files(str(video_path))

        proc_ms = int(timeouts.get("upload_processing_ms", 300000))
        finished = selectors.get("upload_finished")
        if finished:
            await page.locator(f"xpath={finished}").wait_for(timeout=proc_ms)

        desc_sel = selectors.get("description", "//div[@contenteditable='true']")
        desc = page.locator(f"xpath={desc_sel}").first
        await desc.click()
        await desc.fill(caption)

        post_sel = selectors.get("post_button")
        if post_sel:
            await page.locator(f"xpath={post_sel}").click()

        post_now = selectors.get("post_now_button")
        if post_now:
            try:
                pn = page.locator(f"xpath={post_now}")
                if await pn.count() > 0:
                    await pn.first.click(timeout=5000)
            except Exception:
                pass

        confirm = selectors.get("post_confirmation")
        confirm_ms = int(timeouts.get("post_confirm_ms", 120000))
        if confirm:
            await page.locator(f"xpath={confirm}").wait_for(timeout=confirm_ms)

        await browser.disconnect()
        return True, ""
    except Exception as e:
        logger.exception("publish failed")
        if browser is not None:
            try:
                await browser.disconnect()
            except Exception:
                pass
        return False, str(e)


def publish_video(
    settings: AppSettings,
    session: ProfileSession | None,
    video_path: Path,
    caption: str,
) -> tuple[bool, str]:
    return asyncio.run(
        publish_video_async(settings, session, video_path, caption)
    )
