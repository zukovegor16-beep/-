from __future__ import annotations

from dataclasses import dataclass, field

from tiktok_publisher.config import AppSettings
from tiktok_publisher.excel_registry import AccountRow
from tiktok_publisher.queue import list_pending_videos


@dataclass
class AccountSnapshot:
    account_no: str
    account_name: str
    video_folder: str
    videos_per_run: int
    queue_count: int
    dolphin_profile_id: str


@dataclass
class RunPlan:
    accounts: list[AccountRow]
    snapshots: list[AccountSnapshot] = field(default_factory=list)

    @property
    def total_slots(self) -> int:
        return sum(a.videos_per_run for a in self.accounts)


def build_run_plan(accounts: list[AccountRow], settings: AppSettings) -> RunPlan:
    snapshots: list[AccountSnapshot] = []
    for acc in accounts:
        pending = len(list_pending_videos(acc.video_folder, settings))
        snapshots.append(
            AccountSnapshot(
                account_no=acc.account_no,
                account_name=acc.account_name,
                video_folder=str(acc.video_folder),
                videos_per_run=acc.videos_per_run,
                queue_count=pending,
                dolphin_profile_id=acc.dolphin_profile_id,
            )
        )
    return RunPlan(accounts=accounts, snapshots=snapshots)
