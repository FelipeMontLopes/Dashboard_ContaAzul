"""OAuth2 Authorization Code — troca de código por tokens (sem UI)."""

from __future__ import annotations

import base64
import logging
import secrets
from typing import Any
from urllib.parse import urlencode, urlparse

import requests

logger = logging.getLogger(__name__)


class OAuthError(Exception):
    """Erro no fluxo OAuth; mensagens seguras (sem tokens no texto)."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_text: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_text = response_text


def mask_secret(value: str | None) -> str:
    if value is None or not str(value).strip():
        return "***"
    s = str(value).strip()
    if len(s) < 8:
        return "***"
    return f"{s[:3]}...{s[-2:]}"


def generate_state() -> str:
    return secrets.token_urlsafe(32)


def build_authorization_url(
    client_id: str,
    redirect_uri: str,
    auth_url: str,
    scope: str,
    state: str,
) -> str:
    for name, val in (
        ("client_id", client_id),
        ("redirect_uri", redirect_uri),
        ("auth_url", auth_url),
        ("state", state),
    ):
        if not val or not str(val).strip():
            raise ValueError(f"{name} é obrigatório.")

    base = str(auth_url).strip().rstrip("?")
    parsed = urlparse(base)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("auth_url inválida.")

    params = {
        "response_type": "code",
        "client_id": str(client_id).strip(),
        "redirect_uri": str(redirect_uri).strip(),
        "state": str(state).strip(),
        "scope": str(scope).strip(),
    }
    return f"{base}?{urlencode(params)}"


def build_basic_auth_header(client_id: str, client_secret: str) -> str:
    if not client_id or not str(client_id).strip():
        raise ValueError("client_id é obrigatório.")
    if client_secret is None or not str(client_secret).strip():
        raise ValueError("client_secret é obrigatório.")
    raw = f"{str(client_id).strip()}:{str(client_secret).strip()}".encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    return f"Basic {b64}"


def _post_token_request(
    token_url: str,
    client_id: str,
    client_secret: str,
    data: dict[str, str],
    timeout: int,
    operation_name: str,
) -> dict[str, Any]:
    auth_header = build_basic_auth_header(client_id, client_secret)
    headers = {
        "Authorization": auth_header,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    try:
        resp = requests.post(
            str(token_url).strip(),
            headers=headers,
            data=data,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.error("Falha de rede em %s: %s", operation_name, type(exc).__name__)
        raise OAuthError(
            "Não foi possível contatar o servidor de token.",
            status_code=None,
            response_text=str(exc),
        ) from exc

    if not (200 <= resp.status_code < 300):
        logger.warning(
            "Token endpoint retornou status=%s em %s (sem corpo sensível nos logs)",
            resp.status_code,
            operation_name,
        )
        raise OAuthError(
            f"Falha em {operation_name}.",
            status_code=resp.status_code,
            response_text=(resp.text[:2000] if resp.text else None),
        )

    try:
        payload = resp.json()
    except ValueError as exc:
        raise OAuthError(
            "Resposta do servidor de token não é JSON válido.",
            status_code=resp.status_code,
            response_text=(resp.text[:500] if resp.text else None),
        ) from exc

    if not isinstance(payload, dict):
        raise OAuthError(
            "Resposta do servidor de token em formato inesperado.",
            status_code=resp.status_code,
        )
    if not payload.get("access_token"):
        raise OAuthError(
            "Resposta sem access_token.",
            status_code=resp.status_code,
        )
    return payload


def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    token_url: str,
    timeout: int = 30,
) -> dict[str, Any]:
    if not code or not str(code).strip():
        raise ValueError("code é obrigatório.")
    if not client_id or not str(client_id).strip():
        raise ValueError("client_id é obrigatório.")
    if client_secret is None or not str(client_secret).strip():
        raise ValueError("client_secret é obrigatório.")
    if not redirect_uri or not str(redirect_uri).strip():
        raise ValueError("redirect_uri é obrigatório.")
    if not token_url or not str(token_url).strip():
        raise ValueError("token_url é obrigatório.")

    data = {
        "code": str(code).strip(),
        "grant_type": "authorization_code",
        "redirect_uri": str(redirect_uri).strip(),
    }
    return _post_token_request(
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        data=data,
        timeout=timeout,
        operation_name="troca de código OAuth",
    )


def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    token_url: str,
    timeout: int = 30,
) -> dict[str, Any]:
    if not refresh_token or not str(refresh_token).strip():
        raise ValueError("refresh_token é obrigatório.")
    if not client_id or not str(client_id).strip():
        raise ValueError("client_id é obrigatório.")
    if client_secret is None or not str(client_secret).strip():
        raise ValueError("client_secret é obrigatório.")
    if not token_url or not str(token_url).strip():
        raise ValueError("token_url é obrigatório.")

    data = {
        "grant_type": "refresh_token",
        "refresh_token": str(refresh_token).strip(),
    }
    return _post_token_request(
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        data=data,
        timeout=timeout,
        operation_name="refresh de token OAuth",
    )
