"""Testes para oauth_readiness.get_oauth_readiness."""

from types import SimpleNamespace

import oauth_readiness as oauth_readiness_mod
from oauth_readiness import get_oauth_readiness, get_oauth_token_binding_status
from redirect_uri_service import validate_redirect_uri_format


def _valid_redirect_validation():
    return {"valid": True, "warnings": [], "errors": [], "is_placeholder": False}


def _invalid_redirect_validation():
    return {
        "valid": False,
        "warnings": [],
        "errors": ["URL de redirecionamento não informada."],
        "is_placeholder": False,
    }


def test_tudo_configurado_ready_true():
    settings = SimpleNamespace(
        CONTA_AZUL_CLIENT_ID="id",
        CONTA_AZUL_CLIENT_SECRET="sec",
        CONTA_AZUL_AUTH_URL="https://auth.example/login",
        CONTA_AZUL_TOKEN_URL="https://auth.example/token",
    )
    vr = _valid_redirect_validation()
    vr["warnings"] = ["localhost pode não ser aceito"]
    out = get_oauth_readiness(settings, "https://x.ngrok-free.app/", vr)
    assert out["ready"] is True
    assert out["missing"] == []
    assert "localhost pode não ser aceito" in out["warnings"]
    assert "oauth_token_binding" in out


def test_binding_sem_tokens_ok(monkeypatch, tmp_path):
    monkeypatch.setattr(
        oauth_readiness_mod,
        "get_token_db_path",
        lambda: tmp_path / "nao_existe.db",
    )
    settings = SimpleNamespace(CONTA_AZUL_CLIENT_ID="abc1234567890")
    b = get_oauth_token_binding_status(settings)
    assert b["binding_ok"] is True
    assert b["has_stored_tokens"] is False


def test_binding_mismatch(monkeypatch, tmp_path):
    from token_store import save_tokens

    db = tmp_path / "tok.db"
    fp_velho = "a" * 64
    save_tokens(
        "access",
        refresh_token="r",
        expires_in=3600,
        client_id_fingerprint=fp_velho,
        db_path=str(db),
    )
    monkeypatch.setattr(oauth_readiness_mod, "get_token_db_path", lambda: db)

    settings = SimpleNamespace(CONTA_AZUL_CLIENT_ID="outro-client-completamente-diferente-xyz")
    b = get_oauth_token_binding_status(settings)
    assert b["has_stored_tokens"] is True
    assert b["binding_ok"] is False
    assert b["client_mismatch"] is True


def test_sem_client_id():
    settings = SimpleNamespace(
        CONTA_AZUL_CLIENT_ID="",
        CONTA_AZUL_CLIENT_SECRET="sec",
        CONTA_AZUL_AUTH_URL="https://a",
        CONTA_AZUL_TOKEN_URL="https://t",
    )
    out = get_oauth_readiness(settings, "https://x.app/", _valid_redirect_validation())
    assert out["ready"] is False
    assert any("Client ID" in m for m in out["missing"])


def test_sem_client_secret():
    settings = SimpleNamespace(
        CONTA_AZUL_CLIENT_ID="id",
        CONTA_AZUL_CLIENT_SECRET="",
        CONTA_AZUL_AUTH_URL="https://a",
        CONTA_AZUL_TOKEN_URL="https://t",
    )
    out = get_oauth_readiness(settings, "https://x.app/", _valid_redirect_validation())
    assert out["ready"] is False
    assert any("Client Secret" in m for m in out["missing"])


def test_sem_auth_url():
    settings = SimpleNamespace(
        CONTA_AZUL_CLIENT_ID="id",
        CONTA_AZUL_CLIENT_SECRET="sec",
        CONTA_AZUL_AUTH_URL="",
        CONTA_AZUL_TOKEN_URL="https://t",
    )
    out = get_oauth_readiness(settings, "https://x.app/", _valid_redirect_validation())
    assert out["ready"] is False
    assert any("Auth URL" in m for m in out["missing"])


def test_sem_token_url():
    settings = SimpleNamespace(
        CONTA_AZUL_CLIENT_ID="id",
        CONTA_AZUL_CLIENT_SECRET="sec",
        CONTA_AZUL_AUTH_URL="https://a",
        CONTA_AZUL_TOKEN_URL="",
    )
    out = get_oauth_readiness(settings, "https://x.app/", _valid_redirect_validation())
    assert out["ready"] is False
    assert any("Token URL" in m for m in out["missing"])


def test_sem_redirect_uri():
    settings = SimpleNamespace(
        CONTA_AZUL_CLIENT_ID="id",
        CONTA_AZUL_CLIENT_SECRET="sec",
        CONTA_AZUL_AUTH_URL="https://a",
        CONTA_AZUL_TOKEN_URL="https://t",
    )
    out = get_oauth_readiness(settings, "", _invalid_redirect_validation())
    assert out["ready"] is False
    assert any("redirecionamento não configurada" in m for m in out["missing"])


def test_redirect_invalida():
    settings = SimpleNamespace(
        CONTA_AZUL_CLIENT_ID="id",
        CONTA_AZUL_CLIENT_SECRET="sec",
        CONTA_AZUL_AUTH_URL="https://a",
        CONTA_AZUL_TOKEN_URL="https://t",
    )
    vr = {
        "valid": False,
        "warnings": [],
        "errors": ["schema inválido"],
        "is_placeholder": False,
    }
    out = get_oauth_readiness(settings, "ftp://bad", vr)
    assert out["ready"] is False
    assert "schema inválido" in out["missing"]


def test_placeholder_redirect_not_ready():
    settings = SimpleNamespace(
        CONTA_AZUL_CLIENT_ID="id",
        CONTA_AZUL_CLIENT_SECRET="sec",
        CONTA_AZUL_AUTH_URL="https://a",
        CONTA_AZUL_TOKEN_URL="https://t",
    )
    vr = {
        "valid": False,
        "warnings": [],
        "errors": ["detalhe placeholder"],
        "is_placeholder": True,
    }
    out = get_oauth_readiness(settings, "https://abc123.ngrok-free.app/", vr)
    assert out["ready"] is False
    assert any(
        "URL de redirecionamento é placeholder" in m for m in out["missing"]
    )


def test_real_ngrok_url_ready_when_other_fields_ok():
    settings = SimpleNamespace(
        CONTA_AZUL_CLIENT_ID="id",
        CONTA_AZUL_CLIENT_SECRET="sec",
        CONTA_AZUL_AUTH_URL="https://a",
        CONTA_AZUL_TOKEN_URL="https://t",
    )
    uri = "https://a1b2c3d4.ngrok-free.app/"
    vr = validate_redirect_uri_format(uri)
    assert vr["valid"] is True
    out = get_oauth_readiness(settings, uri, vr)
    assert out["ready"] is True


def test_redirect_warning_mas_valida_ready_true():
    settings = SimpleNamespace(
        CONTA_AZUL_CLIENT_ID="id",
        CONTA_AZUL_CLIENT_SECRET="sec",
        CONTA_AZUL_AUTH_URL="https://a",
        CONTA_AZUL_TOKEN_URL="https://t",
    )
    vr = {
        "valid": True,
        "warnings": ["Atenção: barra final"],
        "errors": [],
        "is_placeholder": False,
    }
    out = get_oauth_readiness(settings, "https://x.ngrok-free.app/", vr)
    assert out["ready"] is True
    assert out["missing"] == []
