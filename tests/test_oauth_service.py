"""Testes das funções puras do oauth_service (sem rede real)."""

import base64
import pytest

from oauth_service import (
    OAuthError,
    build_authorization_url,
    build_basic_auth_header,
    exchange_code_for_tokens,
    generate_state,
    mask_secret,
    refresh_access_token,
)


def test_mask_secret():
    assert mask_secret("") == "***"
    assert mask_secret("abc") == "***"
    assert "..." in mask_secret("abcdefghijklmnop")


def test_generate_state_nao_vazio_e_diferente():
    a = generate_state()
    b = generate_state()
    assert a and b
    assert a != b


def test_build_authorization_url_contem_parametros():
    url = build_authorization_url(
        client_id="cid",
        redirect_uri="http://localhost:8501/",
        auth_url="https://auth.contaazul.com/login",
        scope="openid profile",
        state="STATEVAL",
    )
    assert "response_type=code" in url
    assert "client_id=cid" in url
    assert "redirect_uri=" in url
    assert "state=STATEVAL" in url
    assert "scope=" in url


def test_build_authorization_url_falha_sem_client_id():
    with pytest.raises(ValueError):
        build_authorization_url(
            client_id="",
            redirect_uri="http://localhost:8501",
            auth_url="https://auth.contaazul.com/login",
            scope="openid",
            state="x",
        )


def test_build_basic_auth_header_prefixo_basic():
    h = build_basic_auth_header("myid", "mysecret")
    assert h.startswith("Basic ")
    payload = base64.b64decode(h.split(" ", 1)[1]).decode("utf-8")
    assert payload == "myid:mysecret"


def test_build_basic_auth_header_sem_secret_em_texto_puro():
    secret = "super-secret-value-xyz"
    h = build_basic_auth_header("client", secret)
    assert secret not in h


def test_exchange_code_ok(monkeypatch):
    class Resp:
        status_code = 200
        text = '{"access_token":"at","refresh_token":"rt"}'

        def json(self):
            return {"access_token": "at", "refresh_token": "rt", "expires_in": 3600}

    def fake_post(url, headers=None, data=None, timeout=None):
        return Resp()

    monkeypatch.setattr("oauth_service.requests.post", fake_post)

    out = exchange_code_for_tokens(
        code="CODE",
        client_id="id",
        client_secret="sec",
        redirect_uri="http://localhost:8501",
        token_url="https://auth.contaazul.com/oauth2/token",
    )
    assert out["access_token"] == "at"


def test_exchange_code_erro_400(monkeypatch):
    class Resp:
        status_code = 400
        text = "bad"

        def json(self):
            return {}

    def fake_post(url, headers=None, data=None, timeout=None):
        return Resp()

    monkeypatch.setattr("oauth_service.requests.post", fake_post)

    with pytest.raises(OAuthError) as ei:
        exchange_code_for_tokens(
            code="CODE",
            client_id="id",
            client_secret="sec",
            redirect_uri="http://localhost:8501",
            token_url="https://auth.contaazul.com/oauth2/token",
        )
    assert ei.value.status_code == 400


def test_exchange_code_sem_access_token(monkeypatch):
    class Resp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"token_type": "Bearer"}

    def fake_post(url, headers=None, data=None, timeout=None):
        return Resp()

    monkeypatch.setattr("oauth_service.requests.post", fake_post)

    with pytest.raises(OAuthError):
        exchange_code_for_tokens(
            code="CODE",
            client_id="id",
            client_secret="sec",
            redirect_uri="http://localhost:8501",
            token_url="https://auth.contaazul.com/oauth2/token",
        )


def test_refresh_access_token_ok(monkeypatch):
    class Resp:
        status_code = 200
        text = '{"access_token":"new-at"}'

        def json(self):
            return {"access_token": "new-at", "expires_in": 3600}

    def fake_post(url, headers=None, data=None, timeout=None):
        assert data["grant_type"] == "refresh_token"
        return Resp()

    monkeypatch.setattr("oauth_service.requests.post", fake_post)

    out = refresh_access_token(
        refresh_token="r1",
        client_id="id",
        client_secret="sec",
        token_url="https://auth.contaazul.com/oauth2/token",
    )
    assert out["access_token"] == "new-at"


def test_refresh_access_token_erro_400(monkeypatch):
    class Resp:
        status_code = 400
        text = "bad request"

        def json(self):
            return {}

    def fake_post(url, headers=None, data=None, timeout=None):
        return Resp()

    monkeypatch.setattr("oauth_service.requests.post", fake_post)
    with pytest.raises(OAuthError) as ei:
        refresh_access_token(
            refresh_token="r1",
            client_id="id",
            client_secret="sec",
            token_url="https://auth.contaazul.com/oauth2/token",
        )
    assert ei.value.status_code == 400


def test_refresh_access_token_sem_access_token(monkeypatch):
    class Resp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"token_type": "Bearer"}

    def fake_post(url, headers=None, data=None, timeout=None):
        return Resp()

    monkeypatch.setattr("oauth_service.requests.post", fake_post)
    with pytest.raises(OAuthError):
        refresh_access_token(
            refresh_token="r1",
            client_id="id",
            client_secret="sec",
            token_url="https://auth.contaazul.com/oauth2/token",
        )


def test_refresh_access_token_erro_sem_expor_refresh(monkeypatch):
    sensitive = "refresh-super-secreto-123"

    class Resp:
        status_code = 500
        text = "internal"

        def json(self):
            return {}

    def fake_post(url, headers=None, data=None, timeout=None):
        return Resp()

    monkeypatch.setattr("oauth_service.requests.post", fake_post)
    with pytest.raises(OAuthError) as ei:
        refresh_access_token(
            refresh_token=sensitive,
            client_id="id",
            client_secret="sec",
            token_url="https://auth.contaazul.com/oauth2/token",
        )
    assert sensitive not in str(ei.value)
