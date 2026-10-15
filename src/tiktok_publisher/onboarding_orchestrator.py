from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread

from tiktok_publisher.config import AppSettings
from tiktok_publisher.dolphin_profiles import create_profile_for_geo
from tiktok_publisher.excel_registry import ExcelRegistry, OnboardRow
from tiktok_publisher.geo_catalog import resolve_geo
from tiktok_publisher.onboard_plan import build_onboard_plan
from tiktok_publisher.onboarding_runner import OnboardContext, run_onboarding_steps_async
from tiktok_publisher.avatar_library import resolve_avatar_path
from tiktok_publisher.outcomes import Outcome, OutcomeCode
from tiktok_publisher.preflight import run_preflight_onboard
from tiktok_publisher.browser_errors import is_browser_disconnect
from tiktok_publisher.session_runner import profile_browser_session

logger = logging.getLogger(__name__)


@dataclass
class OnboardTask:
    row_index: int
    login: str
    geo: str
    phase: str
    outcome_label: str = ""


@dataclass
class OnboardProgress:
    total: int = 0
    done: int = 0
    ok_count: int = 0
    error_count: int = 0
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "done": self.done,
            "ok_count": self.ok_count,
            "error_count": self.error_count,
        }


class OnboardingOrchestrator:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.excel = ExcelRegistry(settings)
        self._stop = Event()
        self._thread: Thread | None = None
        self._lock = Lock()
        self.running = False
        self.current_task: OnboardTask | None = None
        self._progress = OnboardProgress()
        self._pause_event: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._rows_cache: list[OnboardRow] = []

    @property
    def is_running(self) -> bool:
        return self.running

    def start(self) -> None:
        with self._lock:
            if self.running:
                raise RuntimeError("Онбординг уже запущен")
            pf = run_preflight_onboard(self.settings)
            if not pf.ok:
                raise RuntimeError(
                    "Preflight onboard failed: "
                    + "; ".join(i.message for i in pf.issues if i.level == "error")
                )
            pending = self.excel.read_onboarding_pending()
            if not pending:
                raise RuntimeError("Нет строк онбординга для обработки")
            self._stop.clear()
            self.running = True
            self._thread = Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout=timeout)

    def continue_manual(self) -> bool:
        """Release pause after manual OTP/captcha (call from API thread)."""
        loop = self._loop
        ev = self._pause_event
        if loop is None or ev is None:
            return False

        def _set() -> None:
            ev.set()

        loop.call_soon_threadsafe(_set)
        return True

    def status_snapshot(self) -> dict:
        plan = build_onboard_plan(self._rows_cache, self.settings) if self._rows_cache else None
        return {
            "running": self.running,
            "dry_run": self.settings.dry_run,
            "current_task": self.current_task.__dict__ if self.current_task else None,
            "progress": self._progress.to_dict(),
            "plan": plan.to_dict() if plan else None,
        }

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            rows = self.excel.read_onboarding_pending()
            self._rows_cache = rows
            self._progress = OnboardProgress(total=len(rows))
            if not rows:
                logger.warning("Нет строк онбординга для обработки")
                return
            for row in rows:
                if self._stop.is_set():
                    break
                self._process_row(row, loop)
                self._progress.done += 1
        finally:
            loop.close()
            self._loop = None
            self._pause_event = None
            with self._lock:
                self.running = False
                self.current_task = None

    def _process_row(self, row: OnboardRow, loop: asyncio.AbstractEventLoop) -> None:
        self.current_task = OnboardTask(
            row_index=row.row_index,
            login=row.tiktok_login,
            geo=row.geo,
            phase="validate",
        )
        try:
            if not row.geo.strip():
                self._fail_row(row, OutcomeCode.onboard_data_error, "geo пустой")
                return
            try:
                resolve_geo(self.settings, row.geo)
            except KeyError as e:
                self._fail_row(row, OutcomeCode.onboard_data_error, str(e))
                return
            if not row.tiktok_login.strip():
                self._fail_row(row, OutcomeCode.onboard_data_error, "tiktok_login пустой")
                return
            if not row.tiktok_password_current.strip():
                self._fail_row(row, OutcomeCode.onboard_data_error, "нет текущего пароля")
                return

            password_new = self.settings.resolve_onboard_password_new(
                row.tiktok_password_new
            )
            if not self.settings.dry_run and not password_new:
                self._fail_row(
                    row,
                    OutcomeCode.onboard_data_error,
                    "нет tiktok_password_new и onboard.unified_password",
                )
                return

            ob = self.settings.onboard
            if not self.settings.dry_run and ob.email_code_mode != "manual":
                if not row.email.strip() or not row.email_password.strip():
                    self._fail_row(
                        row,
                        OutcomeCode.onboard_data_error,
                        "email/email_password обязательны для IMAP/webmail",
                    )
                    return

            if not self.settings.dry_run:
                av = resolve_avatar_path(
                    self.settings,
                    login=row.tiktok_login,
                    column_path=row.avatar_path,
                )
                if av is None or not av.is_file():
                    self._fail_row(
                        row,
                        OutcomeCode.onboard_avatar_failed,
                        "аватар не найден (колонка или avatar_library)",
                    )
                    return

            profile_id = row.dolphin_profile_id.strip()
            if not profile_id:
                self.current_task.phase = "create_profile"
                try:
                    profile_id = create_profile_for_geo(
                        self.settings,
                        name=f"tiktok-{row.tiktok_login}",
                        geo_key=row.geo,
                        proxy=row.proxy or None,
                        dry_run=self.settings.dry_run,
                    )
                    self.excel.update_onboard_row(
                        row.row_index,
                        dolphin_profile_id=profile_id,
                        onboard_status="профиль создан",
                    )
                except Exception as e:
                    self._fail_row(row, OutcomeCode.dolphin_error, str(e))
                    return

            pause_ev = asyncio.Event()
            pause_ev.set()
            self._pause_event = pause_ev

            self.current_task.phase = "browser"
            ctx = OnboardContext(
                login=row.tiktok_login,
                password_current=row.tiktok_password_current,
                password_new=password_new or row.tiktok_password_new,
                email=row.email,
                email_password=row.email_password,
                avatar_path=row.avatar_path,
                row_index=row.row_index,
            )

            def _phase(name: str) -> None:
                if self.current_task:
                    self.current_task.phase = name

            outcome = Outcome.from_code(OutcomeCode.unknown_error, "no attempt")
            for attempt in range(2):
                with profile_browser_session(self.settings, profile_id, loop) as bs:
                    self.current_task.phase = "onboard_steps"
                    outcome = loop.run_until_complete(
                        run_onboarding_steps_async(
                            self.settings,
                            bs.handle,
                            ctx,
                            pause_for_manual=pause_ev,
                            on_phase=_phase,
                            loop=loop,
                        )
                    )
                if outcome.code == OutcomeCode.onboard_ready:
                    break
                detail = outcome.detail or outcome.label_ru
                if attempt == 0 and is_browser_disconnect(detail):
                    logger.warning("onboard CDP disconnect, retry profile session")
                    continue
                break

            if outcome.code != OutcomeCode.onboard_ready:
                self._fail_row(row, outcome.code, outcome.detail or outcome.label_ru)
                return

            self.current_task.phase = "promote"
            try:
                self.excel.promote_onboard_to_accounts(row, profile_id)
            except Exception as e:
                self._fail_row(row, OutcomeCode.onboard_data_error, f"promote: {e}")
                return

            self.excel.update_onboard_row(
                row.row_index,
                onboard_status=Outcome.from_code(OutcomeCode.onboard_ready).label_ru,
                onboard_error="",
            )
            self._progress.ok_count += 1
            self.current_task.outcome_label = outcome.label_ru
        except Exception as e:
            logger.exception("onboard row %s failed", row.row_index)
            self._fail_row(row, OutcomeCode.unknown_error, str(e))

    def _fail_row(self, row: OnboardRow, code: OutcomeCode, detail: str) -> None:
        outcome = Outcome.from_code(code, detail)
        self._progress.error_count += 1
        self.excel.update_onboard_row(
            row.row_index,
            onboard_status=outcome.label_ru,
            onboard_error=detail,
        )
        if self.current_task:
            self.current_task.outcome_label = outcome.label_ru
