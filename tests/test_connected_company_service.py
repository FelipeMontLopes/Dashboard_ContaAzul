"""Testes do serviço de verificação da empresa conectada (sem rede por padrão)."""

from pathlib import Path

from services import connected_company_service as ccs


def test_extract_company_fields_dict():
    payload = {
        "nome": " ACME ",
        "id": "uuid-1",
        "cnpj": "11222333000181",
    }
    out = ccs.extract_company_fields(payload)
    assert out["name"] == "ACME"
    assert out["id"] == "uuid-1"
    assert out["document"] == "11222333000181"


def test_extract_company_fields_nao_dict():
    assert ccs.extract_company_fields(None)["name"] is None


def test_metadata_matches_normalizada():
    assert ccs.metadata_matches_live(
        saved_name=" Acme ",
        saved_id="1",
        saved_document="11",
        live_name="acme",
        live_id="1",
        live_document="11",
    )


def test_fetch_live_sem_snapshot_import_na_fonte():
    src = Path(ccs.__file__).read_text(encoding="utf-8")
    assert "api_snapshot" not in src


def test_refresh_metadata_chama_update(monkeypatch, tmp_path):
    db = tmp_path / "db.sqlite"
    calls: dict = {}

    def fake_fetch(**kwargs):
        calls["kwargs"] = kwargs
        return {
            "success": True,
            "name": "Nova",
            "id": "99",
            "document": "123",
            "checked_at": "t",
            "path": "/v1/pessoas/conta-conectada",
            "data": {},
            "error": None,
            "status_code": None,
        }

    def fake_update(**kwargs):
        calls["update"] = kwargs

    monkeypatch.setattr(ccs, "fetch_conta_conectada_live", fake_fetch)
    monkeypatch.setattr("token_store.update_connected_account_metadata", fake_update)

    out = ccs.refresh_connected_company_metadata(db_path=str(db))
    assert out["success"] is True
    assert calls["update"]["connected_account_name"] == "Nova"
    assert calls["update"]["connected_account_id"] == "99"


def test_refresh_falha_nao_chama_update(monkeypatch, tmp_path):
    called = {"n": 0}

    def fake_fetch(**kwargs):
        return {"success": False, "error": "x"}

    def fake_update(**kwargs):
        called["n"] += 1

    monkeypatch.setattr(ccs, "fetch_conta_conectada_live", fake_fetch)
    monkeypatch.setattr("token_store.update_connected_account_metadata", fake_update)

    ccs.refresh_connected_company_metadata(db_path=str(tmp_path / "z.db"))
    assert called["n"] == 0
