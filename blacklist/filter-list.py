#!/usr/bin/env python3
"""Filter a service catalog against the local malware/scam blacklist.

Reads .txt / .csv / .json catalogs and writes kept/removed files.
Does not download or execute remote packages.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/([^/\s\"'`]+)/([^/\s\"'`?#]+)", re.I)
URL_RE = re.compile(r"(?:https?|hxxps?)://[^\s\"'`<>]+", re.I)
HOST_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,24}\b", re.I)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

MULTI_SUFFIX = {
    "co.uk",
    "com.au",
    "com.br",
    "co.jp",
    "co.kr",
    "com.cn",
    "com.tr",
    "com.ua",
    "org.uk",
    "org.au",
    "net.au",
    "github.io",
    "gitlab.io",
    "vercel.app",
    "pages.dev",
    "netlify.app",
    "web.app",
    "firebaseapp.com",
    "herokuapp.com",
    "azurewebsites.net",
    "cloudfront.net",
    "blob.core.windows.net",
}

GENERIC_NAMES = {
    "skills",
    "skill",
    "plugin",
    "plugins",
    "agent",
    "parser",
    "scraper",
    "mcp",
    "update",
    "updater",
    "bot",
    "api",
    "code",
    "claude",
    "openai",
    "cursor",
    "github",
    "openclaw",
    "clawhub",
}

APEX_ALLOW = {
    "github.com",
    "githubusercontent.com",
    "gitlab.com",
    "google.com",
    "microsoft.com",
    "openai.com",
    "anthropic.com",
    "cursor.com",
    "wikipedia.org",
}


def open_text(path: Path):
    if str(path).endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return path.open("r", encoding="utf-8", errors="replace")


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    values = []
    with open_text(path) as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            values.append(line.split("\t", 1)[0].split(",", 1)[0].strip())
    return values


def refang(value: str) -> str:
    value = value.strip()
    value = value.replace("[.]", ".").replace("(.)", ".")
    value = re.sub(r"^hxxps://", "https://", value, flags=re.I)
    value = re.sub(r"^hxxp://", "http://", value, flags=re.I)
    return value


def github_slug(value: str) -> str | None:
    match = GITHUB_RE.search(refang(value))
    if not match:
        parts = value.strip().strip("/").split("/")
        if len(parts) == 2 and all(parts) and "." not in parts[0]:
            owner, repo = parts[0], parts[1]
        else:
            return None
    else:
        owner, repo = match.group(1), match.group(2)
    if repo.lower().endswith(".git"):
        repo = repo[: -len(".git")]
    return f"{owner}/{repo}".lower()


def host_from_url(value: str) -> str | None:
    value = refang(value)
    if "://" not in value:
        return None
    try:
        host = urlparse(value).hostname
    except Exception:
        return None
    return host.lower().strip(".") if host else None


def parents(host: str) -> list[str]:
    host = host.lower().strip(".")
    labels = host.split(".")
    out = [host]
    for i in range(1, max(0, len(labels) - 1)):
        candidate = ".".join(labels[i:])
        out.append(candidate)
        if candidate in MULTI_SUFFIX:
            break
        if candidate.count(".") == 1:
            break
    return out


def load_blacklist(mode: str) -> dict[str, set[str]]:
    urls = {u.lower().rstrip("/") for u in load_lines(HERE / "agentbaiting-skills-mcp-parsers.txt")}
    slugs = {s.lower() for s in load_lines(HERE / "agentbaiting-owner-repo.txt") if s.count("/") == 1}
    for repo in load_lines(HERE / "worldwide" / "github-repos.txt"):
        slug = github_slug(repo)
        if slug:
            slugs.add(slug)
            urls.add(repo.lower().rstrip("/"))
    owners = {s.split("/", 1)[0] for s in slugs if s.count("/") == 1}
    owners.update(o.lower() for o in load_lines(HERE / "worldwide" / "github-owners.txt"))
    owners.discard("https:")
    owners.discard("http:")

    domains: set[str] = set()
    for path in (
        HERE / "extra-malware-domains-2026.txt",
        HERE / "worldwide" / "campaign-domains.txt",
        HERE / "worldwide" / "domains-core.txt.gz" if mode in {"core", "banned", "full"} else None,
        HERE / "worldwide" / "banned-rkn-mirrors.txt.gz" if mode == "banned" else None,
        HERE / "worldwide" / "domains.txt.gz" if mode == "full" else None,
    ):
        if path is None:
            continue
        for item in load_lines(path):
            item = refang(item).lower().strip(".")
            if item and item not in APEX_ALLOW:
                domains.add(item)

    exact_urls = {refang(u).lower().rstrip("/") for u in load_lines(HERE / "worldwide" / "urls.txt.gz")}
    ips = {i for i in load_lines(HERE / "worldwide" / "ips.txt") if IP_RE.fullmatch(i)}

    names: set[str] = set()
    for item in load_lines(HERE / "clawhavoc-skill-names.txt"):
        item = item.lower()
        slug = github_slug(item)
        if slug:
            slugs.add(slug)
            owners.add(slug.split("/", 1)[0])
            tail = slug.split("/")[-1]
            if tail not in GENERIC_NAMES and len(tail) >= 8:
                names.add(tail)
            continue
        if "/" not in item and item not in GENERIC_NAMES and len(item) >= 8:
            names.add(item)
            owners.add(item)

    handles = {h.lower().lstrip("@") for h in load_lines(HERE / "worldwide" / "telegram-handles.txt")}
    brands = {b.lower() for b in load_lines(HERE / "worldwide" / "mirror-brands.txt") if len(b) >= 6}
    return {
        "urls": urls,
        "slugs": slugs,
        "owners": owners,
        "domains": domains,
        "exact_urls": exact_urls,
        "names": names,
        "ips": ips,
        "handles": handles,
        "brands": brands,
    }


def iter_user_entries(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(raw)
        if isinstance(data, list):
            return [item if isinstance(item, str) else json.dumps(item, ensure_ascii=False) for item in data]
        if isinstance(data, dict):
            for key in ("urls", "links", "items", "services", "skills"):
                if isinstance(data.get(key), list):
                    return [str(item) for item in data[key]]
        return [json.dumps(data, ensure_ascii=False)]
    if suffix == ".csv":
        return [",".join(row) for row in csv.reader(raw.splitlines())]
    return [line.rstrip("\n") for line in raw.splitlines()]


def match_reason(text: str, bl: dict[str, set[str]]) -> str | None:
    lowered = refang(text).lower()
    stripped = lowered.rstrip("/")

    if stripped in bl["urls"] or stripped in bl["exact_urls"]:
        return f"url:{stripped}"

    for raw_url in URL_RE.findall(text):
        url = refang(raw_url).lower().rstrip("/")
        if url in bl["urls"] or url in bl["exact_urls"]:
            return f"url:{url}"
        host = host_from_url(url)
        if host:
            for candidate in parents(host):
                if candidate in bl["domains"]:
                    return f"domain:{candidate}"
        slug = github_slug(url)
        if slug:
            if slug in bl["slugs"]:
                return f"github:{slug}"
            owner = slug.split("/", 1)[0]
            if owner in bl["owners"]:
                return f"github-owner:{owner}"

    slug = github_slug(text)
    if slug:
        if slug in bl["slugs"]:
            return f"github:{slug}"
        owner = slug.split("/", 1)[0]
        if owner in bl["owners"]:
            return f"github-owner:{owner}"

    for ip in IP_RE.findall(text):
        if ip in bl["ips"]:
            return f"ip:{ip}"

    for match in re.findall(r"(?:t\.me/|@)([a-z0-9_]{5,32})", lowered):
        if match in bl.get("handles", set()):
            return f"telegram:@{match}"

    for host in HOST_RE.findall(lowered):
        host = host.strip(".")
        if host in APEX_ALLOW:
            continue
        for candidate in parents(host):
            if candidate in bl["domains"]:
                return f"domain:{candidate}"
        for brand in bl.get("brands", set()):
            if brand in host:
                return f"mirror-brand:{brand}"

    tokens = re.findall(r"[a-z0-9._/-]{8,}", lowered)
    for token in tokens:
        if token in bl["names"] and token not in GENERIC_NAMES:
            return f"skill-name:{token}"
        if token in bl["slugs"]:
            return f"github:{token}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Filter a catalog against the 2026 worldwide malware/scam blacklist.")
    parser.add_argument("input", type=Path, help="Your list: .txt, .csv, or .json")
    parser.add_argument("--kept", type=Path, default=Path("kept.txt"))
    parser.add_argument("--removed", type=Path, default=Path("removed.txt"))
    parser.add_argument(
        "--mode",
        choices=("core", "banned", "full"),
        default="full",
        help="core=IOC only; banned=core+RKN/mirrors; full=maximum merge (default)",
    )
    args = parser.parse_args()
    if not args.input.exists():
        print(f"input not found: {args.input}", file=sys.stderr)
        return 2

    print(f"loading blacklist mode={args.mode} ...", file=sys.stderr)
    blacklist = load_blacklist(args.mode)
    print(
        "loaded "
        f"domains={len(blacklist['domains'])} "
        f"urls={len(blacklist['exact_urls'])} "
        f"github={len(blacklist['slugs'])} "
        f"owners={len(blacklist['owners'])}",
        file=sys.stderr,
    )

    kept: list[str] = []
    removed: list[str] = []
    for line in iter_user_entries(args.input):
        if not line.strip() or line.lstrip().startswith("#"):
            kept.append(line)
            continue
        reason = match_reason(line, blacklist)
        if reason:
            removed.append(f"{line}\t# {reason}")
        else:
            kept.append(line)

    args.kept.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    args.removed.write_text("\n".join(removed) + ("\n" if removed else ""), encoding="utf-8")
    print(f"kept={len(kept)} removed={len(removed)}")
    print(f"wrote {args.kept} and {args.removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
