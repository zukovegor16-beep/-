# Калибровка онбординга (Windows)

Чеклист перед первым live-прогоном. Селекторы в репозитории — **шаблоны**; под ваш UI TikTok/Gmail их нужно уточнить.

## 1. Окружение

- [ ] Dolphin Anty запущен, Local API доступен (`doctor`)
- [ ] `config/settings.yaml`: `onboard.unified_password`, `email_code_mode: browser_then_imap` или `imap`
- [ ] Gmail **app password** в Excel `email_password`
- [ ] `geo` и proxy (если есть) согласованы
- [ ] Preflight onboard без **error** (в т.ч. `imap_login` на первой pending-строке)

## 2. Dry-run

```bash
tiktok-publisher onboard-plan
tiktok-publisher onboard --dry-run
```

## 3. Один аккаунт live

- [ ] `onboard` на одной строке «Онбординг»
- [ ] При ошибке: `logs/onboard_row*.png`, `data/onboard_trace.jsonl`
- [ ] Капча/OTP: UI «Продолжить (OTP)»

## 4. Файлы для правки селекторов

| UI | Файл |
|----|------|
| TikTok login/password/verify/avatar | `config/selectors_onboard.yaml` |
| Gmail web | `config/selectors_webmail.yaml` |
| FYP прогрев | `config/selectors_warmup.yaml` |

## 5. После «готов»

- [ ] Строка в «Аккаунты», `video_folder`, `active=да`
- [ ] Preflight publish → Старт (при необходимости warmup `preset: safe`)

## 6. Типичные сбои

| Симптом | Действие |
|---------|----------|
| `imap_login` fail | App password, IMAP enabled in Gmail |
| verify field not shown | XPath `password_verify_code` |
| login not confirmed | `logged_in_indicator` |
| CDP disconnect | Автоматический retry сессии (1 раз) |
