from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from tiktok_publisher.config import AppSettings
from tiktok_publisher.excel_pending import sync_pending_excel
from tiktok_publisher.log_buffer import get_log_tail
from tiktok_publisher.orchestrator import Orchestrator
from tiktok_publisher.preflight import run_preflight


def create_app(settings: AppSettings, orchestrator: Orchestrator) -> FastAPI:
    app = FastAPI(title="TikTok Publisher", version="0.1.0")
    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        index_path = static_dir / "index.html"
        if not index_path.is_file():
            return HTMLResponse("<h1>TikTok Publisher</h1><p>static/index.html missing</p>")
        return HTMLResponse(index_path.read_text(encoding="utf-8"))

    @app.get("/api/status")
    def status() -> dict:
        snap = orchestrator.status_snapshot()
        snap["logs"] = get_log_tail(30)
        return snap

    @app.get("/api/preflight")
    def preflight() -> dict:
        pf = run_preflight(settings)
        return {"ok": pf.ok, "issues": [i.__dict__ for i in pf.issues]}

    @app.post("/api/sync-excel")
    def sync_excel() -> dict:
        applied, failed = sync_pending_excel(settings)
        return {"applied": applied, "failed": failed}

    @app.post("/api/start")
    def start_run() -> dict:
        if orchestrator.is_running:
            raise HTTPException(status_code=409, detail="Already running")
        if settings.orchestrator.require_preflight:
            pf = run_preflight(settings)
            if not pf.ok:
                raise HTTPException(
                    status_code=400,
                    detail={"message": "Preflight failed", "issues": [i.__dict__ for i in pf.issues]},
                )
        try:
            run_id = orchestrator.start()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"run_id": run_id, "started": True}

    @app.post("/api/stop")
    def stop_run() -> dict:
        orchestrator.stop()
        return {"stop_requested": True}

    @app.get("/api/report/latest")
    def report_latest() -> FileResponse:
        path = orchestrator.last_report_path
        if not path or not path.is_file():
            run_id = orchestrator.store.last_run_id()
            if run_id:
                candidate = settings.reports_dir / f"report_{run_id}.xlsx"
                if candidate.is_file():
                    path = candidate
        if not path or not path.is_file():
            raise HTTPException(status_code=404, detail="No report yet")
        return FileResponse(
            path,
            filename=path.name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.get("/api/logs")
    def logs(tail: int = 50) -> dict:
        return {"lines": get_log_tail(tail)}

    return app
