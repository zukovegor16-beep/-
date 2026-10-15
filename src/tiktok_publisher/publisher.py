from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from tiktok_publisher.browser_session import BrowserHandle
from tiktok_publisher.config import AppSettings, load_selectors
from tiktok_publisher.dolphin_client import ProfileSession
from tiktok_publisher.outcomes import OutcomeCode, classify_publish_error
from tiktok_publisher.publish_result import PublishResult

logger = logging.getLogger(__name__)

LOGIN_HINTS = re.compile(
    r"login|log_in|sign_up|signup|/login",
    re.I,
)
CAPTCHA_HINTS = re.compile(r"captcha|verify|verification|robot", re.I)
RATE_LIMIT_HINTS = re.compile(r"rate.?limit|too many|try again later|频繁", re.I)


async def _screenshot(page, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        await page.screenshot(path=str(path), full_page=True)
    except Exception as e:
        logger.warning("screenshot failed: %s", e)


def _is_blocked_page(url: str, body_snippet: str) -> str | None:
    if LOGIN_HINTS.search(url):
        return "TikTok не авторизован — войдите в профиле Dolphin"
    low = body_snippet.lower()
    if CAPTCHA_HINTS.search(low) or CAPTCHA_HINTS.search(url):
        return "TikTok captcha/verify — решите вручную в профиле"
    if RATE_LIMIT_HINTS.search(low):
        return "TikTok rate limit — уменьшите частоту постинга"
    return None


async def _resolve_upload_page(handle: BrowserHandle, upload_url: str, nav_ms: int):
    page = await handle.get_page()
    await page.goto(upload_url, timeout=nav_ms, wait_until="domcontentloaded")
    url = page.url
    try:
        body = (await page.content())[:8000]
    except Exception:
        body = ""
    blocked = _is_blocked_page(url, body)
    if blocked:
        raise RuntimeError(blocked)
    return page


async def _fill_caption(page, desc_sel: str, caption: str) -> None:
    desc = page.locator(f"xpath={desc_sel}").first
    await desc.click(timeout=15000)
    try:
        await desc.fill(caption)
    except Exception:
        await page.keyboard.press("Control+A")
        await page.keyboard.type(caption, delay=20)


async def _verify_post_success(page, selectors: dict, upload_url: str, confirm_ms: int) -> bool:
    """At least 2 of 3 signals that post succeeded."""
    signals = 0
    confirm = selectors.get("post_confirmation")
    if confirm:
        try:
            await page.locator(f"xpath={confirm}").wait_for(timeout=min(confirm_ms, 15000))
            signals += 1
        except Exception:
            pass
    url = page.url
    if "/upload" not in url.lower():
        signals += 1
    post_sel = selectors.get("post_button")
    if post_sel:
        try:
            btn = page.locator(f"xpath={post_sel}")
            if await btn.count() == 0:
                signals += 1
            elif not await btn.first.is_enabled():
                signals += 1
        except Exception:
            signals += 1
    try:
        body = (await page.content())[:8000]
    except Exception:
        body = ""
    if _is_blocked_page(url, body):
        return False
    if signals == 0 and confirm:
        return False
    return signals >= 2 or (signals >= 1 and not confirm)


async def publish_video_async(
    settings: AppSettings,
    session: ProfileSession | None,
    video_path: Path,
    caption: str,
    browser_handle: BrowserHandle | None = None,
    *,
    run_id: str = "",
    account_no: str = "",
    retry: bool = True,
) -> PublishResult:
    if settings.dry_run or (session is None and browser_handle is None):
        logger.info("[dry-run] upload %s caption=%r", video_path.name, caption[:80])
        await asyncio.sleep(0.02)
        return PublishResult(True, OutcomeCode.dry_run, "")

    selectors = load_selectors(settings.selectors_file)
    upload_url = selectors.get("upload_url", "https://www.tiktok.com/upload")
    timeouts = selectors.get("timeouts") or {}
    nav_ms = int(timeouts.get("navigation_ms", 60000))
    proc_ms = int(timeouts.get("upload_processing_ms", 300000))
    confirm_ms = int(timeouts.get("post_confirm_ms", 120000))
    log_dir = Path(settings.logging.log_dir)

    last_err = ""

    for attempt in range(2 if retry else 1):
        page = None
        own_handle = browser_handle is None
        handle = browser_handle
        try:
            if handle is None and session is not None:
                raise RuntimeError("browser_handle required when reusing session")

            page = await _resolve_upload_page(handle, upload_url, nav_ms)

            dismiss = selectors.get("split_window_dismiss")
            if dismiss:
                try:
                    btn = page.locator(f"xpath={dismiss}")
                    if await btn.count() > 0:
                        await btn.first.click(timeout=3000)
                except Exception:
                    pass

            iframe_sel = selectors.get("iframe")
            target = page
            if iframe_sel:
                try:
                    frame = page.frame_locator(f"xpath={iframe_sel}")
                    target = frame
                except Exception:
                    pass

            file_sel = selectors.get("upload_video_input", "//input[@type='file']")
            await target.locator(f"xpath={file_sel}").set_input_files(str(video_path))

            finished = selectors.get("upload_finished")
            if finished:
                await target.locator(f"xpath={finished}").wait_for(timeout=proc_ms)

            desc_sel = selectors.get("description", "//div[@contenteditable='true']")
            await _fill_caption(page if target is page else page, desc_sel, caption)

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

            if not await _verify_post_success(page, selectors, upload_url, confirm_ms):
                raise RuntimeError("Не удалось подтвердить публикацию (success criteria)")

            return PublishResult(True, OutcomeCode.published, "")
        except Exception as e:
            last_err = str(e)
            logger.warning("publish attempt %s failed: %s", attempt + 1, e)
            if page is not None:
                shot = (
                    log_dir
                    / f"fail_{run_id}_{account_no}_{video_path.stem}_a{attempt + 1}.png"
                )
                await _screenshot(page, shot)
            if attempt == 0 and retry and _is_retryable(last_err):
                await asyncio.sleep(2)
                continue
            code = classify_publish_error(last_err)
            return PublishResult(False, code, last_err)
        finally:
            if own_handle and handle is not None:
                await handle.disconnect()

    code = classify_publish_error(last_err)
    return PublishResult(False, code, last_err)


def _is_retryable(err: str) -> bool:
    low = err.lower()
    if any(x in low for x in ("captcha", "авторизован", "rate limit")):
        return False
    return any(
        x in low
        for x in ("timeout", "selector", "waiting", "detached", "navigation", "success criteria")
    )


def publish_video(
    settings: AppSettings,
    session: ProfileSession | None,
    video_path: Path,
    caption: str,
    browser_handle: BrowserHandle | None = None,
    loop: asyncio.AbstractEventLoop | None = None,
    **kwargs,
) -> PublishResult:
    if loop is None:
        return asyncio.run(
            publish_video_async(
                settings,
                session,
                video_path,
                caption,
                browser_handle,
                **kwargs,
            )
        )
    return loop.run_until_complete(
        publish_video_async(
            settings,
            session,
            video_path,
            caption,
            browser_handle,
            **kwargs,
        )
    )
