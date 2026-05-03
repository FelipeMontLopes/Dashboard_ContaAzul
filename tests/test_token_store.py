"""Testes do armazenamento local de tokens."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import app_paths
from services.oauth_identity_service import fingerprint_client_id
from token_store import (
    clear_tokens,
    get_connection_status,
    init_token_db,
    is_connected,
    is_token_expired,
    load_tokens,
    save_tokens,
)


def test_padrao_save_load_mesmo_banco_via_app_paths(monkeypatch, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.setattr(app_paths, "get_project_root", lambda: proj)

    save_tokens("access-default", refresh_token="ref-default", expires_in=7200)
    expected = Path(proj / ".local_data" / "conta_azul_tokens.db").resolve()
    assert expected.is_file()
    data = load_tokens()
    assert data is not None
    assert data["access_token"] == "access-default"
    clear_tokens()
    assert load_tokens() is None


def test_init_token_db_cria_banco_e_tabela(tmp_path):
    db = tmp_path / "tokens.db"
    assert not db.exists()
    init_token_db(str(db))
    assert db.exists()


def test_load_tokens_retorna_none_quando_vazio(tmp_path):
    db = tmp_path / "empty.db"
    assert load_tokens(str(db)) is None


def test_save_e_load_tokens(tmp_path):
    db = tmp_path / "t.db"
    save_tokens("access-secret", refresh_token="refresh-secret", expires_in=3600, db_path=str(db))
    data = load_tokens(str(db))
    assert data is not None
    assert data["access_token"] == "access-secret"
    assert data["refresh_token"] == "refresh-secret"
    assert data["token_type"] == "Bearer"
    assert data["expires_at"] is not None
    assert data["scope"] is None


def test_is_connected_true_apos_salvar(tmp_path):
    db = tmp_path / "c.db"
    save_tokens("tok", db_path=str(db))
    assert is_connected(str(db)) is True


def test_clear_remove_token(tmp_path):
    db = tmp_path / "cl.db"
    save_tokens("tok", db_path=str(db))
    clear_tokens(str(db))
    assert load_tokens(str(db)) is None


def test_is_connected_false_apos_limpar(tmp_path):
    db = tmp_path / "cl2.db"
    save_tokens("tok", db_path=str(db))
    clear_tokens(str(db))
    assert is_connected(str(db)) is False


def test_is_token_expired_true_para_vencido():
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    assert is_token_expired({"expires_at": past}, safety_seconds=60) is True


def test_is_token_expired_false_para_valido():
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert is_token_expired({"expires_at": future}, safety_seconds=60) is False


def test_get_connection_status_nao_retorna_secrets(tmp_path):
    db = tmp_path / "sec.db"
    fp = fingerprint_client_id("meu-client-id") or "x"
    save_tokens(
        "acc-x",
        refresh_token="ref-y",
        expires_in=7200,
        scope="read write",
        client_id_fingerprint=fp,
        client_id_masked="abc...xyz",
        connected_account_name="Empresa",
        connected_account_id="id-1",
        db_path=str(db),
    )
    status = get_connection_status(str(db))
    assert "access_token" not in status
    assert "refresh_token" not in status
    assert status["connected"] is True
    assert status["has_refresh_token"] is True
    assert status["scope"] == "read write"
    assert status["expires_at"] is not None
    assert status["client_id_masked"] == "abc...xyz"
    assert status["connected_account_name"] == "Empresa"
    assert status["connected_account_id"] == "id-1"
    assert len(status["client_id_fingerprint_short"]) >= 8


def test_save_load_preserva_client_id_fingerprint(tmp_path):
    db = tmp_path / "fp.db"
    fp = fingerprint_client_id("app-client") or ""
    save_tokens(
        "tok",
        refresh_token="r",
        expires_in=3600,
        client_id_fingerprint=fp,
        client_id_masked="masked-x",
        db_path=str(db),
    )
    data = load_tokens(str(db))
    assert data is not None
    assert data["client_id_fingerprint"] == fp
    assert data["client_id_masked"] == "masked-x"


def test_migracao_adiciona_colunas_em_banco_antigo(tmp_path):
    import sqlite3

    db = tmp_path / "legacy.db"
    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            """
            CREATE TABLE oauth_tokens (
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
        conn.execute(
            """
            INSERT INTO oauth_tokens (
                id, access_token, refresh_token, token_type,
                expires_at, scope, created_at, updated_at
            )
            VALUES (1, 'at', 'rt', 'Bearer', NULL, NULL, 'c', 'u')
            """
        )
        conn.commit()

    init_token_db(str(db))
    data = load_tokens(str(db))
    assert data is not None
    assert data["access_token"] == "at"
    assert data.get("client_id_fingerprint") is None


def test_is_token_expired_none_retorna_true():
    assert is_token_expired(None) is True


def test_is_token_expired_sem_expires_retorna_false():
    assert is_token_expired({"access_token": "x", "expires_at": None}) is False
