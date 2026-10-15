from pathlib import Path

from openpyxl import Workbook

from tiktok_publisher.config import AppSettings
from tiktok_publisher.excel_registry import ExcelRegistry


def test_read_accounts(tmp_path: Path):
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
    folder = tmp_path / "vids"
    folder.mkdir()
    ws.append([1, "T", str(folder), "pid", 2, "cap1|||cap2", "да"])
    wb.save(xlsx)

    settings = AppSettings(
        excel={
            "registry_path": str(xlsx),
            "sheet_accounts": "Аккаунты",
            "caption_delimiter": "|||",
        }
    )
    reg = ExcelRegistry(settings)
    accs = reg.read_accounts()
    assert len(accs) == 1
    assert accs[0].videos_per_run == 2
    assert accs[0].caption_variants("|||") == ["cap1", "cap2"]
