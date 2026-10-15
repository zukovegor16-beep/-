# Надёжность (v3 + v4)

## Онбординг / прогрев (v4)

- Перед онбордингом: `onboard-plan`, preflight `mode=onboard`, geo в catalog.
- OTP/captcha: пауза + `/api/onboard/continue` или таймаут `manual_wait_sec`.
- Прогрев: при `warmup_fail_blocks_publish` сбой FYP (нет входа/капча) отменяет upload в этой сессии аккаунта.

---

# Надёжность (v3)

## Перед Стартом

1. Закройте `accounts.xlsx` в Excel (иначе запись уйдёт в `data/pending_excel.jsonl`).
2. Dolphin Anty запущен, TikTok залогинен в каждом профиле.
3. `tiktok-publisher preflight` или кнопка проверки в UI — без ошибок уровня **error**.
4. Один экземпляр: не запускайте второй `serve`/`start` (lockfile `data/.publisher.lock`).

## Дубликаты видео

После успешной публикации fingerprint файла пишется в SQLite (`published_assets`). Повтор того же файла на том же аккаунте → `skipped_duplicate` и перенос в `posted/` без повторного upload.

## Excel не записался

- В UI/status: `excel_write_degraded` и `excel_pending_count`.
- Восстановление: `tiktok-publisher sync-excel` или POST `/api/sync-excel`.

## Captcha / login / rate limit

Publisher останавливает retry и возвращает понятную ошибку. Решите вручную в профиле Dolphin, затем `start --only-errors <run_id>` для повтора только failed.

## posting_window

```yaml
orchestrator:
  posting_window:
    start: "09:00"
    end: "21:00"
  posting_window_mode: reject   # или wait — ждать начала окна
  timezone: "Europe/Moscow"
```

## Сбой процесса / зависший профиль

- При выходе процесс пытается `stop_profile` для активных профилей.
- `tiktok-publisher doctor --list-stale-profiles` — подсказка; лишние профили закройте в Dolphin вручную.

## Circuit breaker

`circuit_breaker_consecutive_errors: N` — после N ошибок подряд на аккаунте пропуск оставшихся слотов этого аккаунта в текущем прогоне (0 = выключено).
