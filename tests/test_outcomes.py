from tiktok_publisher.outcomes import (
    OutcomeCode,
    classify_publish_error,
    outcome_from_attempt,
    summarize_account_outcomes,
)


def test_classify_no_login():
    assert classify_publish_error("TikTok не авторизован — войдите") == OutcomeCode.no_login


def test_classify_not_published():
    assert (
        classify_publish_error("Не удалось подтвердить публикацию")
        == OutcomeCode.not_published
    )


def test_summarize_all_published():
    codes = [OutcomeCode.published, OutcomeCode.published]
    s = summarize_account_outcomes(codes, ok_count=2, planned=2)
    assert s.code == OutcomeCode.published
    assert s.label_ru == "опубликовано"


def test_summarize_login_priority():
    codes = [OutcomeCode.published, OutcomeCode.no_login]
    s = summarize_account_outcomes(codes, ok_count=1, planned=2)
    assert s.code == OutcomeCode.no_login
    assert s.label_ru == "нет входа"


def test_summarize_partial():
    codes = [OutcomeCode.published, OutcomeCode.not_published]
    s = summarize_account_outcomes(codes, ok_count=1, planned=2)
    assert s.code == OutcomeCode.partial
    assert "1/2" in s.label_ru


def test_classify_captcha():
    assert classify_publish_error("Please complete captcha verify") == OutcomeCode.captcha


def test_classify_rate_limit():
    assert classify_publish_error("rate limit try again later") == OutcomeCode.rate_limit


def test_summarize_circuit_breaker():
    s = summarize_account_outcomes([OutcomeCode.circuit_breaker], ok_count=0, planned=2)
    assert s.label_ru == "прервано: ошибки подряд"


def test_outcome_from_attempt_dry_run():
    o = outcome_from_attempt(True, dry_run=True)
    assert o.code == OutcomeCode.dry_run
    assert o.label_ru == "тест без публикации"
