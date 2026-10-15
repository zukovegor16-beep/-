from __future__ import annotations

import asyncio
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread

from tiktok_publisher.asset_fingerprint import file_fingerprint
from tiktok_publisher.browser_errors import is_browser_disconnect
from tiktok_publisher.browser_session import BrowserHandle, close_browser, open_browser
from tiktok_publisher.captions import pick_random_caption
from tiktok_publisher.config import AppSettings, OrchestratorSettings
from tiktok_publisher.dolphin_client import DolphinClient, ProfileSession
from tiktok_publisher.dolphin_registry import set_client_factory
from tiktok_publisher.excel_pending import ExcelPendingStore
from tiktok_publisher.excel_registry import AccountRow, ExcelRegistry
from tiktok_publisher.posting_window import in_posting_window, seconds_until_window_opens
from tiktok_publisher.outcomes import (
    Outcome,
    OutcomeCode,
    is_success_code,
    summarize_account_outcomes,
)
from tiktok_publisher.publisher import publish_video_async
from tiktok_publisher.queue import move_to_failed, move_to_posted, next_video
from tiktok_publisher.report import write_run_report
from tiktok_publisher.run_plan import RunPlan, build_run_plan
from tiktok_publisher.speed_presets import apply_speed_preset
from tiktok_publisher.state import PublicationRecord, StateStore
from tiktok_publisher.upload_lock import UploadLock
from tiktok_publisher.warmup import run_warmup

logger = logging.getLogger(__name__)


@dataclass
class CurrentTask:
    account_no: str
    account_name: str
    file_path: str
    caption_preview: str
    phase: str
    outcome_label: str = ""


@dataclass
class RunProgress:
    total_slots: int = 0
    done_slots: int = 0
    ok_count: int = 0
    error_count: int = 0
    started_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        elapsed = max(time.time() - self.started_at, 1.0)
        rate = self.done_slots / elapsed * 3600
        remaining = max(self.total_slots - self.done_slots, 0)
        eta_sec = (remaining / max(self.done_slots, 1)) * elapsed if self.done_slots else None
        return {
            "total_slots": self.total_slots,
            "done_slots": self.done_slots,
            "ok_count": self.ok_count,
            "error_count": self.error_count,
            "posts_per_hour": round(rate, 2),
            "eta_sec": round(eta_sec, 0) if eta_sec is not None else None,
        }


class Orchestrator:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.store = StateStore(settings.db_path)
        self.excel = ExcelRegistry(settings)
        self.dolphin = DolphinClient(settings)
        set_client_factory(lambda: self.dolphin)
        self._excel_pending = ExcelPendingStore(settings.data_dir_path / "pending_excel.jsonl")
        self._stop = Event()
        self._thread: Thread | None = None
        self._lock = Lock()
        self._records_lock = Lock()
        self.running = False
        self.current_run_id: str | None = None
        self.current_task: CurrentTask | None = None
        self._active_tasks: dict[str, CurrentTask] = {}
        self.last_report_path: Path | None = None
        self._accounts_cache: list[AccountRow] = []
        self._run_plan: RunPlan | None = None
        self._progress = RunProgress()
        self._orch: OrchestratorSettings = apply_speed_preset(settings)
        self._excel_degraded = False
        self._consecutive_errors: dict[str, int] = {}
        self.only_errors_from_run_id: str | None = None
        self._retry_paths_by_account: dict[str, list[Path]] = {}
        self._pubs_since_flush = 0

    def start(self) -> str:
        with self._lock:
            if self.running:
                raise RuntimeError("Оркестратор уже запущен")
            self._stop.clear()
            self.running = True
            self._excel_degraded = False
            self._consecutive_errors.clear()
            self._pubs_since_flush = 0
            self._orch = apply_speed_preset(self.settings)
            self.current_run_id = self.store.start_run()
            self._thread = Thread(target=self._run, daemon=True)
            self._thread.start()
            return self.current_run_id

    def stop(self) -> None:
        self._stop.set()

    def wait(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout=timeout)

    @property
    def is_running(self) -> bool:
        return self.running

    def _run(self) -> None:
        run_id = self.current_run_id or ""
        reason = "completed"
        records: list[PublicationRecord] = []
        run_started = time.time()
        try:
            if self._orch.posting_window and self._orch.posting_window_mode == "wait":
                while not in_posting_window(self._orch) and not self._stop.is_set():
                    wait_sec = seconds_until_window_opens(self._orch)
                    logger.info("Ожидание posting_window %.0f сек", wait_sec)
                    time.sleep(min(max(wait_sec, 1.0), 300))

            accounts = self.excel.read_accounts()
            self._accounts_cache = accounts
            self._run_plan = build_run_plan(accounts, self.settings)
            self._progress = RunProgress(
                total_slots=self._run_plan.total_slots,
                started_at=run_started,
            )

            if self.only_errors_from_run_id:
                self._retry_paths_by_account = self._build_retry_map(
                    self.only_errors_from_run_id
                )
                if not self._retry_paths_by_account:
                    reason = "no_errors_to_retry"
                    return

            if not accounts:
                logger.warning("Нет активных аккаунтов в Excel")
                reason = "no_accounts"
                return

            k = max(1, self._orch.max_concurrent_profiles)
            if k == 1:
                for acc in accounts:
                    if self._stop.is_set():
                        reason = "user_stop"
                        break
                    if not in_posting_window(self._orch):
                        reason = "window_end"
                        break
                    self._process_account(acc, run_id, records, run_started)
            else:
                with ThreadPoolExecutor(max_workers=k) as pool:
                    futures = [
                        pool.submit(self._process_account, acc, run_id, records, run_started)
                        for acc in accounts
                    ]
                    for fut in as_completed(futures):
                        if self._stop.is_set():
                            reason = "user_stop"
                        fut.result()
        except Exception as e:
            logger.exception("run failed")
            reason = f"error: {e}"
        finally:
            self.store.finish_run(run_id, reason)
            if records:
                self._write_report(run_id, records, run_started)
            with self._lock:
                self.running = False
                self.current_task = None
                self._active_tasks.clear()
                self.only_errors_from_run_id = None
                self._retry_paths_by_account.clear()

    def _build_retry_map(self, run_id: str) -> dict[str, list[Path]]:
        out: dict[str, list[Path]] = {}
        for rec in self.store.error_publications_for_run(run_id):
            p = Path(rec.file_path)
            if p.is_file():
                out.setdefault(rec.account_no, []).append(p)
        return out

    def _write_report(
        self,
        run_id: str,
        records: list[PublicationRecord],
        run_started: float,
    ) -> None:
        out = self.settings.reports_dir / f"report_{run_id}.xlsx"
        try:
            duration = time.time() - run_started
            self.last_report_path = write_run_report(
                out,
                run_id,
                records,
                self._accounts_cache,
                self.settings,
                run_duration_sec=duration,
            )
        except Exception:
            logger.exception("report write failed")

    def _maybe_flush_report(
        self,
        run_id: str,
        records: list[PublicationRecord],
        run_started: float,
    ) -> None:
        n = self._orch.report_flush_every_n
        if n <= 0:
            return
        self._pubs_since_flush += 1
        if self._pubs_since_flush >= n:
            self._write_report(run_id, records, run_started)
            self._pubs_since_flush = 0

    def _process_account(
        self,
        acc: AccountRow,
        run_id: str,
        records: list[PublicationRecord],
        run_started: float,
    ) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        attempts = 0
        max_attempts = acc.videos_per_run
        retry_paths = self._retry_paths_by_account.get(acc.account_no)
        if retry_paths is not None:
            max_attempts = len(retry_paths)
        delimiter = self.settings.excel.caption_delimiter
        profile_session: ProfileSession | None = None
        browser_handle: BrowserHandle | None = None
        session_restarted = False
        account_codes: list[OutcomeCode] = []
        ok_count = 0
        stopped_by_user = False
        stopped_by_circuit = False

        try:
            if not self.settings.dry_run:
                self._set_task(acc, "", "", "dolphin_start")
                try:
                    profile_session = self.dolphin.start_profile(acc.dolphin_profile_id)
                    browser_handle = open_browser(profile_session, loop)
                except Exception as e:
                    outcome = Outcome.from_code(
                        OutcomeCode.dolphin_error, f"dolphin start: {e}"
                    )
                    account_codes.append(outcome.code)
                    rec = self._make_record_from_outcome(
                        run_id, acc, "", "", outcome
                    )
                    self._append_record(records, rec)
                    return

            if browser_handle and self._needs_warmup_before():
                warmup_outcome = self._run_warmup_phase(loop, browser_handle, acc)
                if warmup_outcome:
                    account_codes.append(warmup_outcome.code)
                    if self._warmup_failed_blocking(warmup_outcome):
                        self._excel_status(
                            acc.row_index,
                            warmup_outcome.label_ru,
                            warmup_outcome.detail or None,
                        )
                        return

            while attempts < max_attempts:
                if self._stop.is_set():
                    stopped_by_user = True
                    return
                if not in_posting_window(self._orch):
                    return
                if self._circuit_open(acc.account_no):
                    logger.warning("circuit breaker: account %s", acc.account_no)
                    stopped_by_circuit = True
                    return

                video = self._next_video_for_account(acc, retry_paths, attempts)
                if video is None:
                    outcome = Outcome.from_code(
                        OutcomeCode.no_videos, "no videos in folder"
                    )
                    account_codes.append(outcome.code)
                    rec = self._make_record_from_outcome(run_id, acc, "", "", outcome)
                    self._finalize_publication(
                        acc, run_id, records, rec, None, run_started=run_started
                    )
                    return

                fp = file_fingerprint(video)
                if self.store.has_successful_asset(acc.account_no, fp):
                    started = _iso_now()
                    outcome = Outcome.from_code(
                        OutcomeCode.duplicate_skipped, "already published (ledger)"
                    )
                    account_codes.append(outcome.code)
                    rec = self._make_record_from_outcome(
                        run_id,
                        acc,
                        str(video),
                        "",
                        outcome,
                        started,
                        started,
                    )
                    self._finalize_publication(
                        acc, run_id, records, rec, video, run_started=run_started
                    )
                    try:
                        move_to_posted(video)
                    except Exception as e:
                        logger.warning("move duplicate to posted: %s", e)
                    if self._orch.skip_duplicate_counts_toward_limit:
                        attempts += 1
                    elif next_video(acc.video_folder, self.settings) is None:
                        attempts += 1
                    continue

                if video.stat().st_size < self._orch.min_video_bytes:
                    outcome = Outcome.from_code(
                        OutcomeCode.file_invalid, "file too small"
                    )
                    account_codes.append(outcome.code)
                    rec = self._make_record_from_outcome(
                        run_id, acc, str(video), "", outcome
                    )
                    self._finalize_publication(
                        acc, run_id, records, rec, video, run_started=run_started
                    )
                    if self._orch.count_errors_toward_limit:
                        attempts += 1
                    continue

                try:
                    caption = pick_random_caption(acc.caption_variants(delimiter))
                except ValueError as e:
                    outcome = Outcome.from_code(OutcomeCode.no_caption, str(e))
                    account_codes.append(outcome.code)
                    rec = self._make_record_from_outcome(
                        run_id, acc, str(video), "", outcome
                    )
                    self._finalize_publication(
                        acc, run_id, records, rec, video, run_started=run_started
                    )
                    if self._orch.count_errors_toward_limit:
                        attempts += 1
                    continue

                if len(caption) > self._orch.max_caption_length:
                    outcome = Outcome.from_code(
                        OutcomeCode.file_invalid, "caption too long"
                    )
                    account_codes.append(outcome.code)
                    rec = self._make_record_from_outcome(
                        run_id, acc, str(video), caption, outcome
                    )
                    self._finalize_publication(
                        acc, run_id, records, rec, video, run_started=run_started
                    )
                    if self._orch.count_errors_toward_limit:
                        attempts += 1
                    continue

                self._set_task(acc, str(video), caption[:120], "upload")
                started = _iso_now()

                pub_result = None
                upload_lock = UploadLock(video)
                try:
                    if not upload_lock.acquire():
                        pub_result = None
                        outcome = Outcome.from_code(
                            OutcomeCode.upload_locked, "upload in progress (lock)"
                        )
                    else:
                        pub_result = loop.run_until_complete(
                            publish_video_async(
                                self.settings,
                                profile_session,
                                video,
                                caption,
                                browser_handle=browser_handle,
                                run_id=run_id,
                                account_no=acc.account_no,
                            )
                        )
                        outcome = pub_result.to_outcome(
                            dry_run=self.settings.dry_run
                        )
                finally:
                    upload_lock.release()

                if (
                    pub_result is not None
                    and not pub_result.ok
                    and browser_handle
                    and not session_restarted
                    and is_browser_disconnect(pub_result.message)
                ):
                    session_restarted = True
                    close_browser(browser_handle)
                    if profile_session:
                        self.dolphin.stop_profile(acc.dolphin_profile_id)
                    profile_session = self.dolphin.start_profile(acc.dolphin_profile_id)
                    browser_handle = open_browser(profile_session, loop)
                    pub_result = loop.run_until_complete(
                        publish_video_async(
                            self.settings,
                            profile_session,
                            video,
                            caption,
                            browser_handle=browser_handle,
                            run_id=run_id,
                            account_no=acc.account_no,
                            retry=False,
                        )
                    )
                    outcome = pub_result.to_outcome(dry_run=self.settings.dry_run)

                finished = _iso_now()
                account_codes.append(outcome.code)
                if is_success_code(outcome.code):
                    ok_count += 1
                rec = self._make_record_from_outcome(
                    run_id, acc, str(video), caption, outcome, started, finished
                )

                if is_success_code(outcome.code):
                    self.store.record_published_asset(
                        acc.account_no,
                        fp,
                        video.name,
                        str(video),
                        "ok",
                        run_id,
                        finished,
                    )
                    self._consecutive_errors[acc.account_no] = 0
                else:
                    self._bump_consecutive_errors(acc.account_no)

                self._set_task(
                    acc, str(video), caption[:120], "upload", outcome.label_ru
                )
                self._finalize_publication(
                    acc,
                    run_id,
                    records,
                    rec,
                    video,
                    outcome=outcome,
                    run_started=run_started,
                )

                if is_success_code(outcome.code) or self._orch.count_errors_toward_limit:
                    attempts += 1

                if browser_handle and not self.settings.dry_run:
                    healthy = loop.run_until_complete(browser_handle.is_healthy())
                    if not healthy and not session_restarted:
                        logger.warning("browser unhealthy after post, will restart next error")

                self._sleep_between_posts(not is_success_code(outcome.code))

            if browser_handle and self._needs_warmup_after():
                warmup_outcome = self._run_warmup_phase(loop, browser_handle, acc)
                if warmup_outcome:
                    account_codes.append(warmup_outcome.code)

        except Exception as e:
            logger.exception("account %s failed", acc.account_no)
            outcome = Outcome.from_code(OutcomeCode.unknown_error, str(e))
            account_codes.append(outcome.code)
            rec = self._make_record_from_outcome(run_id, acc, "", "", outcome)
            self._append_record(records, rec)
        finally:
            if stopped_by_user:
                account_codes.append(OutcomeCode.user_stop)
            if stopped_by_circuit:
                account_codes.append(OutcomeCode.circuit_breaker)
            if account_codes:
                summary = summarize_account_outcomes(
                    account_codes, ok_count, max_attempts
                )
                self._excel_status(
                    acc.row_index, summary.label_ru, summary.detail or None
                )
            close_browser(browser_handle)
            if profile_session and not self.settings.dry_run:
                self.dolphin.stop_profile(acc.dolphin_profile_id)
            loop.close()
            self._clear_task(acc.account_no)

    def _next_video_for_account(
        self,
        acc: AccountRow,
        retry_paths: list[Path] | None,
        index: int,
    ) -> Path | None:
        if retry_paths is not None:
            if index >= len(retry_paths):
                return None
            return retry_paths[index]
        return next_video(acc.video_folder, self.settings)

    def _finalize_publication(
        self,
        acc: AccountRow,
        run_id: str,
        records: list[PublicationRecord],
        rec: PublicationRecord,
        video: Path | None,
        *,
        outcome: Outcome | None = None,
        run_started: float,
    ) -> None:
        code = _parse_outcome_code(rec.status)
        if outcome is None:
            outcome = Outcome.from_code(code, rec.error_message)
        success = is_success_code(code)
        self._append_record(records, rec)
        self._bump_progress(code)
        self._excel_log(
            acc.account_no,
            Path(rec.file_path).name if rec.file_path else "",
            rec.caption_used,
            rec.status_label,
            rec.error_message,
            rec.started_at,
            rec.finished_at,
        )
        if video and success and self.settings.orchestrator.on_success == "move_to_posted":
            try:
                move_to_posted(video)
            except Exception as e:
                logger.warning("move to posted failed: %s", e)
                move_fail = Outcome.from_code(
                    OutcomeCode.published_move_failed, str(e)
                )
                self._excel_status(
                    acc.row_index, move_fail.label_ru, move_fail.detail
                )
        elif video and not success and self._orch.skip_failed_file:
            if code not in (
                OutcomeCode.no_login,
                OutcomeCode.captcha,
                OutcomeCode.rate_limit,
                OutcomeCode.upload_locked,
                OutcomeCode.duplicate_skipped,
            ):
                try:
                    move_to_failed(video)
                except Exception as e:
                    logger.warning("move to failed failed: %s", e)
        self._maybe_flush_report(run_id, records, run_started)

    def _excel_log(self, *args) -> None:
        ok = self.excel.append_log_row(*args)
        if not ok:
            self._excel_degraded = True
            self._excel_pending.append(
                "log_row",
                {
                    "account_no": args[0],
                    "filename": args[1],
                    "caption_used": args[2],
                    "status": args[3],
                    "error": args[4],
                    "started_at": args[5],
                    "finished_at": args[6],
                },
            )
            logger.error("Excel log write failed — queued to pending_excel.jsonl")

    def _excel_status(self, row_index: int, status: str, error: str | None) -> None:
        ok = self.excel.update_account_run_status(row_index, status, error)
        if not ok:
            self._excel_degraded = True
            self._excel_pending.append(
                "account_status",
                {"row_index": row_index, "status": status, "error": error or ""},
            )
            logger.error("Excel status write failed — queued to pending_excel.jsonl")

    def _circuit_open(self, account_no: str) -> bool:
        threshold = self._orch.circuit_breaker_consecutive_errors
        if threshold <= 0:
            return False
        return self._consecutive_errors.get(account_no, 0) >= threshold

    def _bump_consecutive_errors(self, account_no: str) -> None:
        self._consecutive_errors[account_no] = (
            self._consecutive_errors.get(account_no, 0) + 1
        )

    def _set_task(
        self,
        acc: AccountRow,
        file_path: str,
        caption_preview: str,
        phase: str,
        outcome_label: str = "",
    ) -> None:
        t = CurrentTask(
            account_no=acc.account_no,
            account_name=acc.account_name,
            file_path=file_path,
            caption_preview=caption_preview,
            phase=phase,
            outcome_label=outcome_label,
        )
        with self._lock:
            self._active_tasks[acc.account_no] = t
            self.current_task = t

    def _clear_task(self, account_no: str) -> None:
        with self._lock:
            self._active_tasks.pop(account_no, None)
            self.current_task = next(iter(self._active_tasks.values()), None)

    def _append_record(
        self, records: list[PublicationRecord], rec: PublicationRecord
    ) -> None:
        with self._records_lock:
            records.append(rec)
            self.store.add_publication(rec)

    def _bump_progress(self, code: OutcomeCode) -> None:
        with self._lock:
            self._progress.done_slots += 1
            if is_success_code(code):
                self._progress.ok_count += 1
            elif code != OutcomeCode.duplicate_skipped:
                self._progress.error_count += 1

    def _sleep_between_posts(self, after_error: bool) -> None:
        if self._stop.is_set():
            return
        if after_error:
            time.sleep(self._orch.delay_after_error_sec)
            return
        dr = self._orch.delay_between_posts_sec
        time.sleep(random.uniform(dr.min, dr.max))

    def _needs_warmup_before(self) -> bool:
        return self.settings.session.order in (
            "warmup_then_publish",
            "warmup_publish_warmup",
        )

    def _needs_warmup_after(self) -> bool:
        return self.settings.session.order in (
            "publish_then_warmup",
            "warmup_publish_warmup",
        )

    def _run_warmup_phase(
        self,
        loop: asyncio.AbstractEventLoop,
        browser_handle: BrowserHandle,
        acc: AccountRow,
    ) -> Outcome | None:
        if self.settings.session.order == "publish_only":
            return None
        self._set_task(acc, "", "", "warmup")
        result = run_warmup(self.settings, browser_handle, loop)
        return result.outcome

    def _warmup_failed_blocking(self, outcome: Outcome) -> bool:
        if not self.settings.session.warmup_fail_blocks_publish:
            return False
        return outcome.code not in (
            OutcomeCode.warmup_ok,
            OutcomeCode.dry_run,
        )

    def _make_record_from_outcome(
        self,
        run_id: str,
        acc: AccountRow,
        file_path: str,
        caption: str,
        outcome: Outcome,
        started: str | None = None,
        finished: str | None = None,
    ) -> PublicationRecord:
        now = _iso_now()
        return PublicationRecord(
            run_id=run_id,
            account_no=acc.account_no,
            account_name=acc.account_name,
            file_path=file_path,
            caption_used=caption,
            status=outcome.code.value,
            status_label=outcome.label_ru,
            error_message=outcome.detail,
            started_at=started or now,
            finished_at=finished or now,
        )

    def status_snapshot(self) -> dict:
        accounts_summary = []
        if self._run_plan and self.running:
            for snap in self._run_plan.snapshots:
                accounts_summary.append(
                    {
                        "account_no": snap.account_no,
                        "account_name": snap.account_name,
                        "video_folder": snap.video_folder,
                        "videos_per_run": snap.videos_per_run,
                        "queue_count": snap.queue_count,
                        "dolphin_profile_id": snap.dolphin_profile_id,
                    }
                )
        elif self._accounts_cache:
            for acc in self._accounts_cache:
                accounts_summary.append(
                    {
                        "account_no": acc.account_no,
                        "account_name": acc.account_name,
                        "video_folder": str(acc.video_folder),
                        "videos_per_run": acc.videos_per_run,
                        "queue_count": None,
                        "dolphin_profile_id": acc.dolphin_profile_id,
                    }
                )
        else:
            try:
                plan = build_run_plan(self.excel.read_accounts(), self.settings)
                for snap in plan.snapshots:
                    accounts_summary.append(snap.__dict__)
            except Exception as e:
                accounts_summary.append({"error": str(e)})

        with self._lock:
            tasks = [t.__dict__ for t in self._active_tasks.values()]
            task = self.current_task.__dict__ if self.current_task else None
            progress = self._progress.to_dict()

        return {
            "running": self.running,
            "run_id": self.current_run_id,
            "current_task": task,
            "active_tasks": tasks,
            "progress": progress,
            "accounts": accounts_summary,
            "last_report": str(self.last_report_path) if self.last_report_path else None,
            "dry_run": self.settings.dry_run,
            "speed_preset": self._orch.speed_preset,
            "max_concurrent_profiles": self._orch.max_concurrent_profiles,
            "excel_write_degraded": self._excel_degraded,
            "excel_pending_count": self._excel_pending.pending_count(),
        }


def _parse_outcome_code(status: str) -> OutcomeCode:
    legacy = {
        "ok": OutcomeCode.published,
        "error": OutcomeCode.not_published,
        "skipped_duplicate": OutcomeCode.duplicate_skipped,
    }
    if status in legacy:
        return legacy[status]
    try:
        return OutcomeCode(status)
    except ValueError:
        return OutcomeCode.unknown_error


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
