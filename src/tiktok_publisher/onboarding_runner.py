from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import yaml

from tiktok_publisher.browser_session import BrowserHandle
from tiktok_publisher.config import AppSettings
from tiktok_publisher.outcomes import Outcome, OutcomeCode
from tiktok_publisher.publisher import _is_blocked_page

logger = logging.getLogger(__name__)


def _load_onboard_sel(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


async def run_onboarding_steps_async(
    settings: AppSettings,
    handle: BrowserHandle | None,
    *,
    login: str,
    password_current: str,
    password_new: str,
    avatar_path: Path,
    pause_for_manual: asyncio.Event | None,
) -> Outcome:
    if settings.dry_run or handle is None:
        await asyncio.sleep(0.05)
        return Outcome.from_code(OutcomeCode.onboard_ready, "dry-run onboard")

    sel = _load_onboard_sel(settings.selectors_onboard_file)
    nav_ms = int((sel.get("timeouts") or {}).get("navigation_ms", 60000))
    page = await handle.get_page()

    login_url = sel.get("login_url", "https://www.tiktok.com/login")
    await page.goto(login_url, timeout=nav_ms, wait_until="domcontentloaded")

    user_sel = sel.get("login_username")
    pass_sel = sel.get("login_password")
    submit_sel = sel.get("login_submit")
    if user_sel and pass_sel:
        await page.locator(f"xpath={user_sel}").fill(login, timeout=15000)
        await page.locator(f"xpath={pass_sel}").fill(password_current, timeout=15000)
        if submit_sel:
            await page.locator(f"xpath={submit_sel}").click(timeout=15000)
        await asyncio.sleep(3)

    body = (await page.content())[:8000]
    blocked = _is_blocked_page(page.url, body)
    if blocked:
        if settings.onboard.pause_on_captcha and pause_for_manual:
            logger.warning("Onboard pause: %s", blocked)
            pause_for_manual.clear()
            try:
                await asyncio.wait_for(pause_for_manual.wait(), timeout=settings.onboard.manual_wait_sec)
            except asyncio.TimeoutError:
                return Outcome.from_code(OutcomeCode.captcha, "manual wait timeout")
            body = (await page.content())[:8000]
            blocked = _is_blocked_page(page.url, body)
        if blocked:
            from tiktok_publisher.outcomes import classify_publish_error

            return Outcome.from_code(classify_publish_error(blocked), blocked)

    if password_new and password_new != password_current:
        pwd_url = sel.get("password_settings_url")
        if pwd_url:
            await page.goto(pwd_url, timeout=nav_ms, wait_until="domcontentloaded")
            for key, val in (
                ("password_current", password_current),
                ("password_new", password_new),
                ("password_confirm", password_new),
            ):
                xp = sel.get(key)
                if xp:
                    try:
                        await page.locator(f"xpath={xp}").fill(val, timeout=10000)
                    except Exception as e:
                        logger.warning("password field %s: %s", key, e)
            save = sel.get("password_save")
            if save:
                try:
                    await page.locator(f"xpath={save}").click(timeout=10000)
                except Exception as e:
                    logger.warning("password save: %s", e)

    if avatar_path.is_file():
        profile_url = sel.get("profile_edit_url")
        if profile_url:
            await page.goto(profile_url, timeout=nav_ms, wait_until="domcontentloaded")
        av = sel.get("avatar_file_input", "//input[@type='file']")
        try:
            await page.locator(f"xpath={av}").set_input_files(str(avatar_path))
            await asyncio.sleep(2)
        except Exception as e:
            return Outcome.from_code(OutcomeCode.onboard_avatar_failed, str(e))

    return Outcome.from_code(OutcomeCode.onboard_ready, "onboard completed")


def run_onboarding_steps(
    settings: AppSettings,
    handle: BrowserHandle | None,
    loop: asyncio.AbstractEventLoop,
    **kwargs,
) -> Outcome:
    return loop.run_until_complete(
        run_onboarding_steps_async(settings, handle, **kwargs)
    )
