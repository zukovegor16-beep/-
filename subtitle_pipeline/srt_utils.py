from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SrtCue:
    index: int
    start: str
    end: str
    text: str


_TIME = re.compile(
    r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})"
)


def parse_srt(content: str) -> list[SrtCue]:
    blocks = re.split(r"\n\s*\n", content.strip(), flags=re.MULTILINE)
    cues: list[SrtCue] = []
    for block in blocks:
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if len(lines) < 2:
            continue
        try:
            index = int(lines[0])
        except ValueError:
            continue
        m = _TIME.match(lines[1])
        if not m:
            continue
        text = "\n".join(lines[2:])
        cues.append(SrtCue(index=index, start=m.group(1), end=m.group(2), text=text))
    return cues


def format_srt(cues: list[SrtCue]) -> str:
    parts: list[str] = []
    for i, cue in enumerate(cues, start=1):
        parts.append(f"{i}\n{cue.start} --> {cue.end}\n{cue.text}\n")
    return "\n".join(parts).strip() + "\n"


def read_srt(path: str) -> list[SrtCue]:
    with open(path, encoding="utf-8") as f:
        return parse_srt(f.read())


def write_srt(path: str, cues: list[SrtCue]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(format_srt(cues))
