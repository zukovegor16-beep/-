from __future__ import annotations

from pathlib import Path

from subtitle_pipeline.config import WhisperConfig
from subtitle_pipeline.srt_utils import SrtCue, format_srt


def _format_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms_part = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms_part:03d}"


def segments_to_srt(segments) -> str:
    cues: list[SrtCue] = []
    for i, seg in enumerate(segments, start=1):
        text = (seg.text or "").strip()
        if not text:
            continue
        cues.append(
            SrtCue(
                index=i,
                start=_format_timestamp(seg.start),
                end=_format_timestamp(seg.end),
                text=text,
            )
        )
    return format_srt(cues)


def transcribe_to_srt(
    video_path: Path,
    output_srt: Path,
    config: WhisperConfig,
) -> str:
    """
    Transcribe audio from video. Returns detected language code (e.g. 'ru', 'en').
    """
    from faster_whisper import WhisperModel

    device = config.device
    compute_type = config.compute_type
    if device == "auto":
        device = "cuda"
        compute_type = "float16" if compute_type == "auto" else compute_type
        try:
            model_probe = WhisperModel(
                config.model_size, device="cuda", compute_type=compute_type
            )
            del model_probe
        except Exception:
            device = "cpu"
            compute_type = "int8" if compute_type == "auto" else compute_type

    model = WhisperModel(config.model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        str(video_path),
        language=config.language,
        word_timestamps=False,
        vad_filter=True,
    )
    detected = info.language or "en"
    srt_body = segments_to_srt(list(segments))
    output_srt.parent.mkdir(parents=True, exist_ok=True)
    output_srt.write_text(srt_body, encoding="utf-8")
    return detected
