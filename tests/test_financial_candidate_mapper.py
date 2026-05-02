"""Testes de financial_candidate_mapper."""

from services.financial_candidate_mapper import suggest_financial_fields


def test_suggests_id_for_id_field() -> None:
    c = {
        "candidate_id_fields": ["registro_id"],
        "candidate_date_fields": [],
        "candidate_money_fields": [],
        "candidate_status_fields": [],
        "candidate_name_description_fields": [],
        "top_level_keys": [],
        "aggregated_item_keys": [],
    }
    s = suggest_financial_fields(c)
    assert any(x["field"] == "registro_id" for x in s["id"])


def test_suggests_valor_for_amount() -> None:
    c = {
        "candidate_id_fields": [],
        "candidate_date_fields": [],
        "candidate_money_fields": ["valor_liquido"],
        "candidate_status_fields": [],
        "candidate_name_description_fields": [],
        "top_level_keys": [],
        "aggregated_item_keys": [],
    }
    s = suggest_financial_fields(c)
    assert any(x["field"] == "valor_liquido" for x in s["valor"])


def test_suggests_data_for_vencimento() -> None:
    c = {
        "candidate_id_fields": [],
        "candidate_date_fields": ["data_vencimento"],
        "candidate_money_fields": [],
        "candidate_status_fields": [],
        "candidate_name_description_fields": [],
        "top_level_keys": [],
        "aggregated_item_keys": [],
    }
    s = suggest_financial_fields(c)
    assert any(x["field"] == "data_vencimento" for x in s["data"])


def test_suggests_status() -> None:
    c = {
        "candidate_id_fields": [],
        "candidate_date_fields": [],
        "candidate_money_fields": [],
        "candidate_status_fields": ["status"],
        "candidate_name_description_fields": [],
        "top_level_keys": [],
        "aggregated_item_keys": [],
    }
    s = suggest_financial_fields(c)
    assert any(x["field"] == "status" for x in s["status"])


def test_empty_contract_returns_empty_buckets() -> None:
    s = suggest_financial_fields({})
    assert all(len(v) == 0 for v in s.values())


def test_suggests_centro_custo_as_categoria() -> None:
    c = {
        "candidate_id_fields": [],
        "candidate_date_fields": [],
        "candidate_money_fields": [],
        "candidate_status_fields": [],
        "candidate_name_description_fields": [],
        "top_level_keys": ["centro_custo_nome"],
        "aggregated_item_keys": [],
    }
    s = suggest_financial_fields(c)
    assert any(x["field"] == "centro_custo_nome" for x in s["categoria"])


def test_low_confidence_when_only_unknown_keys() -> None:
    c = {
        "candidate_id_fields": [],
        "candidate_date_fields": [],
        "candidate_money_fields": [],
        "candidate_status_fields": [],
        "candidate_name_description_fields": [],
        "top_level_keys": ["foo_bar_xyz"],
        "aggregated_item_keys": [],
    }
    s = suggest_financial_fields(c)
    assert len(s["id"]) == 0 or all(x["confidence"] == "baixa" for x in s["id"])
