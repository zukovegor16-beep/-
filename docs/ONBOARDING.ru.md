# Онбординг TikTok (v4)

## Лист «Онбординг» в `accounts.xlsx`

| Колонка | Назначение |
|---------|------------|
| geo | Ключ из `config/geo_catalog.yaml` (US, DE, …) |
| tiktok_login / tiktok_password_current / tiktok_password_new | Учётная запись TikTok |
| email / email_password | Для OTP (MVP: ручной ввод) |
| avatar_path | Путь к файлу аватарки |
| proxy | Опционально `user:pass@host:port` для нового профиля Dolphin |
| dolphin_profile_id | Пусто → создаётся профиль с geo через pyanty |
| onboard_status / onboard_error | Обновляет программа |

После успеха строка получает `onboard_status=готов`, в лист **«Аккаунты»** добавляется строка с `active=нет`, пустой `video_folder` и указанным `dolphin_profile_id`. Заполните папку, подписи, `videos_per_run` и поставьте `active=да`.

## Geo

Справочник координат и timezone: `config/geo_catalog.yaml`. Код страны в Excel должен совпадать с ключом в YAML.

## OTP и капча

По умолчанию `onboard.otp_mode: manual`. При капче/verify программа ждёт до `manual_wait_sec`, затем продолжайте:

- Web UI: **«Продолжить (OTP)»** → `POST /api/onboard/continue`
- CLI: `onboard-continue` (подсказка; при `serve` используйте API)

## Команды

```bash
python -m tiktok_publisher onboard-plan
python -m tiktok_publisher onboard --dry-run
python -m tiktok_publisher serve
```

Preflight онбординга: `GET /api/onboard/preflight` или `GET /api/preflight?mode=onboard`.

## Безопасность

Пароли в xlsx хранятся в открытом виде. Не коммитьте реальный файл в git. Vault/IMAP — опционально позже (этап F).
