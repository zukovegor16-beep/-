from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from tiktok_publisher.config import AppSettings
from tiktok_publisher.dolphin_client import DolphinClient
from tiktok_publisher.excel_registry import ExcelRegistry
from tiktok_publisher.geo_catalog import load_geo_catalog
from tiktok_publisher.posting_window import in_posting_window
from tiktok_publisher.queue import list_pending_videos
from tiktok_publisher.run_plan import build_run_plan
from tiktok_publisher.speed_presets import apply_speed_preset


@dataclass
class PreflightIssue:
    level: str  # error | warn
    code: str
    message: str


@dataclass
class PreflightResult:
    ok: bool
    issues: list[PreflightIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "issues": [i.__dict__ for i in self.issues],
        }


def run_preflight(settings: AppSettings) -> PreflightResult:
    issues: list[PreflightIssue] = []
    orch = apply_speed_preset(settings)

    if not settings.excel_path.is_file():
        issues.append(PreflightIssue("error", "excel_missing", f"Excel не найден: {settings.excel_path}"))
        return PreflightResult(ok=False, issues=issues)

    try:
        accounts = ExcelRegistry(settings).read_accounts()
    except Exception as e:
        issues.append(PreflightIssue("error", "excel_read", str(e)))
        return PreflightResult(ok=False, issues=issues)

    if not accounts:
        issues.append(PreflightIssue("error", "no_accounts", "Нет активных аккаунтов"))

    seen_no: dict[str, str] = {}
    seen_profile: dict[str, str] = {}
    for acc in accounts:
        if acc.account_no in seen_no:
            issues.append(
                PreflightIssue(
                    "error",
                    "dup_account_no",
                    f"Дубликат account_no {acc.account_no!r} (строки {seen_no[acc.account_no]} и {acc.row_index})",
                )
            )
        seen_no[acc.account_no] = str(acc.row_index)
        if acc.dolphin_profile_id in seen_profile:
            issues.append(
                PreflightIssue(
                    "error",
                    "dup_profile",
                    f"Дубликат dolphin_profile_id {acc.dolphin_profile_id!r}",
                )
            )
        seen_profile[acc.dolphin_profile_id] = acc.account_no

        if not acc.video_folder.is_dir():
            issues.append(
                PreflightIssue(
                    "error",
                    "folder_missing",
                    f"account {acc.account_no}: папка не найдена {acc.video_folder}",
                )
            )
        else:
            for sub in ("posted", "failed"):
                try:
                    (acc.video_folder / sub).mkdir(exist_ok=True)
                except OSError as e:
                    issues.append(
                        PreflightIssue(
                            "warn",
                            "folder_write",
                            f"account {acc.account_no}: нет записи в {sub}/: {e}",
                        )
                    )
            q = len(list_pending_videos(acc.video_folder, settings))
            if q < acc.videos_per_run:
                issues.append(
                    PreflightIssue(
                        "warn",
                        "short_queue",
                        f"account {acc.account_no}: в очереди {q}, запланировано {acc.videos_per_run}",
                    )
                )

    plan = build_run_plan(accounts, settings)
    if plan.total_slots == 0:
        issues.append(PreflightIssue("warn", "zero_slots", "total_slots=0"))

    if not settings.dry_run:
        ping_ok, msg = DolphinClient(settings).ping()
        if not ping_ok:
            issues.append(PreflightIssue("error", "dolphin", f"Dolphin API: {msg}"))

    if orch.posting_window and orch.posting_window_mode == "reject":
        if not in_posting_window(orch):
            issues.append(
                PreflightIssue("error", "posting_window", "Сейчас вне posting_window (mode=reject)")
            )

    if orch.max_concurrent_profiles > 1:
        issues.append(
            PreflightIssue(
                "warn",
                "parallel_k",
                f"max_concurrent_profiles={orch.max_concurrent_profiles}: следите за RAM Dolphin",
            )
        )

    if (
        settings.session.order != "publish_only"
        and orch.max_concurrent_profiles > 1
    ):
        issues.append(
            PreflightIssue(
                "warn",
                "warmup_parallel",
                "Прогрев FYP + K>1: рекомендуется max_concurrent_profiles=1",
            )
        )

    if _excel_locked(settings.excel_path):
        issues.append(
            PreflightIssue(
                "warn",
                "excel_locked",
                "Excel может быть открыт в другой программе — запись пойдёт в pending",
            )
        )

    has_error = any(i.level == "error" for i in issues)
    return PreflightResult(ok=not has_error, issues=issues)


def run_preflight_onboard(settings: AppSettings) -> PreflightResult:
    issues: list[PreflightIssue] = []
    if not settings.excel_path.is_file():
        issues.append(
            PreflightIssue("error", "excel_missing", f"Excel не найден: {settings.excel_path}")
        )
        return PreflightResult(ok=False, issues=issues)

    catalog = load_geo_catalog(settings.geo_catalog_file)
    if not catalog:
        issues.append(
            PreflightIssue(
                "error",
                "geo_catalog",
                f"Пустой или отсутствует geo catalog: {settings.geo_catalog_file}",
            )
        )

    try:
        pending = ExcelRegistry(settings).read_onboarding_pending()
    except Exception as e:
        issues.append(PreflightIssue("error", "excel_onboard", str(e)))
        return PreflightResult(ok=False, issues=issues)

    if not pending:
        issues.append(
            PreflightIssue("warn", "no_onboard_rows", "Нет строк онбординга (все «готов» или лист пуст)")
        )

    for row in pending:
        code = row.geo.strip().upper()
        if not code:
            issues.append(
                PreflightIssue(
                    "error",
                    "geo_empty",
                    f"строка {row.row_index}: geo пустой",
                )
            )
        elif code not in catalog:
            issues.append(
                PreflightIssue(
                    "error",
                    "geo_unknown",
                    f"строка {row.row_index}: geo {row.geo!r} нет в catalog",
                )
            )
        if row.avatar_path and not row.avatar_path.is_file():
            issues.append(
                PreflightIssue(
                    "warn",
                    "avatar_missing",
                    f"строка {row.row_index}: avatar не найден {row.avatar_path}",
                )
            )

    if not settings.dry_run:
        ping_ok, msg = DolphinClient(settings).ping()
        if not ping_ok:
            issues.append(PreflightIssue("error", "dolphin", f"Dolphin API: {msg}"))

    has_error = any(i.level == "error" for i in issues)
    return PreflightResult(ok=not has_error, issues=issues)


def _excel_locked(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with path.open("r+b"):
            return False
    except PermissionError:
        return True
    except OSError:
        return False
