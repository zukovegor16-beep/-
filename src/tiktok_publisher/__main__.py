from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import uvicorn

from tiktok_publisher.config import load_settings
from tiktok_publisher.doctor import run_doctor
from tiktok_publisher.log_buffer import setup_logging
from tiktok_publisher.orchestrator import Orchestrator
from tiktok_publisher.report import export_last_run


def main() -> None:
    parser = argparse.ArgumentParser(prog="tiktok-publisher")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_serve = sub.add_parser("serve", help="Web UI + API")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)

    p_start = sub.add_parser("start", help="Run orchestrator in foreground")
    p_start.add_argument("--dry-run", action="store_true")

    sub.add_parser("stop", help="No-op unless using API; use Ctrl+C for foreground")

    p_report = sub.add_parser("report", help="Export last run report path")
    p_report.add_argument("--run", default="last")

    sub.add_parser("doctor", help="Check config, Excel, folders, Dolphin")

    args = parser.parse_args()
    settings = load_settings()
    setup_logging(settings.logging.log_dir)

    if args.cmd == "doctor":
        sys.exit(run_doctor(settings))

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

    if args.cmd == "start":
        if args.dry_run:
            settings.dry_run = True
        orch = Orchestrator(settings)
        run_id = orch.start()
        logging.info("Started run %s", run_id)
        try:
            orch.wait()
        except KeyboardInterrupt:
            orch.stop()
            orch.wait(120)
        print(f"Report: {orch.last_report_path}")
        return

    if args.cmd == "serve":
        from tiktok_publisher.api import create_app

        host = args.host or settings.server.host
        port = args.port or settings.server.port
        orch = Orchestrator(settings)
        app = create_app(settings, orch)
        uvicorn.run(app, host=host, port=port, log_level="info")
        return

    if args.cmd == "stop":
        print("Для остановки используйте POST /api/stop в веб-UI или Ctrl+C в foreground", file=sys.stderr)
        return


if __name__ == "__main__":
    main()
