from __future__ import annotations

import logging
import re
from typing import Any

from tiktok_publisher.config import AppSettings
from tiktok_publisher.geo_catalog import GeoSpec, resolve_geo

logger = logging.getLogger(__name__)


def _parse_proxy(proxy_raw: str | None) -> dict[str, Any] | None:
    if not proxy_raw or not str(proxy_raw).strip():
        return None
    s = str(proxy_raw).strip()
    # user:pass@host:port or host:port
    m = re.match(r"(?:(?P<login>[^:]+):(?P<password>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)", s)
    if not m:
        return None
    g = m.groupdict()
    return {
        "type": "http",
        "host": g["host"],
        "port": g["port"],
        "login": g.get("login") or "",
        "password": g.get("password") or "",
        "name": s,
    }


def create_profile_for_geo(
    settings: AppSettings,
    name: str,
    geo_key: str,
    proxy: str | None = None,
    *,
    dry_run: bool = False,
) -> str:
    if dry_run:
        fake = f"dry-{geo_key}-{abs(hash(name)) % 10**6}"
        logger.info("[dry-run] create_profile %s geo=%s -> %s", name, geo_key, fake)
        return fake

    spec = resolve_geo(settings, geo_key)
    try:
        from pyanty import DolphinAPI, STABLE_CHROME_VERSION  # type: ignore
    except ImportError as e:
        raise RuntimeError("pip install 'tiktok-publisher[dolphin]'") from e

    token = settings.dolphin.api_token
    api = DolphinAPI(api_key=token) if token else DolphinAPI()
    fingerprint = api.generate_fingerprint(
        platform="windows",
        browser_version=STABLE_CHROME_VERSION,
    )
    data = api.fingerprint_to_profile(name=name, fingerprint=fingerprint)
    data["geolocation"] = {
        "mode": "manual",
        "latitude": spec.latitude,
        "longitude": spec.longitude,
        "accuracy": 100,
    }
    data["timezone"] = {"mode": "manual", "value": spec.timezone}
    data["locale"] = {"mode": "manual", "value": spec.locale}
    proxy_dict = _parse_proxy(proxy)
    if proxy_dict:
        data["proxy"] = proxy_dict

    result = api.create_profile(data)
    profile_id = str(result.get("browserProfileId") or result.get("id") or "")
    if not profile_id:
        raise RuntimeError(f"create_profile failed: {result}")
    logger.info("Created Dolphin profile %s geo=%s", profile_id, geo_key)
    return profile_id


def apply_geo_spec_to_profile_data(data: dict, spec: GeoSpec) -> dict:
    data = dict(data)
    data["geolocation"] = {
        "mode": "manual",
        "latitude": spec.latitude,
        "longitude": spec.longitude,
        "accuracy": 100,
    }
    data["timezone"] = {"mode": "manual", "value": spec.timezone}
    data["locale"] = {"mode": "manual", "value": spec.locale}
    return data
