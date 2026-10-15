# TikTok Publisher

Локальная автопубликация TikTok через **Dolphin Anty**: один **Excel**-реестр, папки с видео, **Старт** в веб-интерфейсе.

## Требования

- Windows (Dolphin Anty + Local API)
- Python 3.11+
- Dolphin Anty запущен, в каждом профиле — ручной вход в TikTok

## Установка

```bash
pip install -e ".[dolphin,dev]"
tiktok-publisher doctor
```

Скопируйте настройки:

```bash
copy config\settings.example.yaml config\settings.yaml
copy config\accounts.template.xlsx config\accounts.xlsx
```

Заполните `config/accounts.xlsx` (лист **Аккаунты**). Пример колонок — [`docs/EXCEL_SPEC.ru.md`](docs/EXCEL_SPEC.ru.md).

## Dolphin Anty

1. Создайте профиль на аккаунт (прокси, fingerprint).
2. Откройте профиль, войдите в TikTok.
3. Скопируйте **Profile ID** в колонку `dolphin_profile_id` в Excel.

Программа на один блок `videos_per_run` для строки Excel: **один** start profile → до N загрузок подряд (один CDP) → **stop profile**.

При `max_concurrent_profiles: K` (K>1) несколько аккаунтов идут параллельно; внутри аккаунта порядок по-прежнему последовательный.

## Запуск

```bash
tiktok-publisher serve
```

Откройте http://127.0.0.1:8765 — **Старт** / **Стоп** / **Скачать отчёт**.

Тест без TikTok:

```yaml
# config/settings.yaml
dry_run: true
```

```bash
tiktok-publisher start --dry-run
```

## Поведение

- **Sequential:** сначала `videos_per_run` роликов для первой активной строки, затем для второй и т.д.
- **Подпись:** случайный вариант из `caption_variants` (`|||`).
- **После успеха:** файл в `video_folder/posted/`; при ошибке и `skip_failed_file: true` — в `failed/`.
- **Отчёт:** `data/reports/report_<run_id>.xlsx` (лист **Метрики**: posts_per_hour, длительность).
- **Скорость:** `orchestrator.speed_preset` — `safe` / `normal` / `fast` (паузы между постами) или `custom` (свои `delay_between_posts_sec`).

## CLI

| Команда | Описание |
|---------|----------|
| `serve` | Веб-UI |
| `start --dry-run` | Прогон в консоли |
| `doctor` | Проверка Excel, папок, Dolphin |
| `report --run last` | Путь к последнему отчёту |
| `plan` | План прогона (очереди, total_slots) без публикации |
| `smoke --profile-id ID` | Проверка Dolphin: start → CDP → stop |

## Документация

- [`docs/PLAN.ru.md`](docs/PLAN.ru.md) — архитектура
- [`docs/EXCEL_SPEC.ru.md`](docs/EXCEL_SPEC.ru.md) — формат Excel
