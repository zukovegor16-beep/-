from __future__ import annotations

import secrets


def split_caption_variants(raw: str, delimiter: str = "|||") -> list[str]:
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    parts: list[str] = []
    for chunk in text.replace("\r\n", "\n").split("\n"):
        for piece in chunk.split(delimiter):
            piece = piece.strip()
            if piece:
                parts.append(piece)
    return parts


def pick_random_caption(variants: list[str]) -> str:
    if not variants:
        raise ValueError("нет вариантов подписи (caption_variants пусто)")
    return secrets.SystemRandom().choice(variants)
