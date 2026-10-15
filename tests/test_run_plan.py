from pathlib import Path

from openpyxl import Workbook

from tiktok_publisher.config import AppSettings
from tiktok_publisher.excel_registry import ExcelRegistry
from tiktok_publisher.run_plan import build_run_plan


def test_run_plan_total_slots_and_queue(tmp_path: Path):
    folder = tmp_path / "vids"
    folder.mkdir()
    (folder / "a.mp4").write_bytes(b"1")
    (folder / "b.mp4").write_bytes(b"2")

    xlsx = tmp_path / "acc.xlsx"
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
        ]
    )
    ws.append([1, "A", str(folder), "p1", 3, "c1", "да"])
    ws.append([2, "B", str(tmp_path / "empty"), "p2", 1, "c2", "да"])
    wb.save(xlsx)

    settings = AppSettings(
        excel={"registry_path": str(xlsx), "sheet_accounts": "Аккаунты"},
    )
    accounts = ExcelRegistry(settings).read_accounts()
    plan = build_run_plan(accounts, settings)
    assert plan.total_slots == 4
    assert len(plan.snapshots) == 2
    assert plan.snapshots[0].queue_count == 2
    assert plan.snapshots[1].queue_count == 0
