from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import yaml

from tiktok_publisher.browser_session import BrowserHandle
from tiktok_publisher.config import AppSettings
from tiktok_publisher.email_code import extract_verification_code
from tiktok_publisher.onboard_steps import click_xpath_retry, fill_xpath_retry, onboard_screenshot

logger = logging.getLogger(__name__)


def _load_webmail_sel(settings: AppSettings) -> dict:
    path = settings.selectors_webmail_file
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    provider = settings.onboard.email_provider
    if provider in raw and isinstance(raw[provider], dict):
        return {**raw, **raw[provider]}
    return raw


def _webmail_login_url(settings: AppSettings, sel: dict) -> str:
    if settings.onboard.email_webmail_url:
        return settings.onboard.email_webmail_url
    if settings.onboard.email_provider == "outlook":
        return sel.get("login_url", "https://outlook.live.com/mail/")
    return sel.get("login_url", "https://mail.google.com/")


async def login_webmail_async(
    settings: AppSettings,
    handle: BrowserHandle,
    email: str,
    email_password: str,
    *,
    row_index: int = 0,
) -> bool:
    sel = _load_webmail_sel(settings)
    nav_ms = int((sel.get("timeouts") or {}).get("navigation_ms", 60000))
    page = await handle.new_page()
    await page.goto(_webmail_login_url(settings, sel), timeout=nav_ms, wait_until="domcontentloaded")

    for key, val, next_key in (
        ("email_input", email, "email_next"),
        ("password_input", email_password, "password_next"),
    ):
        xp = sel.get(key)
        if not xp:
            logger.warning("webmail selector missing: %s", key)
            return False
        await fill_xpath_retry(page, xp, val)
        nx = sel.get(next_key)
        if nx:
            try:
                await click_xpath_retry(page, nx)
            except Exception as e:
                logger.debug("webmail next %s: %s", next_key, e)
        await asyncio.sleep(2)

    ready = sel.get("inbox_ready")
    if ready:
        try:
            await page.locator(f"xpath={ready}").wait_for(timeout=nav_ms)
        except Exception as e:
            logger.warning("webmail inbox not ready: %s", e)
            await onboard_screenshot(settings, page, "webmail_inbox_fail", row_index)
            return False
    return True


async def fetch_code_from_webmail_tab_async(
    settings: AppSettings,
    handle: BrowserHandle,
) -> str | None:
    """Scan open pages for TikTok verification code in visible text."""
    pattern = settings.onboard.email_code_regex
    pages = handle.browser.pages
    if asyncio.iscoroutine(pages):
        pages = await pages
    if not pages and handle.browser.contexts:
        ctx = handle.browser.contexts[0]
        pages = ctx.pages
    for page in pages or []:
        try:
            text = await page.content()
            code = extract_verification_code(text, pattern=pattern)
            if code:
                return code
        except Exception as e:
            logger.debug("webmail scan page: %s", e)
    return None
