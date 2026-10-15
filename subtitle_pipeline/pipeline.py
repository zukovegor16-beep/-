from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from subtitle_pipeline.config import PipelineConfig, SubtitleLanguage
from subtitle_pipeline.languages import target_subtitle_lang
from subtitle_pipeline.render import render_burned_captions
from subtitle_pipeline.transcribe import transcribe_to_srt
from subtitle_pipeline.translate import SrtTranslator


@dataclass
class PipelineResult:
    output_video: Path
    master_srt: Path
    final_srt: Path
    detected_language: str
    subtitle_language: str


class SubtitlePipeline:
    """
    End-to-end: video → (transcribe) → (translate) → animated burn-in.

    Plug this class into your local video processor after cut/encode steps.
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._translator = SrtTranslator(config.translation)

    def _work_paths(self, video_in: Path, stem: str) -> dict[str, Path]:
        base = self.config.paths.work_dir / stem
        base.mkdir(parents=True, exist_ok=True)
        return {
            "dir": base,
            "master_srt": base / "master.srt",
            "final_srt": base / "final.srt",
        }

    def run(
        self,
        video_in: Path,
        video_out: Path,
        *,
        subtitle_language: SubtitleLanguage | str | None = None,
    ) -> PipelineResult:
        video_in = video_in.resolve()
        video_out = video_out.resolve()
        stem = video_in.stem
        paths = self._work_paths(video_in, stem)

        detected = transcribe_to_srt(
            video_in,
            paths["master_srt"],
            self.config.whisper,
        )

        lang_cfg = subtitle_language or self.config.subtitle_language
        if isinstance(lang_cfg, SubtitleLanguage):
            lang_key = lang_cfg.value
        else:
            lang_key = str(lang_cfg)

        target = target_subtitle_lang(lang_key, detected)

        if target == detected.split("-")[0]:
            paths["final_srt"].write_text(
                paths["master_srt"].read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        else:
            self._translator.translate_srt_file(
                paths["master_srt"],
                paths["final_srt"],
                source_whisper=detected,
                target_whisper=target,
            )

        render_burned_captions(
            video_in,
            paths["final_srt"],
            video_out,
            self.config.pycaps,
        )

        if not self.config.paths.keep_intermediates:
            for p in (paths["master_srt"], paths["final_srt"]):
                if p.exists():
                    p.unlink()

        return PipelineResult(
            output_video=video_out,
            master_srt=paths["master_srt"],
            final_srt=paths["final_srt"],
            detected_language=detected,
            subtitle_language=target,
        )
