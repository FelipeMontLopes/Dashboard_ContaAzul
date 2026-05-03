"""Testes do handler global de callback OAuth (sem rede e sem SQLite real)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import oauth_callback_handler as och
from oauth_service import OAuthError
from services.oauth_identity_service import fingerprint_client_id, mask_client_id


@pytest.fixture(autouse=True)
def _no_connected_account_probe(monkeypatch):
    monkeypatch.setattr(och, "_try_fetch_connected_account_metadata", lambda **k: None)


@pytest.fixture
def fake_st(monkeypatch):
    """Substitui streamlit no handler com query_params e session_state controláveis."""
    st = MagicMock()
    st.query_params = MagicMock()
    st.session_state = {}
    monkeypatch.setattr(och, "st", st)
    return st


@pytest.fixture
def full_settings():
    return SimpleNamespace(
        CONTA_AZUL_CLIENT_ID="client-id",
        CONTA_AZUL_CLIENT_SECRET="secret",
        CONTA_AZUL_AUTH_URL="https://auth.example/login",
        CONTA_AZUL_TOKEN_URL="https://auth.example/token",
        CONTA_AZUL_REDIRECT_URI="https://app.example/cb",
        CONTA_AZUL_API_BASE_URL="https://api.example",
        CONTA_AZUL_SCOPE="openid profile",
        CONTA_AZUL_DIAGNOSTIC_PATH="/v1/pessoas/conta-conectada",
    )


def test_sem_callback_retorna_handled_false(fake_st):
    out = och.handle_oauth_callback({})
    assert out["handled"] is False
    assert out["status"] == "no_callback"


def test_error_retorna_handled_true_fail(fake_st):
    out = och.handle_oauth_callback({"error": "access_denied"})
    assert out["handled"] is True
    assert out["success"] is False
    assert out["status"] == "oauth_error"
    assert "Autorização cancelada ou recusada" in (out["message"] or "")


def test_state_invalido_nao_chama_exchange(
    monkeypatch, fake_st, full_settings
):
    monkeypatch.setattr(och, "get_settings", lambda: full_settings)
    monkeypatch.setattr(och, "get_oauth_readiness", lambda *a, **k: {"ready": True})
    monkeypatch.setattr(och, "get_effective_redirect_uri", lambda **k: "https://r/")
    monkeypatch.setattr(
        och,
        "validate_redirect_uri_format",
        lambda u: {"valid": True, "warnings": [], "errors": []},
    )
    monkeypatch.setattr(och, "init_token_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "init_oauth_state_db", lambda *a, **k: None)

    called = {"n": 0}

    def boom(**kwargs):
        called["n"] += 1
        raise AssertionError("exchange não deve ser chamado")

    monkeypatch.setattr(och, "exchange_code_for_tokens", boom)
    monkeypatch.setattr(och, "validate_state", lambda *a, **k: False)
    monkeypatch.setattr(och, "clear_state", lambda *a, **k: None)

    out = och.handle_oauth_callback({"code": "c1", "state": "bad"})
    assert called["n"] == 0
    assert out["status"] == "invalid_state"


def test_code_state_valido_chama_exchange_e_salva_tokens(
    monkeypatch, fake_st, full_settings
):
    monkeypatch.setattr(och, "get_settings", lambda: full_settings)
    monkeypatch.setattr(och, "get_oauth_readiness", lambda *a, **k: {"ready": True})
    monkeypatch.setattr(och, "get_effective_redirect_uri", lambda **k: "https://r/")
    monkeypatch.setattr(
        och,
        "validate_redirect_uri_format",
        lambda u: {"valid": True, "warnings": [], "errors": []},
    )
    monkeypatch.setattr(och, "init_token_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "init_oauth_state_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "validate_state", lambda *a, **k: True)
    monkeypatch.setattr(
        och,
        "load_state_context",
        lambda *a, **k: {"state": "x", "redirect_uri": None, "created_at": "t"},
    )

    saved = {}
    exchange_kw: dict = {}

    def fake_exchange(**kwargs):
        exchange_kw.update(kwargs)
        saved.update(kwargs)
        return {
            "access_token": "at",
            "refresh_token": "rt",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid",
        }

    monkeypatch.setattr(och, "exchange_code_for_tokens", fake_exchange)

    def fake_save(**kwargs):
        saved["save_kw"] = kwargs

    monkeypatch.setattr(och, "save_tokens", fake_save)
    monkeypatch.setattr(
        och,
        "load_tokens",
        lambda db_path=None: {
            "access_token": "at",
            "refresh_token": "rt",
            "token_type": "Bearer",
            "expires_at": None,
            "scope": "openid",
            "updated_at": "t",
        },
    )
    monkeypatch.setattr(och, "clear_state", lambda *a, **k: None)

    out = och.handle_oauth_callback({"code": "auth-code-xyz", "state": "ok"})
    assert exchange_kw.get("redirect_uri") == "https://r/"
    assert "save_kw" in saved
    assert saved["save_kw"]["access_token"] == "at"
    assert saved["save_kw"]["client_id_fingerprint"] == fingerprint_client_id("client-id")
    assert saved["save_kw"]["client_id_masked"] == mask_client_id("client-id")
    assert out["success"] is True
    assert out["status"] == "connected"
    assert out["token_saved"] is True
    assert out["has_access_token_response"] is True
    assert out["has_refresh_token_response"] is True
    assert out["token_db_path"]


def test_usa_redirect_uri_do_contexto(monkeypatch, fake_st, full_settings):
    monkeypatch.setattr(och, "get_settings", lambda: full_settings)
    monkeypatch.setattr(och, "get_oauth_readiness", lambda *a, **k: {"ready": True})
    monkeypatch.setattr(och, "get_effective_redirect_uri", lambda **k: "https://fallback/")
    monkeypatch.setattr(
        och,
        "validate_redirect_uri_format",
        lambda u: {"valid": True, "warnings": [], "errors": []},
    )
    monkeypatch.setattr(och, "init_token_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "init_oauth_state_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "validate_state", lambda *a, **k: True)
    monkeypatch.setattr(
        och,
        "load_state_context",
        lambda *a, **k: {
            "redirect_uri": "https://from-context/cb",
            "state": "x",
            "created_at": "t",
        },
    )

    captured = {}

    def fake_exchange(**kwargs):
        captured.update(kwargs)
        return {"access_token": "a"}

    monkeypatch.setattr(och, "exchange_code_for_tokens", fake_exchange)
    monkeypatch.setattr(och, "save_tokens", lambda **k: None)
    monkeypatch.setattr(och, "load_tokens", lambda db_path=None: {"access_token": "a"})
    monkeypatch.setattr(och, "clear_state", lambda *a, **k: None)

    och.handle_oauth_callback({"code": "c", "state": "s"})
    assert captured["redirect_uri"] == "https://from-context/cb"


def test_fallback_redirect_sem_contexto(monkeypatch, fake_st, full_settings):
    monkeypatch.setattr(och, "get_settings", lambda: full_settings)
    monkeypatch.setattr(och, "get_oauth_readiness", lambda *a, **k: {"ready": True})
    monkeypatch.setattr(och, "get_effective_redirect_uri", lambda **k: "https://fallback/app/")
    monkeypatch.setattr(
        och,
        "validate_redirect_uri_format",
        lambda u: {"valid": True, "warnings": [], "errors": []},
    )
    monkeypatch.setattr(och, "init_token_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "init_oauth_state_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "validate_state", lambda *a, **k: True)
    monkeypatch.setattr(och, "load_state_context", lambda *a, **k: None)

    captured = {}

    def fake_exchange(**kwargs):
        captured.update(kwargs)
        return {"access_token": "a"}

    monkeypatch.setattr(och, "exchange_code_for_tokens", fake_exchange)
    monkeypatch.setattr(och, "save_tokens", lambda **k: None)
    monkeypatch.setattr(och, "load_tokens", lambda db_path=None: {"access_token": "a"})
    monkeypatch.setattr(och, "clear_state", lambda *a, **k: None)

    och.handle_oauth_callback({"code": "c", "state": "s"})
    assert captured["redirect_uri"] == "https://fallback/app/"


def test_oauth_error_mensagem_segura(monkeypatch, fake_st, full_settings):
    monkeypatch.setattr(och, "get_settings", lambda: full_settings)
    monkeypatch.setattr(och, "get_oauth_readiness", lambda *a, **k: {"ready": True})
    monkeypatch.setattr(och, "get_effective_redirect_uri", lambda **k: "https://r/")
    monkeypatch.setattr(
        och,
        "validate_redirect_uri_format",
        lambda u: {"valid": True, "warnings": [], "errors": []},
    )
    monkeypatch.setattr(och, "init_token_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "init_oauth_state_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "validate_state", lambda *a, **k: True)
    monkeypatch.setattr(och, "load_state_context", lambda *a, **k: None)

    def raise_oauth(**kwargs):
        raise OAuthError(
            "Falha na troca do código.",
            status_code=400,
            response_text="SEGREDO_NAO_EXIBIR",
        )

    monkeypatch.setattr(och, "exchange_code_for_tokens", raise_oauth)
    monkeypatch.setattr(och, "clear_state", lambda *a, **k: None)

    out = och.handle_oauth_callback({"code": "c", "state": "s"})
    assert out["success"] is False
    assert out["message"] == "Falha na troca do código."
    assert "SEGREDO" not in (out["message"] or "")


def test_exception_generica_mensagem_segura(monkeypatch, fake_st, full_settings):
    monkeypatch.setattr(och, "get_settings", lambda: full_settings)
    monkeypatch.setattr(och, "get_oauth_readiness", lambda *a, **k: {"ready": True})
    monkeypatch.setattr(och, "get_effective_redirect_uri", lambda **k: "https://r/")
    monkeypatch.setattr(
        och,
        "validate_redirect_uri_format",
        lambda u: {"valid": True, "warnings": [], "errors": []},
    )
    monkeypatch.setattr(och, "init_token_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "init_oauth_state_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "validate_state", lambda *a, **k: True)
    monkeypatch.setattr(och, "load_state_context", lambda *a, **k: None)
    monkeypatch.setattr(
        och,
        "exchange_code_for_tokens",
        MagicMock(side_effect=RuntimeError("boom")),
    )
    monkeypatch.setattr(och, "clear_state", lambda *a, **k: None)

    out = och.handle_oauth_callback({"code": "c", "state": "s"})
    assert out["success"] is False
    assert out["message"] == "Erro inesperado ao concluir conexão OAuth."


def test_tokens_nao_confirmados_localmente(monkeypatch, fake_st, full_settings):
    monkeypatch.setattr(och, "get_settings", lambda: full_settings)
    monkeypatch.setattr(och, "get_oauth_readiness", lambda *a, **k: {"ready": True})
    monkeypatch.setattr(och, "get_effective_redirect_uri", lambda **k: "https://r/")
    monkeypatch.setattr(
        och,
        "validate_redirect_uri_format",
        lambda u: {"valid": True, "warnings": [], "errors": []},
    )
    monkeypatch.setattr(och, "init_token_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "init_oauth_state_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "validate_state", lambda *a, **k: True)
    monkeypatch.setattr(och, "load_state_context", lambda *a, **k: None)
    monkeypatch.setattr(
        och,
        "exchange_code_for_tokens",
        lambda **k: {"access_token": "ok"},
    )
    monkeypatch.setattr(och, "save_tokens", lambda **k: None)
    monkeypatch.setattr(och, "load_tokens", lambda db_path=None: None)
    monkeypatch.setattr(och, "clear_state", lambda *a, **k: None)

    out = och.handle_oauth_callback({"code": "c", "state": "s"})
    assert out["status"] == "persist_failed"
    assert out["token_saved"] is False
    assert "persistência" in (out["message"] or "")


def test_nao_processa_code_duplicado(monkeypatch, fake_st, full_settings):
    monkeypatch.setattr(och, "get_settings", lambda: full_settings)
    monkeypatch.setattr(och, "get_oauth_readiness", lambda *a, **k: {"ready": True})
    monkeypatch.setattr(och, "get_effective_redirect_uri", lambda **k: "https://r/")
    monkeypatch.setattr(
        och,
        "validate_redirect_uri_format",
        lambda u: {"valid": True, "warnings": [], "errors": []},
    )
    monkeypatch.setattr(och, "init_token_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "init_oauth_state_db", lambda *a, **k: None)
    monkeypatch.setattr(och, "validate_state", lambda *a, **k: True)
    monkeypatch.setattr(och, "load_state_context", lambda *a, **k: None)

    calls = {"n": 0}

    def fake_exchange(**kwargs):
        calls["n"] += 1
        return {"access_token": "x"}

    monkeypatch.setattr(och, "exchange_code_for_tokens", fake_exchange)
    monkeypatch.setattr(och, "save_tokens", lambda **k: None)
    monkeypatch.setattr(och, "load_tokens", lambda db_path=None: {"access_token": "x"})
    monkeypatch.setattr(och, "clear_state", lambda *a, **k: None)

    och.handle_oauth_callback({"code": "same-code", "state": "s"})
    fp = fake_st.session_state.get("oauth_last_processed_code_fp")
    assert fp is not None

    out2 = och.handle_oauth_callback({"code": "same-code", "state": "s"})
    assert calls["n"] == 1
    assert out2["status"] == "duplicate_callback"
