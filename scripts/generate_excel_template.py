#!/usr/bin/env python3
"""Generate config/accounts.template.xlsx."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

HEADERS = [
    "account_no",
    "account_name",
    "video_folder",
    "dolphin_profile_id",
    "videos_per_run",
    "caption_variants",
    "active",
    "last_run_status",
    "last_run_error",
    "last_run_at",
]

EXAMPLE_ROW = [
    1,
    "Shop_1",
    r"D:\Videos\acc01",
    "123456789",
    2,
    "Текст 1 #fyp|||Текст 2 #shop|||Текст 3",
    "да",
    "",
    "",
    "",
]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "config" / "accounts.template.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Аккаунты"
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.append(EXAMPLE_ROW)
    ws.column_dimensions["C"].width = 36
    ws.column_dimensions["F"].width = 48
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
