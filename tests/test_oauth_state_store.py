"""Testes do armazenamento local de OAuth state."""

import sqlite3

import pytest

from oauth_state_store import (
    clear_state,
    init_oauth_state_db,
    load_state,
    load_state_context,
    save_state,
    validate_state,
)


def test_load_state_none_quando_vazio(tmp_path):
    db = tmp_path / "st.db"
    assert load_state(str(db)) is None


def test_save_e_load_state(tmp_path):
    db = tmp_path / "st.db"
    save_state("abc-state", db_path=str(db))
    assert load_state(str(db)) == "abc-state"


def test_validate_state_true(tmp_path):
    db = tmp_path / "st.db"
    save_state("same", db_path=str(db))
    assert validate_state("same", db_path=str(db)) is True


def test_validate_state_false(tmp_path):
    db = tmp_path / "st.db"
    save_state("expected", db_path=str(db))
    assert validate_state("other", db_path=str(db)) is False


def test_clear_state_remove(tmp_path):
    db = tmp_path / "st.db"
    save_state("x", db_path=str(db))
    clear_state(str(db))
    assert load_state(str(db)) is None


def test_save_state_com_redirect_uri(tmp_path):
    db = tmp_path / "st2.db"
    save_state("st", redirect_uri="https://cb.example/oauth", db_path=str(db))
    ctx = load_state_context(str(db))
    assert ctx is not None
    assert ctx["state"] == "st"
    assert ctx["redirect_uri"] == "https://cb.example/oauth"
    assert load_state(str(db)) == "st"


def test_migration_adiciona_redirect_uri(tmp_path):
    db = tmp_path / "legacy.db"
    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            """
            CREATE TABLE oauth_states (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO oauth_states (id, state, created_at) VALUES (1, 'old', '2020-01-01')",
        )
        conn.commit()
    init_oauth_state_db(str(db))
    save_state("new", redirect_uri="https://t.com", db_path=str(db))
    ctx = load_state_context(str(db))
    assert ctx["redirect_uri"] == "https://t.com"
