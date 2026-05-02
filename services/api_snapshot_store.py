"""Persistência de snapshots sanitizados de respostas da API Conta Azul."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app_paths import get_snapshot_db_path
from services.diagnostico_api_service import sanitize_api_response


def _resolve_db_path(db_path: str | None) -> str:
    return db_path if db_path is not None else str(get_snapshot_db_path())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_json_dumps(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps({"_serialization_error": str(obj)}, ensure_ascii=False)


def init_snapshot_db(db_path: str | None = None) -> None:
    path = _resolve_db_path(db_path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                resource_name TEXT NOT NULL,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                params_json TEXT,
                status TEXT,
                status_code INTEGER,
                success INTEGER NOT NULL,
                response_json TEXT,
                error_message TEXT,
                fetched_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_api_snapshot(
    resource_name: str,
    method: str,
    path: str,
    params: dict[str, Any] | None,
    success: bool,
    data: Any = None,
    error_message: str | None = None,
    status_code: int | None = None,
    db_path: str | None = None,
) -> int:
    """Persiste snapshot com dados já sanitizados (sem tokens em claro). Retorna id."""
    init_snapshot_db(db_path)
    p = _resolve_db_path(db_path)
    params_clean = params if params is not None else {}
    params_json = _safe_json_dumps(params_clean)

    safe_data: Any = None
    if data is not None:
        try:
            safe_data = sanitize_api_response(data)
        except Exception:
            safe_data = {"_sanitize_fallback": str(type(data).__name__)}

    response_json: str | None
    if safe_data is not None:
        response_json = _safe_json_dumps(safe_data)
    else:
        response_json = None

    st = "ok" if success else "error"
    with sqlite3.connect(p) as conn:
        cur = conn.execute(
            """
            INSERT INTO api_snapshots (
                resource_name, method, path, params_json, status, status_code,
                success, response_json, error_message, fetched_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resource_name,
                method.strip().upper(),
                path,
                params_json,
                st,
                status_code,
                1 if success else 0,
                response_json,
                error_message,
                _now_iso(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def list_api_snapshots(
    limit: int = 50,
    resource_name: str | None = None,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    init_snapshot_db(db_path)
    p = _resolve_db_path(db_path)
    limit = max(1, min(int(limit), 500))
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        if resource_name:
            rows = conn.execute(
                """
                SELECT id, resource_name, method, path, params_json, status, status_code,
                       success, response_json, error_message, fetched_at
                FROM api_snapshots
                WHERE resource_name = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (resource_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, resource_name, method, path, params_json, status, status_code,
                       success, response_json, error_message, fetched_at
                FROM api_snapshots
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def get_latest_snapshot(resource_name: str, db_path: str | None = None) -> dict[str, Any] | None:
    init_snapshot_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, resource_name, method, path, params_json, status, status_code,
                   success, response_json, error_message, fetched_at
            FROM api_snapshots
            WHERE resource_name = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (resource_name,),
        ).fetchone()
    return dict(row) if row else None


def get_snapshot_by_id(snapshot_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    init_snapshot_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT id, resource_name, method, path, params_json, status, status_code,
                   success, response_json, error_message, fetched_at
            FROM api_snapshots
            WHERE id = ?
            """,
            (int(snapshot_id),),
        ).fetchone()
    return dict(row) if row else None
