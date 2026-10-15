from __future__ import annotations

import re


def extract_verification_code(
    text: str,
    pattern: str = r"\b(\d{6})\b",
    *,
    sender_hints: tuple[str, ...] = ("tiktok", "noreply", "account"),
) -> str | None:
    low = text.lower()
    if not any(h in low for h in sender_hints):
        # still try if body mentions verification / code
        if not any(x in low for x in ("verification", "verify", "код", "code")):
            return None
    matches = re.findall(pattern, text)
    if not matches:
        return None
    return str(matches[0])
