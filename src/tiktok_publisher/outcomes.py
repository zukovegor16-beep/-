from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class OutcomeCode(str, Enum):
    published = "published"
    not_published = "not_published"
    no_login = "no_login"
    captcha = "captcha"
    rate_limit = "rate_limit"
    no_videos = "no_videos"
    no_caption = "no_caption"
    file_invalid = "file_invalid"
    duplicate_skipped = "duplicate_skipped"
    dolphin_error = "dolphin_error"
    dry_run = "dry_run"
    partial = "partial"
    user_stop = "user_stop"
    circuit_breaker = "circuit_breaker"
    published_move_failed = "published_move_failed"
    upload_locked = "upload_locked"
    unknown_error = "unknown_error"
    onboard_ready = "onboard_ready"
    onboard_avatar_failed = "onboard_avatar_failed"
    onboard_data_error = "onboard_data_error"
    warmup_ok = "warmup_ok"


LABELS_RU: dict[OutcomeCode, str] = {
    OutcomeCode.published: "опубликовано",
    OutcomeCode.not_published: "нет публикации",
    OutcomeCode.no_login: "нет входа",
    OutcomeCode.captcha: "капча",
    OutcomeCode.rate_limit: "лимит TikTok",
    OutcomeCode.no_videos: "нет видео",
    OutcomeCode.no_caption: "нет подписи",
    OutcomeCode.file_invalid: "файл не подходит",
    OutcomeCode.duplicate_skipped: "уже опубликовано",
    OutcomeCode.dolphin_error: "ошибка Dolphin",
    OutcomeCode.dry_run: "тест без публикации",
    OutcomeCode.partial: "частично опубликовано",
    OutcomeCode.user_stop: "остановлено",
    OutcomeCode.circuit_breaker: "прервано: ошибки подряд",
    OutcomeCode.published_move_failed: "опубликовано (файл не перенесён)",
    OutcomeCode.upload_locked: "файл занят",
    OutcomeCode.unknown_error: "ошибка",
    OutcomeCode.onboard_ready: "готов",
    OutcomeCode.onboard_avatar_failed: "аватар не установлен",
    OutcomeCode.onboard_data_error: "ошибка данных",
    OutcomeCode.warmup_ok: "прогрев выполнен",
}

SUMMARY_PRIORITY: list[OutcomeCode] = [
    OutcomeCode.no_login,
    OutcomeCode.captcha,
    OutcomeCode.rate_limit,
    OutcomeCode.dolphin_error,
    OutcomeCode.circuit_breaker,
    OutcomeCode.user_stop,
]


@dataclass(frozen=True)
class Outcome:
    code: OutcomeCode
    label_ru: str
    detail: str = ""

    @staticmethod
    def from_code(code: OutcomeCode, detail: str = "") -> Outcome:
        label = LABELS_RU.get(code, code.value)
        if code == OutcomeCode.partial and detail:
            label = detail
        return Outcome(code=code, label_ru=label, detail=detail)


def is_success_code(code: OutcomeCode) -> bool:
    return code in (OutcomeCode.published, OutcomeCode.dry_run)


def is_failure_for_retry(code: OutcomeCode) -> bool:
    return code not in (
        OutcomeCode.published,
        OutcomeCode.dry_run,
        OutcomeCode.duplicate_skipped,
    )


def classify_publish_error(message: str) -> OutcomeCode:
    low = message.lower()
    if any(x in low for x in ("авторизован", "login", "log_in", "sign_up", "signup")):
        return OutcomeCode.no_login
    if "captcha" in low or "verify" in low or "капча" in low:
        return OutcomeCode.captcha
    if "rate limit" in low or "лимит" in low or "try again later" in low:
        return OutcomeCode.rate_limit
    if "success criteria" in low or "подтвердить публикацию" in low:
        return OutcomeCode.not_published
    if "upload in progress" in low or "файл занят" in low:
        return OutcomeCode.upload_locked
    if "dolphin" in low:
        return OutcomeCode.dolphin_error
    return OutcomeCode.not_published


def outcome_from_publish(ok: bool, message: str, *, dry_run: bool) -> Outcome:
    if dry_run and ok:
        return Outcome.from_code(OutcomeCode.dry_run, message)
    if ok:
        return Outcome.from_code(OutcomeCode.published, message)
    code = classify_publish_error(message)
    return Outcome.from_code(code, message)


def outcome_from_attempt(
    ok: bool,
    dry_run: bool,
    err: str = "",
    internal_status: str = "",
) -> Outcome:
    """Map legacy ok/error attempts to Outcome (uses message classification on failure)."""
    detail = err or internal_status
    return outcome_from_publish(ok, detail, dry_run=dry_run)


def summarize_account_outcomes(
    codes: list[OutcomeCode],
    ok_count: int,
    planned: int,
) -> Outcome:
    if not codes:
        return Outcome.from_code(OutcomeCode.unknown_error, "нет попыток")

    for priority in SUMMARY_PRIORITY:
        if priority in codes:
            return Outcome.from_code(priority)

    if ok_count >= planned and planned > 0 and all(
        c in (OutcomeCode.published, OutcomeCode.dry_run, OutcomeCode.duplicate_skipped)
        for c in codes
    ):
        if any(c == OutcomeCode.dry_run for c in codes) and not any(
            c == OutcomeCode.published for c in codes
        ):
            return Outcome.from_code(OutcomeCode.dry_run)
        return Outcome.from_code(OutcomeCode.published)

    if 0 < ok_count < planned:
        label = f"частично опубликовано ({ok_count}/{planned})"
        return Outcome(code=OutcomeCode.partial, label_ru=label, detail=label)

    if ok_count == 0:
        dominant = _dominant_failure(codes)
        return Outcome.from_code(dominant)

    return Outcome.from_code(OutcomeCode.published)


def _dominant_failure(codes: list[OutcomeCode]) -> OutcomeCode:
    for priority in SUMMARY_PRIORITY:
        if priority in codes:
            return priority
    for c in codes:
        if not is_success_code(c) and c != OutcomeCode.duplicate_skipped:
            return c
    return OutcomeCode.not_published
