from __future__ import annotations

from typing import Any

from auth_client_factory import AuthClientError, get_authenticated_client
from config import get_settings
from conta_azul_client import ContaAzulAPIError

_SENSITIVE_KEYS = {
    "access_token",
    "refresh_token",
    "token",
    "authorization",
    "client_secret",
    "secret",
    "password",
    "senha",
}


def mask_sensitive_data(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    v = value.strip()
    if len(v) < 8:
        return "***"
    return f"{v[:4]}...{v[-4:]}"


def _is_sensitive_key(key: Any) -> bool:
    if key is None:
        return False
    k = str(key).strip().lower()
    return any(s in k for s in _SENSITIVE_KEYS)


def sanitize_api_response(data: Any) -> Any:
    if isinstance(data, dict):
        out: dict[Any, Any] = {}
        for key, value in data.items():
            if _is_sensitive_key(key):
                out[key] = mask_sensitive_data(value)
            else:
                out[key] = sanitize_api_response(value)
        return out
    if isinstance(data, list):
        return [sanitize_api_response(item) for item in data]
    return data


def call_diagnostic_endpoint(path: str | None = None) -> dict[str, Any]:
    cfg = get_settings()
    diagnostic_path = (path if path is not None else cfg.CONTA_AZUL_DIAGNOSTIC_PATH).strip()

    if not diagnostic_path:
        return {
            "success": False,
            "path": diagnostic_path,
            "status": "unexpected_error",
            "data": None,
            "error": "Endpoint de diagnóstico não configurado.",
        }

    try:
        client = get_authenticated_client()
        raw = client.get(diagnostic_path)
        safe = sanitize_api_response(raw)
        return {
            "success": True,
            "path": diagnostic_path,
            "status": "ok",
            "data": safe,
            "error": None,
        }
    except AuthClientError as exc:
        return {
            "success": False,
            "path": diagnostic_path,
            "status": "auth_error",
            "data": None,
            "error": str(exc),
        }
    except ContaAzulAPIError as exc:
        return {
            "success": False,
            "path": diagnostic_path,
            "status": "api_error",
            "data": None,
            "error": str(exc.message),
            "status_code": exc.status_code,
        }
    except Exception:
        return {
            "success": False,
            "path": diagnostic_path,
            "status": "unexpected_error",
            "data": None,
            "error": "Falha inesperada no diagnóstico da API.",
        }
