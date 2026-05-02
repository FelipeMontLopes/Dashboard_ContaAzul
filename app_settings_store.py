"""Armazenamento local de configurações da aplicação (chave/valor)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app_paths import get_app_settings_db_path


def _resolve_db_path(db_path: str | None) -> str:
    return db_path if db_path is not None else str(get_app_settings_db_path())


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_settings_db(db_path: str | None = None) -> None:
    path = _resolve_db_path(db_path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()


def set_setting(key: str, value: str, db_path: str | None = None) -> None:
    if not key or not str(key).strip():
        raise ValueError("key não pode ser vazia.")
    path = _resolve_db_path(db_path)
    init_settings_db(path)
    now = _now_utc_iso()
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (str(key).strip(), value, now),
        )
        conn.commit()


def get_setting(key: str, default=None, db_path: str | None = None):
    import os

    path = _resolve_db_path(db_path)
    if not os.path.isfile(path):
        return default
    init_settings_db(path)
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
    if row is None:
        return default
    return row[0]


def delete_setting(key: str, db_path: str | None = None) -> None:
    import os

    path = _resolve_db_path(db_path)
    if not os.path.isfile(path):
        return
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
        conn.commit()


def get_all_settings(db_path: str | None = None) -> dict[str, str]:
    import os

    path = _resolve_db_path(db_path)
    if not os.path.isfile(path):
        return {}
    init_settings_db(path)
    with sqlite3.connect(path) as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    return {str(k): (v if v is not None else "") for k, v in rows}
