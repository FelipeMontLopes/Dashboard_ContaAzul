"""Regras puras para saber se o fluxo OAuth pode ser iniciado (sem Streamlit)."""

from __future__ import annotations

from typing import Any

from redirect_uri_service import sanitize_redirect_uri


def get_oauth_readiness(
    settings: Any,
    effective_redirect_uri: str,
    redirect_validation: dict[str, Any],
) -> dict[str, Any]:
    """
    Determina se Client ID, Secret, URLs de auth/token e redirect efetivo estão ok.

    ``redirect_validation`` deve ser o retorno de ``validate_redirect_uri_format``
    (chaves: valid, warnings, errors; opcional: is_placeholder).
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
    return {"ready": ready, "missing": missing, "warnings": warnings}
