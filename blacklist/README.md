# Чёрный список вредоносных Skills / MCP / «парсеров» (сентябрь 2026)

Это не выдуманный каталог на 600 случайных сайтов. Это **официальный срез** кампании **FakeGit / AgentBaiting** плюс подтверждённые IOC соседних кампаний. Island зафиксировала **более 600** вредоносных карточек Skills и MCP в публичных каталогах — ровно тот порядок чисел, который вы описали.

Если другой ИИ выдал вам «базу из 1000+ сервисов», с высокой вероятностью туда попали эти репозитории. Их нужно **удалить и не открывать**.

## Что удалять в первую очередь

| Файл | Сколько | Что это |
| --- | ---: | --- |
| `agentbaiting-skills-mcp-parsers.txt` | **613** | GitHub URL фейковых Skills, MCP, парсеров, Claude/OpenClaw-приманок |
| `agentbaiting-owner-repo.txt` | 613 | Тот же список в виде `owner/repo` |
| `agentbaiting-skills-mcp-parsers.csv` | 613 | URL + теги + SHA-256 вредоносного ZIP |
| `clawhavoc-skill-names.txt` | ~80 | Имена вредоносных OpenClaw/ClawHub skills и авторов |
| `extra-malware-domains-2026.txt` | ~20 | Домены фейковых установщиков ChatGPT/Claude и C2 |

Полный список Island — **7854** вредоносных репозитория (не только AI):  
https://github.com/island-io/island-security-research-artifacts/blob/main/agentbaiting/malicious-repositories-and-zip-hashes-2026-07.csv

## Как прогнать свою базу

Положите свой список в `my-list.txt` (по одной ссылке или строке) и выполните:

```bash
python3 blacklist/filter-list.py my-list.txt --kept kept.txt --removed removed.txt
```

Скрипт только сравнивает строки с чёрным списком. Он ничего не скачивает и не запускает.

## Почему эти ссылки опасны

Кампания подсовывает репозиторий, который выглядит как Skill, MCP-сервер или парсер. README просит скачать ZIP/EXE и «просто запустить». Внутри — **SmartLoader → StealC** (или Atomic Stealer для OpenClaw). Цель — украсть сессии браузера, пароли, API-ключи, кошельки.

Типичные признаки, по которым строку надо удалять сразу:

- просят скачать `.zip` / `.exe` и нажать «Run anyway»;
- пароль на архив «для распаковки»;
- внутри `application.cmd` + `luau.exe` / `lua51.dll` + `.txt`;
- аккаунт GitHub отличается на одну букву от известного автора;
- карточка живёт на LobeHub / Glama / MCP.so / MCP Market / ClawHub, а исходник — свежий GitHub с чужим README.

Каталоги выше **не являются вредоносным ПО сами по себе**, но они уже индексировали сотни заражённых карточек. Наличие записи в каталоге — не доказательство безопасности.

## Что нельзя принимать за «безопасный сервис»

- Любой «бесплатный Walmart/Gmail/WhatsApp/Databricks MCP».
- Любой «awesome-claude-skills» не от официального издателя. Настоящий каталог: `ComposioHQ/awesome-claude-skills`. Подделка: `Mann1988/awesome-claude-skills`.
- Любой «parser / scraper / OSINT toolkit» с готовым Windows-инсталлятором.
- Фейковые загрузчики ChatGPT/Claude: `openew.app`, `download-version.1-5-8.com`.
- Typosquat-скилы ClawHub: `clawhubb`, `clawhubcli`, `cllawhub` и т.п.

Перед установкой OpenClaw-скила проверяйте имя в Clawdex: https://clawdex.koi.security/

## Если вы уже открывали такие ссылки

1. Не запускайте скачанные ZIP/EXE.
2. Если уже запускали — отключите машину от сети, смените пароли **после** очистки, отзовите сессии браузера, OAuth, API-токены и облачные ключи. Смены пароля недостаточно: StealC забирает живые сессии.
3. Проверьте GitHub/npm/Telegram-сессии и криптокошельки.

## Источники (актуальность: 2026)

- Island, 20 июля 2026: [AgentBaiting](https://www.island.io/blog/agentbaiting-how-800-fake-ai-skills-and-mcp-servers-delivered-malware)
- Island IOC CSV: [malicious-repositories-and-zip-hashes-2026-07.csv](https://github.com/island-io/island-security-research-artifacts/blob/main/agentbaiting/malicious-repositories-and-zip-hashes-2026-07.csv)
- Koi, февраль 2026: [ClawHavoc, 341 → 824 вредоносных skills](https://www.koi.ai/blog/clawhavoc-341-malicious-clawedbot-skills-found-by-the-bot-they-were-targeting)
- Trend Micro: [OpenClaw / Atomic Stealer IOC](https://www.trendmicro.com/content/dam/trendmicro/global/en/research/26/b/amos-stealer-openclaw/ioc-malicious-openclaw-skills-used-to-distribute-atomic-macos-stealer.txt)
- Push Security / Evalian: фейковый установщик ChatGPT `openew.app`
- Rapid7: фейковый установщик Claude `download-version.1-5-8.com`

Пришлите свой файл со 1000+ ссылками — можно прогнать его против этого списка точечно.
