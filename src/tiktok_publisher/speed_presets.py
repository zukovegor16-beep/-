from __future__ import annotations

from tiktok_publisher.config import AppSettings, DelayRange, OrchestratorSettings


PRESETS: dict[str, dict] = {
    "safe": {"delay_between_posts_sec": DelayRange(min=90, max=180), "delay_after_error_sec": 600},
    "normal": {"delay_between_posts_sec": DelayRange(min=45, max=120), "delay_after_error_sec": 300},
    "fast": {"delay_between_posts_sec": DelayRange(min=15, max=45), "delay_after_error_sec": 120},
}


def apply_speed_preset(settings: AppSettings) -> OrchestratorSettings:
    orch = settings.orchestrator.model_copy(deep=True)
    preset = orch.speed_preset or "normal"
    if preset == "custom":
        return orch
    if preset in PRESETS:
        p = PRESETS[preset]
        orch.delay_between_posts_sec = p["delay_between_posts_sec"]
        orch.delay_after_error_sec = p["delay_after_error_sec"]
    return orch
