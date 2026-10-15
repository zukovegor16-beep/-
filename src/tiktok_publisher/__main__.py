from __future__ import annotations

import argparse
import logging
import sys

import uvicorn

from tiktok_publisher.config import load_settings
from tiktok_publisher.doctor import run_doctor
from tiktok_publisher.excel_pending import sync_pending_excel
from tiktok_publisher.instance_lock import InstanceLock, InstanceLockError
from tiktok_publisher.log_buffer import setup_logging
from tiktok_publisher.orchestrator import Orchestrator
from tiktok_publisher.preflight import run_preflight
from tiktok_publisher.report import export_last_run


def _print_preflight(settings, exit_on_fail: bool) -> bool:
    pf = run_preflight(settings)
    for issue in pf.issues:
        tag = issue.level.upper()
        print(f"[{tag}] {issue.code}: {issue.message}")
    if not pf.ok and exit_on_fail:
        return False
    return pf.ok or not exit_on_fail


def main() -> None:
    parser = argparse.ArgumentParser(prog="tiktok-publisher")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve", help="Web UI + API")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)

    p_start = sub.add_parser("start", help="Run orchestrator in foreground")
    p_start.add_argument("--dry-run", action="store_true")
    p_start.add_argument("--skip-preflight", action="store_true")
    p_start.add_argument("--only-errors", metavar="RUN_ID", default=None)

    sub.add_parser("stop", help="No-op unless using API; use Ctrl+C for foreground")

    p_report = sub.add_parser("report", help="Export last run report path")
    p_report.add_argument("--run", default="last")

    p_doctor = sub.add_parser("doctor", help="Check config, Excel, folders, Dolphin")
    p_doctor.add_argument(
        "--list-stale-profiles",
        action="store_true",
        help="Показать подсказку по зависшим профилям Dolphin",
    )

    sub.add_parser("plan", help="Show run plan from Excel (no publish)")
    sub.add_parser("preflight", help="Preflight checks without publishing")
    sub.add_parser("sync-excel", help="Apply pending Excel writes from last failed sync")

    p_onboard = sub.add_parser("onboard", help="Run onboarding from Excel sheet")
    p_onboard.add_argument("--dry-run", action="store_true")
    p_onboard.add_argument("--skip-preflight", action="store_true")

    sub.add_parser("onboard-plan", help="Show pending onboarding rows (no CDP)")
    sub.add_parser("onboard-continue", help="Resume onboard after manual OTP (with serve API)")

    p_smoke = sub.add_parser("smoke", help="Open TikTok upload in Dolphin profile")
    p_smoke.add_argument("--profile-id", required=True)

    args = parser.parse_args()
    settings = load_settings()
    setup_logging(settings.logging.log_dir)

    if args.cmd == "doctor":
        if getattr(args, "list_stale_profiles", False):
            from tiktok_publisher.dolphin_registry import active_profiles

            ids = active_profiles()
            if ids:
                print("[warn] active in this process:", ", ".join(ids))
            else:
                print("[info] нет активных профилей в этом процессе")
            print("[info] закройте лишние профили в Dolphin Anty вручную при сбоях")
        sys.exit(run_doctor(settings))

    if args.cmd == "preflight":
        ok = _print_preflight(settings, exit_on_fail=False)
        sys.exit(0 if ok else 1)

    if args.cmd == "sync-excel":
        applied, failed = sync_pending_excel(settings)
        print(f"applied={applied} failed={failed}")
        sys.exit(0 if failed == 0 else 1)

    if args.cmd == "onboard-plan":
        from tiktok_publisher.excel_registry import ExcelRegistry
        from tiktok_publisher.onboard_plan import build_onboard_plan

        reg = ExcelRegistry(settings)
        pending = reg.read_onboarding_pending()
        plan = build_onboard_plan(pending, settings)
        print(f"Pending onboarding rows: {plan.total}")
        for s in plan.rows:
            print(
                f"  row={s.row_index} geo={s.geo} login={s.tiktok_login!r} "
                f"profile={'yes' if s.has_profile else 'no'} avatar={'ok' if s.avatar_ok else '—'}"
            )
        return

    if args.cmd == "onboard-continue":
        print(
            "Используйте POST /api/onboard/continue при запущенном serve "
            "или дождитесь таймаута manual_wait_sec",
            file=sys.stderr,
        )
        return

    if args.cmd == "onboard":
        from tiktok_publisher.onboarding_orchestrator import OnboardingOrchestrator
        from tiktok_publisher.preflight import run_preflight_onboard

        if args.dry_run:
            settings.dry_run = True
        if not args.skip_preflight:
            pf = run_preflight_onboard(settings)
            for issue in pf.issues:
                print(f"[{issue.level.upper()}] {issue.code}: {issue.message}")
            if not pf.ok:
                sys.exit(1)
        lock = InstanceLock(settings.data_dir_path / ".publisher.lock")
        try:
            lock.acquire()
        except InstanceLockError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
        ob = OnboardingOrchestrator(settings)
        try:
            ob.start()
        except Exception as e:
            print(e, file=sys.stderr)
            sys.exit(1)
        try:
            ob.wait()
        except KeyboardInterrupt:
            ob.stop()
            ob.wait(120)
        finally:
            lock.release()
        return

    if args.cmd == "plan":
        from tiktok_publisher.excel_registry import ExcelRegistry
        from tiktok_publisher.run_plan import build_run_plan

        accs = ExcelRegistry(settings).read_accounts()
        plan = build_run_plan(accs, settings)
        print(f"Accounts: {len(accs)}, total slots: {plan.total_slots}")
        for s in plan.snapshots:
            print(
                f"  {s.account_no} {s.account_name!r} queue={s.queue_count} "
                f"per_run={s.videos_per_run} profile={s.dolphin_profile_id}"
            )
        return

    if args.cmd == "smoke":
        from tiktok_publisher.smoke import run_smoke

        sys.exit(run_smoke(settings, args.profile_id))

    if args.cmd == "report":
        from tiktok_publisher.state import StateStore

        store = StateStore(settings.db_path)
        if args.run == "last":
            path = export_last_run(settings, store)
            if path:
                print(path)
            else:
                print("No runs yet", file=sys.stderr)
                sys.exit(1)
        return

    lock = InstanceLock(settings.data_dir_path / ".publisher.lock")

    if args.cmd == "start":
        if args.dry_run:
            settings.dry_run = True
        if not args.skip_preflight and settings.orchestrator.require_preflight:
            if not _print_preflight(settings, exit_on_fail=True):
                sys.exit(1)
        try:
            lock.acquire()
        except InstanceLockError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
        orch = Orchestrator(settings)
        if args.only_errors:
            orch.only_errors_from_run_id = args.only_errors
        run_id = orch.start()
        logging.info("Started run %s", run_id)
        try:
            orch.wait()
        except KeyboardInterrupt:
            orch.stop()
            orch.wait(120)
        finally:
            lock.release()
        print(f"Report: {orch.last_report_path}")
        return

    if args.cmd == "serve":
        from tiktok_publisher.api import create_app

        try:
            lock.acquire()
        except InstanceLockError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
        host = args.host or settings.server.host
        port = args.port or settings.server.port
        from tiktok_publisher.onboarding_orchestrator import OnboardingOrchestrator

        orch = Orchestrator(settings)
        onboard_orch = OnboardingOrchestrator(settings)
        app = create_app(settings, orch, onboard_orch)
        try:
            uvicorn.run(app, host=host, port=port, log_level="info")
        finally:
            lock.release()
        return

    if args.cmd == "stop":
        print(
            "Для остановки используйте POST /api/stop в веб-UI или Ctrl+C в foreground",
            file=sys.stderr,
        )
        return


if __name__ == "__main__":
    main()
