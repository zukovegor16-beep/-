from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tiktok_publisher.config import AppSettings
from tiktok_publisher.excel_registry import ExcelRegistry

logger = logging.getLogger(__name__)


@dataclass
class PendingExcelOp:
    kind: str
    payload: dict[str, Any]


class ExcelPendingStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, kind: str, payload: dict[str, Any]) -> None:
        line = json.dumps({"kind": kind, "payload": payload}, ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def pending_count(self) -> int:
        if not self.path.is_file():
            return 0
        return sum(1 for _ in self.path.open(encoding="utf-8"))

    def read_all(self) -> list[PendingExcelOp]:
        if not self.path.is_file():
            return []
        ops: list[PendingExcelOp] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            ops.append(PendingExcelOp(kind=data["kind"], payload=data["payload"]))
        return ops

    def clear(self) -> None:
        if self.path.is_file():
            self.path.unlink()


def sync_pending_excel(settings: AppSettings) -> tuple[int, int]:
    """Returns (applied, failed)."""
    store = ExcelPendingStore(settings.data_dir_path / "pending_excel.jsonl")
    ops = store.read_all()
    if not ops:
        return 0, 0
    excel = ExcelRegistry(settings)
    applied = 0
    failed = 0
    remaining: list[PendingExcelOp] = []
    for op in ops:
        ok = False
        if op.kind == "log_row":
            p = op.payload
            ok = excel.append_log_row(
                p["account_no"],
                p["filename"],
                p["caption_used"],
                p["status"],
                p["error"],
                p["started_at"],
                p["finished_at"],
            )
        elif op.kind == "account_status":
            p = op.payload
            ok = excel.update_account_run_status(
                int(p["row_index"]), p["status"], p.get("error")
            )
        if ok:
            applied += 1
        else:
            failed += 1
            remaining.append(op)
    store.clear()
    for op in remaining:
        store.append(op.kind, op.payload)
    if applied:
        logger.info("sync-excel: applied %s, failed %s", applied, failed)
    return applied, failed
