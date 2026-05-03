"""Persistência local de tokens OAuth (MVP, uma conexão por banco)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from app_paths import get_token_db_path
from services.oauth_identity_service import short_fingerprint


def _resolve_db_path(db_path: str | None) -> str:
    return db_path if db_path is not None else str(get_token_db_path())


_OAUTH_EXTRA_COLUMNS: tuple[tuple[str, str], ...] = (
    ("client_id_fingerprint", "TEXT"),
    ("client_id_masked", "TEXT"),
    ("connected_account_name", "TEXT"),
    ("connected_account_id", "TEXT"),
)


def _migrate_oauth_columns(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(oauth_tokens)").fetchall()
    existing = {str(r[1]) for r in rows}
    for col, sql_type in _OAUTH_EXTRA_COLUMNS:
        if col not in existing:
            conn.execute(f"ALTER TABLE oauth_tokens ADD COLUMN {col} {sql_type}")


def init_token_db(db_path: str | None = None) -> None:
    path = _resolve_db_path(db_path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                access_token TEXT,
                refresh_token TEXT,
                token_type TEXT,
                expires_at TEXT,
                scope TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        _migrate_oauth_columns(conn)
        conn.commit()


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_expires_at(value: str | None) -> datetime | None:
    if not value or not str(value).strip():
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def save_tokens(
    access_token: str,
    refresh_token: str | None = None,
    token_type: str = "Bearer",
    expires_in: int | None = None,
    scope: str | None = None,
    *,
    client_id_fingerprint: str | None = None,
    client_id_masked: str | None = None,
    connected_account_name: str | None = None,
    connected_account_id: str | None = None,
    db_path: str | None = None,
) -> None:
    if not access_token or not str(access_token).strip():
        raise ValueError("access_token é obrigatório.")

    path = _resolve_db_path(db_path)
    init_token_db(path)
    now_iso = _now_utc_iso()

    expires_at: str | None = None
    if expires_in is not None:
        try:
            sec = int(expires_in)
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=sec)).isoformat()
        except (TypeError, ValueError):
            expires_at = None

    prior = load_tokens(path)
    fp_use = (
        client_id_fingerprint
        if client_id_fingerprint is not None
        else (prior.get("client_id_fingerprint") if prior else None)
    )
    masked_use = (
        client_id_masked if client_id_masked is not None else (prior.get("client_id_masked") if prior else None)
    )
    name_use = (
        connected_account_name
        if connected_account_name is not None
        else (prior.get("connected_account_name") if prior else None)
    )
    id_use = (
        connected_account_id
        if connected_account_id is not None
        else (prior.get("connected_account_id") if prior else None)
    )

    with sqlite3.connect(path) as conn:
        row = conn.execute("SELECT id, created_at FROM oauth_tokens WHERE id = 1").fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO oauth_tokens (
                    id, access_token, refresh_token, token_type,
                    expires_at, scope, created_at, updated_at,
                    client_id_fingerprint, client_id_masked,
                    connected_account_name, connected_account_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    access_token.strip(),
                    refresh_token.strip() if refresh_token else None,
                    token_type or "Bearer",
                    expires_at,
                    scope,
                    now_iso,
                    now_iso,
                    fp_use,
                    masked_use,
                    name_use,
                    id_use,
                ),
            )
        else:
            created_at = row[1]
            conn.execute(
                """
                UPDATE oauth_tokens SET
                    access_token = ?,
                    refresh_token = ?,
                    token_type = ?,
                    expires_at = ?,
                    scope = ?,
                    updated_at = ?,
                    client_id_fingerprint = ?,
                    client_id_masked = ?,
                    connected_account_name = ?,
                    connected_account_id = ?
                WHERE id = 1
                """,
                (
                    access_token.strip(),
                    refresh_token.strip() if refresh_token else None,
                    token_type or "Bearer",
                    expires_at,
                    scope,
                    now_iso,
                    fp_use,
                    masked_use,
                    name_use,
                    id_use,
                ),
            )
            if created_at is None:
                conn.execute(
                    "UPDATE oauth_tokens SET created_at = ? WHERE id = 1 AND created_at IS NULL",
                    (now_iso,),
                )
        conn.commit()


def update_connected_account_metadata(
    *,
    connected_account_name: str | None,
    connected_account_id: str | None,
    db_path: str | None = None,
) -> None:
    """Atualiza apenas nome/ID da conta conectada (sem alterar tokens)."""
    path = _resolve_db_path(db_path)
    if not _db_exists(path):
        return
    init_token_db(path)
    now_iso = _now_utc_iso()
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            UPDATE oauth_tokens SET
                connected_account_name = ?,
                connected_account_id = ?,
                updated_at = ?
            WHERE id = 1
            """,
            (connected_account_name, connected_account_id, now_iso),
        )
        conn.commit()


def load_tokens(db_path: str | None = None) -> dict[str, Any] | None:
    path = _resolve_db_path(db_path)
    if not _db_exists(path):
        return None
    init_token_db(path)
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT access_token, refresh_token, token_type, expires_at, scope,
                   created_at, updated_at,
                   client_id_fingerprint, client_id_masked,
                   connected_account_name, connected_account_id
            FROM oauth_tokens WHERE id = 1
            """
        ).fetchone()
    if row is None:
        return None
    data = dict(row)
    if not data.get("access_token"):
        return None
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "token_type": data["token_type"],
        "expires_at": data["expires_at"],
        "scope": data["scope"],
        "created_at": data["created_at"],
        "updated_at": data["updated_at"],
        "client_id_fingerprint": data.get("client_id_fingerprint"),
        "client_id_masked": data.get("client_id_masked"),
        "connected_account_name": data.get("connected_account_name"),
        "connected_account_id": data.get("connected_account_id"),
    }


def _db_exists(db_path: str) -> bool:
    import os

    return os.path.isfile(db_path)


def clear_tokens(db_path: str | None = None) -> None:
    path = _resolve_db_path(db_path)
    if not _db_exists(path):
        return
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM oauth_tokens WHERE id = 1")
        conn.commit()


def is_connected(db_path: str | None = None) -> bool:
    data = load_tokens(db_path)
    return bool(data and data.get("access_token"))


def is_token_expired(token_data: dict[str, Any] | None, safety_seconds: int = 60) -> bool:
    if token_data is None:
        return True
    raw = token_data.get("expires_at")
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        return False
    exp = _parse_expires_at(str(raw))
    if exp is None:
        return True
    try:
        safety = int(safety_seconds)
    except (TypeError, ValueError):
        safety = 60
    limite = datetime.now(timezone.utc) + timedelta(seconds=safety)
    return exp <= limite


def get_connection_status(db_path: str | None = None) -> dict[str, Any]:
    """
    Status seguro da conexão local — nunca inclui access_token nem refresh_token.
    """
    data = load_tokens(db_path)
    connected = bool(data and data.get("access_token"))
    has_refresh = bool(data and data.get("refresh_token"))
    expires_raw = data.get("expires_at") if data else None
    expired = is_token_expired(data) if data else True
    fp_full = data.get("client_id_fingerprint") if data else None
    return {
        "connected": connected,
        "has_refresh_token": has_refresh,
        "expires_at": expires_raw if expires_raw else None,
        "expired": expired if connected else True,
        "scope": data.get("scope") if data else None,
        "updated_at": data.get("updated_at") if data else None,
        "client_id_masked": data.get("client_id_masked") if data else None,
        "client_id_fingerprint_short": short_fingerprint(fp_full),
        "connected_account_name": data.get("connected_account_name") if data else None,
        "connected_account_id": data.get("connected_account_id") if data else None,
    }
