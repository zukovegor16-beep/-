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
from tiktok_publisher.onboard_steps import (
    click_xpath_retry,
    fill_xpath_retry,
    onboard_screenshot,
    wait_xpath_visible,
)
from tiktok_publisher.onboard_trace import OnboardTrace
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
    row_index: int = 0


def _load_onboard_sel(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _set_phase(cb: PhaseCallback, name: str) -> None:
    if cb:
        cb(name)


def _needs_webmail_login(settings: AppSettings) -> bool:
    mode = settings.onboard.email_code_mode
    return mode in ("webmail", "browser_then_imap")


def _uses_imap_for_code(settings: AppSettings) -> bool:
    return settings.onboard.email_code_mode in ("imap", "browser_then_imap")


async def _pause_if_blocked(
    settings: AppSettings,
    page,
    pause_for_manual: asyncio.Event | None,
    trace: OnboardTrace | None,
    phase_rec,
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
            if trace and phase_rec:
                trace.finish_phase(phase_rec, ok=False, detail="manual wait timeout")
            return Outcome.from_code(OutcomeCode.captcha, "manual wait timeout")
        body = (await page.content())[:8000]
        blocked = _is_blocked_page(page.url, body)
    if blocked:
        from tiktok_publisher.outcomes import classify_publish_error

        if trace and phase_rec:
            trace.finish_phase(phase_rec, ok=False, detail=blocked)
        return Outcome.from_code(classify_publish_error(blocked), blocked)
    return None


async def _assert_logged_in(page, sel: dict, nav_ms: int) -> bool:
    ind = sel.get("logged_in_indicator")
    if not ind:
        return "/login" not in (page.url or "").lower()
    try:
        await page.locator(f"xpath={ind}").wait_for(timeout=min(nav_ms, 15000))
        return True
    except Exception:
        return "/login" not in (page.url or "").lower()


async def _tiktok_login(
    settings: AppSettings,
    page,
    sel: dict,
    ctx: OnboardContext,
    nav_ms: int,
) -> None:
    login_url = sel.get("login_url", "https://www.tiktok.com/login")
    await page.goto(login_url, timeout=nav_ms, wait_until="domcontentloaded")

    use_email = sel.get("login_use_email_tab")
    if use_email:
        try:
            await click_xpath_retry(page, use_email, attempts=2)
            await asyncio.sleep(1)
        except Exception as e:
            logger.debug("login_use_email_tab: %s", e)

    user_sel = sel.get("login_email") or sel.get("login_username")
    pass_sel = sel.get("login_password")
    submit_sel = sel.get("login_submit")
    login_id = ctx.email.strip() or ctx.login
    if not user_sel or not pass_sel:
        raise RuntimeError("login selectors missing in selectors_onboard.yaml")
    await fill_xpath_retry(page, user_sel, login_id)
    await fill_xpath_retry(page, pass_sel, ctx.password_current)
    if submit_sel:
        await click_xpath_retry(page, submit_sel)
    await asyncio.sleep(3)
    if not await _assert_logged_in(page, sel, nav_ms):
        shot = await onboard_screenshot(settings, page, "login_fail", ctx.row_index)
        raise RuntimeError(f"login not confirmed url={page.url} shot={shot}")


async def _change_password(
    page,
    sel: dict,
    ctx: OnboardContext,
    nav_ms: int,
) -> bool:
    """Returns True if verify code step is expected."""
    if not ctx.password_new or ctx.password_new == ctx.password_current:
        return False
    pwd_url = sel.get("password_settings_url")
    if pwd_url:
        await page.goto(pwd_url, timeout=nav_ms, wait_until="domcontentloaded")
    for key, val in (
        ("password_current", ctx.password_current),
        ("password_new", ctx.password_new),
        ("password_confirm", ctx.password_new),
    ):
        xp = sel.get(key)
        if not xp:
            raise RuntimeError(f"password selector missing: {key}")
        await fill_xpath_retry(page, xp, val)
    save = sel.get("password_save")
    if not save:
        raise RuntimeError("password_save selector missing")
    await click_xpath_retry(page, save)
    await asyncio.sleep(2)
    verify_xp = sel.get("password_verify_code") or sel.get("login_otp_code")
    return bool(verify_xp)


async def _wait_for_verify_prompt(page, sel: dict, timeout_sec: int) -> bool:
    xp = sel.get("password_verify_code") or sel.get("login_otp_code")
    if not xp:
        return False
    return await wait_xpath_visible(page, xp, float(timeout_sec))


async def _enter_verify_code(page, sel: dict, code: str) -> None:
    xp = sel.get("password_verify_code") or sel.get("login_otp_code")
    if not xp:
        raise RuntimeError("verify code selector missing")
    await fill_xpath_retry(page, xp, code)
    submit = sel.get("password_verify_submit") or sel.get("login_otp_submit")
    if submit:
        await click_xpath_retry(page, submit)
    await asyncio.sleep(2)


async def _verify_password_changed(page, sel: dict, timeout_sec: int = 15) -> bool:
    ok_xp = sel.get("password_change_success")
    err_xp = sel.get("password_change_error")
    if err_xp:
        try:
            if await page.locator(f"xpath={err_xp}").count() > 0:
                return False
        except Exception:
            pass
    if ok_xp:
        return await wait_xpath_visible(page, ok_xp, timeout_sec)
    verify_xp = sel.get("password_verify_code") or sel.get("login_otp_code")
    if verify_xp:
        return not await wait_xpath_visible(page, verify_xp, 5)
    return True


async def _fetch_verification_code(
    settings: AppSettings,
    handle: BrowserHandle,
    ctx: OnboardContext,
    pause_for_manual: asyncio.Event | None,
    loop: asyncio.AbstractEventLoop,
    since_unix: float,
) -> tuple[str | None, str | None]:
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
                return None, None
        return "__manual__", None

    if _uses_imap_for_code(settings):
        result = await loop.run_in_executor(
            None,
            lambda: wait_for_verification_code_imap(
                settings,
                ctx.email,
                ctx.email_password,
                since_unix=since_unix,
                mark_read=True,
            ),
        )
        if result:
            return result.code, result.uid
        return None, None

    deadline = time.time() + settings.onboard.email_code_timeout_sec
    while time.time() < deadline:
        code = await fetch_code_from_webmail_tab_async(settings, handle)
        if code:
            return code, None
        await asyncio.sleep(6)
    return None, None


async def _upload_avatar(
    settings: AppSettings,
    page,
    sel: dict,
    avatar: Path,
    nav_ms: int,
    row_index: int,
) -> None:
    profile_url = sel.get("profile_edit_url")
    if profile_url:
        await page.goto(profile_url, timeout=nav_ms, wait_until="domcontentloaded")
    av = sel.get("avatar_file_input", "//input[@type='file']")
    await page.locator(f"xpath={av}").set_input_files(str(avatar))
    await asyncio.sleep(2)
    save = sel.get("avatar_save")
    if save:
        try:
            await click_xpath_retry(page, save)
            await asyncio.sleep(2)
        except Exception as e:
            shot = await onboard_screenshot(settings, page, "avatar_save_fail", row_index)
            raise RuntimeError(f"avatar save click failed: {e} shot={shot}") from e
    ok_xp = sel.get("avatar_success")
    if ok_xp and not await wait_xpath_visible(page, ok_xp, 20):
        shot = await onboard_screenshot(settings, page, "avatar_verify_fail", row_index)
        raise RuntimeError(f"avatar success not detected shot={shot}")


async def run_onboarding_steps_async(
    settings: AppSettings,
    handle: BrowserHandle | None,
    ctx: OnboardContext,
    *,
    pause_for_manual: asyncio.Event | None,
    on_phase: PhaseCallback = None,
    loop: asyncio.AbstractEventLoop | None = None,
) -> Outcome:
    trace = OnboardTrace(row_index=ctx.row_index, login=ctx.login)
    try:
        if settings.dry_run or handle is None:
            for phase in (
                "webmail",
                "tiktok_login",
                "password",
                "email_code",
                "avatar",
            ):
                _set_phase(on_phase, phase)
                pr = trace.start_phase(phase)
                trace.finish_phase(pr, ok=True, detail="dry-run")
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

        if _needs_webmail_login(settings):
            _set_phase(on_phase, "webmail")
            pr = trace.start_phase("webmail")
            ok = await login_webmail_async(
                settings, handle, ctx.email, ctx.email_password
            )
            if not ok:
                shot = await onboard_screenshot(settings, page, "webmail_fail", ctx.row_index)
                trace.finish_phase(pr, ok=False, detail="webmail login", screenshot=str(shot) if shot else None)
                return Outcome.from_code(
                    OutcomeCode.onboard_email_failed, "webmail login failed"
                )
            trace.finish_phase(pr, ok=True)

        _set_phase(on_phase, "tiktok_login")
        pr = trace.start_phase("tiktok_login")
        try:
            await _tiktok_login(settings, page, sel, ctx, nav_ms)
        except Exception as e:
            shot = await onboard_screenshot(settings, page, "tiktok_login_fail", ctx.row_index)
            trace.finish_phase(pr, ok=False, detail=str(e), screenshot=str(shot) if shot else None)
            return Outcome.from_code(OutcomeCode.no_login, str(e))
        blocked = await _pause_if_blocked(settings, page, pause_for_manual, trace, pr)
        if blocked:
            return blocked
        trace.finish_phase(pr, ok=True)

        _set_phase(on_phase, "password")
        pr = trace.start_phase("password")
        expect_verify = False
        since_unix = time.time()
        try:
            expect_verify = await _change_password(page, sel, ctx, nav_ms)
        except Exception as e:
            shot = await onboard_screenshot(settings, page, "password_fail", ctx.row_index)
            trace.finish_phase(pr, ok=False, detail=str(e), screenshot=str(shot) if shot else None)
            return Outcome.from_code(OutcomeCode.onboard_password_not_changed, str(e))
        trace.finish_phase(pr, ok=True, detail="saved")

        if expect_verify:
            if not await _wait_for_verify_prompt(
                page, sel, settings.onboard.email_code_timeout_sec
            ):
                shot = await onboard_screenshot(settings, page, "verify_prompt_timeout", ctx.row_index)
                pr_code = trace.start_phase("email_code")
                trace.finish_phase(pr_code, ok=False, detail="no verify field", screenshot=str(shot) if shot else None)
                return Outcome.from_code(
                    OutcomeCode.onboard_verify_code_timeout,
                    f"verify field not shown shot={shot}",
                )

            _set_phase(on_phase, "email_code")
            pr = trace.start_phase("email_code")
            if loop is None:
                loop = asyncio.get_event_loop()
            code, imap_uid = await _fetch_verification_code(
                settings, handle, ctx, pause_for_manual, loop, since_unix
            )
            if not code:
                shot = await onboard_screenshot(settings, page, "email_code_timeout", ctx.row_index)
                trace.finish_phase(pr, ok=False, detail="no code", screenshot=str(shot) if shot else None)
                return Outcome.from_code(
                    OutcomeCode.onboard_verify_code_timeout,
                    "verification code not received",
                )

            if code != "__manual__":
                try:
                    await _enter_verify_code(page, sel, code)
                except Exception as e:
                    shot = await onboard_screenshot(settings, page, "verify_enter_fail", ctx.row_index)
                    trace.finish_phase(pr, ok=False, detail=str(e), screenshot=str(shot) if shot else None)
                    return Outcome.from_code(
                        OutcomeCode.onboard_password_not_changed, str(e)
                    )
                if not await _verify_password_changed(page, sel):
                    shot = await onboard_screenshot(settings, page, "password_verify_fail", ctx.row_index)
                    trace.finish_phase(pr, ok=False, detail="verify failed", screenshot=str(shot) if shot else None)
                    return Outcome.from_code(
                        OutcomeCode.onboard_password_not_changed,
                        "password verify not confirmed",
                    )
            trace.finish_phase(pr, ok=True, imap_uid=imap_uid)

        _set_phase(on_phase, "avatar")
        pr = trace.start_phase("avatar")
        try:
            await _upload_avatar(settings, page, sel, avatar, nav_ms, ctx.row_index)
        except Exception as e:
            shot = await onboard_screenshot(settings, page, "avatar_fail", ctx.row_index)
            trace.finish_phase(pr, ok=False, detail=str(e), screenshot=str(shot) if shot else None)
            return Outcome.from_code(OutcomeCode.onboard_avatar_failed, str(e))
        trace.finish_phase(pr, ok=True)

        blocked = await _pause_if_blocked(settings, page, pause_for_manual, None, None)
        if blocked:
            return blocked

        return Outcome.from_code(OutcomeCode.onboard_ready, "onboard completed")
    finally:
        trace.persist(settings)


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
