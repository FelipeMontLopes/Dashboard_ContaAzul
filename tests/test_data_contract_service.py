"""Testes de data_contract_service."""

from __future__ import annotations

import json

import pytest

from services import data_contract_service as dcs


def test_infer_json_contract_simple_dict() -> None:
    c = dcs.infer_json_contract({"nome": "x", "valor_total": 10.5})
    assert c["root_type"] == "dict"
    assert "nome" in c["top_level_keys"]
    assert "valor_total" in (c["candidate_money_fields"] or [])


def test_infer_json_contract_list_of_dict() -> None:
    rows = [
        {"id": "1", "data_vencimento": "2024-01-15", "valor": 100},
        {"id": "2", "data_vencimento": "2024-02-01", "valor": 200},
    ]
    c = dcs.infer_json_contract(rows)
    assert c["root_type"] == "list"
    assert c["total_items"] == 2
    assert "data_vencimento" in (c["candidate_date_fields"] or [])
    assert "valor" in (c["candidate_money_fields"] or [])


def test_infer_json_contract_empty_list() -> None:
    c = dcs.infer_json_contract([])
    assert c["root_type"] == "list"
    assert c["total_items"] == 0


def test_detects_date_candidate_keys() -> None:
    c = dcs.infer_json_contract({"competencia": "2024-03-01"})
    assert "competencia" in (c["candidate_date_fields"] or [])


def test_detects_money_candidate_keys() -> None:
    c = dcs.infer_json_contract({"saldo_liquido": 1})
    assert "saldo_liquido" in (c["candidate_money_fields"] or [])


def test_detects_status_candidate_keys() -> None:
    c = dcs.infer_json_contract({"situacao": "ABERTO"})
    assert "situacao" in (c["candidate_status_fields"] or [])


def test_sanitize_examples_removes_sensitive_keys() -> None:
    c = dcs.infer_json_contract(
        [{"access_token": "eyJhbGciOiJIUzI1NiIsIm-secret-part", "name": "ok"}]
    )
    ex = c["safe_examples"][0]
    assert isinstance(ex, dict)
    assert ex.get("access_token") != "eyJhbGciOiJIUzI1NiIsIm-secret-part"


def test_infer_contract_from_snapshot_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"items": [{"id": 1}]}

    def _fake_get_snapshot_by_id(snapshot_id: int, db_path: str | None = None):
        return {
            "id": snapshot_id,
            "resource_name": "test_res",
            "path": "/v1/x",
            "fetched_at": "2025-01-01T00:00:00+00:00",
            "response_json": json.dumps(payload),
        }

    monkeypatch.setattr(dcs, "get_snapshot_by_id", _fake_get_snapshot_by_id)
    out = dcs.infer_contract_from_snapshot(42)
    assert out.get("error") is None
    assert out["snapshot_id"] == 42
    assert out["resource_name"] == "test_res"
    assert out["contract"]["root_type"] == "dict"
    assert "pagination_candidates" in out["contract"]


def test_infer_json_contract_pagination_candidates() -> None:
    c = dcs.infer_json_contract({"pagina": 1, "itens": [], "total_registros": 10})
    assert "pagina" in (c.get("pagination_candidates") or [])
    assert "total_registros" in (c.get("pagination_candidates") or [])
