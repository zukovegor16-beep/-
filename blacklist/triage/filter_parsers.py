#!/usr/bin/env python3
from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SRC = Path("/workspace/blacklist/triage/keep/парсер.txt")
OUT = Path("/workspace/blacklist/triage/keep")
GITHUB_RE = re.compile(r"^https?://github\.com/[^/]+/[^/#?]+", re.I)

# Не веб-сборщик: парсит файл/протокол, не сайт.
NOT_WEB = [
    (re.compile(r"sql-parser|jsoup-html-parsing|Golang-html-parsing|markdown-ui-dsl", re.I), "разбор кода/разметки, не сайт"),
    (re.compile(r"dmarc-parser|EEWParser|vrscene-parser|07-fpga-itch-parser|cryptoschema-extractor", re.I), "разбор формата/протокола, не сайт"),
    (re.compile(r"PDF-Highlight-Extractor|OCR-Document-parser|rag-ready-extractor|n8n-Parse-Invoices", re.I), "разбор своего файла/документа, не чужой сайт"),
    (re.compile(r"ai-resume-parser|ResumeParser", re.I), "разбор резюме-файла, не сайт"),
]

WEB = [
    (re.compile(r"google-images|lightning-image|scrappe-tout", re.I), "картинки с веба"),
    (re.compile(r"youtube|tubescrape|video-scraping", re.I), "YouTube / видео"),
    (re.compile(r"linkedin", re.I), "LinkedIn: вакансии или Sales Navigator"),
    (re.compile(r"facebook", re.I), "Facebook: события, подписки, маркет, хештеги"),
    (re.compile(r"instagram|linktree", re.I), "Instagram / Linktree"),
    (re.compile(r"amazon|myntra|g2-reviews|rebecca-minkoff|e-commerce|Web-Scraper-for-E-commerce", re.I), "магазины и отзывы"),
    (re.compile(r"immobiliare|autoscout|savills|auction|marketplace", re.I), "объявления: жильё, авто, аукцион"),
    (re.compile(r"google-news|Indian-Express|osint-feed", re.I), "новости"),
    (re.compile(r"osint|cosint|maltego|Brahmastra|D4rk_Intel|TotalOSINT|blueosint", re.I), "OSINT-набор"),
    (re.compile(r"attorney|oab|cna-oab", re.I), "справочник адвокатов"),
    (re.compile(r"postal-code|correos", re.I), "почтовые индексы"),
    (re.compile(r"hospital|krankenhaus", re.I), "справочник больниц"),
    (re.compile(r"divesite|divessi", re.I), "каталог дайв-сайтов"),
    (re.compile(r"telegram-gift|Telegram-Gift", re.I), "подарки в Telegram"),
    (re.compile(r"youtube-email", re.I), "почты с YouTube"),
    (re.compile(r"whatsapp-chat", re.I), "чат WhatsApp + скрейп"),
    (re.compile(r"CookieExtractor", re.I), "достать cookies (это уже не обычный парсер)"),
    (re.compile(r"github\.com.*follows|boyfriend", re.I), "подписки на GitHub"),
    (re.compile(r"recruit|on3-recruit", re.I), "спортивный рекрутинг"),
    (re.compile(r"blockchain-data", re.I), "данные блокчейна"),
    (re.compile(r"gsa-elibrary", re.I), "библиотека GSA"),
    (re.compile(r"flarecrawl|librecrawl|imperium-crawl|spa-crawler|scraping-browser|scrape-rs|Scrapy|LongParser|partnershipparser|Scrapstyle|scraped|crawlbase", re.I), "универсальный краулер без узкой цели"),
]


def github_alive(url: str) -> bool:
    match = GITHUB_RE.match(url.strip())
    if not match:
        return url.endswith("youtube-thumbnail-grabber") is False and False
    page = match.group(0)
    request = urllib.request.Request(page, method="HEAD", headers={"User-Agent": "catalog-liveness-check"})
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=8, context=context) as response:
            return 200 <= response.status < 400
    except urllib.error.HTTPError as error:
        if error.code in {403, 405}:
            request.method = "GET"
            request.add_header("Range", "bytes=0-0")
            try:
                with urllib.request.urlopen(request, timeout=8, context=context) as response:
                    return 200 <= response.status < 400
            except Exception:
                return False
        return False
    except OSError:
        return False


def classify(item: str) -> tuple[str, str]:
    for pat, why in NOT_WEB:
        if pat.search(item):
            return "не_сайт", why
    for pat, why in WEB:
        if pat.search(item):
            return "сайт", why
    return "сайт", "сборщик по имени, цель неясна"


def main() -> None:
    items = [ln.strip() for ln in SRC.read_text().splitlines() if ln.strip()]
    alive = {}
    to_check = [i for i in items if i.startswith("http")]
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = {pool.submit(github_alive, i): i for i in to_check}
        for fut in as_completed(futs):
            alive[futs[fut]] = fut.result()
    # голые имена без URL
    for i in items:
        if i not in alive:
            alive[i] = False

    rows = []
    for item in items:
        kind, why = classify(item)
        rows.append((item, kind, why, alive.get(item, False)))

    web_live = [r for r in rows if r[1] == "сайт" and r[3]]
    web_dead = [r for r in rows if r[1] == "сайт" and not r[3]]
    not_web = [r for r in rows if r[1] == "не_сайт"]

    def dump(path, subset):
        lines = [f"{url}\t{why}" for url, _, why, _ in subset]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    dump(OUT / "парсер-сайт-живые.txt", web_live)
    dump(OUT / "парсер-сайт-мертвые.txt", web_dead)
    dump(OUT / "парсер-не-сайт.txt", not_web)

    by_why = {}
    for url, kind, why, ok in web_live:
        by_why.setdefault(why, []).append(url)

    md = [
        "# Парсеры: что именно и что могут",
        "",
        "Проверил ссылку (открывается ли GitHub). Код не запускал.",
        "«Могут» = по названию. В этой кампании внутри ZIP иногда стилер, не сборщик.",
        "",
        f"Всего в коробке: {len(items)}",
        f"Сборщики сайтов, ссылка живая: {len(web_live)}",
        f"Сборщики сайтов, ссылка мёртвая: {len(web_dead)}",
        f"Не сборщики сайтов (файл/протокол/резюме): {len(not_web)}",
        "",
        "## Живые сборщики сайтов",
        "",
    ]
    for why, urls in sorted(by_why.items(), key=lambda x: (-len(x[1]), x[0])):
        md.append(f"### {why} ({len(urls)})")
        md.append("")
        md.append("Что могут: забрать с указанного места список (товары, посты, объявления) в файл.")
        md.append("")
        for url in urls:
            md.append(f"- {url}")
        md.append("")
    md += [
        "## Не сборщики чужого сайта",
        "",
        "Слово parser есть, но это разбор своего файла или протокола.",
        "",
    ]
    for url, _, why, ok in not_web:
        status = "ссылка живая" if ok else "ссылка мёртвая"
        md.append(f"- {url} — {why} ({status})")
    md += ["", "## Мёртвые сборщики (404)", ""]
    for url, _, why, _ in web_dead:
        md.append(f"- {url} — {why}")
    md.append("")
    (OUT / "парсер-разбор.md").write_text("\n".join(md), encoding="utf-8")
    print(f"web_live={len(web_live)} web_dead={len(web_dead)} not_web={len(not_web)}")
    for why, urls in sorted(by_why.items(), key=lambda x: -len(x[1])):
        print(f"  {len(urls):3} {why}")


if __name__ == "__main__":
    main()
