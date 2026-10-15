from __future__ import annotations

import argparse
from pathlib import Path

from subtitle_pipeline.config import PipelineConfig, SubtitleLanguage
from subtitle_pipeline.pipeline import SubtitlePipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Local animated subtitles: transcribe → translate → pycaps burn-in"
    )
    parser.add_argument("input", type=Path, help="Input video")
    parser.add_argument("output", type=Path, help="Output video with burned captions")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("subtitle_pipeline/config.example.yaml"),
        help="YAML config path",
    )
    parser.add_argument(
        "--subtitle-language",
        choices=["en", "ru", "same"],
        default=None,
        help="Override config subtitle_language",
    )
    args = parser.parse_args()

    cfg = PipelineConfig.from_yaml(args.config)
    sub_lang = (
        SubtitleLanguage(args.subtitle_language)
        if args.subtitle_language
        else None
    )

    result = SubtitlePipeline(cfg).run(
        args.input,
        args.output,
        subtitle_language=sub_lang,
    )
    print(f"Done: {result.output_video}")
    print(f"Speech: {result.detected_language} → subtitles: {result.subtitle_language}")
    print(f"SRT: {result.final_srt}")


if __name__ == "__main__":
    main()
