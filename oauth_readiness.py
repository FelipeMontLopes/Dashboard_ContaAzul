"""Regras puras para saber se o fluxo OAuth pode ser iniciado (sem Streamlit)."""

from __future__ import annotations

from typing import Any

from app_paths import get_token_db_path
from redirect_uri_service import sanitize_redirect_uri
from services.oauth_identity_service import fingerprint_client_id, mask_client_id, short_fingerprint


def get_oauth_token_binding_status(settings: Any, db_path: str | None = None) -> dict[str, Any]:
    """
    Compara tokens persistidos com o Client ID atual (fingerprint SHA-256).
    Não expõe segredos; usa apenas metadados já salvos e o Client ID de configuração.
    """
    from token_store import load_tokens

    path = db_path if db_path is not None else str(get_token_db_path())
    cid = str(getattr(settings, "CONTA_AZUL_CLIENT_ID", "") or "").strip()
    current_fp = fingerprint_client_id(cid)
    current_masked = mask_client_id(cid)

    data = load_tokens(path)
    if not data or not data.get("access_token"):
        return {
            "has_stored_tokens": False,
            "legacy_no_fingerprint": False,
            "client_mismatch": False,
            "binding_ok": True,
            "current_client_id_masked": current_masked,
            "stored_client_id_masked": None,
            "stored_fingerprint_short": "não informado",
            "fingerprints_match": True,
            "message": None,
        }

    stored_fp = data.get("client_id_fingerprint")
    stored_masked = data.get("client_id_masked")

    if not stored_fp:
        return {
            "has_stored_tokens": True,
            "legacy_no_fingerprint": True,
            "client_mismatch": False,
            "binding_ok": False,
            "current_client_id_masked": current_masked,
            "stored_client_id_masked": stored_masked,
            "stored_fingerprint_short": "não informado",
            "fingerprints_match": False,
            "message": (
                "Conexão OAuth antiga sem identificação do aplicativo. "
                "Reconecte a Conta Azul ou use Limpar conexão local."
            ),
        }

    if current_fp is None:
        match = False
    else:
        match = stored_fp == current_fp

    return {
        "has_stored_tokens": True,
        "legacy_no_fingerprint": False,
        "client_mismatch": not match,
        "binding_ok": match,
        "current_client_id_masked": current_masked,
        "stored_client_id_masked": stored_masked,
        "stored_fingerprint_short": short_fingerprint(stored_fp),
        "fingerprints_match": match,
        "message": (
            None
            if match
            else "A conexão salva pertence a outro Client ID. Limpe a conexão local e conecte novamente."
        ),
    }


def get_oauth_readiness(
    settings: Any,
    effective_redirect_uri: str,
    redirect_validation: dict[str, Any],
    db_path: str | None = None,
) -> dict[str, Any]:
    """
    Determina se Client ID, Secret, URLs de auth/token e redirect efetivo estão ok.

    ``redirect_validation`` deve ser o retorno de ``validate_redirect_uri_format``
    (chaves: valid, warnings, errors; opcional: is_placeholder).

    ``ready`` refere-se apenas à configuração necessária para **iniciar** o OAuth.
    Vinculação token↔Client ID vem em ``oauth_token_binding``.
    """
    missing: list[str] = []

    if not str(getattr(settings, "CONTA_AZUL_CLIENT_ID", "") or "").strip():
        missing.append("Client ID não configurado")
    if not str(getattr(settings, "CONTA_AZUL_CLIENT_SECRET", "") or "").strip():
        missing.append("Client Secret não configurado")
    if not str(getattr(settings, "CONTA_AZUL_AUTH_URL", "") or "").strip():
        missing.append("Auth URL não configurada")
    if not str(getattr(settings, "CONTA_AZUL_TOKEN_URL", "") or "").strip():
        missing.append("Token URL não configurada")

    eff = sanitize_redirect_uri(effective_redirect_uri)
    if not eff:
        missing.append("URL efetiva de redirecionamento não configurada")
    elif not redirect_validation.get("valid"):
        errs = redirect_validation.get("errors") or []
        if errs:
            missing.extend(str(e) for e in errs)
        else:
            missing.append("URL efetiva de redirecionamento inválida")
        if redirect_validation.get("is_placeholder"):
            ph = (
                "URL de redirecionamento é placeholder; informe a URL pública real "
                "do ngrok ou do deploy."
            )
            if ph not in missing:
                missing.append(ph)

    warnings = list(redirect_validation.get("warnings") or [])
    ready = len(missing) == 0

    binding = get_oauth_token_binding_status(settings, db_path)
    if binding["legacy_no_fingerprint"]:
        warnings.append(
            "Tokens salvos sem vínculo ao Client ID atual. "
            "Limpe a conexão local e autorize novamente."
        )
    if binding["client_mismatch"]:
        warnings.append(
            "A conexão salva pertence a outro Client ID. Limpe a conexão local e conecte novamente."
        )

    return {
        "ready": ready,
        "missing": missing,
        "warnings": warnings,
        "oauth_token_binding": binding,
    }
