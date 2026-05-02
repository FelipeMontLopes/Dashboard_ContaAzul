"""Exploração controlada de endpoints GET da API Conta Azul com snapshots sanitizados."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from auth_client_factory import AuthClientError, get_authenticated_client
from conta_azul_client import ContaAzulAPIError
from services.api_snapshot_store import save_api_snapshot
from services.diagnostico_api_service import sanitize_api_response


def get_default_financial_period_params(
    days_back: int = 90,
    days_forward: int = 30,
    *,
    pagina: int = 1,
    tamanho_pagina: int = 100,
) -> dict[str, Any]:
    """
    Parâmetros de período para endpoints financeiros (eventos-financeiros).

    data_inicio / data_fim em formato ISO local sem timezone, como esperado pela API.
    """
    today = date.today()
    start_d = today - timedelta(days=int(days_back))
    end_d = today + timedelta(days=int(days_forward))
    data_inicio = f"{start_d.isoformat()}T00:00:00"
    data_fim = f"{end_d.isoformat()}T23:59:59"
    return {
        "pagina": int(pagina),
        "tamanho_pagina": int(tamanho_pagina),
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }


def get_default_endpoints(
    days_back: int = 90,
    days_forward: int = 30,
    tamanho_pagina: int = 100,
) -> list[dict[str, Any]]:
    """Lista de endpoints padrão com parâmetros calculados no momento da chamada."""
    fin = get_default_financial_period_params(
        days_back=days_back,
        days_forward=days_forward,
        pagina=1,
        tamanho_pagina=tamanho_pagina,
    )
    return [
        {
            "resource_name": "conta_conectada",
            "method": "GET",
            "path": "/v1/pessoas/conta-conectada",
            "params": {},
        },
        {
            "resource_name": "pessoas",
            "method": "GET",
            "path": "/v1/pessoas",
            "params": {"pagina": 1, "tamanho_pagina": int(tamanho_pagina)},
        },
        {
            "resource_name": "financeiro_saldo_inicial",
            "method": "GET",
            "path": "/v1/financeiro/eventos-financeiros/saldo-inicial",
            "params": dict(fin),
        },
        {
            "resource_name": "financeiro_alteracoes",
            "method": "GET",
            "path": "/v1/financeiro/eventos-financeiros/alteracoes",
            "params": dict(fin),
        },
    ]


def summarize_response_shape(data: Any) -> dict[str, Any]:
    """Resumo não sensível da forma dos dados (para diagnóstico)."""
    if data is None:
        return {"type": "null"}
    if isinstance(data, str):
        return {"type": "string", "length": len(data)}
    if isinstance(data, (int, float, bool)):
        return {"type": type(data).__name__}
    if isinstance(data, list):
        n = len(data)
        if n == 0:
            return {"type": "list", "length": 0}
        first = data[0]
        if isinstance(first, dict):
            return {
                "type": "list",
                "length": n,
                "first_item_keys": list(first.keys())[:50],
            }
        return {"type": "list", "length": n, "first_item_type": type(first).__name__}
    if isinstance(data, dict):
        keys_summary: dict[str, Any] = {}
        for key, val in list(data.items())[:80]:
            if isinstance(val, list):
                keys_summary[str(key)] = {"type": "list", "length": len(val)}
            elif isinstance(val, dict):
                keys_summary[str(key)] = {
                    "type": "dict",
                    "keys": list(val.keys())[:30],
                }
            else:
                keys_summary[str(key)] = {"type": type(val).__name__}
        return {"type": "dict", "keys": keys_summary}
    return {"type": type(data).__name__}


def call_api_endpoint(
    resource_name: str,
    method: str,
    path: str,
    params: dict[str, Any] | None = None,
    save_snapshot: bool = True,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Executa GET autenticado, sanitiza resposta, opcionalmente persiste snapshot."""
    params = params if params is not None else {}
    method_u = (method or "GET").strip().upper()

    base: dict[str, Any] = {
        "success": False,
        "resource_name": resource_name,
        "method": method_u,
        "path": path,
        "params": params,
        "status_code": None,
        "data": None,
        "error_message": None,
        "response_shape": {},
    }

    if method_u != "GET":
        msg = "Apenas GET é suportado neste explorador."
        base["error_message"] = msg
        base["response_shape"] = summarize_response_shape(None)
        if save_snapshot:
            save_api_snapshot(
                resource_name,
                method_u,
                path,
                params,
                False,
                data=None,
                error_message=msg,
                status_code=None,
                db_path=db_path,
            )
        return base

    if not path or not str(path).startswith("/"):
        msg = "Path inválido: deve começar com /"
        base["error_message"] = msg
        base["response_shape"] = summarize_response_shape(None)
        if save_snapshot:
            save_api_snapshot(
                resource_name,
                method_u,
                path or "",
                params,
                False,
                data=None,
                error_message=msg,
                status_code=None,
                db_path=db_path,
            )
        return base

    try:
        client = get_authenticated_client()
        raw = client.get(path, params=params or {})
        safe = sanitize_api_response(raw)
        shape = summarize_response_shape(safe)
        base.update(
            {
                "success": True,
                "status_code": 200,
                "data": safe,
                "response_shape": shape,
                "error_message": None,
            }
        )
        if save_snapshot:
            save_api_snapshot(
                resource_name,
                method_u,
                path,
                params,
                True,
                data=raw,
                error_message=None,
                status_code=200,
                db_path=db_path,
            )
        return base
    except AuthClientError as exc:
        msg = str(exc)
        base["error_message"] = msg
        base["response_shape"] = summarize_response_shape(None)
        if save_snapshot:
            save_api_snapshot(
                resource_name,
                method_u,
                path,
                params,
                False,
                data=None,
                error_message=msg,
                status_code=None,
                db_path=db_path,
            )
        return base
    except ContaAzulAPIError as exc:
        msg = exc.message
        base["error_message"] = msg
        base["status_code"] = exc.status_code
        base["response_shape"] = summarize_response_shape(None)
        if save_snapshot:
            save_api_snapshot(
                resource_name,
                method_u,
                path,
                params,
                False,
                data=None,
                error_message=msg,
                status_code=exc.status_code,
                db_path=db_path,
            )
        return base
    except Exception as exc:
        msg = f"Erro inesperado: {type(exc).__name__}"
        base["error_message"] = msg
        base["response_shape"] = summarize_response_shape(None)
        if save_snapshot:
            save_api_snapshot(
                resource_name,
                method_u,
                path,
                params,
                False,
                data=None,
                error_message=msg,
                status_code=None,
                db_path=db_path,
            )
        return base


def test_default_endpoints(
    db_path: str | None = None,
    days_back: int = 90,
    days_forward: int = 30,
    tamanho_pagina: int = 100,
) -> list[dict[str, Any]]:
    """Chama todos os endpoints padrão e retorna lista de resultados."""
    out: list[dict[str, Any]] = []
    for ep in get_default_endpoints(
        days_back=days_back,
        days_forward=days_forward,
        tamanho_pagina=tamanho_pagina,
    ):
        r = call_api_endpoint(
            ep["resource_name"],
            ep["method"],
            ep["path"],
            ep.get("params") or {},
            save_snapshot=True,
            db_path=db_path,
        )
        out.append(r)
    return out


def needs_financial_period_params(path: str) -> bool:
    """True se o path for dos endpoints financeiros que exigem data_inicio/data_fim."""
    p = (path or "").strip()
    return (
        "/financeiro/eventos-financeiros/saldo-inicial" in p
        or "/financeiro/eventos-financeiros/alteracoes" in p
    )
