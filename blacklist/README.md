# Чёрный список вредоносных сервисов (сентябрь 2026)

Сначала здесь были **613** фейковых Skills/MCP/парсеров. Теперь добавлен мировой слой: фишинг, стилеры, фейковые установщики, финансовые пирамиды ЦБ, Discord/crypto-скамы и все репозитории FakeGit.

Это список **для удаления**. Ссылки из него не открывать и не устанавливать.

## Сколько записей сейчас

| Слой | Файл | Записей | Смысл |
| --- | --- | ---: | --- |
| Skills / MCP / парсеры | `agentbaiting-skills-mcp-parsers.txt` | **613** | точный срез Island под ИИ-скилы |
| Все FakeGit репозитории | `worldwide/github-repos.txt` | **7 654** | SmartLoader/StealC на GitHub |
| Ядро (высокое качество) | `worldwide/domains-core.txt.gz` | **270 965** | URLhaus, ThreatFox, ЦБ РФ, CERT.PL, Phishing Army, C2 |
| Максимум по миру | `worldwide/domains.txt.gz` | **4 660 757** | ядро + HaGeZi TIF + Blocklist Project + Phishing.Database + Discord/Polkadot scams |
| Свежие вредоносные URL | `worldwide/urls.txt.gz` | **147 509** | OpenPhish, URLhaus, phishing-filter |
| Кампании 2026 | `worldwide/campaign-domains.txt` | **60+** | фейковые ChatGPT/Claude/Ghidra/dnSpy установщики |

Снимок собран **23 сентября 2026**.

## Как прогнать большой список

```bash
# максимум совпадений по миру
python3 blacklist/filter-list.py my-list.txt --mode full --kept kept.txt --removed removed.txt

# только более чистые официальные фиды (меньше ложных срабатываний)
python3 blacklist/filter-list.py my-list.txt --mode core --kept kept.txt --removed removed.txt
```

Скрипт ничего не скачивает. Он только сравнивает хосты, GitHub `owner/repo` и известные URL.

## Что здесь закрыто сверх прошлого списка

- Весь Island FakeGit, не только AI: **7 654** репозитория
- Реестр ЦБ РФ по финансовым пирамидам и нелегальным участникам рынка
- Активный фишинг: OpenPhish, Phishing Army, CERT.PL, mitchellkrog Phishing.Database
- Malware URL/C2: URLhaus, ThreatFox, C2IntelFeeds
- HaGeZi Threat Intelligence Feeds + Fake sites
- Discord AntiScam и Polkadot phishing deny-list
- Фейковые загрузчики инструментов: `ghidralite.com`, `dnspy.org`, `ilspy.org`, `openew.app`, `download-version.1-5-8.com`

## Осторожно

`full` специально максимальный. В Blocklist Project и похожих фидах бывают ложные срабатывания. Если вычистится слишком много легитимных сервисов — перезапустите с `--mode core`.

Каталоги LobeHub / Glama / MCP.so / MCP Market / ClawHub сами по себе не malware, но они уже индексировали сотни заражённых карточек. Не считайте запись в каталоге доказательством безопасности.

Перед OpenClaw-скилом проверяйте имя в Clawdex: https://clawdex.koi.security/

Источники: `SOURCES.txt` и `worldwide/STATS.txt`.
