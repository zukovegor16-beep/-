from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from subtitle_pipeline.config import PycapsConfig


class PycapsRenderError(RuntimeError):
    pass


def _find_pycaps() -> str:
    exe = shutil.which("pycaps")
    if exe:
        return exe
    raise PycapsRenderError(
        "pycaps CLI not found. Install: "
        'pip install "git+https://github.com/francozanardi/pycaps.git#egg=pycaps[base,faster-whisper]"'
    )


def render_burned_captions(
    video_in: Path,
    transcript_srt: Path,
    video_out: Path,
    config: PycapsConfig,
) -> Path:
    """
    Animated burn-in via pycaps. Skips ASR when --transcript is provided.
    """
    pycaps = _find_pycaps()
    video_out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        pycaps,
        "render",
        "--input",
        str(video_in),
        "--output",
        str(video_out),
        "--template",
        config.template,
        "--transcript",
        str(transcript_srt),
        "--transcript-format",
        "srt",
        "--whisper-backend",
        config.whisper_backend,
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise PycapsRenderError(
            f"pycaps failed (exit {proc.returncode}):\n{proc.stderr or proc.stdout}"
        )
    if not video_out.exists():
        raise PycapsRenderError("pycaps finished but output file missing")
    return video_out
