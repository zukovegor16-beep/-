from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tiktok_publisher.config import AppSettings


@dataclass
class OnboardPhaseRecord:
    phase: str
    started_at: float
    finished_at: float | None = None
    ok: bool = True
    detail: str = ""
    screenshot: str | None = None
    imap_uid: str | None = None


@dataclass
class OnboardTrace:
    row_index: int
    login: str
    phases: list[OnboardPhaseRecord] = field(default_factory=list)

    def start_phase(self, name: str) -> OnboardPhaseRecord:
        rec = OnboardPhaseRecord(phase=name, started_at=time.time())
        self.phases.append(rec)
        return rec

    def finish_phase(
        self,
        rec: OnboardPhaseRecord,
        *,
        ok: bool = True,
        detail: str = "",
        screenshot: str | None = None,
        imap_uid: str | None = None,
    ) -> None:
        rec.finished_at = time.time()
        rec.ok = ok
        rec.detail = detail
        rec.screenshot = screenshot
        rec.imap_uid = imap_uid

    def persist(self, settings: AppSettings) -> None:
        path = settings.data_dir_path / "onboard_trace.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(
            {
                "row_index": self.row_index,
                "login": self.login,
                "phases": [asdict(p) for p in self.phases],
            },
            ensure_ascii=False,
        )
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
