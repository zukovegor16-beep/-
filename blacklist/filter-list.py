#!/usr/bin/env python3
"""Remove known-malicious Skills / MCP / parser entries from a user catalog.

Reads any text/CSV/JSON file, matches URLs, GitHub owner/repo slugs,
domains, and ClawHavoc skill names against this blacklist, then writes
kept and removed files. Does not fetch or execute remote packages.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{1,200}")
GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/([^/\s]+)/([^/\s?#]+)", re.I)
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


def load_lines(path: Path) -> list[str]:
    values: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        values.append(line.split(",", 1)[0].strip())
    return values


def normalize_host(value: str) -> str:
    value = value.strip().lower()
    value = value.replace("hxxps://", "https://").replace("hxxp://", "http://")
    value = value.replace("[.]", ".")
    if "://" not in value and "/" not in value and "." in value:
        return value.lstrip(".")
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return (parsed.hostname or "").lower()


def github_slug(value: str) -> str | None:
    match = GITHUB_RE.search(value)
    if match:
        repo = match.group(2).lower()
        if repo.endswith(".git"):
            repo = repo[: -len(".git")]
        return f"{match.group(1).lower()}/{repo}"
    parts = value.strip().strip("/").split("/")
    if len(parts) == 2 and all(parts):
        repo = parts[1].lower()
        if repo.endswith(".git"):
            repo = repo[: -len(".git")]
        return f"{parts[0].lower()}/{repo}"
    return None


def load_blacklist() -> dict[str, set[str]]:
    urls = {u.lower() for u in load_lines(HERE / "agentbaiting-skills-mcp-parsers.txt")}
    slugs = {s.lower() for s in load_lines(HERE / "agentbaiting-owner-repo.txt")}
    owners = {s.split("/", 1)[0] for s in slugs if "/" in s}
    domains = {normalize_host(d) for d in load_lines(HERE / "extra-malware-domains-2026.txt")}
    domains.discard("")
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
        elif "/" in item:
            owners.add(item.split("/", 1)[0])
    return {"urls": urls, "slugs": slugs, "owners": owners, "domains": domains, "names": names}


def extract_needles(text: str) -> set[str]:
    needles = {text.lower().strip()}
    slug = github_slug(text)
    if slug:
        needles.add(slug)
        needles.add(slug.split("/", 1)[0])
        needles.add(slug.split("/")[-1])
    host = normalize_host(text)
    if host:
        needles.add(host)
    for token in TOKEN_RE.findall(text):
        needles.add(token.lower())
        slug = github_slug(token)
        if slug:
            needles.add(slug)
            needles.add(slug.split("/")[-1])
    return {n for n in needles if n}


def match_reason(text: str, bl: dict[str, set[str]]) -> str | None:
    lowered = text.lower()
    for url in bl["urls"]:
        if url in lowered:
            return f"island-url:{url}"
    for needle in extract_needles(text):
        if needle in bl["urls"]:
            return f"island-url:{needle}"
        if needle in bl["slugs"]:
            return f"github:{needle}"
        if "/" in needle and needle.split("/", 1)[0] in bl["owners"]:
            return f"github-owner:{needle.split('/', 1)[0]}"
        if needle in bl["owners"] and "/" not in needle:
            return f"github-owner:{needle}"
        if needle in bl["domains"]:
            return f"domain:{needle}"
        if needle in bl["names"] and needle not in GENERIC_NAMES and len(needle) >= 8:
            return f"skill-name:{needle}"
    return None


def iter_user_entries(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(raw)
        if isinstance(data, list):
            return [json.dumps(item, ensure_ascii=False) if not isinstance(item, str) else item for item in data]
        if isinstance(data, dict):
            for key in ("urls", "links", "items", "services", "skills"):
                if isinstance(data.get(key), list):
                    return [str(item) for item in data[key]]
            return [json.dumps(data, ensure_ascii=False)]
    if suffix == ".csv":
        rows = []
        reader = csv.reader(raw.splitlines())
        for row in reader:
            rows.append(",".join(row))
        return rows
    return [line.rstrip("\n") for line in raw.splitlines()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Filter a service catalog against the 2026 skills/malware blacklist.")
    parser.add_argument("input", type=Path, help="Your list: .txt, .csv, or .json")
    parser.add_argument("--kept", type=Path, default=Path("kept.txt"))
    parser.add_argument("--removed", type=Path, default=Path("removed.txt"))
    args = parser.parse_args()

    if not args.input.exists():
        print(f"input not found: {args.input}", file=sys.stderr)
        return 2

    blacklist = load_blacklist()
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
