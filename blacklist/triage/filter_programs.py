#!/usr/bin/env python3
"""Оставить программы/скилы. Убрать сайты вроде lordfilm. Исходники не удаляет."""

from __future__ import annotations

import gzip
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "keep"

# Сначала узкие типы, потом общее «софт».
KEEP_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("стилер", re.compile(r"stealer|infosteal|keylog|cookie.?steal|browser-data-grabber|crypto.?clipper|grab.?cookie", re.I)),
    ("рассылка", re.compile(r"mailer|mass.?mail|bulk.?mail|smtp|multi-email-sender|whatsender|sms.?blast|spammer|newsletter", re.I)),
    ("авторегер", re.compile(r"autoreg|auto.?reg|account.?gen|acc.?gen|joiner|follower.?bot|nacrut", re.I)),
    ("парсер", re.compile(r"pars|scrap|crawler|crawl|osint|grabber|harvester|extractor", re.I)),
    ("скил_mcp", re.compile(r"\bmcp\b|mcp-|skill|openclaw|claude-|claude_code|agent-skill|composio", re.I)),
    ("кряк_чит", re.compile(r"crack|cheat|keygen|trainer|unlock|nulled|license.?bypass|no-trial|no.?trial", re.I)),
    ("качалка", re.compile(r"download|yt-?dl|ytdlp|youtube-video|torrent.?client|magnet", re.I)),
    ("бот", re.compile(r"userbot|telegram-bot|discord-bot|chatbot|\bbot\b|-bot", re.I)),
    ("софт", re.compile(
        r"toolkit|plugin|auto-?update|updater|installer|checker|brute|combo|rat\b|crypter|"
        r"fud\b|bypass|spoof|inject|exploit|payload|stub|miner|proxy.?tool|sms.?bomber",
        re.I,
    )),
]

DROP_JUNK = re.compile(
    r"course|tutorial|from-scratch|portfolio|fundamentals|homework|assignment|"
    r"flappy|love-calculator|todo-list|to-do-list|calculator$|hospital-management|"
    r"blog-public|\.github$|\.emacs|devfolio|fundamentals",
    re.I,
)


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        return [ln.strip() for ln in handle if ln.strip() and not ln.startswith("#")]


def write_lines(path: Path, values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(values) + ("\n" if values else ""), encoding="utf-8")


def classify(item: str) -> str | None:
    if DROP_JUNK.search(item) and not re.search(r"pars|scrap|skill|mcp|stealer|mailer", item, re.I):
        return None
    for label, pattern in KEEP_RULES:
        if pattern.search(item):
            return label
    return None


def main() -> None:
    always: set[str] = set()
    always.update(load_lines(ROOT / "agentbaiting-skills-mcp-parsers.txt"))
    for name in load_lines(ROOT / "clawhavoc-skill-names.txt"):
        always.add(name)

    pool = load_lines(OUT.parent / "01b-working-malware-tools.txt")
    kept: dict[str, str] = {}
    dropped_not_tool: list[str] = []

    for item in pool:
        if item in always:
            kept[item] = classify(item) or "скил_mcp"
            continue
        label = classify(item)
        if label:
            kept[item] = label
        else:
            dropped_not_tool.append(item)

    websites = load_lines(OUT.parent / "01a-pirate-gambling.txt.gz")

    by_cat: dict[str, list[str]] = {}
    for item, label in kept.items():
        by_cat.setdefault(label, []).append(item)

    order = [label for label, _ in KEEP_RULES]
    lines = ["# программы и скилы. сайты вроде lordfilm убраны.", ""]
    for label in order:
        items = sorted(by_cat.get(label, []))
        if not items:
            continue
        lines.append(f"# --- {label} ({len(items)}) ---")
        lines.extend(items)
        lines.append("")
        write_lines(OUT / f"{label}.txt", items)

    write_lines(OUT / "programs-and-skills.txt", [ln for ln in lines if not ln.startswith("# ---") or True])
    # чистый список без заголовков для прогона
    write_lines(OUT / "programs-and-skills-urls.txt", sorted(kept))
    write_lines(OUT / "dropped-not-a-tool.sample.txt", sorted(dropped_not_tool)[:300])
    write_lines(OUT / "dropped-websites-1a.note.txt", [
        "1а целиком убрана из рабочего набора: это сайты, не программы.",
        f"кино_торренты_казино_адресов={len(websites)}",
        "исходник не удалён: ../01a-pirate-gambling.txt.gz",
        "актуальные адреса сайтов не используем: ../01a-current-and-spare.txt",
        "",
    ])

    stats = [
        "убраны_сайты_1а=да",
        f"сайтов_убрано={len(websites)}",
        f"программ_скилов_осталось={len(kept)}",
        f"1б_не_похоже_на_инструмент={len(dropped_not_tool)}",
    ]
    for label in order:
        stats.append(f"{label}={len(by_cat.get(label, []))}")
    stats.append("")
    write_lines(OUT / "STATS.txt", stats)
    write_lines(OUT / "README.md", [
        "# Что осталось после фильтра",
        "",
        "Убрана ерунда вроде лордфильма: кино, торренты, казино, ставки — это сайты.",
        "Оставлены программы и скилы: парсеры, рассылки, авторегеры, стилеры, кряки, боты, MCP, прочий софт.",
        "Закон и мораль не смотрел. Стилеры и рассылки на месте.",
        "",
        "Главный список: `programs-and-skills-urls.txt`",
        "По коробкам: `парсер.txt`, `рассылка.txt`, `авторегер.txt`, `стилер.txt`, …",
        "Сайты не удалены с диска, просто не в рабочем наборе: `dropped-websites-1a.note.txt`",
        "Домашка и визитки из 1б: `dropped-not-a-tool.sample.txt`",
        "",
    ])
    print("\n".join(stats))


if __name__ == "__main__":
    main()
