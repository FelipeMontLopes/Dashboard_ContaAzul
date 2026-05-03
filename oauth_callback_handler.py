"""Processamento centralizado do callback OAuth (?code= / ?error=) para Streamlit."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

import streamlit as st

from app_paths import get_oauth_state_db_path, get_token_db_path
from config import get_settings
from conta_azul_client import ContaAzulClient
from oauth_readiness import get_oauth_readiness
from oauth_service import OAuthError, exchange_code_for_tokens
from oauth_state_store import clear_state, init_oauth_state_db, load_state_context, validate_state
from redirect_uri_service import (
    get_effective_redirect_uri,
    sanitize_redirect_uri,
    validate_redirect_uri_format,
)
from services.connected_company_service import extract_company_fields
from services.oauth_identity_service import fingerprint_client_id, mask_client_id
from token_store import init_token_db, load_tokens, save_tokens, update_connected_account_metadata


def _sanitize_error_description(raw: str | None, max_len: int = 400) -> str:
    if raw is None or not str(raw).strip():
        return ""
    s = " ".join(str(raw).split())
    if len(s) > max_len:
        s = s[:max_len] + "…"
    if len(s) > 80 and re.search(r"[A-Za-z0-9+/=_-]{40,}", s):
        return ""
    return s


def _try_clear_oauth_query_params() -> None:
    for key in ("code", "state", "error", "error_description"):
        try:
            if key in st.query_params:
                del st.query_params[key]
        except Exception:
            pass


def _single_param(qp: Any, key: str) -> str | None:
    if qp is None:
        return None
    try:
        if key not in qp:
            return None
        val = qp[key]
        if isinstance(val, list):
            return val[0] if val else None
        return str(val) if val is not None else None
    except Exception:
        return None


def _token_paths() -> tuple[str, str]:
    token_db = str(Path(get_token_db_path()).resolve())
    state_db = str(Path(get_oauth_state_db_path()).resolve())
    return token_db, state_db


def _try_fetch_connected_account_metadata(
    *,
    access_token: str,
    api_base_url: str,
    diagnostic_path: str,
    db_path: str,
) -> None:
    """Preenche metadata após OAuth. Falhas são ignoradas (metadata permanece vazia)."""
    try:
        clean_base = (api_base_url or "").strip()
        clean_path = (diagnostic_path or "").strip() or "/v1/pessoas/conta-conectada"
        if not clean_base or not access_token.strip():
            return
        client = ContaAzulClient(base_url=clean_base, access_token=access_token)
        raw = client.get(clean_path)
        fields = extract_company_fields(raw if isinstance(raw, dict) else {})
        update_connected_account_metadata(
            connected_account_name=fields["name"],
            connected_account_id=fields["id"],
            connected_account_document=fields["document"],
            db_path=db_path,
        )
    except Exception:
        return


def _meta(
    *,
    token_saved: bool | None,
    has_access_token_response: bool | None,
    has_refresh_token_response: bool | None,
    token_db_path: str | None,
) -> dict[str, Any]:
    return {
        "token_saved": token_saved,
        "has_access_token_response": has_access_token_response,
        "has_refresh_token_response": has_refresh_token_response,
        "token_db_path": token_db_path,
    }


def handle_oauth_callback(query_params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """
    Processa callback OAuth a partir de ``query_params`` ou ``st.query_params``.

    Não registra tokens nem código completo. Evita processar o mesmo ``code`` duas vezes
    na mesma sessão Streamlit.
    """
    token_db_path_abs, oauth_state_db_path_abs = _token_paths()

    qp = st.query_params if query_params is None else query_params

    err_oauth = _single_param(qp, "error")
    err_desc_raw = _single_param(qp, "error_description")
    code = _single_param(qp, "code")
    state_cb = _single_param(qp, "state")

    if err_oauth:
        extra = _sanitize_error_description(err_desc_raw)
        msg = "Autorização cancelada ou recusada pela Conta Azul."
        if extra:
            msg = f"{msg} {extra}"
        return {
            "handled": True,
            "success": False,
            "status": "oauth_error",
            "message": msg,
            **_meta(
                token_saved=False,
                has_access_token_response=False,
                has_refresh_token_response=False,
                token_db_path=token_db_path_abs,
            ),
        }

    if not code or not state_cb:
        return {
            "handled": False,
            "success": None,
            "status": "no_callback",
            "message": None,
            **_meta(
                token_saved=None,
                has_access_token_response=None,
                has_refresh_token_response=None,
                token_db_path=token_db_path_abs,
            ),
        }

    init_token_db(token_db_path_abs)
    init_oauth_state_db(oauth_state_db_path_abs)

    settings = get_settings()
    effective_redirect = get_effective_redirect_uri()
    vr = validate_redirect_uri_format(effective_redirect)
    oauth_ready = get_oauth_readiness(
        settings, effective_redirect, vr, db_path=token_db_path_abs
    )["ready"]

    if not oauth_ready:
        return {
            "handled": True,
            "success": False,
            "status": "oauth_not_ready",
            "message": (
                "Configure Client ID, Client Secret, Auth URL, Token URL e URL de "
                "redirecionamento efetiva antes de conectar."
            ),
            **_meta(
                token_saved=False,
                has_access_token_response=False,
                has_refresh_token_response=False,
                token_db_path=token_db_path_abs,
            ),
        }

    fp = hashlib.sha256(str(code).strip().encode("utf-8")).hexdigest()
    if st.session_state.get("oauth_last_processed_code_fp") == fp:
        _try_clear_oauth_query_params()
        return {
            "handled": False,
            "success": None,
            "status": "duplicate_callback",
            "message": None,
            **_meta(
                token_saved=None,
                has_access_token_response=None,
                has_refresh_token_response=None,
                token_db_path=token_db_path_abs,
            ),
        }

    try:
        if not validate_state(state_cb, db_path=oauth_state_db_path_abs):
            clear_state(oauth_state_db_path_abs)
            return {
                "handled": True,
                "success": False,
                "status": "invalid_state",
                "message": "Falha de segurança: state OAuth inválido.",
                **_meta(
                    token_saved=False,
                    has_access_token_response=False,
                    has_refresh_token_response=False,
                    token_db_path=token_db_path_abs,
                ),
            }

        ctx_oauth = load_state_context(oauth_state_db_path_abs)
        redirect_exchange = ""
        if ctx_oauth and ctx_oauth.get("redirect_uri"):
            redirect_exchange = sanitize_redirect_uri(ctx_oauth["redirect_uri"])
        if not redirect_exchange:
            redirect_exchange = get_effective_redirect_uri()
        if not sanitize_redirect_uri(redirect_exchange):
            clear_state(oauth_state_db_path_abs)
            return {
                "handled": True,
                "success": False,
                "status": "missing_redirect",
                "message": (
                    "URL de redirecionamento não encontrada para esta sessão. "
                    "Configure a URL pública ou o `.env` e use \"Conectar Conta Azul\" novamente."
                ),
                **_meta(
                    token_saved=False,
                    has_access_token_response=False,
                    has_refresh_token_response=False,
                    token_db_path=token_db_path_abs,
                ),
            }

        resp = exchange_code_for_tokens(
            code=str(code).strip(),
            client_id=settings.CONTA_AZUL_CLIENT_ID.strip(),
            client_secret=settings.CONTA_AZUL_CLIENT_SECRET.strip(),
            redirect_uri=redirect_exchange,
            token_url=settings.CONTA_AZUL_TOKEN_URL.strip(),
        )
        has_at = bool(resp.get("access_token"))
        has_rt = bool(resp.get("refresh_token"))

        cid_strip = settings.CONTA_AZUL_CLIENT_ID.strip()
        save_tokens(
            access_token=resp["access_token"],
            refresh_token=resp.get("refresh_token"),
            token_type=resp.get("token_type", "Bearer"),
            expires_in=resp.get("expires_in"),
            scope=resp.get("scope"),
            client_id_fingerprint=fingerprint_client_id(cid_strip),
            client_id_masked=mask_client_id(cid_strip),
            connected_account_name=None,
            connected_account_id=None,
            connected_account_document=None,
            db_path=token_db_path_abs,
        )
        verified = load_tokens(token_db_path_abs)
        if not verified or not verified.get("access_token"):
            clear_state(oauth_state_db_path_abs)
            return {
                "handled": True,
                "success": False,
                "status": "persist_failed",
                "message": "Tokens recebidos, mas não foi possível confirmar persistência local.",
                **_meta(
                    token_saved=False,
                    has_access_token_response=has_at,
                    has_refresh_token_response=has_rt,
                    token_db_path=token_db_path_abs,
                ),
            }

        clear_state(oauth_state_db_path_abs)
        st.session_state["oauth_last_processed_code_fp"] = fp
        try:
            st.session_state.pop("oauth_auth_url", None)
        except Exception:
            pass

        _try_fetch_connected_account_metadata(
            access_token=resp["access_token"],
            api_base_url=settings.CONTA_AZUL_API_BASE_URL.strip(),
            diagnostic_path=settings.CONTA_AZUL_DIAGNOSTIC_PATH.strip(),
            db_path=token_db_path_abs,
        )

        return {
            "handled": True,
            "success": True,
            "status": "connected",
            "message": "Conta Azul conectada com sucesso.",
            **_meta(
                token_saved=True,
                has_access_token_response=has_at,
                has_refresh_token_response=has_rt,
                token_db_path=token_db_path_abs,
            ),
        }
    except OAuthError as exc:
        clear_state(oauth_state_db_path_abs)
        return {
            "handled": True,
            "success": False,
            "status": "oauth_exchange_failed",
            "message": exc.message,
            **_meta(
                token_saved=False,
                has_access_token_response=False,
                has_refresh_token_response=False,
                token_db_path=token_db_path_abs,
            ),
        }
    except Exception:
        clear_state(oauth_state_db_path_abs)
        return {
            "handled": True,
            "success": False,
            "status": "unexpected_error",
            "message": "Erro inesperado ao concluir conexão OAuth.",
            **_meta(
                token_saved=False,
                has_access_token_response=False,
                has_refresh_token_response=False,
                token_db_path=token_db_path_abs,
            ),
        }
