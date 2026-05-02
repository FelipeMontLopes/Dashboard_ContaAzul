"""Persistência local do parâmetro OAuth `state` (CSRF), uma linha por banco."""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any

from app_paths import get_oauth_state_db_path


def _resolve_db_path(db_path: str | None) -> str:
    return db_path if db_path is not None else str(get_oauth_state_db_path())


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _migrate_oauth_states_schema(conn: sqlite3.Connection) -> None:
    cols = [row[1] for row in conn.execute("PRAGMA table_info(oauth_states)").fetchall()]
    if "redirect_uri" not in cols:
        conn.execute("ALTER TABLE oauth_states ADD COLUMN redirect_uri TEXT")


def init_oauth_state_db(db_path: str | None = None) -> None:
    path = _resolve_db_path(db_path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_states (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state TEXT NOT NULL,
                redirect_uri TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        _migrate_oauth_states_schema(conn)
        conn.commit()


def save_state(
    state: str,
    redirect_uri: str | None = None,
    db_path: str | None = None,
) -> None:
    if not state or not str(state).strip():
        raise ValueError("state é obrigatório.")
    path = _resolve_db_path(db_path)
    init_oauth_state_db(path)
    now = _now_utc_iso()
    redir = str(redirect_uri).strip() if redirect_uri else None
    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT id FROM oauth_states WHERE id = 1").fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO oauth_states (id, state, redirect_uri, created_at)
                VALUES (1, ?, ?, ?)
                """,
                (str(state).strip(), redir, now),
            )
        else:
            conn.execute(
                """
                UPDATE oauth_states
                SET state = ?, redirect_uri = ?, created_at = ?
                WHERE id = 1
                """,
                (str(state).strip(), redir, now),
            )
        conn.commit()


def load_state(db_path: str | None = None) -> str | None:
    ctx = load_state_context(db_path)
    if ctx is None:
        return None
    s = ctx.get("state")
    return str(s).strip() if s else None


def load_state_context(db_path: str | None = None) -> dict[str, Any] | None:
    import os

    path = _resolve_db_path(db_path)
    if not os.path.isfile(path):
        return None
    init_oauth_state_db(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT state, redirect_uri, created_at FROM oauth_states WHERE id = 1"
        ).fetchone()
    if row is None:
        return None
    st = row["state"]
    if st is None or not str(st).strip():
        return None
    return {
        "state": str(st).strip(),
        "redirect_uri": row["redirect_uri"] if row["redirect_uri"] else None,
        "created_at": row["created_at"],
    }


def clear_state(db_path: str | None = None) -> None:
    import os

    path = _resolve_db_path(db_path)
    if not os.path.isfile(path):
        return
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM oauth_states WHERE id = 1")
        conn.commit()


def validate_state(received_state: str | None, db_path: str | None = None) -> bool:
    if received_state is None or not str(received_state).strip():
        return False
    saved = load_state(db_path)
    if saved is None:
        return False
    a = saved
    b = str(received_state).strip()
    try:
        return secrets.compare_digest(a, b)
    except ValueError:
        return False
