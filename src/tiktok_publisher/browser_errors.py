from __future__ import annotations


def is_browser_disconnect(err: str) -> bool:
    low = (err or "").lower()
    return any(x in low for x in ("disconnect", "closed", "target", "browser has been"))
