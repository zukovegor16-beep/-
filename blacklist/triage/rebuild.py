#!/usr/bin/env python3
"""Пересборка двух списков: рабочее vs пустой скам. URL не открываются."""

from __future__ import annotations

import gzip
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent

# Сайты, которые обычно открываются как сервис (кино / торрент / казино).
FUNCTIONAL_ILLEGAL_BRANDS = {
    "lordfilm", "lordfilms", "lord-film", "lord-films", "lordsfilm", "lordsfilms",
    "lordserial", "lordserials", "lord-serial", "1lordfilm", "2lordserials",
    "kinogo", "hdrezka", "rutor", "123rutor", "arutor", "piratbit", "blackrutor",
    "kinokrad", "seasonvar", "baskino", "allserial", "alexfilm", "filmix",
    "animego", "animedia", "animevost", "animebesst", "lostfilm",
    "rutracker", "nnmclub", "nnm-club", "kinozal", "megapeer",
    "admiralx", "admiral-x", "azino777", "1xslots", "7kcasino", "7k-casino",
    "7k-cazino", "888starz", "24-vulkan", "arkada-casino", "arkadacasino",
    "aufcasino", "auroracasino", "banda-casino", "bandacasino", "24x7olimp",
    "vavada", "pinco", "1xbet", "melbet", "mostbet",
}
BRAND_DENY = {
    "azureedge", "azurefd", "azurewebsites", "appspot", "aappspot",
    "github", "yandex", "amazonaws", "cloudflare", "googleapis",
    "blogspot", "bitbucket", "beeline",
}
CSAM_HINT = re.compile(r"(child.?porn|csam|preteen|lolicon|underage.?porn)", re.I)


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        return [ln.strip() for ln in handle if ln.strip() and not ln.startswith("#")]


def write_lines(path: Path, values, gzip_out: bool = False) -> None:
    data = "\n".join(sorted(values)) + ("\n" if values else "")
    path.parent.mkdir(parents=True, exist_ok=True)
    if gzip_out:
        path.write_bytes(gzip.compress(data.encode("utf-8"), compresslevel=9))
    else:
        path.write_text(data, encoding="utf-8")


def write_sample(path: Path, values: list[str]) -> None:
    path.write_text("\n".join(values) + ("\n" if values else ""), encoding="utf-8")


def has_brand(value: str, brands: set[str]) -> bool:
    low = value.lower()
    return any(b in low for b in brands)


def take(values, n: int) -> list[str]:
    return list(sorted(values))[:n]


def main() -> None:
    pirate: set[str] = set()
    rkn_unclassified: list[str] = []
    csam_omitted = 0
    for item in load_lines(ROOT / "worldwide" / "banned-rkn-mirrors.txt.gz"):
        if CSAM_HINT.search(item):
            csam_omitted += 1
            continue
        if has_brand(item, BRAND_DENY):
            rkn_unclassified.append(item)
            continue
        if has_brand(item, FUNCTIONAL_ILLEGAL_BRANDS):
            pirate.add(item)
        else:
            rkn_unclassified.append(item)

    # Рабочий объект: репозиторий / скил / парсер можно клонировать или запустить.
    # Тип скила не важен: вредоносный парсер тоже сюда, если архив реальный.
    tools: set[str] = set()
    for item in load_lines(ROOT / "worldwide" / "github-repos.txt"):
        tools.add(item)
    for item in load_lines(ROOT / "agentbaiting-skills-mcp-parsers.txt"):
        tools.add(item)
    for item in load_lines(ROOT / "clawhavoc-skill-names.txt"):
        tools.add(item)

    empty: set[str] = set()
    for item in load_lines(ROOT / "extra-malware-domains-2026.txt"):
        empty.add(item)
    for item in load_lines(ROOT / "worldwide" / "campaign-domains.txt"):
        empty.add(item)
    for item in load_lines(ROOT / "worldwide" / "domains-core.txt.gz"):
        empty.add(item)

    telegram: set[str] = set()
    for item in load_lines(ROOT / "worldwide" / "telegram-handles.txt"):
        telegram.add(f"t.me/{item.lstrip('@')}")

    working = set(pirate) | set(tools)
    scam = set(empty) | set(telegram)
    overlap = working & scam
    working -= overlap
    scam -= overlap

    write_lines(OUT / "01a-pirate-gambling.txt.gz", pirate, gzip_out=True)
    write_lines(OUT / "01b-working-malware-tools.txt", tools)
    write_lines(OUT / "01-working-links.txt.gz", working, gzip_out=True)
    write_lines(OUT / "01-illegal-but-functional.txt.gz", working, gzip_out=True)
    write_lines(OUT / "02a-phishing-c2-pyramids-installers.txt.gz", empty, gzip_out=True)
    write_lines(OUT / "02b-telegram-scam-handles.txt", telegram)
    write_lines(OUT / "02-empty-scam.txt.gz", scam, gzip_out=True)
    write_lines(OUT / "02-pure-scam.txt.gz", scam, gzip_out=True)
    write_lines(OUT / "00-overlap-both.txt", overlap)
    write_sample(OUT / "03-unclassified-rkn.sample.txt", take(rkn_unclassified, 400))

    write_sample(OUT / "01a-pirate-gambling.sample.txt", take(pirate, 200))
    write_sample(OUT / "01b-working-malware-tools.sample.txt", take(tools, 250))
    write_sample(
        OUT / "01-working-links.sample.txt",
        take(pirate, 80) + take([t for t in tools if "github.com" in t], 150) + take(
            [t for t in tools if "github.com" not in t], 50
        ),
    )
    write_sample(OUT / "01-illegal-but-functional.sample.txt", take(pirate, 80) + take(tools, 150))
    write_sample(OUT / "02-empty-scam.sample.txt", take(empty, 150) + take(telegram, 50))
    write_sample(OUT / "02-pure-scam.sample.txt", take(empty, 150) + take(telegram, 50))
    write_sample(OUT / "02a-phishing-c2-pyramids-installers.sample.txt", take(empty, 200))
    write_sample(OUT / "02b-telegram-scam-handles.sample.txt", take(telegram, 200))

    stats = "\n".join(
        [
            "split=works_vs_empty_lure",
            "visited_each_url=no",
            "skill_type_ignored=yes",
            f"list1_working_total={len(working)}",
            f"list1a_pirate_gambling={len(pirate)}",
            f"list1b_working_malware_tools={len(tools)}",
            f"list2_empty_scam_total={len(scam)}",
            f"list2a_phishing_c2_pyramids={len(empty)}",
            f"list2b_telegram_handles={len(telegram)}",
            f"overlap={len(overlap)}",
            f"list3_unclassified_rkn={len(rkn_unclassified)}",
            f"csam_hints_omitted={csam_omitted}",
            "",
        ]
    )
    (OUT / "STATS.txt").write_text(stats, encoding="utf-8")
    print(stats)


if __name__ == "__main__":
    main()
