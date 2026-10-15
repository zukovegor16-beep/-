from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class SubtitleLanguage(str, Enum):
    """Target subtitle language or match spoken language."""

    SAME = "same"
    EN = "en"
    RU = "ru"


@dataclass
class WhisperConfig:
    model_size: str = "small"
    device: str = "auto"  # auto | cpu | cuda
    compute_type: str = "auto"
    language: str | None = None  # None = auto-detect


@dataclass
class TranslationConfig:
    model_id: str = "facebook/nllb-200-distilled-600M"
    batch_size: int = 8
    max_new_tokens: int = 256


@dataclass
class PycapsConfig:
    template: str = "minimalist"
    whisper_backend: str = "faster"
    video_quality: str | None = None  # passed through when supported


@dataclass
class PathsConfig:
    work_dir: Path = Path("work/subtitles")
    keep_intermediates: bool = True


@dataclass
class PipelineConfig:
    subtitle_language: SubtitleLanguage = SubtitleLanguage.EN
    whisper: WhisperConfig = field(default_factory=WhisperConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    pycaps: PycapsConfig = field(default_factory=PycapsConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> PipelineConfig:
        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        sub_lang = SubtitleLanguage(raw.get("subtitle_language", "en"))

        whisper_raw = raw.get("whisper", {})
        trans_raw = raw.get("translation", {})
        pycaps_raw = raw.get("pycaps", {})
        paths_raw = raw.get("paths", {})

        paths = PathsConfig(
            work_dir=Path(paths_raw.get("work_dir", "work/subtitles")),
            keep_intermediates=bool(paths_raw.get("keep_intermediates", True)),
        )

        return cls(
            subtitle_language=sub_lang,
            whisper=WhisperConfig(
                model_size=whisper_raw.get("model_size", "small"),
                device=whisper_raw.get("device", "auto"),
                compute_type=whisper_raw.get("compute_type", "auto"),
                language=whisper_raw.get("language"),
            ),
            translation=TranslationConfig(
                model_id=trans_raw.get("model_id", "facebook/nllb-200-distilled-600M"),
                batch_size=int(trans_raw.get("batch_size", 8)),
                max_new_tokens=int(trans_raw.get("max_new_tokens", 256)),
            ),
            pycaps=PycapsConfig(
                template=pycaps_raw.get("template", "minimalist"),
                whisper_backend=pycaps_raw.get("whisper_backend", "faster"),
                video_quality=pycaps_raw.get("video_quality"),
            ),
            paths=paths,
        )
