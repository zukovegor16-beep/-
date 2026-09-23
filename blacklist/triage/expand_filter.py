#!/usr/bin/env python3
"""Убрать игровые читы и то, что просит оплату. Докинуть из уже собранной базы 1б."""

from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

KEEP = Path(__file__).resolve().parent / "keep"
ROOT = Path(__file__).resolve().parents[1]
GITHUB_RE = re.compile(r"^https?://github\.com/[^/]+/[^/#?]+", re.I)

GAME = re.compile(
    r"cheat|trainer|aim-?bot|aimbot|esp\b|no-recoil|loot-drop|auto-farm-clicker|"
    r"hamster-kombat|hamster-bot|roblox|fortnite|minecraft-afk|mir4|"
    r"free-fire|piggypiggy|slay-the-spire|atlyss|warzone|rust-cheat|"
    r"valorant|pubg|niox|ace-serve-trainer|tennis.?manager|"
    r"hoi4-dlc|witcher-3-dlc|elder-scrolls-online-dlc|"
    r"chibi-clash|common-ground-world|omega-life|glyphx|"
    r"pig-card-game|pinball|adoptme|royale-high|neon-abyss|"
    r"dune-awakening|rainbow-six|ant-man-simulator|hurtworld|"
    r"dayz-underground|war-thunder-aim|obby-creator|bread-run|"
    r"climb-jump-tower|arksurvival|r6-recoil|rbxfpsunlocker|"
    r"bluecheatah|zergcheater|\bapex\b",
    re.I,
)
PAID = re.compile(
    r"enterprise-download|professional-download|full-download|"
    r"subscription|paywall|buy-now|license-store",
    re.I,
)

EXPAND = {
    "стилер": re.compile(
        r"stealer|infosteal|stealc|redline|lumma|raccoon|vidar|aurora-stealer|"
        r"browser-data-grabber|cookie.?log|keylog|hades-stealer",
        re.I,
    ),
    "рассылка": re.compile(
        r"mailer|mass.?mail|bulk.?mail|smtp.?sender|multi-email-sender|"
        r"whatsender|sms.?blast|mass.?dm|telegram.?sender|email-bomber",
        re.I,
    ),
    "авторегер": re.compile(
        r"autoreg|auto.?reg|account.?gen|acc.?gen|account-creator|"
        r"signup-bot|discord-joiner|token-gen|instagram-reg|tiktok-reg",
        re.I,
    ),
    "качалка": re.compile(
        r"youtube-?(dl|download)|gallery-dl|instaloader|spotdl|"
        r"tiktok-download|soundcloud-download|pixiv-download|"
        r"telegram-media-download|bulk-image-download|"
        r"playlist-download|mp3-mp4-download",
        re.I,
    ),
    "парсер": re.compile(r"scraper|web-scraper|linkedin-.*scrap|facebook-.*scrap", re.I),
    "скил_mcp": re.compile(r"\bmcp-server\b|mcp-gateway|claude-skill|agent-skill", re.I),
    "бот": re.compile(
        r"telegram-bot|discord-bot|whatsapp-bot|userbot|"
        r"polymarket-bot|copy-?trading-bot|mass-dm-bot",
        re.I,
    ),
    "кряк_чит": re.compile(r"no-trial|nulled|premium-unlocked|professional-crack", re.I),
    "софт": re.compile(r"quasarrat|nullrat|android-rat|infosteal-builder", re.I),
}


def load(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.startswith("#")]


def write(path: Path, values) -> None:
    path.write_text("\n".join(sorted(set(values))) + ("\n" if values else ""), encoding="utf-8")


def github_alive(url: str) -> bool:
    match = GITHUB_RE.match(url.strip().rstrip("/"))
    if not match:
        return False
    request = urllib.request.Request(match.group(0), method="HEAD", headers={"User-Agent": "catalog-liveness-check"})
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


def junk(item: str) -> str | None:
    if GAME.search(item):
        return "игровой чит / фарм"
    if PAID.search(item):
        return "похоже, что за использование просят оплату"
    return None


def main() -> None:
    boxes = {
        "парсер": load(KEEP / "парсер.txt"),
        "рассылка": load(KEEP / "рассылка.txt"),
        "стилер": load(KEEP / "стилер.txt"),
        "авторегер": load(KEEP / "авторегер.txt"),
        "качалка": load(KEEP / "качалка.txt"),
        "бот": load(KEEP / "бот.txt"),
        "софт": load(KEEP / "софт.txt"),
        "кряк_чит": load(KEEP / "кряк_чит.txt"),
        "скил_mcp": load(KEEP / "скил_mcp.txt"),
    }
    removed: list[str] = []
    cleaned: dict[str, list[str]] = {}
    for name, items in boxes.items():
        keep_items = []
        for item in items:
            reason = junk(item)
            if reason:
                removed.append(f"{item}\t{reason}")
            else:
                keep_items.append(item)
        cleaned[name] = keep_items

    pool = load(ROOT / "worldwide" / "github-repos.txt")
    pool += load(ROOT / "agentbaiting-skills-mcp-parsers.txt")
    pool += load(KEEP.parent / "01b-working-malware-tools.txt")
    already = {x for vals in cleaned.values() for x in vals}
    already.update(x.split("\t", 1)[0] for x in removed)
    added: dict[str, list[str]] = {k: [] for k in EXPAND}
    for item in pool:
        if not item.startswith("http"):
            continue
        if item in already:
            continue
        if junk(item):
            continue
        for box, pattern in EXPAND.items():
            if pattern.search(item):
                added[box].append(item)
                already.add(item)
                break

    candidates = [u for vals in added.values() for u in vals]
    print(f"new candidates {len(candidates)}")
    alive: dict[str, bool] = {}
    if candidates:
        with ThreadPoolExecutor(max_workers=12) as pool_exec:
            futs = {pool_exec.submit(github_alive, url): url for url in candidates}
            for fut in as_completed(futs):
                alive[futs[fut]] = fut.result()

    added_live_n = 0
    for box, items in added.items():
        live = [u for u in items if alive.get(u)]
        added_live_n += len(live)
        cleaned[box].extend(live)

    for name, items in cleaned.items():
        write(KEEP / f"{name}.txt", items)
    write(KEEP / "programs-and-skills-urls.txt", [u for vals in cleaned.values() for u in vals])
    write(KEEP / "убрано-читы-и-оплата.txt", removed)

    total = sum(len(v) for v in cleaned.values())
    stats = [
        "убраны_игровые_читы=да",
        "убрано_если_нужна_оплата=да",
        "расширение=только_уже_собранная_база_1б_плюс_публичные_репо",
        f"программ_скилов_осталось={total}",
        f"добавлено_живых_из_базы={added_live_n}",
        f"убрано_читов_и_оплаты={len(removed)}",
    ]
    for name in cleaned:
        stats.append(f"{name}={len(cleaned[name])}")
    stats.append("")
    (KEEP / "STATS.txt").write_text("\n".join(stats), encoding="utf-8")
    print("\n".join(stats))


if __name__ == "__main__":
    main()
