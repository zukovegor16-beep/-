from pathlib import Path

from tiktok_publisher.config import AppSettings
from tiktok_publisher.queue import list_pending_videos, move_to_posted, next_video


def test_queue_and_posted(tmp_path: Path):
    settings = AppSettings()
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.mov").write_bytes(b"y")
    posted = tmp_path / "posted"
    posted.mkdir()
    (posted / "old.mp4").write_bytes(b"z")

    assert len(list_pending_videos(tmp_path, settings)) == 2
    n = next_video(tmp_path, settings)
    assert n and n.name in {"a.mp4", "b.mov"}
    moved_name = n.name
    move_to_posted(n)
    assert not (tmp_path / moved_name).exists()
    assert (tmp_path / "posted" / moved_name).exists()
    assert len(list_pending_videos(tmp_path, settings)) == 1
