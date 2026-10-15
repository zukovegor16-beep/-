from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


@dataclass
class PublicationRecord:
    run_id: str
    account_no: str
    account_name: str
    file_path: str
    caption_used: str
    status: str
    error_message: str
    started_at: str
    finished_at: str


class StateStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    stopped_at TEXT,
                    stop_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS publications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    account_no TEXT NOT NULL,
                    account_name TEXT,
                    file_path TEXT NOT NULL,
                    caption_used TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(id)
                );
                """
            )

    def start_run(self) -> str:
        run_id = uuid4().hex[:12]
        now = _iso_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runs (id, started_at) VALUES (?, ?)",
                (run_id, now),
            )
        return run_id

    def finish_run(self, run_id: str, reason: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET stopped_at = ?, stop_reason = ? WHERE id = ?",
                (_iso_now(), reason, run_id),
            )

    def add_publication(self, rec: PublicationRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO publications (
                    run_id, account_no, account_name, file_path, caption_used,
                    status, error_message, started_at, finished_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rec.run_id,
                    rec.account_no,
                    rec.account_name,
                    rec.file_path,
                    rec.caption_used,
                    rec.status,
                    rec.error_message,
                    rec.started_at,
                    rec.finished_at,
                ),
            )

    def publications_for_run(self, run_id: str) -> list[PublicationRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM publications WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        return [_row_to_pub(r) for r in rows]

    def last_run_id(self) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return row["id"] if row else None


def _iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _row_to_pub(row: sqlite3.Row) -> PublicationRecord:
    return PublicationRecord(
        run_id=row["run_id"],
        account_no=row["account_no"],
        account_name=row["account_name"] or "",
        file_path=row["file_path"],
        caption_used=row["caption_used"] or "",
        status=row["status"],
        error_message=row["error_message"] or "",
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )
