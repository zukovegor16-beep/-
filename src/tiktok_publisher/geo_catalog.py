from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from tiktok_publisher.config import AppSettings


@dataclass(frozen=True)
class GeoSpec:
    latitude: float
    longitude: float
    timezone: str
    locale: str


def load_geo_catalog(path: Path | None = None) -> dict[str, GeoSpec]:
    if path is None:
        path = Path("config/geo_catalog.yaml")
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, GeoSpec] = {}
    for key, val in raw.items():
        if not isinstance(val, dict):
            continue
        code = str(key).strip().upper()
        out[code] = GeoSpec(
            latitude=float(val["latitude"]),
            longitude=float(val["longitude"]),
            timezone=str(val["timezone"]),
            locale=str(val["locale"]),
        )
    return out


def resolve_geo(settings: AppSettings, geo_key: str) -> GeoSpec:
    catalog = load_geo_catalog(settings.geo_catalog_file)
    code = geo_key.strip().upper()
    if code not in catalog:
        raise KeyError(f"geo '{geo_key}' not in catalog {settings.geo_catalog_file}")
    return catalog[code]
