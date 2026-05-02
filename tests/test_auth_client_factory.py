from dataclasses import dataclass

import pytest

from auth_client_factory import AuthClientError, get_authenticated_client
from token_store import load_tokens, save_tokens


@dataclass
class DummySettings:
    CONTA_AZUL_CLIENT_ID: str = "cid"
    CONTA_AZUL_CLIENT_SECRET: str = "csecret"
    CONTA_AZUL_TOKEN_URL: str = "https://auth.contaazul.com/oauth2/token"
    CONTA_AZUL_API_BASE_URL: str = "https://api-v2.contaazul.com"


def _patch_settings(monkeypatch, settings: DummySettings | None = None):
    monkeypatch.setattr("auth_client_factory.get_settings", lambda: settings or DummySettings())


def test_sem_token_salvo_levanta_erro(tmp_path, monkeypatch):
    _patch_settings(monkeypatch)
    db = tmp_path / "tokens.db"
    with pytest.raises(AuthClientError):
        get_authenticated_client(str(db))


def test_token_valido_retorna_client_sem_refresh(tmp_path, monkeypatch):
    _patch_settings(monkeypatch)
    db = tmp_path / "tokens.db"
    save_tokens("access-ok", refresh_token="refresh-ok", expires_in=3600, db_path=str(db))

    called = {"refresh": 0}

    def fake_refresh(**kwargs):
        called["refresh"] += 1
        return {"access_token": "new"}

    monkeypatch.setattr("auth_client_factory.refresh_access_token", fake_refresh)
    client = get_authenticated_client(str(db))
    assert client.base_url == "https://api-v2.contaazul.com"
    assert called["refresh"] == 0


def test_token_expirado_com_refresh_renova_e_salva(tmp_path, monkeypatch):
    _patch_settings(monkeypatch)
    db = tmp_path / "tokens.db"
    save_tokens("old-at", refresh_token="old-rt", expires_in=-10, db_path=str(db))

    def fake_refresh(**kwargs):
        return {"access_token": "new-at", "expires_in": 3600}

    monkeypatch.setattr("auth_client_factory.refresh_access_token", fake_refresh)
    client = get_authenticated_client(str(db))
    assert client.access_token == "new-at"
    saved = load_tokens(str(db))
    assert saved is not None
    assert saved["access_token"] == "new-at"


def test_token_expirado_sem_refresh_levanta_erro(tmp_path, monkeypatch):
    _patch_settings(monkeypatch)
    db = tmp_path / "tokens.db"
    save_tokens("old-at", refresh_token=None, expires_in=-10, db_path=str(db))
    with pytest.raises(AuthClientError):
        get_authenticated_client(str(db))


def test_refresh_com_novo_refresh_token_atualiza(tmp_path, monkeypatch):
    _patch_settings(monkeypatch)
    db = tmp_path / "tokens.db"
    save_tokens("old-at", refresh_token="old-rt", expires_in=-10, db_path=str(db))

    def fake_refresh(**kwargs):
        return {"access_token": "new-at", "refresh_token": "new-rt", "expires_in": 3600}

    monkeypatch.setattr("auth_client_factory.refresh_access_token", fake_refresh)
    get_authenticated_client(str(db))
    saved = load_tokens(str(db))
    assert saved is not None
    assert saved["refresh_token"] == "new-rt"


def test_refresh_sem_refresh_token_preserva_antigo(tmp_path, monkeypatch):
    _patch_settings(monkeypatch)
    db = tmp_path / "tokens.db"
    save_tokens("old-at", refresh_token="old-rt", expires_in=-10, db_path=str(db))

    def fake_refresh(**kwargs):
        return {"access_token": "new-at", "expires_in": 3600}

    monkeypatch.setattr("auth_client_factory.refresh_access_token", fake_refresh)
    get_authenticated_client(str(db))
    saved = load_tokens(str(db))
    assert saved is not None
    assert saved["refresh_token"] == "old-rt"


def test_config_incompleta_levanta_erro(tmp_path, monkeypatch):
    bad = DummySettings(CONTA_AZUL_CLIENT_ID="")
    _patch_settings(monkeypatch, bad)
    db = tmp_path / "tokens.db"
    save_tokens("at", refresh_token="rt", expires_in=3600, db_path=str(db))
    with pytest.raises(AuthClientError):
        get_authenticated_client(str(db))


def test_erro_refresh_vira_authclienterror_sem_expor_token(tmp_path, monkeypatch):
    _patch_settings(monkeypatch)
    db = tmp_path / "tokens.db"
    save_tokens("old-at", refresh_token="sensitive-refresh-token", expires_in=-10, db_path=str(db))

    def fake_refresh(**kwargs):
        raise Exception("low-level error with sensitive-refresh-token")

    monkeypatch.setattr("auth_client_factory.refresh_access_token", fake_refresh)
    with pytest.raises(AuthClientError) as ei:
        get_authenticated_client(str(db))
    assert "sensitive-refresh-token" not in str(ei.value)
