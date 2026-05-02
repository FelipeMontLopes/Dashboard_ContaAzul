"""Sugestões exploratórias de mapeamento financeiro a partir de um contrato inferido."""

from __future__ import annotations

from typing import Any


def _norm(s: Any) -> str:
    return str(s).strip().lower()


def _add(
    bucket: dict[str, list[dict[str, Any]]],
    role: str,
    field: str,
    confidence: str,
    reason: str,
) -> None:
    if not field:
        return
    for ex in bucket.setdefault(role, []):
        if ex.get("field") == field:
            return
    bucket[role].append(
        {"field": field, "confidence": confidence, "reason": reason}
    )


def suggest_financial_fields(contract: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """
    Retorna candidatos por papel semântico (não aplica regra de negócio no dashboard).
    confidence: alta | media | baixa
    """
    out: dict[str, list[dict[str, Any]]] = {
        "id": [],
        "data": [],
        "valor": [],
        "status": [],
        "descricao": [],
        "pessoa_cliente_fornecedor": [],
        "tipo_movimento": [],
        "categoria": [],
    }

    if not contract or not isinstance(contract, dict):
        return out

    keys = list(
        dict.fromkeys(
            (contract.get("top_level_keys") or [])
            + (contract.get("aggregated_item_keys") or [])
        )
    )

    for field in contract.get("candidate_id_fields") or []:
        _add(out, "id", str(field), "alta", "nome/chave sugere identificador")

    for field in contract.get("candidate_date_fields") or []:
        _add(out, "data", str(field), "alta", "nome ou valor sugere data")

    for field in contract.get("candidate_money_fields") or []:
        _add(out, "valor", str(field), "alta", "nome ou tipo numérico sugere valor monetário")

    for field in contract.get("candidate_status_fields") or []:
        _add(out, "status", str(field), "alta", "nome sugere status")

    for field in contract.get("candidate_name_description_fields") or []:
        _add(out, "descricao", str(field), "media", "nome sugere texto descritivo")

    for k in keys:
        nk = _norm(k)
        if any(x in nk for x in ("cliente", "fornecedor", "pessoa", "customer", "supplier")):
            _add(
                out,
                "pessoa_cliente_fornecedor",
                str(k),
                "media" if "id" not in nk else "alta",
                "palavra-chave de relacionamento",
            )
        if any(x in nk for x in ("tipo", "type", "natureza", "direction")):
            _add(out, "tipo_movimento", str(k), "media", "palavra-chave de tipo/natureza")
        if any(
            x in nk
            for x in (
                "categoria",
                "category",
                "classificacao",
                "classificação",
                "plano",
                "centro_custo",
                "centrocusto",
            )
        ):
            _add(out, "categoria", str(k), "media", "palavra-chave de categoria / centro de custo")

    # Baixa confiança: chaves remanescentes que parecem id numérico
    for k in keys:
        nk = _norm(k)
        if nk.endswith("_id") or nk == "id":
            if not any(x["field"] == k for x in out["id"]):
                _add(out, "id", str(k), "baixa", "sufixo _id ou chave id")

    return out
