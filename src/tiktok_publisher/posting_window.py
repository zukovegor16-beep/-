from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from tiktok_publisher.config import OrchestratorSettings


def _parse_hm(value: str) -> time:
    parts = value.strip().split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0
    return time(h, m)


def window_config(orch: OrchestratorSettings) -> tuple[time, time] | None:
    pw = orch.posting_window
    if not pw:
        return None
    start = pw.get("start") or pw.get("from")
    end = pw.get("end") or pw.get("to")
    if not start or not end:
        return None
    return _parse_hm(str(start)), _parse_hm(str(end))


def in_posting_window(orch: OrchestratorSettings, now: datetime | None = None) -> bool:
    cfg = window_config(orch)
    if cfg is None:
        return True
    start_t, end_t = cfg
    tz = ZoneInfo(orch.timezone)
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)
    t = now.time()
    if start_t <= end_t:
        return start_t <= t <= end_t
    return t >= start_t or t <= end_t


def seconds_until_window_opens(orch: OrchestratorSettings, now: datetime | None = None) -> float:
    cfg = window_config(orch)
    if cfg is None:
        return 0.0
    start_t, _ = cfg
    tz = ZoneInfo(orch.timezone)
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)
    target = datetime.combine(now.date(), start_t, tzinfo=tz)
    if target <= now:
        target += timedelta(days=1)
    return max((target - now).total_seconds(), 0.0)
