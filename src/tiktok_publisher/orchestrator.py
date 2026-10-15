from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread
from tiktok_publisher.captions import pick_random_caption
from tiktok_publisher.config import AppSettings
from tiktok_publisher.dolphin_client import DolphinClient, ProfileSession
from tiktok_publisher.excel_registry import AccountRow, ExcelRegistry
from tiktok_publisher.publisher import publish_video
from tiktok_publisher.queue import move_to_posted, next_video
from tiktok_publisher.report import write_run_report
from tiktok_publisher.state import PublicationRecord, StateStore

logger = logging.getLogger(__name__)


@dataclass
class CurrentTask:
    account_no: str
    account_name: str
    file_path: str
    caption_preview: str
    phase: str


class Orchestrator:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.store = StateStore(settings.db_path)
        self.excel = ExcelRegistry(settings)
        self.dolphin = DolphinClient(settings)
        self._stop = Event()
        self._thread: Thread | None = None
        self._lock = Lock()
        self.running = False
        self.current_run_id: str | None = None
        self.current_task: CurrentTask | None = None
        self.last_report_path: Path | None = None
        self._accounts_cache: list[AccountRow] = []

    def start(self) -> str:
        with self._lock:
            if self.running:
                raise RuntimeError("Оркестратор уже запущен")
            self._stop.clear()
            self.running = True
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
        try:
            accounts = self.excel.read_accounts()
            self._accounts_cache = accounts
            if not accounts:
                logger.warning("Нет активных аккаунтов в Excel")
                reason = "no_accounts"
                return

            for acc in accounts:
                if self._stop.is_set():
                    reason = "user_stop"
                    break
                self._process_account(acc, run_id, records)
        except Exception as e:
            logger.exception("run failed")
            reason = f"error: {e}"
        finally:
            self.store.finish_run(run_id, reason)
            if records:
                out = self.settings.reports_dir / f"report_{run_id}.xlsx"
                try:
                    self.last_report_path = write_run_report(
                        out, run_id, records, self._accounts_cache, self.settings
                    )
                except Exception:
                    logger.exception("report write failed")
            with self._lock:
                self.running = False
                self.current_task = None

    def _process_account(
        self,
        acc: AccountRow,
        run_id: str,
        records: list[PublicationRecord],
    ) -> None:
        attempts = 0
        max_attempts = acc.videos_per_run
        delimiter = self.settings.excel.caption_delimiter

        while attempts < max_attempts:
            if self._stop.is_set():
                return

            video = next_video(acc.video_folder, self.settings)
            if video is None:
                rec = self._make_record(
                    run_id,
                    acc,
                    "",
                    "",
                    "error",
                    "no videos in folder",
                )
                records.append(rec)
                self.store.add_publication(rec)
                self.excel.update_account_run_status(acc.row_index, "error", "no videos")
                logger.warning("account %s: no videos", acc.account_no)
                return

            try:
                variants = acc.caption_variants(delimiter)
                caption = pick_random_caption(variants)
            except ValueError as e:
                rec = self._make_record(
                    run_id, acc, str(video), "", "error", str(e)
                )
                records.append(rec)
                self.store.add_publication(rec)
                self.excel.update_account_run_status(acc.row_index, "error", str(e))
                attempts += 1
                continue

            self.current_task = CurrentTask(
                account_no=acc.account_no,
                account_name=acc.account_name,
                file_path=str(video),
                caption_preview=caption[:120],
                phase="publishing",
            )

            started = _iso_now()
            session: ProfileSession | None = None
            ok = False
            err = ""
            try:
                if not self.settings.dry_run:
                    self.current_task.phase = "dolphin_start"
                    session = self.dolphin.start_profile(acc.dolphin_profile_id)
                self.current_task.phase = "upload"
                ok, err = publish_video(self.settings, session, video, caption)
            except Exception as e:
                ok, err = False, str(e)
            finally:
                if session and not self.settings.dry_run:
                    self.dolphin.stop_profile(acc.dolphin_profile_id)

            finished = _iso_now()
            status = "ok" if ok else "error"
            rec = self._make_record(
                run_id, acc, str(video), caption, status, err, started, finished
            )
            records.append(rec)
            self.store.add_publication(rec)

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

            attempts += 1
            self._sleep_between_posts(status == "error")

        self.current_task = None

    def _sleep_between_posts(self, after_error: bool) -> None:
        if self._stop.is_set():
            return
        if after_error:
            time.sleep(self.settings.orchestrator.delay_after_error_sec)
            return
        dr = self.settings.orchestrator.delay_between_posts_sec
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
        try:
            accounts = self.excel.read_accounts()
        except Exception as e:
            accounts = []
            accounts_summary.append({"error": str(e)})

        for acc in accounts:
            from tiktok_publisher.queue import list_pending_videos

            pending = len(list_pending_videos(acc.video_folder, self.settings))
            accounts_summary.append(
                {
                    "account_no": acc.account_no,
                    "account_name": acc.account_name,
                    "video_folder": str(acc.video_folder),
                    "videos_per_run": acc.videos_per_run,
                    "queue_count": pending,
                    "dolphin_profile_id": acc.dolphin_profile_id,
                }
            )

        task = None
        if self.current_task:
            t = self.current_task
            task = {
                "account_no": t.account_no,
                "account_name": t.account_name,
                "file_path": t.file_path,
                "caption_preview": t.caption_preview,
                "phase": t.phase,
            }

        return {
            "running": self.running,
            "run_id": self.current_run_id,
            "current_task": task,
            "accounts": accounts_summary,
            "last_report": str(self.last_report_path) if self.last_report_path else None,
            "dry_run": self.settings.dry_run,
        }


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
