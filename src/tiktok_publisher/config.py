from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class DolphinSettings(BaseModel):
    api_base: str = "http://127.0.0.1:3001"
    api_token: str | None = None


class DelayRange(BaseModel):
    min: int = 45
    max: int = 120


class OrchestratorSettings(BaseModel):
    mode: Literal["sequential", "round_robin"] = "sequential"
    max_concurrent_profiles: int = 1
    speed_preset: Literal["safe", "normal", "fast", "custom"] = "normal"
    delay_between_posts_sec: DelayRange = Field(default_factory=DelayRange)
    delay_after_error_sec: int = 300
    count_errors_toward_limit: bool = True
    count_infra_errors_toward_limit: bool = False
    skip_failed_file: bool = True
    skip_duplicate_counts_toward_limit: bool = False
    posting_window: dict[str, str] | None = None
    posting_window_mode: Literal["reject", "wait"] = "reject"
    timezone: str = "Europe/Moscow"
    on_success: Literal["move_to_posted"] = "move_to_posted"
    dolphin_min_start_interval_sec: float = 1.0
    report_flush_every_n: int = 5
    circuit_breaker_consecutive_errors: int = 0
    min_video_bytes: int = 1024
    max_caption_length: int = 2200
    require_preflight: bool = True


class QueueSettings(BaseModel):
    sort_by: Literal["mtime", "name"] = "mtime"
    extensions: list[str] = Field(default_factory=lambda: [".mp4", ".mov"])


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765


class PathsSettings(BaseModel):
    content_root: str = "./content"
    data_dir: str = "./data"


class ExcelSettings(BaseModel):
    registry_path: str = "./config/accounts.xlsx"
    sheet_accounts: str = "Аккаунты"
    sheet_onboarding: str = "Онбординг"
    caption_delimiter: str = "|||"


class WarmupSettings(BaseModel):
    preset: Literal["safe", "normal"] = "normal"
    scroll_count_min: int = 5
    scroll_count_max: int = 12
    scroll_pause_sec: DelayRange = Field(default_factory=lambda: DelayRange(min=2, max=6))
    watch_time_sec: DelayRange = Field(default_factory=lambda: DelayRange(min=3, max=12))
    likes_min: int = 0
    likes_max: int = 3
    like_probability: float = 0.35
    scroll_up_probability: float = 0.08
    max_duration_sec: int = 180


class SessionSettings(BaseModel):
    order: Literal[
        "publish_only",
        "warmup_then_publish",
        "publish_then_warmup",
        "warmup_publish_warmup",
    ] = "warmup_then_publish"
    warmup_fail_blocks_publish: bool = True
    warmup: WarmupSettings = Field(default_factory=WarmupSettings)


class OnboardSettings(BaseModel):
    pause_on_captcha: bool = True
    manual_wait_sec: int = 300
    otp_mode: Literal["manual", "auto"] = "manual"
    unified_password: str | None = None
    avatar_library_dir: str = "./content/avatars"
    avatar_pick: Literal["column", "by_login", "random"] = "by_login"
    email_provider: Literal["gmail", "outlook", "mail_ru", "custom"] = "gmail"
    email_code_mode: Literal["webmail", "imap", "manual", "browser_then_imap"] = "imap"
    email_webmail_url: str | None = None
    imap_host: str | None = None
    imap_port: int = 993
    imap_use_ssl: bool = True
    email_code_timeout_sec: int = 180
    email_code_regex: str = r"\b(\d{6})\b"
    selectors_webmail_path: str = "./config/selectors_webmail.yaml"


class LoggingSettings(BaseModel):
    log_dir: str = "./logs"


class AppSettings(BaseModel):
    dry_run: bool = False
    dolphin: DolphinSettings = Field(default_factory=DolphinSettings)
    session: SessionSettings = Field(default_factory=SessionSettings)
    onboard: OnboardSettings = Field(default_factory=OnboardSettings)
    orchestrator: OrchestratorSettings = Field(default_factory=OrchestratorSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    excel: ExcelSettings = Field(default_factory=ExcelSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    selectors_path: str = "./config/selectors.yaml"
    selectors_onboard_path: str = "./config/selectors_onboard.yaml"
    selectors_warmup_path: str = "./config/selectors_warmup.yaml"
    geo_catalog_path: str = "./config/geo_catalog.yaml"

    def resolve_onboard_password_new(self, row_password_new: str) -> str:
        if row_password_new and str(row_password_new).strip():
            return str(row_password_new).strip()
        if self.onboard.unified_password:
            return self.onboard.unified_password.strip()
        return ""

    @property
    def data_dir_path(self) -> Path:
        return Path(self.paths.data_dir)

    @property
    def db_path(self) -> Path:
        return self.data_dir_path / "state.db"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir_path / "reports"

    @property
    def excel_path(self) -> Path:
        return Path(self.excel.registry_path)

    @property
    def selectors_file(self) -> Path:
        return Path(self.selectors_path)

    @property
    def selectors_onboard_file(self) -> Path:
        return Path(self.selectors_onboard_path)

    @property
    def selectors_warmup_file(self) -> Path:
        return Path(self.selectors_warmup_path)

    @property
    def geo_catalog_file(self) -> Path:
        return Path(self.geo_catalog_path)

    @property
    def selectors_webmail_file(self) -> Path:
        return Path(self.onboard.selectors_webmail_path)

    @property
    def avatar_library_path(self) -> Path:
        return Path(self.onboard.avatar_library_dir)


def load_settings(path: Path | None = None) -> AppSettings:
    if path is None:
        path = Path("config/settings.yaml")
    if not path.is_file():
        example = Path("config/settings.example.yaml")
        if example.is_file():
            data = yaml.safe_load(example.read_text(encoding="utf-8"))
            return AppSettings.model_validate(data or {})
        return AppSettings()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return AppSettings.model_validate(data or {})


def load_selectors(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
