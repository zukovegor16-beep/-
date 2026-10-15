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

from tiktok_publisher.browser_session import BrowserHandle, close_browser, open_browser
from tiktok_publisher.captions import pick_random_caption
from tiktok_publisher.config import AppSettings, OrchestratorSettings
from tiktok_publisher.dolphin_client import DolphinClient, ProfileSession
from tiktok_publisher.excel_registry import AccountRow, ExcelRegistry
from tiktok_publisher.publisher import publish_video_async
from tiktok_publisher.queue import move_to_failed, move_to_posted, next_video
from tiktok_publisher.report import write_run_report
from tiktok_publisher.run_plan import RunPlan, build_run_plan
from tiktok_publisher.speed_presets import apply_speed_preset
from tiktok_publisher.state import PublicationRecord, StateStore

logger = logging.getLogger(__name__)


@dataclass
class CurrentTask:
    account_no: str
    account_name: str
    file_path: str
    caption_preview: str
    phase: str


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

    def start(self) -> str:
        with self._lock:
            if self.running:
                raise RuntimeError("Оркестратор уже запущен")
            self._stop.clear()
            self.running = True
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
            accounts = self.excel.read_accounts()
            self._accounts_cache = accounts
            self._run_plan = build_run_plan(accounts, self.settings)
            self._progress = RunProgress(
                total_slots=self._run_plan.total_slots,
                started_at=run_started,
            )
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
                    self._process_account(acc, run_id, records)
            else:
                with ThreadPoolExecutor(max_workers=k) as pool:
                    futures = [
                        pool.submit(self._process_account, acc, run_id, records)
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
            with self._lock:
                self.running = False
                self.current_task = None
                self._active_tasks.clear()

    def _process_account(
        self,
        acc: AccountRow,
        run_id: str,
        records: list[PublicationRecord],
    ) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        attempts = 0
        max_attempts = acc.videos_per_run
        delimiter = self.settings.excel.caption_delimiter
        profile_session: ProfileSession | None = None
        browser_handle: BrowserHandle | None = None

        try:
            if not self.settings.dry_run:
                self._set_task(
                    acc,
                    "",
                    "",
                    "dolphin_start",
                )
                profile_session = self.dolphin.start_profile(acc.dolphin_profile_id)
                browser_handle = open_browser(profile_session, loop)

            while attempts < max_attempts:
                if self._stop.is_set():
                    return

                video = next_video(acc.video_folder, self.settings)
                if video is None:
                    rec = self._make_record(
                        run_id, acc, "", "", "error", "no videos in folder"
                    )
                    self._append_record(records, rec)
                    self.excel.update_account_run_status(
                        acc.row_index, "error", "no videos"
                    )
                    return

                try:
                    caption = pick_random_caption(acc.caption_variants(delimiter))
                except ValueError as e:
                    rec = self._make_record(run_id, acc, str(video), "", "error", str(e))
                    self._append_record(records, rec)
                    self.excel.update_account_run_status(acc.row_index, "error", str(e))
                    if self._orch.count_errors_toward_limit:
                        attempts += 1
                    continue

                self._set_task(acc, str(video), caption[:120], "upload")

                started = _iso_now()
                ok, err = loop.run_until_complete(
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
                finished = _iso_now()
                status = "ok" if ok else "error"
                rec = self._make_record(
                    run_id, acc, str(video), caption, status, err, started, finished
                )
                self._append_record(records, rec)
                self._bump_progress(status)

                self.excel.append_log_row(
                    acc.account_no,
                    video.name,
                    caption,
                    status,
                    err,
                    started,
                    finished,
                )
                self.excel.update_account_run_status(acc.row_index, status, err or None)

                if ok and self.settings.orchestrator.on_success == "move_to_posted":
                    try:
                        move_to_posted(video)
                    except Exception as e:
                        logger.warning("move to posted failed: %s", e)
                elif not ok and self._orch.skip_failed_file:
                    try:
                        move_to_failed(video)
                    except Exception as e:
                        logger.warning("move to failed failed: %s", e)

                if ok or self._orch.count_errors_toward_limit:
                    attempts += 1

                self._sleep_between_posts(status == "error")

        except Exception as e:
            logger.exception("account %s failed", acc.account_no)
            rec = self._make_record(run_id, acc, "", "", "error", str(e))
            self._append_record(records, rec)
        finally:
            close_browser(browser_handle)
            if profile_session and not self.settings.dry_run:
                self.dolphin.stop_profile(acc.dolphin_profile_id)
            loop.close()
            self._clear_task(acc.account_no)

    def _set_task(
        self,
        acc: AccountRow,
        file_path: str,
        caption_preview: str,
        phase: str,
    ) -> None:
        t = CurrentTask(
            account_no=acc.account_no,
            account_name=acc.account_name,
            file_path=file_path,
            caption_preview=caption_preview,
            phase=phase,
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

    def _bump_progress(self, status: str) -> None:
        with self._lock:
            self._progress.done_slots += 1
            if status == "ok":
                self._progress.ok_count += 1
            else:
                self._progress.error_count += 1

    def _sleep_between_posts(self, after_error: bool) -> None:
        if self._stop.is_set():
            return
        if after_error:
            time.sleep(self._orch.delay_after_error_sec)
            return
        dr = self._orch.delay_between_posts_sec
        time.sleep(random.uniform(dr.min, dr.max))

    def _make_record(
        self,
        run_id: str,
        acc: AccountRow,
        file_path: str,
        caption: str,
        status: str,
        error: str,
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
            status=status,
            error_message=error,
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
        }


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
