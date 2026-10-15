from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import os
import tempfile

from openpyxl import Workbook, load_workbook

from tiktok_publisher.captions import split_caption_variants
from tiktok_publisher.config import AppSettings

HEADER_ALIASES = {
    "last_run_status": {
        "last_run_status",
        "status",
        "статус",
        "run_status",
    },
    "account_no": {"account_no", "номер", "account", "id"},
    "account_name": {"account_name", "name", "имя", "название"},
    "video_folder": {"video_folder", "folder", "папка", "video_folder_path"},
    "dolphin_profile_id": {"dolphin_profile_id", "profile_id", "dolphin", "profile"},
    "videos_per_run": {"videos_per_run", "videos", "count", "n", "количество"},
    "caption_variants": {"caption_variants", "captions", "подписи", "caption"},
    "active": {"active", "активен", "enabled"},
}


def _normalize_header(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace(" ", "_")


def _map_headers(row: tuple[Any, ...]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for idx, cell in enumerate(row):
        key = _normalize_header(cell)
        for canonical, aliases in HEADER_ALIASES.items():
            if key == canonical or key in aliases:
                mapping[canonical] = idx
                break
    return mapping


def _cell(row: tuple[Any, ...], col_map: dict[str, int], name: str) -> Any:
    idx = col_map.get(name)
    if idx is None or idx >= len(row):
        return None
    return row[idx]


def _parse_active(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"1", "true", "yes", "y", "да", "on", "active"}


@dataclass
class AccountRow:
    row_index: int  # 1-based Excel row
    account_no: str
    account_name: str
    video_folder: Path
    dolphin_profile_id: str
    videos_per_run: int
    caption_variants_raw: str
    active: bool

    def caption_variants(self, delimiter: str) -> list[str]:
        return split_caption_variants(self.caption_variants_raw, delimiter)


def _atomic_save_workbook(wb, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=".xlsx", dir=str(dest.parent))
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        wb.save(tmp_path)
        tmp_path.replace(dest)
    finally:
        if tmp_path.is_file():
            tmp_path.unlink(missing_ok=True)


class ExcelRegistry:
    _write_lock = Lock()

    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.path = settings.excel_path

    def read_accounts(self) -> list[AccountRow]:
        if not self.path.is_file():
            raise FileNotFoundError(f"Excel не найден: {self.path}")
        wb = load_workbook(self.path, read_only=True, data_only=True)
        sheet_name = self.settings.excel.sheet_accounts
        if sheet_name not in wb.sheetnames:
            wb.close()
            raise ValueError(f"Лист «{sheet_name}» не найден в {self.path}")
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        wb.close()
        if not rows:
            return []
        col_map = _map_headers(rows[0])
        required = [
            "account_no",
            "video_folder",
            "dolphin_profile_id",
            "videos_per_run",
            "caption_variants",
            "active",
        ]
        missing = [r for r in required if r not in col_map]
        if missing:
            raise ValueError(f"В Excel нет колонок: {', '.join(missing)}")

        accounts: list[AccountRow] = []
        for i, row in enumerate(rows[1:], start=2):
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue
            active = _parse_active(_cell(row, col_map, "active"))
            if not active:
                continue
            try:
                n = int(_cell(row, col_map, "videos_per_run"))
            except (TypeError, ValueError):
                n = 0
            folder_raw = _cell(row, col_map, "video_folder")
            accounts.append(
                AccountRow(
                    row_index=i,
                    account_no=str(_cell(row, col_map, "account_no")).strip(),
                    account_name=str(_cell(row, col_map, "account_name") or "").strip(),
                    video_folder=Path(str(folder_raw).strip()),
                    dolphin_profile_id=str(_cell(row, col_map, "dolphin_profile_id")).strip(),
                    videos_per_run=max(0, n),
                    caption_variants_raw=str(_cell(row, col_map, "caption_variants") or ""),
                    active=True,
                )
            )
        return accounts

    def update_account_run_status(
        self,
        row_index: int,
        status: str,
        error: str | None = None,
    ) -> bool:
        """Returns False if file locked or missing."""
        if not self.path.is_file():
            return False
        with self._write_lock:
            try:
                wb = load_workbook(self.path)
            except PermissionError:
                return False
            sheet_name = self.settings.excel.sheet_accounts
            if sheet_name not in wb.sheetnames:
                wb.close()
                return False
            ws = wb[sheet_name]
            headers = [c.value for c in ws[1]]
            col_map = _map_headers(tuple(headers))
            now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
            updates: dict[str, Any] = {
                "last_run_status": status,
                "last_run_error": error or "",
                "last_run_at": now,
            }
            for field, value in updates.items():
                idx = col_map.get(field)
                if idx is not None:
                    ws.cell(row=row_index, column=idx + 1, value=value)
            try:
                _atomic_save_workbook(wb, self.path)
            except PermissionError:
                wb.close()
                return False
            except OSError:
                wb.close()
                return False
            wb.close()
            return True

    def append_log_row(
        self,
        account_no: str,
        filename: str,
        caption_used: str,
        status: str,
        error: str,
        started_at: str,
        finished_at: str,
    ) -> bool:
        if not self.path.is_file():
            return False
        with self._write_lock:
            try:
                wb = load_workbook(self.path)
            except PermissionError:
                return False
            log_name = "Log"
            if log_name not in wb.sheetnames:
                ws = wb.create_sheet(log_name)
                ws.append(
                    [
                        "started_at",
                        "finished_at",
                        "account_no",
                        "file",
                        "caption_used",
                        "status",
                        "error",
                    ]
                )
            ws = wb[log_name]
            ws.append(
                [
                    started_at,
                    finished_at,
                    account_no,
                    filename,
                    caption_used,
                    status,
                    error,
                ]
            )
            try:
                _atomic_save_workbook(wb, self.path)
            except PermissionError:
                wb.close()
                return False
            except OSError:
                wb.close()
                return False
            wb.close()
            return True


def create_workbook_from_template(template: Path, dest: Path) -> None:
    if dest.is_file():
        return
    if not template.is_file():
        wb = Workbook()
        ws = wb.active
        ws.title = "Аккаунты"
        ws.append(
            [
                "account_no",
                "account_name",
                "video_folder",
                "dolphin_profile_id",
                "videos_per_run",
                "caption_variants",
                "active",
                "status",
                "last_run_error",
                "last_run_at",
            ]
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        wb.save(dest)
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(template.read_bytes())
