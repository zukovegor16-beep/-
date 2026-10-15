from __future__ import annotations

from tiktok_publisher.config import AppSettings, WarmupSettings


def apply_warmup_preset(settings: AppSettings) -> WarmupSettings:
    w = settings.session.warmup.model_copy(deep=True)
    if w.preset == "safe":
        w.scroll_count_min = max(w.scroll_count_min, 8)
        w.scroll_count_max = max(w.scroll_count_max, 18)
        w.watch_time_sec.min = max(w.watch_time_sec.min, 5)
        w.watch_time_sec.max = max(w.watch_time_sec.max, 18)
        w.like_probability = min(w.like_probability, 0.2)
        w.max_duration_sec = max(w.max_duration_sec, 240)
    return w
