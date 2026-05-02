"""Testes de resolução de configuração (.env / ambiente / st.secrets)."""

import pytest

from config import (
    _DEFAULT_API_BASE_URL,
    _DEFAULT_AUTH_URL,
    _DEFAULT_DIAGNOSTIC_PATH,
    _DEFAULT_SCOPE,
    _DEFAULT_TOKEN_URL,
    get_settings,
)


_ENV_KEYS = (
    "CONTA_AZUL_CLIENT_ID",
    "CONTA_AZUL_CLIENT_SECRET",
    "CONTA_AZUL_REDIRECT_URI",
    "CONTA_AZUL_AUTH_URL",
    "CONTA_AZUL_TOKEN_URL",
    "CONTA_AZUL_API_BASE_URL",
    "CONTA_AZUL_SCOPE",
    "CONTA_AZUL_DIAGNOSTIC_PATH",
)


@pytest.fixture
def clear_conta_azul_env(monkeypatch):
    for k in _ENV_KEYS:
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def fake_streamlit_secrets(monkeypatch):
    import streamlit as st

    monkeypatch.setattr(st, "secrets", {}, raising=False)


def test_env_var_precedes_streamlit_secrets(
    monkeypatch, clear_conta_azul_env, fake_streamlit_secrets
):
    import streamlit as st

    monkeypatch.setenv("CONTA_AZUL_CLIENT_ID", "from_env")
    monkeypatch.setattr(
        st,
        "secrets",
        {"CONTA_AZUL_CLIENT_ID": "from_secrets"},
        raising=False,
    )
    assert get_settings().CONTA_AZUL_CLIENT_ID == "from_env"


def test_streamlit_secrets_when_env_empty(
    monkeypatch, clear_conta_azul_env, fake_streamlit_secrets
):
    import streamlit as st

    monkeypatch.setenv("CONTA_AZUL_CLIENT_ID", "")
    monkeypatch.setattr(
        st,
        "secrets",
        {"CONTA_AZUL_CLIENT_ID": "only_secrets"},
        raising=False,
    )
    assert get_settings().CONTA_AZUL_CLIENT_ID == "only_secrets"


def test_safe_defaults_when_unset(monkeypatch, clear_conta_azul_env, fake_streamlit_secrets):
    s = get_settings()
    assert s.CONTA_AZUL_CLIENT_ID == ""
    assert s.CONTA_AZUL_CLIENT_SECRET == ""
    assert s.CONTA_AZUL_REDIRECT_URI == ""
    assert s.CONTA_AZUL_AUTH_URL == _DEFAULT_AUTH_URL
    assert s.CONTA_AZUL_TOKEN_URL == _DEFAULT_TOKEN_URL
    assert s.CONTA_AZUL_API_BASE_URL == _DEFAULT_API_BASE_URL
    assert s.CONTA_AZUL_SCOPE == _DEFAULT_SCOPE
    assert s.CONTA_AZUL_DIAGNOSTIC_PATH == _DEFAULT_DIAGNOSTIC_PATH
