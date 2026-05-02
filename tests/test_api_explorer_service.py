"""Testes de api_explorer_service (sem chamadas HTTP reais)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from auth_client_factory import AuthClientError
from conta_azul_client import ContaAzulAPIError
from services import api_explorer_service as ex


def test_summarize_dict() -> None:
    s = ex.summarize_response_shape({"a": [1, 2], "b": {"z": 1}})
    assert s["type"] == "dict"
    assert "a" in s["keys"]


def test_summarize_list_of_dict() -> None:
    s = ex.summarize_response_shape([{"id": 1}, {"id": 2}])
    assert s["type"] == "list"
    assert s["length"] == 2
    assert "id" in (s.get("first_item_keys") or [])


def test_summarize_empty_list() -> None:
    s = ex.summarize_response_shape([])
    assert s["type"] == "list"
    assert s["length"] == 0


class _FakeClient:
    def __init__(self, payload: Any = None, exc: Exception | None = None) -> None:
        self._payload = payload
        self._exc = exc

    def get(self, path: str, params: dict | None = None) -> Any:
        if self._exc:
            raise self._exc
        return self._payload


def test_call_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = str(tmp_path / "s.db")

    monkeypatch.setattr(
        ex,
        "get_authenticated_client",
        lambda: _FakeClient({"items": [{"id": 1}]}),
    )
    r = ex.call_api_endpoint("r", "GET", "/v1/pessoas", {}, save_snapshot=True, db_path=db)
    assert r["success"] is True
    assert r["data"] == {"items": [{"id": 1}]}
    assert r["response_shape"]["type"] == "dict"


def test_call_auth_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = str(tmp_path / "s.db")

    def _boom() -> Any:
        raise AuthClientError("sem oauth")

    monkeypatch.setattr(ex, "get_authenticated_client", _boom)
    r = ex.call_api_endpoint("r", "GET", "/v1/x", {}, db_path=db)
    assert r["success"] is False
    assert "oauth" in (r["error_message"] or "").lower()


def test_call_api_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = str(tmp_path / "s.db")

    class _Err:
        def get(self, path: str, params: dict | None = None) -> Any:
            raise ContaAzulAPIError(403, "proibido", response_text=None)

    monkeypatch.setattr(ex, "get_authenticated_client", lambda: _Err())
    r = ex.call_api_endpoint("r", "GET", "/v1/x", {}, db_path=db)
    assert r["success"] is False
    assert r["status_code"] == 403


def test_path_without_slash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = str(tmp_path / "s.db")
    monkeypatch.setattr(ex, "get_authenticated_client", lambda: _FakeClient({}))
    r = ex.call_api_endpoint("r", "GET", "sem-barra", {}, db_path=db)
    assert r["success"] is False
    assert "Path inválido" in (r["error_message"] or "")


def test_params_none_becomes_empty_dict(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = str(tmp_path / "s.db")
    calls: list[dict | None] = []

    class _Cap:
        def get(self, path: str, params: dict | None = None) -> dict:
            calls.append(params)
            return {}

    monkeypatch.setattr(ex, "get_authenticated_client", lambda: _Cap())
    ex.call_api_endpoint("r", "GET", "/v1/a", None, db_path=db)
    assert calls == [{}]


def test_get_default_financial_period_params_structure() -> None:
    p = ex.get_default_financial_period_params()
    assert p["pagina"] == 1
    assert p["tamanho_pagina"] == 100
    assert "data_inicio" in p and "data_fim" in p
    assert "T00:00:00" in p["data_inicio"]
    assert "T23:59:59" in p["data_fim"]


def test_get_default_endpoints_financial_have_dates() -> None:
    eps = ex.get_default_endpoints()
    by_name = {e["resource_name"]: e for e in eps}
    assert "data_inicio" in by_name["financeiro_saldo_inicial"]["params"]
    assert "data_fim" in by_name["financeiro_saldo_inicial"]["params"]
    assert "data_inicio" in by_name["financeiro_alteracoes"]["params"]
    assert by_name["pessoas"]["params"]["pagina"] == 1


def test_call_forwards_params_to_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db = str(tmp_path / "s.db")
    calls: list[tuple[str, dict | None]] = []

    class _Cap:
        def get(self, path: str, params: dict | None = None) -> dict:
            calls.append((path, params))
            return {}

    monkeypatch.setattr(ex, "get_authenticated_client", lambda: _Cap())
    params = {"data_inicio": "2026-01-01T00:00:00", "data_fim": "2026-03-12T23:59:59"}
    ex.call_api_endpoint(
        "fin",
        "GET",
        "/v1/financeiro/eventos-financeiros/saldo-inicial",
        params,
        db_path=db,
    )
    assert len(calls) == 1
    assert calls[0][1] == params


def test_needs_financial_period_params() -> None:
    assert ex.needs_financial_period_params("/v1/financeiro/eventos-financeiros/saldo-inicial")
    assert ex.needs_financial_period_params("/x/financeiro/eventos-financeiros/alteracoes")
    assert not ex.needs_financial_period_params("/v1/pessoas")
