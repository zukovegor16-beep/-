"""
Example: call from your existing video processor after trim/filters.

    from pathlib import Path
    from subtitle_pipeline import PipelineConfig, SubtitlePipeline, SubtitleLanguage

    cfg = PipelineConfig.from_yaml(Path("subtitle_pipeline/config.example.yaml"))
    pipeline = SubtitlePipeline(cfg)

    # RU speech → EN animated subs
    pipeline.run(
        video_in=Path("out/clip_raw.mp4"),
        video_out=Path("out/clip_final.mp4"),
        subtitle_language=SubtitleLanguage.EN,
    )
"""

from __future__ import annotations

from pathlib import Path

from subtitle_pipeline import PipelineConfig, SubtitleLanguage, SubtitlePipeline


def after_your_encode_step(raw_mp4: Path, final_mp4: Path, subs: str = "en") -> None:
    cfg = PipelineConfig.from_yaml(
        Path(__file__).resolve().parent / "config.example.yaml"
    )
    SubtitlePipeline(cfg).run(
        raw_mp4,
        final_mp4,
        subtitle_language=SubtitleLanguage(subs),
    )


if __name__ == "__main__":
    after_your_encode_step(
        Path("samples/input.mp4"),
        Path("samples/output_captioned.mp4"),
        subs="en",
    )
