from __future__ import annotations

from dataclasses import dataclass

from tiktok_publisher.config import AppSettings
from tiktok_publisher.excel_registry import OnboardRow
from tiktok_publisher.geo_catalog import load_geo_catalog


@dataclass
class OnboardPlanSnapshot:
    row_index: int
    geo: str
    tiktok_login: str
    has_profile: bool
    avatar_ok: bool


@dataclass
class OnboardPlan:
    rows: list[OnboardPlanSnapshot]
    total: int

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "rows": [
                {
                    "row_index": s.row_index,
                    "geo": s.geo,
                    "tiktok_login": s.tiktok_login,
                    "has_profile": s.has_profile,
                    "avatar_ok": s.avatar_ok,
                }
                for s in self.rows
            ],
        }


def build_onboard_plan(rows: list[OnboardRow], settings: AppSettings) -> OnboardPlan:
    catalog = load_geo_catalog(settings.geo_catalog_file)
    snapshots: list[OnboardPlanSnapshot] = []
    for row in rows:
        snapshots.append(
            OnboardPlanSnapshot(
                row_index=row.row_index,
                geo=row.geo,
                tiktok_login=row.tiktok_login,
                has_profile=bool(row.dolphin_profile_id.strip()),
                avatar_ok=row.avatar_path.is_file() if row.avatar_path else False,
            )
        )
        code = row.geo.strip().upper()
        if code and code not in catalog:
            pass  # preflight catches geo errors
    return OnboardPlan(rows=snapshots, total=len(snapshots))
