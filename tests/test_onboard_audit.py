from pathlib import Path

from tiktok_publisher.email_imap import _from_matches, _imap_since_date
from tiktok_publisher.onboard_trace import OnboardTrace
from tiktok_publisher.config import AppSettings
import time


def test_imap_from_filter():
    assert _from_matches("TikTok <noreply@tiktok.com>", ("tiktok",))
    assert not _from_matches("Newsletter <news@shop.com>", ("tiktok",))


def test_imap_since_date():
    s = _imap_since_date(time.time())
    assert len(s.split("-")) == 3


def test_onboard_trace_persist(tmp_path: Path):
    settings = AppSettings(paths={"data_dir": str(tmp_path / "data")})
    tr = OnboardTrace(row_index=2, login="u@x.com")
    pr = tr.start_phase("tiktok_login")
    tr.finish_phase(pr, ok=True)
    tr.persist(settings)
    assert (tmp_path / "data" / "onboard_trace.jsonl").is_file()
