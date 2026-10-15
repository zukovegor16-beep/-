from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from openpyxl import Workbook

from tiktok_publisher.config import AppSettings
from tiktok_publisher.outcomes import OutcomeCode
from tiktok_publisher.publish_result import PublishResult
from tiktok_publisher.dolphin_client import ProfileSession
from tiktok_publisher.orchestrator import Orchestrator


def _make_workbook(xlsx: Path, folder: Path, videos_per_run: int = 2) -> None:
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
    ws.append([1, "A", str(folder), "111", videos_per_run, "t1|||t2", "да"])
    wb.save(xlsx)


def test_dolphin_start_once_per_account_block(tmp_path: Path):
    folder = tmp_path / "acc01"
    folder.mkdir()
    (folder / "v1.mp4").write_bytes(b"1")
    (folder / "v2.mp4").write_bytes(b"2")
    xlsx = tmp_path / "acc.xlsx"
    _make_workbook(xlsx, folder, videos_per_run=2)

    settings = AppSettings(
        dry_run=False,
        paths={"data_dir": str(tmp_path / "data"), "content_root": str(tmp_path)},
        excel={"registry_path": str(xlsx), "sheet_accounts": "Аккаунты"},
        orchestrator={
            "speed_preset": "custom",
            "min_video_bytes": 1,
            "delay_between_posts_sec": {"min": 0, "max": 0},
            "delay_after_error_sec": 0,
        },
    )

    starts: list[str] = []
    stops: list[str] = []
    session = ProfileSession(profile_id="111", port=9222, ws_endpoint="ws://x")

    def fake_start(pid: str) -> ProfileSession:
        starts.append(pid)
        return session

    publish = AsyncMock(
        return_value=PublishResult(True, OutcomeCode.published, "")
    )
    handle = MagicMock()
    handle.is_healthy = AsyncMock(return_value=True)

    orch = Orchestrator(settings)
    with (
        patch.object(orch.dolphin, "start_profile", side_effect=fake_start),
        patch.object(orch.dolphin, "stop_profile", side_effect=lambda pid: stops.append(pid)),
        patch("tiktok_publisher.orchestrator.open_browser", return_value=handle),
        patch("tiktok_publisher.orchestrator.close_browser"),
        patch("tiktok_publisher.orchestrator.publish_video_async", publish),
    ):
        orch.start()
        orch.wait(timeout=30)

    assert not orch.is_running
    assert starts == ["111"]
    assert stops == ["111"]
    assert publish.await_count == 2
    for call in publish.await_args_list:
        assert call.kwargs.get("browser_handle") is handle


def test_parallel_two_accounts(tmp_path: Path):
    folders = []
    for i in (1, 2):
        f = tmp_path / f"acc{i}"
        f.mkdir()
        (f / "v.mp4").write_bytes(b"x")
        folders.append(f)

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
    ws.append([1, "A", str(folders[0]), "101", 1, "c", "да"])
    ws.append([2, "B", str(folders[1]), "102", 1, "c", "да"])
    wb.save(xlsx)

    settings = AppSettings(
        dry_run=True,
        paths={"data_dir": str(tmp_path / "data"), "content_root": str(tmp_path)},
        excel={"registry_path": str(xlsx), "sheet_accounts": "Аккаунты"},
        orchestrator={
            "speed_preset": "custom",
            "min_video_bytes": 1,
            "max_concurrent_profiles": 2,
            "delay_between_posts_sec": {"min": 0, "max": 0},
            "delay_after_error_sec": 0,
        },
    )

    orch = Orchestrator(settings)
    orch.start()
    orch.wait(timeout=30)
    assert not orch.is_running
    recs = orch.store.publications_for_run(orch.current_run_id or "")
    assert len(recs) == 2
    assert {r.account_no for r in recs} == {"1", "2"}
