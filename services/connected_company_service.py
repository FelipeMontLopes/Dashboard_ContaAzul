"""Verificação da empresa conectada via `/v1/pessoas/conta-conectada` (sem snapshots)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from auth_client_factory import AuthClientError, get_authenticated_client
from config import get_settings
from conta_azul_client import ContaAzulAPIError
from services.diagnostico_api_service import sanitize_api_response


def extract_company_fields(payload: Any) -> dict[str, Any]:
    """
    Extrai nome, identificador e documento comuns da resposta conta-conectada.
    Valores são para exibição operacional (não são tokens).
    """
    if not isinstance(payload, dict):
        return {"name": None, "id": None, "document": None}

    nome = (
        payload.get("nome")
        or payload.get("razaoSocial")
        or payload.get("razao_social")
        or payload.get("name")
        or payload.get("fantasia")
    )
    acc_id = payload.get("id") or payload.get("uuid")
    doc = (
        payload.get("cnpj")
        or payload.get("cpf")
        or payload.get("documento")
        or payload.get("numeroDocumento")
    )
    if nome is not None:
        nome = str(nome).strip() or None
    if acc_id is not None:
        acc_id = str(acc_id).strip() or None
    if doc is not None:
        doc = str(doc).strip() or None
    return {"name": nome, "id": acc_id, "document": doc}


def fetch_conta_conectada_live(db_path: str | None = None) -> dict[str, Any]:
    """
    Chama o endpoint configurado ao vivo com ``get_authenticated_client`` (sem snapshot).

    Não persiste nada. Retorna dados sanitizados para UI.
    """
    cfg = get_settings()
    path = (cfg.CONTA_AZUL_DIAGNOSTIC_PATH or "").strip() or "/v1/pessoas/conta-conectada"
    checked_at = datetime.now(timezone.utc).isoformat()

    try:
        client = get_authenticated_client(db_path=db_path)
        raw = client.get(path)
        safe = sanitize_api_response(raw)
        fields = extract_company_fields(safe if isinstance(safe, dict) else {})
        return {
            "success": True,
            "checked_at": checked_at,
            "path": path,
            "data": safe,
            "name": fields["name"],
            "id": fields["id"],
            "document": fields["document"],
            "error": None,
            "status_code": None,
        }
    except AuthClientError as exc:
        return {
            "success": False,
            "checked_at": checked_at,
            "path": path,
            "data": None,
            "name": None,
            "id": None,
            "document": None,
            "error": str(exc),
            "status_code": None,
        }
    except ContaAzulAPIError as exc:
        return {
            "success": False,
            "checked_at": checked_at,
            "path": path,
            "data": None,
            "name": None,
            "id": None,
            "document": None,
            "error": str(exc.message),
            "status_code": exc.status_code,
        }
    except Exception:
        return {
            "success": False,
            "checked_at": checked_at,
            "path": path,
            "data": None,
            "name": None,
            "id": None,
            "document": None,
            "error": "Falha inesperada ao consultar empresa conectada.",
            "status_code": None,
        }


def refresh_connected_company_metadata(db_path: str | None = None) -> dict[str, Any]:
    """
    Consulta conta-conectada ao vivo e persiste nome/id/documento em ``token_store``.
    Não altera access/refresh tokens.
    """
    result = fetch_conta_conectada_live(db_path=db_path)
    if result.get("success"):
        from token_store import update_connected_account_metadata

        update_connected_account_metadata(
            connected_account_name=result.get("name"),
            connected_account_id=result.get("id"),
            connected_account_document=result.get("document"),
            db_path=db_path,
        )
    return result


def metadata_matches_live(
    *,
    saved_name: str | None,
    saved_id: str | None,
    saved_document: str | None,
    live_name: str | None,
    live_id: str | None,
    live_document: str | None,
) -> bool:
    """Comparação simples para alerta operacional (não é validação OAuth)."""

    def norm(v: str | None) -> str:
        return (v or "").strip().lower()

    return (
        norm(saved_name) == norm(live_name)
        and norm(saved_id) == norm(live_id)
        and norm(saved_document) == norm(live_document)
    )
