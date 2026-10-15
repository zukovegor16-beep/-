# Онбординг TikTok (E2E)

## Порядок в одном профиле Dolphin

1. Создание/старт профиля (geo, proxy из Excel).
2. **Почта** (режим `webmail`): вход в Gmail/Outlook во второй вкладке.
3. **TikTok:** логин (`tiktok_login` + `tiktok_password_current`; для входа по email используется колонка `email`, если заполнена).
4. **Пароль:** смена на `tiktok_password_new` **или** `onboard.unified_password` из `settings.yaml` (один пароль на все аккаунты).
5. **Код из письма:** `imap` (SINCE дата + From TikTok, последнее письмо), `browser_then_imap` (webmail login + IMAP код), `webmail`, `manual` + «Продолжить».
6. **Надёжность:** retry кликов/fill, скриншоты `logs/onboard_row{N}_*.png`, trace `data/onboard_trace.jsonl`.
7. **Аватар:** файл из колонки `avatar_path` или каталога `onboard.avatar_library_dir` (`by_login` → `login.jpg`).
8. Excel: `onboard_status=готов`, строка в «Аккаунты» (`active=нет`). Заполните `video_folder`, `active=да` → публикация.

Прогрев после активации аккаунта — [`WARMUP.ru.md`](WARMUP.ru.md).

## Лист «Онбординг»

| Колонка | Назначение |
|---------|------------|
| geo | `geo_catalog.yaml` |
| tiktok_login | Логин TikTok (часто = email) |
| tiktok_password_current | Текущий пароль |
| tiktok_password_new | Опционально; иначе `unified_password` |
| email / email_password | IMAP/webmail (app password для Gmail) |
| avatar_path | Опционально, если есть `avatar_library` |
| dolphin_profile_id | Пусто → создать профиль |
| onboard_status / onboard_error | Статусы RU |

## Настройки (`onboard` в settings.yaml)

```yaml
onboard:
  unified_password: "ВАШ_ЕДИНЫЙ_ПАРОЛЬ"   # не коммитить
  email_code_mode: imap
  email_provider: gmail
  avatar_library_dir: "./content/avatars"
  avatar_pick: by_login
  email_code_timeout_sec: 180
```

Пример сложного пароля (замените локально): `TkOps#2026!xK9`.

## Команды и UI

```bash
tiktok-publisher onboard-plan
tiktok-publisher onboard --dry-run
tiktok-publisher serve   # Онбординг / Продолжить (OTP)
```

## Риски

- Селекторы TikTok и webmail меняются — калибровка на Windows.
- Gmail: используйте **пароль приложения**, не обычный пароль + 2FA.
- Автоматизация webmail хрупкая; **IMAP** стабильнее.

## E2E чеклист (Windows)

- [ ] Dolphin запущен, `doctor` ok
- [ ] `onboard-plan` — pending строки, geo, email, unified_password
- [ ] `onboard` на 1 строке (не dry-run)
- [ ] Код из письма получен (IMAP) или manual continue
- [ ] «Аккаунты»: `active=да`, папка видео → preflight → Старт публикации
