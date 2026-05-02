import pytest

from conta_azul_client import ContaAzulAPIError, ContaAzulClient, mask_token


class DummyResponse:
    def __init__(self, status_code=200, json_data=None, text="", json_raises=False):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self._json_raises = json_raises

    def json(self):
        if self._json_raises:
            raise ValueError("invalid json")
        return self._json_data


def test_base_url_vazio_levanta_value_error():
    with pytest.raises(ValueError):
        ContaAzulClient(base_url="", access_token="token123456")


def test_access_token_vazio_levanta_value_error():
    with pytest.raises(ValueError):
        ContaAzulClient(base_url="https://api.exemplo.com", access_token="")


def test_path_com_barra_sem_barra_monta_url(monkeypatch):
    captured = []

    def fake_request(self, method, url, **kwargs):
        captured.append(url)
        return DummyResponse(status_code=200, json_data={"ok": True}, text='{"ok":true}')

    monkeypatch.setattr("requests.Session.request", fake_request)
    c = ContaAzulClient("https://api.exemplo.com/", "token123456789")
    c.get("v1/clientes")
    c.get("/v1/clientes")

    assert captured[0] == "https://api.exemplo.com/v1/clientes"
    assert captured[1] == "https://api.exemplo.com/v1/clientes"


def test_resposta_json_200_retorna_dict(monkeypatch):
    def fake_request(self, method, url, **kwargs):
        return DummyResponse(status_code=200, json_data={"id": 1}, text='{"id":1}')

    monkeypatch.setattr("requests.Session.request", fake_request)
    c = ContaAzulClient("https://api.exemplo.com", "token123456789")
    out = c.get("/v1/recurso")
    assert out == {"id": 1}


def test_resposta_texto_200_retorna_texto(monkeypatch):
    def fake_request(self, method, url, **kwargs):
        return DummyResponse(status_code=200, text="ok", json_raises=True)

    monkeypatch.setattr("requests.Session.request", fake_request)
    c = ContaAzulClient("https://api.exemplo.com", "token123456789")
    out = c.get("/ping")
    assert out == "ok"


def test_resposta_204_retorna_none(monkeypatch):
    def fake_request(self, method, url, **kwargs):
        return DummyResponse(status_code=204, text="")

    monkeypatch.setattr("requests.Session.request", fake_request)
    c = ContaAzulClient("https://api.exemplo.com", "token123456789")
    out = c.delete("/v1/recurso/1")
    assert out is None


def test_erro_401_levanta_api_error(monkeypatch):
    def fake_request(self, method, url, **kwargs):
        return DummyResponse(status_code=401, text="unauthorized")

    monkeypatch.setattr("requests.Session.request", fake_request)
    c = ContaAzulClient("https://api.exemplo.com", "token123456789")
    with pytest.raises(ContaAzulAPIError) as exc:
        c.get("/v1/protegido")
    assert exc.value.status_code == 401


def test_erro_404_levanta_api_error(monkeypatch):
    def fake_request(self, method, url, **kwargs):
        return DummyResponse(status_code=404, text="not found")

    monkeypatch.setattr("requests.Session.request", fake_request)
    c = ContaAzulClient("https://api.exemplo.com", "token123456789")
    with pytest.raises(ContaAzulAPIError) as exc:
        c.get("/v1/inexistente")
    assert exc.value.status_code == 404


def test_erro_429_tenta_retry(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    def fake_request(self, method, url, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            return DummyResponse(status_code=429, text="too many")
        return DummyResponse(status_code=200, json_data={"ok": True}, text='{"ok":true}')

    def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr("requests.Session.request", fake_request)
    monkeypatch.setattr("time.sleep", fake_sleep)

    c = ContaAzulClient("https://api.exemplo.com", "token123456789", max_retries=2)
    out = c.get("/v1/retry")

    assert out == {"ok": True}
    assert calls["n"] == 3
    assert sleeps == [1, 2]


def test_mask_token_nao_retorna_token_completo():
    token = "abcdefghijklmnop"
    masked = mask_token(token)
    assert masked != token
    assert masked.startswith("abcdef")
    assert masked.endswith("nop")
