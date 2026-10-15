# Прогрев FYP (warmup v2)

## Поведение

- Отдельная вкладка `/foryou` (не первая вкладка профиля).
- Закрытие login-modal (`dismiss_login` в `selectors_warmup.yaml`).
- **Watch time** — пауза 3–12 сек (preset `safe` длиннее) перед каждым скроллом.
- Скролл: wheel + ArrowDown, иногда ArrowUp (`scroll_up_probability`).
- Случайные движения мыши между роликами.
- Лайки с вероятностью `like_probability` (в preset `safe` ниже).

## Настройки

```yaml
session:
  order: warmup_then_publish
  warmup:
    preset: normal   # safe | normal
    scroll_count_min: 5
    scroll_count_max: 12
    watch_time_sec: { min: 3, max: 12 }
    scroll_up_probability: 0.08
```

При `warmup_fail_blocks_publish: true` сбой прогрева (нет входа / капча) отменяет upload в этой сессии.

## Калибровка

Обновите `config/selectors_warmup.yaml` под ваш UI TikTok. Рекомендуется `max_concurrent_profiles: 1` при прогреве.
