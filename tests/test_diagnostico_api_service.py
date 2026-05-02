import pytest

from auth_client_factory import AuthClientError
from conta_azul_client import ContaAzulAPIError
from services.diagnostico_api_service import call_diagnostic_endpoint, sanitize_api_response


def test_sanitize_mascara_access_token_dict():
    data = {"access_token": "abcdef123456"}
    out = sanitize_api_response(data)
    assert out["access_token"] != data["access_token"]
    assert "..." in out["access_token"]


def test_sanitize_mascara_refresh_token_aninhado():
    data = {"meta": {"refresh_token": "refresh-token-123456"}}
    out = sanitize_api_response(data)
    assert out["meta"]["refresh_token"] != data["meta"]["refresh_token"]


def test_sanitize_mascara_authorization_lista():
    data = [{"authorization": "Bearer token-grande-123456789"}]
    out = sanitize_api_response(data)
    assert out[0]["authorization"] != data[0]["authorization"]


def test_sanitize_preserva_campos_comuns():
    data = {"nome": "Maria", "email": "maria@empresa.com"}
    out = sanitize_api_response(data)
    assert out["nome"] == "Maria"
    assert out["email"] == "maria@empresa.com"


def test_call_endpoint_success(monkeypatch):
    class FakeClient:
        def get(self, path):
            return {"id": 1, "nome": "Empresa X"}

    monkeypatch.setattr("services.diagnostico_api_service.get_authenticated_client", lambda: FakeClient())
    monkeypatch.setattr(
        "services.diagnostico_api_service.get_settings",
        lambda: type("S", (), {"CONTA_AZUL_DIAGNOSTIC_PATH": "/v1/pessoas/conta-conectada"})(),
    )
    out = call_diagnostic_endpoint()
    assert out["success"] is True
    assert out["status"] == "ok"
    assert out["data"]["nome"] == "Empresa X"


def test_call_endpoint_auth_error(monkeypatch):
    def fake_client():
        raise AuthClientError("não conectado")

    monkeypatch.setattr("services.diagnostico_api_service.get_authenticated_client", fake_client)
    monkeypatch.setattr(
        "services.diagnostico_api_service.get_settings",
        lambda: type("S", (), {"CONTA_AZUL_DIAGNOSTIC_PATH": "/v1/pessoas/conta-conectada"})(),
    )
    out = call_diagnostic_endpoint()
    assert out["success"] is False
    assert out["status"] == "auth_error"


def test_call_endpoint_api_error_com_status(monkeypatch):
    class FakeClient:
        def get(self, path):
            raise ContaAzulAPIError(403, "forbidden", "x")

    monkeypatch.setattr("services.diagnostico_api_service.get_authenticated_client", lambda: FakeClient())
    monkeypatch.setattr(
        "services.diagnostico_api_service.get_settings",
        lambda: type("S", (), {"CONTA_AZUL_DIAGNOSTIC_PATH": "/v1/pessoas/conta-conectada"})(),
    )
    out = call_diagnostic_endpoint()
    assert out["success"] is False
    assert out["status"] == "api_error"
    assert out["status_code"] == 403


def test_call_endpoint_exception_generica(monkeypatch):
    class FakeClient:
        def get(self, path):
            raise RuntimeError("boom")

    monkeypatch.setattr("services.diagnostico_api_service.get_authenticated_client", lambda: FakeClient())
    monkeypatch.setattr(
        "services.diagnostico_api_service.get_settings",
        lambda: type("S", (), {"CONTA_AZUL_DIAGNOSTIC_PATH": "/v1/pessoas/conta-conectada"})(),
    )
    out = call_diagnostic_endpoint()
    assert out["success"] is False
    assert out["status"] == "unexpected_error"


def test_call_endpoint_usa_path_explicito(monkeypatch):
    called = {"path": None}

    class FakeClient:
        def get(self, path):
            called["path"] = path
            return {"ok": True}

    monkeypatch.setattr("services.diagnostico_api_service.get_authenticated_client", lambda: FakeClient())
    out = call_diagnostic_endpoint("/custom/path")
    assert out["success"] is True
    assert called["path"] == "/custom/path"


def test_call_endpoint_nao_retorna_token_bruto(monkeypatch):
    class FakeClient:
        def get(self, path):
            return {"token": "token-super-secreto-999999"}

    monkeypatch.setattr("services.diagnostico_api_service.get_authenticated_client", lambda: FakeClient())
    monkeypatch.setattr(
        "services.diagnostico_api_service.get_settings",
        lambda: type("S", (), {"CONTA_AZUL_DIAGNOSTIC_PATH": "/v1/pessoas/conta-conectada"})(),
    )
    out = call_diagnostic_endpoint()
    assert out["success"] is True
    assert out["data"]["token"] != "token-super-secreto-999999"
