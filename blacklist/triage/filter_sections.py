#!/usr/bin/env python3
"""Разбор остальных коробок в том же формате, что парсеры."""

from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

KEEP = Path(__file__).resolve().parent / "keep"
GITHUB_RE = re.compile(r"^https?://github\.com/[^/]+/[^/#?]+", re.I)

SECTIONS = {
    "рассылка": "рассылка.txt",
    "стилер": "стилер.txt",
    "авторегер": "авторегер.txt",
    "качалка": "качалка.txt",
    "бот": "бот.txt",
    "софт": "софт.txt",
    "кряк_чит": "кряк_чит.txt",
    "скил_mcp": "скил_mcp.txt",
}


def load_items(name: str) -> list[str]:
    path = KEEP / name
    return [ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")]


def github_alive(url: str) -> bool:
    match = GITHUB_RE.match(url.strip().rstrip("/"))
    if not match:
        return False
    request = urllib.request.Request(
        match.group(0), method="HEAD", headers={"User-Agent": "catalog-liveness-check"}
    )
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


def first_match(item: str, rules: list[tuple[re.Pattern[str], str, bool]]) -> tuple[str, bool]:
    for pattern, why, keep in rules:
        if pattern.search(item):
            return why, keep
    return "по имени из коробки, цель узкая или неясна", True


RULES: dict[str, list[tuple[re.Pattern[str], str, bool]]] = {
    "рассылка": [
        (re.compile(r"whatsender|whatsapp", re.I), "рассылка в WhatsApp (есть No-Trial — ещё и в кряках)", True),
        (re.compile(r"sms.?enabler", re.I), "кряк SMS-программы: отправка SMS", True),
        (re.compile(r"mailer|email-sender|massmail", re.I), "массовые письма на почту", True),
        (re.compile(r"mass.?dm|auto.?mass.?dm", re.I), "массовые лички в мессенджере", True),
    ],
    "стилер": [
        (re.compile(r"stealer|browser-data-grabber", re.I), "забрать пароли/данные браузера", True),
    ],
    "авторегер": [
        (re.compile(r"joiner|token", re.I), "зайти в Discord пачкой по токену", True),
    ],
    "качалка": [
        (re.compile(r"vscode-extension|Enterprise-Download|ACDSee|Ninja-Ripper|Remote-Desktop-Manager", re.I), "скачать программу, не контент с сайта", False),
        (re.compile(r"AdoptME-Script-Download", re.I), "скачать скрипт к игре, не качалка веба", False),
        (re.compile(r"youtube|mp3|mp4|playlist|music-download|Downloadify|rekordbox-spotify", re.I), "скачать видео/музыку с YouTube или Spotify", True),
        (re.compile(r"pixiv|image|gallery|manga|smugmug|kodi|Bulk-Image", re.I), "скачать картинки/мангу пачкой", True),
        (re.compile(r"telegram", re.I), "скачать медиа из Telegram", True),
        (re.compile(r"slideshare|pesu-slide|takeout", re.I), "скачать слайды или архив Google Takeout", True),
        (re.compile(r"dab-downloader|RemoteDownloaderPHP|phoenix-downloader", re.I), "качалка без ясной цели", True),
    ],
    "бот": [
        (re.compile(r"awesome-telegram-bots|awesome-lark-bots|mastodon-bots|Bot-n-animado", re.I), "список или картинка, не рабочий бот", False),
        (re.compile(r"LibString|soil-moisture|dizhi|gonopbx|Fire-Fighting-Bot|Merge-bot-Gui", re.I), "слово bot в нике или не тот смысл", False),
        (re.compile(r"block-bots|iot-botnet|Botnet|botguard", re.I), "антибот / ботнет-симулятор, не бот-помощник", False),
        (re.compile(r"chatbot|rag-chat|ai-chatbot|AI-Chatbot|Mental-Health-Chatbot|NEWS-Chatbot|faq-order", re.I), "чат-бот / отвечает на вопросы", True),
        (re.compile(r"userbot|telegram|whatsapp|weixin|zalo|discord-translator|discord-gatekeeper|Discord-Twitch|Serializd-Discord|agent-telegram|tele-bot|giveaway-lottery", re.I), "бот в мессенджере (Telegram/WhatsApp/Discord)", True),
        (re.compile(r"trad|polymarket|kalshi|bnb|airdrop|mev|copy.?trad|arbitrage|pumpfun|raydium|hyperliquid|solana|memecoin|sniper|volume-bot|fourmeme|dex-|mt4|kucoin|bitquant|xstocks", re.I), "торговля и крипта: сам ставит сделки", True),
        (re.compile(r"youtube-like|linkedin-easyapply|instagram|Quora|TikTok-Report|bluesky", re.I), "накрутка / автодействия в соцсетях", True),
        (re.compile(r"minecraft|fortnite|hamster|roblox|mir4|pinball|free-fire|R6-Recoil|Pig-Card|Hamster", re.I), "бот в игре: фарм, кликер, AFK", True),
        (re.compile(r"music-bot|ffmpeg-video|spotify-playlist|Expense-Tracker|outlook-selenium|Email-Automation", re.I), "бытовой бот: музыка, почта, расходы", True),
    ],
    "софт": [
        (re.compile(r"dataset|anti-spoofing-dataset|Noise-Injection-Techniques|Finetune-your-notes", re.I), "датасет или заметки, не программа", False),
        (re.compile(r"fact-checker|Fake-News-Detector|plugin-health-monitor|File-Integrity-Checker|sql-injection-attack-detection|ARP-Spoofing-Detection", re.I), "проверка/детектор, учебный софт", False),
        (re.compile(r"wordpress-plugin-boilerplate|Hytale-Example-Plugin|oci-plugin-example|plugin.video.netflix|obsidian|strapi-plugin|intellij|vite-plugin|koplugin|TraversalNavigation", re.I), "плагин к чужой программе (сайт, IDE, плеер)", True),
        (re.compile(r"QuasarRAT|NullRAT|gorat|Android-RAT|/rat$|airat", re.I), "удалённое управление чужим ПК", True),
        (re.compile(r"Eth-Miner|smart-money-miner|MinerU", re.I), "майнер или «miner» в имени", True),
        (re.compile(r"CVV-checker|TDataChecker|CryptoChecker|OFFICE-CHECKER|domain-checker|proxy-multi-protocol-checker|WebSocketChecker|brute_it|Wordpress-Bruter|ssh-brute", re.I), "чекер / перебор аккаунтов или карт", True),
        (re.compile(r"bypass|inject|exploit|spoof|payload|UAC-Bypass|CAPTCHA-Bypass|SSL-Bypass|SQL-Injector|SQLVuln|kexploit|Executor-Injector", re.I), "обход защиты / inject / exploit по имени", True),
        (re.compile(r"activation-toolkit|Installer|Uninstaller|Updater-Releases|sailarr-installer", re.I), "установщик или активатор", True),
        (re.compile(r"toolkit|plugin|hackingtool", re.I), "набор инструментов / плагин", True),
    ],
    "кряк_чит": [
        (re.compile(r"cheatsheet|cheat-sheet|CodeTrainer|SQL-Trainer|pid-trainer|anticrack|WebSecurityCheatSheet", re.I), "шпаргалка или тренажёр по коду, не кряк", False),
        (re.compile(r"Hash_crack|AuthCrack|crackwifi|WhiteBoxAesCrack", re.I), "взлом хеша/пароля/протокола, не «скачать VMware»", True),
        (re.compile(r"vegas-pro-version|aseprite-pixel-art-editor|adobe-photoshop-version|adobe-premiere", re.I), "кряк/дамп редактора (видео, пиксель, Adobe)", True),
        (re.compile(r"no-trial|nulled|premium-unlock|activation-unlocked|DLC-Unlocker|unlocker|Professional-Crack|_Crack", re.I), "платная программа без оплаты (No-Trial / Unlock)", True),
        (re.compile(r"cheat|trainer|aim|esp|loot-drop|Auto-Farm-Clicker|Hack-Game|glyphx|APEX", re.I), "чит или трейнер к игре", True),
    ],
    "скил_mcp": [
        (re.compile(r"kaspersky|tdsskiller", re.I), "установщик антивируса, не скил", False),
        (re.compile(r"from-scratch|claude-code-book|awesome-claude-code", re.I), "книга/курс про Claude, не рабочий скил", False),
        (re.compile(r"\bmcp\b|mcp-", re.I), "MCP: ИИ подключается к сервису или базе", True),
        (re.compile(r"openclaw|clawhub|cllawhub|clawwhub", re.I), "скил/клиента OpenClaw", True),
        (re.compile(r"skill|claude|agent-skill|dotskills", re.I), "скил для Claude/Cursor: надстройка «умею вот это»", True),
    ],
}


def classify(section: str, item: str) -> tuple[str, bool]:
    if not item.startswith("http") and "github.com" not in item.lower():
        if "/" in item and not item.startswith("http"):
            return "неполный указатель owner/repo, не готовая ссылка", False
        return "голое имя без ссылки, открыть некуда", False
    return first_match(item, RULES[section])


def write_md(section: str, title: str, can_do: str, rows: list[tuple[str, str, bool, bool]]) -> None:
    keep_live = [r for r in rows if r[2] and r[3]]
    not_fit = [r for r in rows if not r[2]]
    dead = [r for r in rows if r[2] and not r[3]]
    by_why: dict[str, list[str]] = {}
    for url, why, keep, ok in keep_live:
        by_why.setdefault(why, []).append(url)

    lines = [
        f"# {title}: что именно и что реально могут",
        "",
        "Проверил ссылку (открывается ли GitHub). Код не запускал.",
        "«Могут» = по названию. В этой кампании внутри ZIP иногда стилер, не обещанный софт.",
        "",
        f"Всего в коробке: {len(rows)}",
        f"По делу, ссылка открывается: **{len(keep_live)}**",
        f"Не этот функционал: {len(not_fit)}",
        f"Ссылка мёртвая: {len(dead)}",
        "",
        f"Что обещают уметь: {can_do}",
        "",
        "## Живые, по делу",
        "",
    ]
    if not by_why:
        lines.append("Пусто.")
        lines.append("")
    for why, urls in sorted(by_why.items(), key=lambda x: (-len(x[1]), x[0])):
        lines.append(f"### {why} ({len(urls)})")
        lines.append("")
        for url in urls:
            lines.append(f"- {url}")
        lines.append("")
    lines += ["## Не этот функционал — из коробки убрал", "",]
    if not not_fit:
        lines.append("Нет.")
        lines.append("")
    for url, why, _, ok in not_fit:
        status = "ссылка живая" if ok else "ссылка мёртвая / нет URL"
        lines.append(f"- {url} — {why} ({status})")
    lines += ["", "## Мёртвые (404 или нет страницы)", ""]
    if not dead:
        lines.append("Нет.")
        lines.append("")
    for url, why, _, _ in dead:
        lines.append(f"- {url} — {why}")
    lines.append("")
    (KEEP / f"{section}-разбор.md").write_text("\n".join(lines), encoding="utf-8")
    (KEEP / f"{section}.txt").write_text("\n".join(sorted(r[0] for r in keep_live)) + ("\n" if keep_live else ""), encoding="utf-8")
    (KEEP / f"{section}-убрано.txt").write_text(
        "\n".join(f"{r[0]}\t{r[1]}" for r in not_fit + dead) + ("\n" if not_fit or dead else ""),
        encoding="utf-8",
    )
    return len(keep_live), len(not_fit), len(dead)


def main() -> None:
    all_urls: list[str] = []
    for fname in SECTIONS.values():
        all_urls.extend(x for x in load_items(fname) if x.startswith("http"))
    parsers = load_items("парсер.txt")
    all_urls.extend(parsers)

    alive: dict[str, bool] = {}
    uniq = sorted(set(all_urls))
    print(f"checking {len(uniq)} urls")
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = {pool.submit(github_alive, url): url for url in uniq}
        for fut in as_completed(futs):
            alive[futs[fut]] = fut.result()

    titles = {
        "рассылка": ("Рассылки", "отправить много писем или сообщений"),
        "стилер": ("Стилеры", "забрать сохранённые пароли и данные с чужого ПК"),
        "авторегер": ("Авторегер", "зайти пачкой в сервис без ручной регистрации"),
        "качалка": ("Качалки", "скачать с сайта пачку файлов (видео, картинки, чаты)"),
        "бот": ("Боты", "крутятся сами: торгуют, пишут в чат, фармят, жмут кнопки"),
        "софт": ("Прочий софт", "плагины, чекеры, обход, удалёнка, установщики"),
        "кряк_чит": ("Кряки и No-Trial", "платная программа без оплаты или чит к игре"),
        "скил_mcp": ("Скилы и MCP", "надстройка для ИИ: подключить умение или сервис"),
    }
    counts = {"парсер": len(parsers)}
    kept_urls = set(parsers)
    for section, fname in SECTIONS.items():
        items = load_items(fname)
        # backup once
        backup = KEEP / f"{section}-было.txt"
        if not backup.exists():
            backup.write_text("\n".join(items) + "\n", encoding="utf-8")
        rows = []
        for item in items:
            why, keep = classify(section, item)
            ok = alive.get(item, False) if item.startswith("http") else False
            rows.append((item, why, keep, ok))
        title, can_do = titles[section]
        live_n, _, _ = write_md(section, title, can_do, rows)
        counts[section] = live_n
        kept_urls.update(r[0] for r in rows if r[2] and r[3])
        print(f"{section}: keep_live={live_n} / {len(items)}")

    (KEEP / "programs-and-skills-urls.txt").write_text("\n".join(sorted(kept_urls)) + "\n", encoding="utf-8")
    stats = [
        "убраны_сайты_1а=да",
        "код_не_запускали=да",
        f"программ_скилов_осталось={len(kept_urls)}",
        f"парсер={counts['парсер']}",
        f"рассылка={counts['рассылка']}",
        f"стилер={counts['стилер']}",
        f"авторегер={counts['авторегер']}",
        f"качалка={counts['качалка']}",
        f"бот={counts['бот']}",
        f"софт={counts['софт']}",
        f"кряк_чит={counts['кряк_чит']}",
        f"скил_mcp={counts['скил_mcp']}",
        "",
    ]
    (KEEP / "STATS.txt").write_text("\n".join(stats), encoding="utf-8")
    print("\n".join(stats))


if __name__ == "__main__":
    main()
