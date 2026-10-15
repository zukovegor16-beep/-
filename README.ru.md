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

Программа при публикации: **start profile** → Patchright CDP → upload → **stop profile**.

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
- **После успеха:** файл в `video_folder/posted/`.
- **Отчёт:** `data/reports/report_<run_id>.xlsx`.

## CLI

| Команда | Описание |
|---------|----------|
| `serve` | Веб-UI |
| `start --dry-run` | Прогон в консоли |
| `doctor` | Проверка Excel, папок, Dolphin |
| `report --run last` | Путь к последнему отчёту |

## Документация

- [`docs/PLAN.ru.md`](docs/PLAN.ru.md) — архитектура
- [`docs/EXCEL_SPEC.ru.md`](docs/EXCEL_SPEC.ru.md) — формат Excel
