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
    delay_between_posts_sec: DelayRange = Field(default_factory=DelayRange)
    delay_after_error_sec: int = 300
    posting_window: dict[str, str] | None = None
    timezone: str = "Europe/Moscow"
    on_success: Literal["move_to_posted"] = "move_to_posted"


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
    caption_delimiter: str = "|||"


class LoggingSettings(BaseModel):
    log_dir: str = "./logs"


class AppSettings(BaseModel):
    dry_run: bool = False
    dolphin: DolphinSettings = Field(default_factory=DolphinSettings)
    orchestrator: OrchestratorSettings = Field(default_factory=OrchestratorSettings)
    queue: QueueSettings = Field(default_factory=QueueSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    excel: ExcelSettings = Field(default_factory=ExcelSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    selectors_path: str = "./config/selectors.yaml"

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
