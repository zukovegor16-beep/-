from pathlib import Path

from tiktok_publisher.avatar_library import resolve_avatar_path
from tiktok_publisher.config import AppSettings
from tiktok_publisher.email_code import extract_verification_code


def test_extract_tiktok_code():
    body = "Your TikTok verification code is 482913. Do not share."
    assert extract_verification_code(body) == "482913"


def test_extract_no_code():
    assert extract_verification_code("Hello world") is None


def test_avatar_by_login(tmp_path: Path):
    lib = tmp_path / "avatars"
    lib.mkdir()
    img = lib / "user1.jpg"
    img.write_bytes(b"x")
    settings = AppSettings(
        onboard={
            "avatar_library_dir": str(lib),
            "avatar_pick": "by_login",
        }
    )
    p = resolve_avatar_path(
        settings, login="user1", column_path=Path("/nonexistent")
    )
    assert p == img


def test_resolve_unified_password():
    s = AppSettings(onboard={"unified_password": "TkOps#2026!xK9"})
    assert s.resolve_onboard_password_new("") == "TkOps#2026!xK9"
    assert s.resolve_onboard_password_new("custom") == "custom"
