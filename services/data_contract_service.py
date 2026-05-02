"""Inferência de contrato de dados a partir de JSON (snapshots sanitizados)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from services.api_snapshot_store import get_latest_snapshot, get_snapshot_by_id
from services.diagnostico_api_service import sanitize_api_response

_MAX_LIST_SAMPLE = 20
_MAX_SAFE_EXAMPLES = 3

_DATE_KEY_FRAGMENTS = (
    "data",
    "date",
    "vencimento",
    "competencia",
    "competência",
    "created_at",
    "updated_at",
    "emissao",
    "emissão",
    "pagamento",
    "registro",
    "periodo",
    "período",
)
_MONEY_KEY_FRAGMENTS = (
    "valor",
    "amount",
    "total",
    "saldo",
    "liquido",
    "líquido",
    "bruto",
    "preco",
    "preço",
    "juros",
    "multa",
    "desconto",
)
_STATUS_KEY_FRAGMENTS = ("status", "situacao", "situação", "state")
_ID_KEY_FRAGMENTS = ("id", "uuid", "codigo", "código", "identificador")
_PAGINATION_FRAGMENTS = (
    "pagina",
    "page",
    "tamanho",
    "size",
    "limit",
    "offset",
    "total",
    "quantidade",
    "elementos",
    "registros",
    "pages",
    "proximo",
    "próximo",
    "has_next",
    "paginacao",
    "paginação",
)

_NAME_KEY_FRAGMENTS = (
    "nome",
    "descricao",
    "descrição",
    "description",
    "observacao",
    "observação",
    "titulo",
    "título",
    "razao",
    "razão",
)


def _norm_key(key: Any) -> str:
    return str(key).strip().lower()


def _key_matches_fragments(key: Any, fragments: tuple[str, ...]) -> bool:
    nk = _norm_key(key)
    return any(f in nk for f in fragments)


def _looks_like_iso_date(val: Any) -> bool:
    if not isinstance(val, str) or len(val) < 8:
        return False
    s = val.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        try:
            datetime.fromisoformat(s.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False
    return False


def _looks_like_money_value(val: Any) -> bool:
    if isinstance(val, bool):
        return False
    if isinstance(val, (int, float)):
        return True
    return False


def _classify_field_key(key: Any) -> dict[str, bool]:
    return {
        "date": _key_matches_fragments(key, _DATE_KEY_FRAGMENTS),
        "money": _key_matches_fragments(key, _MONEY_KEY_FRAGMENTS),
        "status": _key_matches_fragments(key, _STATUS_KEY_FRAGMENTS),
        "id": _key_matches_fragments(key, _ID_KEY_FRAGMENTS) or _norm_key(key) == "id",
        "name": _key_matches_fragments(key, _NAME_KEY_FRAGMENTS),
    }


def _merge_unique(existing: list[str], new_items: list[str]) -> list[str]:
    seen = set(existing)
    out = list(existing)
    for x in new_items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _infer_keys_from_dict_sample(d: dict[str, Any]) -> tuple[dict[str, str], dict[str, list[str]]]:
    key_types: dict[str, str] = {}
    classifications: dict[str, list[str]] = {
        "date": [],
        "money": [],
        "status": [],
        "id": [],
        "name": [],
    }
    for k, v in d.items():
        ks = str(k)
        key_types[ks] = type(v).__name__
        cls = _classify_field_key(k)
        if cls["date"] or _looks_like_iso_date(v):
            classifications["date"].append(ks)
        if cls["money"] or _looks_like_money_value(v):
            classifications["money"].append(ks)
        if cls["status"]:
            classifications["status"].append(ks)
        if cls["id"]:
            classifications["id"].append(ks)
        if cls["name"]:
            classifications["name"].append(ks)
    return key_types, classifications


def _aggregate_list_of_dicts(items: list[dict[str, Any]]) -> tuple[list[str], dict[str, str], dict[str, list[str]]]:
    all_keys: list[str] = []
    merged_types: dict[str, str] = {}
    agg_cls: dict[str, list[str]] = {
        "date": [],
        "money": [],
        "status": [],
        "id": [],
        "name": [],
    }
    sample = items[:_MAX_LIST_SAMPLE]
    for row in sample:
        kt, cl = _infer_keys_from_dict_sample(row)
        all_keys = _merge_unique(all_keys, list(kt.keys()))
        for k, t in kt.items():
            merged_types.setdefault(k, t)
        for cat in agg_cls:
            agg_cls[cat] = _merge_unique(agg_cls[cat], cl[cat])
    return all_keys, merged_types, agg_cls


def _pagination_candidate_keys(key_list: list[str]) -> list[str]:
    """Heurística para chaves que podem indicar paginação ou totais."""
    out: list[str] = []
    for k in key_list:
        nk = _norm_key(k)
        if any(f in nk for f in _PAGINATION_FRAGMENTS):
            out.append(str(k))
    return list(dict.fromkeys(out))


def _with_pagination(contract: dict[str, Any]) -> dict[str, Any]:
    keys = (contract.get("top_level_keys") or []) + (contract.get("aggregated_item_keys") or [])
    contract["pagination_candidates"] = _pagination_candidate_keys(keys)
    return contract


def _nested_simple_summary(obj: dict[str, Any], max_keys: int = 40) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, (k, v) in enumerate(obj.items()):
        if i >= max_keys:
            out["_truncated"] = True
            break
        if isinstance(v, dict):
            out[str(k)] = {"type": "dict", "keys": list(v.keys())[:30]}
        elif isinstance(v, list):
            out[str(k)] = {"type": "list", "length": len(v)}
        else:
            out[str(k)] = {"type": type(v).__name__}
    return out


def infer_json_contract(data: Any) -> dict[str, Any]:
    """
    Analisa estrutura JSON e devolve metadados exploratórios (sem regra de negócio final).
    """
    if data is None:
        return _with_pagination({
            "root_type": "null",
            "total_items": None,
            "top_level_keys": [],
            "key_types": {},
            "candidate_date_fields": [],
            "candidate_money_fields": [],
            "candidate_status_fields": [],
            "candidate_id_fields": [],
            "candidate_name_description_fields": [],
            "aggregated_item_keys": [],
            "nested_hints": {},
            "safe_examples": [],
        })

    if isinstance(data, str):
        return _with_pagination({
            "root_type": "string",
            "total_items": None,
            "top_level_keys": [],
            "key_types": {},
            "candidate_date_fields": [],
            "candidate_money_fields": [],
            "candidate_status_fields": [],
            "candidate_id_fields": [],
            "candidate_name_description_fields": [],
            "aggregated_item_keys": [],
            "nested_hints": {},
            "safe_examples": [sanitize_api_response(data)],
        })

    if isinstance(data, list):
        total = len(data)
        if total == 0:
            return _with_pagination({
                "root_type": "list",
                "total_items": 0,
                "top_level_keys": [],
                "key_types": {},
                "candidate_date_fields": [],
                "candidate_money_fields": [],
                "candidate_status_fields": [],
                "candidate_id_fields": [],
                "candidate_name_description_fields": [],
                "aggregated_item_keys": [],
                "nested_hints": {},
                "safe_examples": [],
            })
        first = data[0]
        if isinstance(first, dict):
            agg_keys, merged_types, agg_cls = _aggregate_list_of_dicts(
                [x for x in data if isinstance(x, dict)]
            )
            examples_raw = data[:_MAX_SAFE_EXAMPLES]
            safe = [sanitize_api_response(x) for x in examples_raw]
            return _with_pagination({
                "root_type": "list",
                "total_items": total,
                "top_level_keys": agg_keys,
                "key_types": merged_types,
                "candidate_date_fields": agg_cls["date"],
                "candidate_money_fields": agg_cls["money"],
                "candidate_status_fields": agg_cls["status"],
                "candidate_id_fields": agg_cls["id"],
                "candidate_name_description_fields": agg_cls["name"],
                "aggregated_item_keys": agg_keys,
                "nested_hints": {},
                "safe_examples": safe,
            })
        return _with_pagination({
            "root_type": "list",
            "total_items": total,
            "top_level_keys": [],
            "key_types": {"_item": type(first).__name__},
            "candidate_date_fields": [],
            "candidate_money_fields": [],
            "candidate_status_fields": [],
            "candidate_id_fields": [],
            "candidate_name_description_fields": [],
            "aggregated_item_keys": [],
            "nested_hints": {},
            "safe_examples": [sanitize_api_response(first)],
        })

    if isinstance(data, dict):
        key_types, cls_map = _infer_keys_from_dict_sample(data)
        top_keys = list(key_types.keys())
        nested = _nested_simple_summary(data)
        examples_raw = [data] if data else []
        safe = [sanitize_api_response(x) for x in examples_raw[:_MAX_SAFE_EXAMPLES]]
        return _with_pagination({
            "root_type": "dict",
            "total_items": None,
            "top_level_keys": top_keys,
            "key_types": key_types,
            "candidate_date_fields": cls_map["date"],
            "candidate_money_fields": cls_map["money"],
            "candidate_status_fields": cls_map["status"],
            "candidate_id_fields": cls_map["id"],
            "candidate_name_description_fields": cls_map["name"],
            "aggregated_item_keys": [],
            "nested_hints": nested,
            "safe_examples": safe,
        })

    return _with_pagination({
        "root_type": type(data).__name__,
        "total_items": None,
        "top_level_keys": [],
        "key_types": {},
        "candidate_date_fields": [],
        "candidate_money_fields": [],
        "candidate_status_fields": [],
        "candidate_id_fields": [],
        "candidate_name_description_fields": [],
        "aggregated_item_keys": [],
        "nested_hints": {},
        "safe_examples": [sanitize_api_response(data)],
    })


def infer_contract_from_snapshot(snapshot_id: int, db_path: str | None = None) -> dict[str, Any]:
    row = get_snapshot_by_id(snapshot_id, db_path=db_path)
    if not row:
        return {
            "error": "snapshot não encontrado",
            "snapshot_id": None,
            "resource_name": None,
            "contract": None,
        }
    sid = int(row["id"])
    raw = row.get("response_json")
    if not raw:
        return {
            "error": "snapshot sem response_json",
            "snapshot_id": sid,
            "resource_name": row.get("resource_name"),
            "path": row.get("path"),
            "fetched_at": row.get("fetched_at"),
            "contract": None,
        }
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "error": "response_json inválido",
            "snapshot_id": sid,
            "resource_name": row.get("resource_name"),
            "path": row.get("path"),
            "fetched_at": row.get("fetched_at"),
            "contract": None,
        }
    contract = infer_json_contract(data)
    return {
        "snapshot_id": sid,
        "resource_name": row["resource_name"],
        "path": row["path"],
        "fetched_at": row["fetched_at"],
        "contract": contract,
    }


def infer_latest_contract(resource_name: str, db_path: str | None = None) -> dict[str, Any]:
    row = get_latest_snapshot(resource_name, db_path=db_path)
    if not row:
        return {"error": f"nenhum snapshot para '{resource_name}'", "contract": None}
    sid = int(row["id"])
    return infer_contract_from_snapshot(sid, db_path=db_path)
