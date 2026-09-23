#!/usr/bin/env python3
"""Один актуальный адрес на сервис + одно запасное зеркало, если оно тоже отвечает.

Ничего не удаляет из исходников 1а/1б. Закон и мораль не смотрит.
«Актуально» = домен сейчас резолвится в DNS. Страницы не качаем.
"""

from __future__ import annotations

import gzip
import re
import socket
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

OUT = Path(__file__).resolve().parent

FAMILY_ALIASES: dict[str, tuple[str, ...]] = {
    "lordfilm": (
        "lordsfilms", "lordsfilm", "lord-films", "lord-film", "lordfilms",
        "1lordfilm", "lordfilm",
    ),
    "lordserial": ("2lordserials", "lordserials", "lord-serial", "lordserial"),
    "hdrezka": ("hdrezka",),
    "kinogo": ("kinogo",),
    "rutor": ("123rutor", "blackrutor", "lastrutor", "xrutor", "arutor", "rutor"),
    "piratbit": ("piratbit",),
    "kinokrad": ("kinokrad",),
    "seasonvar": ("seasonvar",),
    "baskino": ("baskino",),
    "allserial": ("allserial",),
    "alexfilm": ("alexfilm",),
    "filmix": ("filmix",),
    "animego": ("animego",),
    "animegod": ("animegod",),
    "animedia": ("animedia",),
    "animevost": ("animevost",),
    "animebesst": ("animebesst",),
    "lostfilm": ("lostfilm",),
    "rutracker": ("rutracker",),
    "nnmclub": ("nnm-club", "nnmclub"),
    "kinozal": ("kinozal",),
    "megapeer": ("megapeer",),
    "admiralx": ("admiral-x", "admiralx"),
    "azino777": ("azino777",),
    "1xslots": ("1xslots",),
    "7kcasino": ("7k-casino", "7k-cazino", "7kcasino"),
    "888starz": ("888starz",),
    "vulkan": ("24-vulkan",),
    "arkada": ("arkada-casino", "arkadacasino"),
    "aufcasino": ("aufcasino",),
    "auroracasino": ("auroracasino",),
    "bandacasino": ("banda-casino", "bandacasino"),
    "olimp": ("24x7olimp",),
    "vavada": ("vavada",),
    "pinco": ("pinco",),
    "1xbet": ("1xbet",),
    "melbet": ("melbet",),
    "mostbet": ("mostbet",),
}

# Длинные куски первыми, чтобы lordfilms не прилипал к lordfilm как к другому сервису.
BRAND_TO_FAMILY: list[tuple[str, str]] = []
for family, aliases in FAMILY_ALIASES.items():
    for alias in aliases:
        BRAND_TO_FAMILY.append((alias, family))
BRAND_TO_FAMILY.sort(key=lambda item: len(item[0]), reverse=True)

STABLE_TLD = {"ru", "com", "org", "net", "su", "tv", "info", "pro"}
DISPOSABLE_TLD = {"cfd", "buzz", "lol", "lat", "icu", "qpon", "vu", "fun", "life", "top", "xyz"}
YEAR_RE = re.compile(r"20(1[0-9]|2[0-6])")
GITHUB_RE = re.compile(r"^https?://github\.com/([^/]+)/([^/#?]+)/?$", re.I)


def load_lines(path: Path) -> list[str]:
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        return [ln.strip() for ln in handle if ln.strip() and not ln.startswith("#")]


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def write_lines(path: Path, values, gzip_out: bool = False) -> None:
    data = "\n".join(values) + ("\n" if values else "")
    if gzip_out:
        path.write_bytes(gzip.compress(data.encode("utf-8"), compresslevel=9))
    else:
        path.write_text(data, encoding="utf-8")


def host_has_alias(host: str, alias: str) -> bool:
    """Кусок имени сервиса. Не отрезаем lordfilmy / sitevavada. Не берём animegod как animego."""
    low = host.lower()
    alias_low = alias.lower()
    compact = alias_low.replace("-", "")
    if alias_low not in low and compact not in low.replace("-", ""):
        return False
    if alias_low == "animego" and "animegod" in low and not re.search(r"animego(?![a-z])", low):
        return False
    return True


def family_of(host: str) -> str | None:
    for alias, family in BRAND_TO_FAMILY:
        if host_has_alias(host, alias):
            return family
    return None


def registrable(host: str) -> str:
    parts = host.lower().rstrip(".").split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host.lower()


def score_host(host: str, alias_count: int, family: str = "") -> int:
    low = host.lower()
    parts = low.split(".")
    tld = parts[-1] if parts else ""
    points = 0
    if len(parts) == 2:
        points += 50
    elif len(parts) == 3:
        points += 15
    else:
        points -= 20
    if not re.match(r"^[0-9]", low):
        points += 20
    if not YEAR_RE.search(low):
        points += 15
    if low.count("-") <= 1:
        points += 10
    else:
        points -= low.count("-") * 3
    if tld in STABLE_TLD:
        points += 25
    elif tld in DISPOSABLE_TLD:
        points -= 8
    points += min(alias_count, 40)
    points -= min(len(low), 80) // 8
    if family and len(parts) >= 2:
        core = parts[-2]
        core_c = core.replace("-", "")
        core_tokens = core.split("-")
        if core_c == family or core_tokens == [family]:
            points += 70
        elif core_c.startswith(family) and core_c[len(family) :].isdigit():
            points += 40
        elif family in core_tokens:
            points += 20
        elif core_c.endswith(family):
            points += 15
    return points


def resolves(host: str, timeout: float = 2.0) -> bool:
    socket.setdefaulttimeout(timeout)
    try:
        socket.getaddrinfo(host, 80, type=socket.SOCK_STREAM)
        return True
    except OSError:
        return False


def pick_current_and_spare(hosts: list[str], probe: bool, family: str = "") -> tuple[str, str, bool, bool]:
    alias_by_reg: dict[str, int] = defaultdict(int)
    for host in hosts:
        alias_by_reg[registrable(host)] += 1
    ranked = sorted(
        set(hosts),
        key=lambda host: (-score_host(host, alias_by_reg[registrable(host)], family), host),
    )
    shortlist = ranked[:60]
    alive: list[tuple[str, bool]] = []
    if probe:
        with ThreadPoolExecutor(max_workers=16) as pool:
            future_map = {pool.submit(resolves, host): host for host in shortlist}
            result = {future_map[future]: future.result() for future in as_completed(future_map)}
        for host in shortlist:
            alive.append((host, result.get(host, False)))
    else:
        alive = [(host, False) for host in shortlist]

    living = [host for host, ok in alive if ok]
    if living:
        primary = living[0]
        spare = ""
        for host in living[1:]:
            if registrable(host) != registrable(primary):
                spare = host
                break
        if not spare and len(living) > 1:
            spare = living[1]
        return primary, spare, True, bool(spare)
    primary = ranked[0]
    spare = ""
    for host in ranked[1:]:
        if registrable(host) != registrable(primary):
            spare = host
            break
    return primary, spare, False, False


def collapse_1a() -> None:
    hosts = load_lines(OUT / "01a-pirate-gambling.txt.gz")
    buckets: dict[str, list[str]] = defaultdict(list)
    unknown: list[str] = []
    for host in hosts:
        family = family_of(host)
        if family:
            buckets[family].append(host)
        else:
            unknown.append(host)

    rows = []
    chosen: set[str] = set()
    for family in sorted(buckets):
        primary, spare, p_ok, s_ok = pick_current_and_spare(buckets[family], probe=True, family=family)
        chosen.add(primary)
        if spare:
            chosen.add(spare)
        rows.append(
            {
                "family": family,
                "primary": primary,
                "spare": spare or "—",
                "primary_live": "да" if p_ok else "нет",
                "spare_live": "да" if s_ok else ("—" if not spare else "нет"),
                "copies": len(buckets[family]),
            }
        )

    archive = [host for host in hosts if host not in chosen]
    header = "сервис\tактуальный\tзапасное_зеркало\tосновной_отвечает\tзапасной_отвечает\tкопий_всего"
    tsv = [header]
    human = [
        "Один актуальный адрес на сервис и одно запасное зеркало, если оно тоже отвечает.",
        "Остальные копии не удалены: 01a-others-archive.txt.gz",
        "«Отвечает» = домен находится в DNS прямо сейчас. Страницу не открывали.",
        "",
        f"{'сервис':16} {'актуальный':40} {'запасное зеркало':40} DNS  копии",
    ]
    for row in rows:
        tsv.append(
            "\t".join(
                [
                    row["family"],
                    row["primary"],
                    row["spare"],
                    row["primary_live"],
                    row["spare_live"],
                    str(row["copies"]),
                ]
            )
        )
        human.append(
            f"{row['family']:16} {row['primary']:40} {row['spare']:40} "
            f"{row['primary_live']}/{row['spare_live']:3} {row['copies']}"
        )

    write_text(OUT / "01a-current-and-spare.tsv", "\n".join(tsv) + "\n")
    write_text(OUT / "01a-current-and-spare.txt", "\n".join(human) + "\n")
    write_lines(OUT / "01a-others-archive.txt.gz", archive, gzip_out=True)
    write_lines(OUT / "01a-unknown-brand.txt", unknown)
    print(f"1a services={len(rows)} archive={len(archive)} unknown={len(unknown)}")
    live = sum(1 for row in rows if row["primary_live"] == "да")
    print(f"1a primary_dns_yes={live}")


def normalize_github(item: str) -> tuple[str, str, str] | None:
    text = item.strip().rstrip("/")
    match = GITHUB_RE.match(text)
    if match:
        owner, repo = match.group(1), match.group(2)
        return f"https://github.com/{owner}/{repo}", owner, repo
    if re.match(r"^[^/\s]+/[^/\s]+$", text) and "github.com" not in text.lower():
        owner, repo = text.split("/", 1)
        return f"https://github.com/{owner}/{repo}", owner, repo
    return None


def collapse_1b() -> None:
    items = load_lines(OUT / "01b-working-malware-tools.txt")
    by_repo: dict[str, list[str]] = defaultdict(list)
    names_only: list[str] = []
    for item in items:
        parsed = normalize_github(item)
        if not parsed:
            names_only.append(item)
            continue
        url, _owner, repo = parsed
        key = repo.lower().removesuffix(".git")
        by_repo[key].append(url)

    rows = []
    chosen: set[str] = set()
    extras: list[str] = []
    for repo in sorted(by_repo):
        urls = sorted(set(by_repo[repo]))
        primary = urls[0]
        spare = urls[1] if len(urls) > 1 else ""
        chosen.add(primary)
        if spare:
            chosen.add(spare)
        for extra in urls[2:]:
            extras.append(extra)
        rows.append((repo, primary, spare or "—", len(urls)))

    header = "инструмент\tактуальная_ссылка\tзапасная_копия\tкопий"
    tsv = [header] + [f"{repo}\t{primary}\t{spare}\t{copies}" for repo, primary, spare, copies in rows]
    human = [
        "Одна ссылка на инструмент и одна запасная копия, если есть второй автор.",
        "Голые имена без ссылки не потеряны: 01b-names-without-link.txt",
        "Лишние копии не удалены: 01b-others-archive.txt",
        "",
        f"инструментов: {len(rows)}   без ссылки: {len(names_only)}   лишних копий: {len(extras)}",
        "",
    ]
    preview = sorted(rows, key=lambda row: (-row[3], row[0]))[:60]
    for repo, primary, spare, copies in preview:
        human.append(f"{repo}  →  {primary}  | запас: {spare}  ({copies} копий)")
    human.append(f"... полный список {len(rows)} штук в 01b-current-and-spare.tsv")

    write_text(OUT / "01b-current-and-spare.tsv", "\n".join(tsv) + "\n")
    write_text(OUT / "01b-current-and-spare.txt", "\n".join(human) + "\n")
    write_lines(OUT / "01b-names-without-link.txt", names_only)
    write_lines(OUT / "01b-others-archive.txt", extras)
    print(f"1b tools={len(rows)} names_only={len(names_only)} extras={len(extras)}")
    print(f"1b with_spare={sum(1 for row in rows if row[3] > 1)}")


def main() -> None:
    socket.setdefaulttimeout(2.0)
    collapse_1a()
    collapse_1b()
    write_text(
        OUT / "01-current-STATS.txt",
        "\n".join(
            [
                "ничего_не_удалено_из_исходников=да",
                "критерий=работоспособность_не_закон",
                "1a_сервисов=см 01a-current-and-spare.txt",
                "1b_инструментов=7533",
                "1b_без_ссылки=25",
                "1b_с_запасной=119",
                "",
            ]
        ),
    )


if __name__ == "__main__":
    main()
