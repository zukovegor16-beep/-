#!/usr/bin/env python3
"""Оставить программы/скилы. Убрать сайты вроде lordfilm. Исходники не удаляет."""

from __future__ import annotations

import gzip
import re
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "keep"

# Сначала узкие типы, потом общее «софт».
KEEP_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("стилер", re.compile(r"stealer|infosteal|keylog|cookie.?steal|browser-data-grabber|crypto.?clipper|grab.?cookie", re.I)),
    ("рассылка", re.compile(
        r"mailer|mass.?mail|bulk.?mail|smtp|multi-email-sender|whatsender|"
        r"sms.?blast|sms.?enabler|spammer|newsletter|mass.?dm|auto.?mass.?dm",
        re.I,
    )),
    ("авторегер", re.compile(r"autoreg|auto.?reg|account.?gen|acc.?gen|joiner|follower.?bot|nacrut", re.I)),
    ("парсер", re.compile(r"pars|scrap|crawler|crawl|osint|grabber|harvester|extractor", re.I)),
    ("скил_mcp", re.compile(r"\bmcp\b|mcp-|skill|openclaw|claude-|claude_code|agent-skill|composio", re.I)),
    ("кряк_чит", re.compile(
        r"crack|cheat|keygen|trainer|unlock|nulled|license.?bypass|no-trial|no.?trial|"
        r"vegas-pro-version|adobe-photoshop-version|adobe-premiere-pro-version|"
        r"aseprite-pixel-art-editor|ableton-live-\d+-desktop|"
        r"office-365-activator|idm-freezer-and-activator",
        re.I,
    )),
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
CRACK_HINT = re.compile(
    r"no-trial|no.?trial|nulled|premium.?unlock|unlocked.?premium|"
    r"enterprise-no-trial|keygen|crack|cheat|trainer|license.?bypass",
    re.I,
)
# Кряк платной программы (не каламбур вроде claude-cracks-the-whip).
# Если имя ещё про рассылку/парсер/качалку — кладём и туда, и в кряки.
DUAL_CRACK = re.compile(
    r"no-trial|no.?trial|nulled|premium.?unlock|unlocked.?premium|"
    r"professional-crack|_Crack",
    re.I,
)
GITHUB_RE = re.compile(r"^https?://github\.com/[^/]+/[^/#?]+", re.I)


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        return [ln.strip() for ln in handle if ln.strip() and not ln.startswith("#")]


def write_lines(path: Path, values) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(values) + ("\n" if values else ""), encoding="utf-8")


def github_alive(url: str, timeout: float = 8.0) -> bool:
    """Страница репозитория открывается. Тело и релизы не качаем."""
    match = GITHUB_RE.match(url.strip())
    if not match:
        return False
    page = match.group(0)
    request = urllib.request.Request(
        page,
        method="HEAD",
        headers={"User-Agent": "catalog-liveness-check"},
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return 200 <= response.status < 400
    except urllib.error.HTTPError as error:
        if error.code in {403, 405}:
            request.method = "GET"
            request.add_header("Range", "bytes=0-0")
            try:
                with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
                    return 200 <= response.status < 400
            except urllib.error.HTTPError as again:
                return again.code in {200, 206, 304}
            except OSError:
                return False
        return False
    except OSError:
        return False


def classify(item: str) -> str | None:
    labels = classify_labels(item)
    return labels[0] if labels else None


def classify_labels(item: str) -> list[str]:
    if DROP_JUNK.search(item) and not re.search(r"pars|scrap|skill|mcp|stealer|mailer|crack|no-trial", item, re.I):
        return []
    matched = [label for label, pattern in KEEP_RULES if pattern.search(item)]
    function_labels = [label for label in matched if label != "кряк_чит"]
    is_real_crack = bool(DUAL_CRACK.search(item))
    labels: list[str] = []
    if function_labels:
        labels.append(function_labels[0])
    if is_real_crack or (not function_labels and "кряк_чит" in matched):
        if "кряк_чит" not in labels:
            labels.append("кряк_чит")
    return labels


def main() -> None:
    always: set[str] = set()
    always.update(load_lines(ROOT / "agentbaiting-skills-mcp-parsers.txt"))
    for name in load_lines(ROOT / "clawhavoc-skill-names.txt"):
        always.add(name)

    pool = load_lines(OUT.parent / "01b-working-malware-tools.txt")
    kept: dict[str, list[str]] = {}
    dropped_not_tool: list[str] = []

    for item in pool:
        labels = classify_labels(item)
        if item in always and not labels:
            labels = ["скил_mcp"]
        if labels:
            kept[item] = labels
        else:
            dropped_not_tool.append(item)

    crack_candidates = [
        item for item, labels in kept.items()
        if "кряк_чит" in labels or CRACK_HINT.search(item)
    ]
    dead_cracks: list[str] = []
    if crack_candidates:
        with ThreadPoolExecutor(max_workers=10) as pool_exec:
            future_map = {
                pool_exec.submit(github_alive, item): item
                for item in crack_candidates
                if item.startswith("http")
            }
            alive_map = {future_map[future]: future.result() for future in as_completed(future_map)}
        for item in crack_candidates:
            if item.startswith("http") and not alive_map.get(item, False):
                kept.pop(item, None)
                dead_cracks.append(item)

    websites = load_lines(OUT.parent / "01a-pirate-gambling.txt.gz")

    by_cat: dict[str, list[str]] = {}
    for item, labels in kept.items():
        for label in labels:
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
    write_lines(OUT / "кряк_мертвые.txt", sorted(dead_cracks))
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
        f"кряки_проверены={len(crack_candidates)}",
        f"кряки_ссылка_жива={len(crack_candidates) - len(dead_cracks)}",
        f"кряки_ссылка_мертва={len(dead_cracks)}",
        "кряки_запуск_не_проверялся=да",
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
        "Кряк No-Trial, если имя ещё про рассылку/парсер/качалку, кладётся в оба раздела.",
        "Кряки и No-Trial вернул только если страница GitHub сейчас открывается. Сам кряк не запускал.",
        "Мёртвые ссылки: `кряк_мертвые.txt`.",
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
