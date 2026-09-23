# Чёрный список для вычистки каталога

Снимок **23 сентября 2026**. Это не «все ссылки интернета». Это максимум, который сейчас можно честно собрать из открытых фидов.

## Цифры без прикрас

| Слой | Файл | Записей |
| --- | --- | ---: |
| Skills / MCP / парсеры | `agentbaiting-skills-mcp-parsers.txt` | 613 |
| FakeGit репозитории | `worldwide/github-repos.txt` | 7 654 |
| Ядро IOC | `worldwide/domains-core.txt.gz` | 270 965 |
| Запрещённые + зеркала (РКН/antifilter) | `worldwide/banned-rkn-mirrors.txt.gz` | **1 687 056** |
| Все уникальные домены | `worldwide/domains.txt.gz` | **7 030 450** |
| URL | `worldwide/urls.txt.gz` | 950 606 |

Новых доменов после прошлого прохода: **+2 369 693**.

## Как прогнать ваш большой список

```bash
# максимум
python3 blacklist/filter-list.py my-list.txt --mode full --kept kept.txt --removed removed.txt

# только запрещённые/зеркала + ядро IOC
python3 blacklist/filter-list.py my-list.txt --mode banned --kept kept.txt --removed removed.txt

# только malware/phishing/ЦБ, без lordfilm/казино
python3 blacklist/filter-list.py my-list.txt --mode core --kept kept.txt --removed removed.txt
```

## Что добавлено сейчас

- Публичный дамп **zapret-info/z-i** (реестр блокировок РФ, дата дампа **2025-10-01**)
- **antifilter.download** — 1.66M строк, зеркала lordfilm, казино, пиратские площадки
- **re:filter** `domains_all.lst`
- nxdomain-записи (уже закрытые/мёртвые запрещённые домены)
- Blocklist Project: piracy, abuse, fraud, gambling, redirect
- StevenBlack hosts (gambling/porn/fakenews)
- HaGeZi badware hoster

## Чего нет и не будет из открытого доступа

- Официальный операторский дамп РКН с vigruzki.rkn.gov.ru — нужен сертификат оператора связи. Его нет.
- Живые зеркала, которых ещё нет ни в одном дампе. Их нельзя «предугадать».
- Закрытые Telegram-витрины, личные Google Docs, Discord-сервера без публичного IOC.
- Платные полные выгрузки ThreatFox / PhishTank без ключа.
- Списки обхода блокировок уровня «разблокировать Instagram/Twitter/JetBrains» — это обычные сервисы, не malware. Их сознательно не клал в чёрный список.

Если в вашем файле есть зеркало, которого нет в этих 7 млн доменов, его нет в публичных реестрах на дату снимка. Тогда пришлите сам файл — отфильтрую точечно и по паттернам (`lordfilm*`, `*-mirror*`, и т.д.).
