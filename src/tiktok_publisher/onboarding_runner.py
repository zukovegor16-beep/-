from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

from tiktok_publisher.avatar_library import resolve_avatar_path
from tiktok_publisher.browser_session import BrowserHandle
from tiktok_publisher.config import AppSettings
from tiktok_publisher.email_imap import wait_for_verification_code_imap
from tiktok_publisher.email_webmail import (
    fetch_code_from_webmail_tab_async,
    login_webmail_async,
)
from tiktok_publisher.outcomes import Outcome, OutcomeCode
from tiktok_publisher.publisher import _is_blocked_page

logger = logging.getLogger(__name__)

PhaseCallback = Callable[[str], None] | None


@dataclass
class OnboardContext:
    login: str
    password_current: str
    password_new: str
    email: str
    email_password: str
    avatar_path: Path


def _load_onboard_sel(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _set_phase(cb: PhaseCallback, name: str) -> None:
    if cb:
        cb(name)


async def _pause_if_blocked(
    settings: AppSettings,
    page,
    pause_for_manual: asyncio.Event | None,
) -> Outcome | None:
    body = (await page.content())[:8000]
    blocked = _is_blocked_page(page.url, body)
    if not blocked:
        return None
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
    return None


async def _tiktok_login(page, sel: dict, ctx: OnboardContext, nav_ms: int) -> Outcome | None:
    login_url = sel.get("login_url", "https://www.tiktok.com/login")
    await page.goto(login_url, timeout=nav_ms, wait_until="domcontentloaded")

    use_email = sel.get("login_use_email_tab")
    if use_email:
        try:
            await page.locator(f"xpath={use_email}").click(timeout=10000)
            await asyncio.sleep(1)
        except Exception as e:
            logger.debug("login_use_email_tab: %s", e)

    user_sel = sel.get("login_username") or sel.get("login_email")
    pass_sel = sel.get("login_password")
    submit_sel = sel.get("login_submit")
    login_id = ctx.email.strip() or ctx.login
    if user_sel and pass_sel:
        await page.locator(f"xpath={user_sel}").fill(login_id, timeout=15000)
        await page.locator(f"xpath={pass_sel}").fill(ctx.password_current, timeout=15000)
        if submit_sel:
            await page.locator(f"xpath={submit_sel}").click(timeout=15000)
        await asyncio.sleep(3)
    return None


async def _change_password(page, sel: dict, ctx: OnboardContext, nav_ms: int) -> None:
    if not ctx.password_new or ctx.password_new == ctx.password_current:
        return
    pwd_url = sel.get("password_settings_url")
    if pwd_url:
        await page.goto(pwd_url, timeout=nav_ms, wait_until="domcontentloaded")
    for key, val in (
        ("password_current", ctx.password_current),
        ("password_new", ctx.password_new),
        ("password_confirm", ctx.password_new),
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
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning("password save: %s", e)


async def _enter_verify_code(page, sel: dict, code: str) -> bool:
    xp = sel.get("password_verify_code") or sel.get("login_otp_code")
    if not xp:
        return False
    try:
        loc = page.locator(f"xpath={xp}")
        if await loc.count() == 0:
            return False
        await loc.first.fill(code, timeout=10000)
        submit = sel.get("password_verify_submit") or sel.get("login_otp_submit")
        if submit:
            await page.locator(f"xpath={submit}").click(timeout=10000)
        await asyncio.sleep(2)
        return True
    except Exception as e:
        logger.warning("verify code entry: %s", e)
        return False


async def _wait_for_verify_prompt(page, sel: dict, timeout_sec: int) -> bool:
    xp = sel.get("password_verify_code") or sel.get("login_otp_code")
    if not xp:
        return True
    deadline = time.time() + min(timeout_sec, 60)
    while time.time() < deadline:
        try:
            if await page.locator(f"xpath={xp}").count() > 0:
                return True
        except Exception:
            pass
        await asyncio.sleep(1)
    return False


async def _fetch_verification_code(
    settings: AppSettings,
    handle: BrowserHandle,
    ctx: OnboardContext,
    pause_for_manual: asyncio.Event | None,
    loop: asyncio.AbstractEventLoop,
) -> str | None:
    mode = settings.onboard.email_code_mode
    if mode == "manual":
        if pause_for_manual:
            pause_for_manual.clear()
            try:
                await asyncio.wait_for(
                    pause_for_manual.wait(),
                    timeout=settings.onboard.manual_wait_sec,
                )
            except asyncio.TimeoutError:
                return None
        return "__manual__"

    if mode == "imap":
        return await loop.run_in_executor(
            None,
            lambda: wait_for_verification_code_imap(
                settings, ctx.email, ctx.email_password
            ),
        )

    # webmail: refresh open mail tabs
    deadline = time.time() + settings.onboard.email_code_timeout_sec
    while time.time() < deadline:
        code = await fetch_code_from_webmail_tab_async(settings, handle)
        if code:
            return code
        await asyncio.sleep(6)
    return None


async def _upload_avatar(page, sel: dict, avatar: Path, nav_ms: int) -> Outcome | None:
    profile_url = sel.get("profile_edit_url")
    if profile_url:
        await page.goto(profile_url, timeout=nav_ms, wait_until="domcontentloaded")
    av = sel.get("avatar_file_input", "//input[@type='file']")
    try:
        await page.locator(f"xpath={av}").set_input_files(str(avatar))
        await asyncio.sleep(2)
    except Exception as e:
        return Outcome.from_code(OutcomeCode.onboard_avatar_failed, str(e))
    return None


async def run_onboarding_steps_async(
    settings: AppSettings,
    handle: BrowserHandle | None,
    ctx: OnboardContext,
    *,
    pause_for_manual: asyncio.Event | None,
    on_phase: PhaseCallback = None,
    loop: asyncio.AbstractEventLoop | None = None,
) -> Outcome:
    if settings.dry_run or handle is None:
        for phase in (
            "webmail",
            "tiktok_login",
            "password",
            "email_code",
            "avatar",
        ):
            _set_phase(on_phase, phase)
            await asyncio.sleep(0.01)
        return Outcome.from_code(OutcomeCode.onboard_ready, "dry-run onboard")

    sel = _load_onboard_sel(settings.selectors_onboard_file)
    nav_ms = int((sel.get("timeouts") or {}).get("navigation_ms", 60000))
    page = await handle.get_page()

    avatar = resolve_avatar_path(
        settings, login=ctx.login, column_path=ctx.avatar_path
    )
    if avatar is None or not avatar.is_file():
        return Outcome.from_code(
            OutcomeCode.onboard_avatar_failed,
            "avatar not found in library or column",
        )

    if settings.onboard.email_code_mode == "webmail":
        _set_phase(on_phase, "webmail")
        ok = await login_webmail_async(
            settings, handle, ctx.email, ctx.email_password
        )
        if not ok:
            return Outcome.from_code(
                OutcomeCode.onboard_email_failed, "webmail login failed"
            )

    _set_phase(on_phase, "tiktok_login")
    err = await _tiktok_login(page, sel, ctx, nav_ms)
    if err:
        return err
    blocked = await _pause_if_blocked(settings, page, pause_for_manual)
    if blocked:
        return blocked

    _set_phase(on_phase, "password")
    await _change_password(page, sel, ctx, nav_ms)
    await _wait_for_verify_prompt(
        page, sel, settings.onboard.email_code_timeout_sec
    )

    _set_phase(on_phase, "email_code")
    if loop is None:
        loop = asyncio.get_event_loop()
    code = await _fetch_verification_code(
        settings, handle, ctx, pause_for_manual, loop
    )
    if not code:
        return Outcome.from_code(
            OutcomeCode.onboard_verify_code_timeout,
            "verification code not received",
        )

    if code != "__manual__":
        entered = await _enter_verify_code(page, sel, code)
        if not entered:
            return Outcome.from_code(
                OutcomeCode.onboard_password_not_changed,
                "verify code field not found",
            )

    _set_phase(on_phase, "avatar")
    av_err = await _upload_avatar(page, sel, avatar, nav_ms)
    if av_err:
        return av_err

    return Outcome.from_code(OutcomeCode.onboard_ready, "onboard completed")


def run_onboarding_steps(
    settings: AppSettings,
    handle: BrowserHandle | None,
    loop: asyncio.AbstractEventLoop,
    ctx: OnboardContext,
    **kwargs,
) -> Outcome:
    kwargs.setdefault("loop", loop)
    return loop.run_until_complete(
        run_onboarding_steps_async(settings, handle, ctx, **kwargs)
    )
