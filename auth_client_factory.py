"""Factory central de cliente autenticado com refresh automático de access token."""

from __future__ import annotations

from typing import Any

from app_paths import get_token_db_path
from conta_azul_client import ContaAzulClient
from config import get_settings
from oauth_service import refresh_access_token
from services.oauth_identity_service import fingerprint_client_id
from token_store import is_token_expired, load_tokens, save_tokens

LEGACY_TOKEN_MSG = (
    "Conexão OAuth antiga sem identificação do aplicativo. Reconecte a Conta Azul."
)
CLIENT_ID_MISMATCH_MSG = (
    "A conexão OAuth salva pertence a outro Client ID. Limpe a conexão local e conecte novamente."
)


class AuthClientError(Exception):
    """Erros amigáveis da criação de cliente autenticado (sem segredos)."""


def _validate_token_client_binding(token_data: dict[str, Any], client_id: str) -> None:
    fp_saved = token_data.get("client_id_fingerprint")
    fp_now = fingerprint_client_id(client_id.strip())
    if fp_now is None:
        return
    if not fp_saved:
        raise AuthClientError(LEGACY_TOKEN_MSG)
    if fp_saved != fp_now:
        raise AuthClientError(CLIENT_ID_MISMATCH_MSG)


def get_authenticated_client(db_path: str | None = None) -> ContaAzulClient:
    path = db_path if db_path is not None else str(get_token_db_path())
    settings = get_settings()
    client_id = settings.CONTA_AZUL_CLIENT_ID.strip()
    client_secret = settings.CONTA_AZUL_CLIENT_SECRET.strip()
    token_url = settings.CONTA_AZUL_TOKEN_URL.strip()
    api_base_url = settings.CONTA_AZUL_API_BASE_URL.strip()

    if not client_id or not client_secret or not token_url or not api_base_url:
        raise AuthClientError(
            "Configuração OAuth incompleta. Verifique CLIENT_ID, CLIENT_SECRET, TOKEN_URL e API_BASE_URL."
        )

    token_data = load_tokens(path)
    if not token_data or not token_data.get("access_token"):
        raise AuthClientError("Nenhuma conexão OAuth encontrada. Conecte a Conta Azul primeiro.")

    _validate_token_client_binding(token_data, client_id)

    if not is_token_expired(token_data):
        return ContaAzulClient(base_url=api_base_url, access_token=token_data["access_token"])

    refresh_token_value = token_data.get("refresh_token")
    if not refresh_token_value:
        raise AuthClientError("Token expirado e sem refresh token. Reconecte a Conta Azul.")

    try:
        refreshed = refresh_access_token(
            refresh_token=refresh_token_value,
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url,
        )
    except Exception as exc:
        raise AuthClientError(
            "Falha ao renovar a sessão OAuth. Reconecte a Conta Azul e tente novamente."
        ) from exc

    new_access = refreshed.get("access_token")
    if not new_access:
        raise AuthClientError("Resposta de renovação inválida. Reconecte a Conta Azul.")

    new_refresh = refreshed.get("refresh_token") or refresh_token_value
    save_tokens(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type=refreshed.get("token_type") or token_data.get("token_type") or "Bearer",
        expires_in=refreshed.get("expires_in"),
        scope=refreshed.get("scope") or token_data.get("scope"),
        client_id_fingerprint=token_data.get("client_id_fingerprint"),
        client_id_masked=token_data.get("client_id_masked"),
        connected_account_name=token_data.get("connected_account_name"),
        connected_account_id=token_data.get("connected_account_id"),
        db_path=path,
    )
    return ContaAzulClient(base_url=api_base_url, access_token=new_access)
