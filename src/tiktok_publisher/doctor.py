from __future__ import annotations

from pathlib import Path

from tiktok_publisher.config import AppSettings, load_settings
from tiktok_publisher.dolphin_client import DolphinClient
from tiktok_publisher.excel_registry import ExcelRegistry, create_workbook_from_template
from tiktok_publisher.geo_catalog import load_geo_catalog


def run_doctor(settings: AppSettings | None = None) -> int:
    settings = settings or load_settings()
    ok = True
    print("=== tiktok-publisher doctor ===\n")

    settings_path = Path("config/settings.yaml")
    if settings_path.is_file():
        print(f"[ok] settings: {settings_path}")
    else:
        print("[warn] config/settings.yaml не найден — используются defaults/example")

    template = Path("config/accounts.template.xlsx")
    dest = settings.excel_path
    create_workbook_from_template(template, dest)
    if dest.is_file():
        print(f"[ok] excel: {dest}")
    else:
        print(f"[fail] excel: {dest}")
        ok = False

    try:
        accounts = ExcelRegistry(settings).read_accounts()
        print(f"[ok] активных аккаунтов в Excel: {len(accounts)}")
        for acc in accounts:
            if acc.video_folder.is_dir():
                print(f"  [ok] папка {acc.video_folder}")
            else:
                print(f"  [warn] папка не найдена: {acc.video_folder}")
                ok = False
    except Exception as e:
        print(f"[fail] чтение Excel: {e}")
        ok = False

    settings.data_dir_path.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    print(f"[ok] data dir: {settings.data_dir_path}")

    if settings.dry_run:
        print("[info] dry_run=true — Dolphin не требуется для тестового прогона")
    else:
        ping_ok, msg = DolphinClient(settings).ping()
        if ping_ok:
            print(f"[ok] Dolphin API: {msg}")
        else:
            print(f"[warn] Dolphin API: {msg} (запустите Dolphin Anty на Windows)")

    sel = settings.selectors_file
    if sel.is_file():
        print(f"[ok] selectors: {sel}")
    else:
        print(f"[warn] selectors missing: {sel}")

    geo_path = settings.geo_catalog_file
    catalog = load_geo_catalog(geo_path)
    if catalog:
        print(f"[ok] geo catalog: {geo_path} ({len(catalog)} keys)")
    else:
        print(f"[warn] geo catalog empty/missing: {geo_path}")

    try:
        import pyanty  # noqa: F401

        print("[ok] pyanty installed (Dolphin profile create)")
    except ImportError:
        print("[warn] pyanty не установлен — pip install 'tiktok-publisher[dolphin]'")

    try:
        pending = ExcelRegistry(settings).read_onboarding_pending()
        print(f"[info] онбординг pending: {len(pending)} строк")
    except Exception as e:
        print(f"[info] лист онбординг: {e}")

    k = settings.orchestrator.max_concurrent_profiles
    print(f"[info] session.order={settings.session.order}")
    print(f"[info] max_concurrent_profiles={k} (рекомендация: K=1 до 16GB RAM, K=2–3 при 32GB+)")
    print(f"[info] speed_preset={settings.orchestrator.speed_preset}")

    print("\n=== done ===")
    return 0 if ok else 1
