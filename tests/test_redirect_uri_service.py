from types import SimpleNamespace

import pytest

from app_settings_store import set_setting
from redirect_uri_service import (
    SETTING_REDIRECT_URI,
    clear_redirect_uri_override,
    get_effective_redirect_uri,
    get_env_redirect_uri,
    save_redirect_uri_override,
    sanitize_redirect_uri,
    validate_redirect_uri_format,
)


def test_sanitize_strip():
    assert sanitize_redirect_uri("  https://a.com  ") == "https://a.com"


def test_validate_erro_vazio():
    r = validate_redirect_uri_format("")
    assert r["valid"] is False
    assert r["errors"]
    assert r.get("is_placeholder") is False


def test_validate_https_ok():
    r = validate_redirect_uri_format("https://api.example.com/callback")
    assert r["valid"] is True
    assert not r["errors"]
    assert r.get("is_placeholder") is False


def test_validate_http_localhost_warning():
    r = validate_redirect_uri_format("http://localhost:8501")
    assert r["valid"] is True
    assert any("localhost" in w for w in r["warnings"])


def test_validate_http_nao_localhost_warning():
    r = validate_redirect_uri_format("http://api.interno.local:8501/callback")
    assert r["valid"] is True
    assert any("HTTPS" in w or "https" in w.lower() for w in r["warnings"])


def test_validate_barra_final_warning():
    r = validate_redirect_uri_format("https://x.com/")
    assert r["valid"] is True
    assert any("barra" in w.lower() for w in r["warnings"])


def test_validate_rejeita_abc123_ngrok_placeholder():
    r = validate_redirect_uri_format("https://abc123.ngrok-free.app/")
    assert r["valid"] is False
    assert r.get("is_placeholder") is True


def test_validate_rejeita_seu_subdominio_ngrok_placeholder():
    r = validate_redirect_uri_format("https://seu-subdominio.ngrok-free.app")
    assert r["valid"] is False
    assert r.get("is_placeholder") is True


def test_validate_rejeita_example_com_callback():
    r = validate_redirect_uri_format("https://example.com/callback")
    assert r["valid"] is False
    assert r.get("is_placeholder") is True


def test_validate_aceita_ngrok_real():
    r = validate_redirect_uri_format("https://a1b2c3d4.ngrok-free.app/")
    assert r["valid"] is True
    assert r.get("is_placeholder") is False


def test_validate_aceita_https_producao():
    r = validate_redirect_uri_format("https://dashboard-minhaempresa.com/callback")
    assert r["valid"] is True
    assert r.get("is_placeholder") is False


def test_get_effective_override_sobre_env(monkeypatch, tmp_path):
    db = str(tmp_path / "app.db")
    monkeypatch.setattr(
        "redirect_uri_service.get_settings",
        lambda: SimpleNamespace(CONTA_AZUL_REDIRECT_URI="https://env.com"),
    )
    set_setting(SETTING_REDIRECT_URI, "https://saved.com", db_path=db)
    assert get_effective_redirect_uri(db_path=db) == "https://saved.com"


def test_get_effective_usa_env(monkeypatch, tmp_path):
    db = str(tmp_path / "app.db")
    monkeypatch.setattr(
        "redirect_uri_service.get_settings",
        lambda: SimpleNamespace(CONTA_AZUL_REDIRECT_URI="https://envonly.com"),
    )
    assert get_effective_redirect_uri(db_path=db) == "https://envonly.com"


def test_save_override_valida(monkeypatch, tmp_path):
    db = str(tmp_path / "app.db")
    monkeypatch.setattr(
        "redirect_uri_service.get_settings",
        lambda: SimpleNamespace(CONTA_AZUL_REDIRECT_URI=""),
    )
    save_redirect_uri_override("https://ngrok.example/app", db_path=db)
    assert get_effective_redirect_uri(db_path=db) == "https://ngrok.example/app"


def test_save_override_invalida(tmp_path):
    db = str(tmp_path / "app.db")
    with pytest.raises(ValueError):
        save_redirect_uri_override("ftp://bad", db_path=db)


def test_env_redirect(monkeypatch):
    monkeypatch.setattr(
        "redirect_uri_service.get_settings",
        lambda: SimpleNamespace(CONTA_AZUL_REDIRECT_URI="  https://e.com  "),
    )
    assert get_env_redirect_uri() == "https://e.com"


def test_clear_override(monkeypatch, tmp_path):
    db = str(tmp_path / "app.db")
    monkeypatch.setattr(
        "redirect_uri_service.get_settings",
        lambda: SimpleNamespace(CONTA_AZUL_REDIRECT_URI="https://env.com"),
    )
    save_redirect_uri_override("https://saved.com", db_path=db)
    clear_redirect_uri_override(db_path=db)
    assert get_effective_redirect_uri(db_path=db) == "https://env.com"
