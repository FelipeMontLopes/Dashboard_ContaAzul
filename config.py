"""Configuração: .env local + variáveis de ambiente + Streamlit secrets (Cloud)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Caminho do .env ao lado deste arquivo. Não sobrescreve variáveis já definidas
# no ambiente do processo (override implícito False).
_PROJECT_ROOT = Path(__file__).resolve().parent
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_PATH)

# Defaults alinhados ao Portal Conta Azul / .env.example (sem credenciais).
_DEFAULT_AUTH_URL = "https://auth.contaazul.com/login"
_DEFAULT_TOKEN_URL = "https://auth.contaazul.com/oauth2/token"
_DEFAULT_API_BASE_URL = "https://api-v2.contaazul.com"
_DEFAULT_SCOPE = "openid profile aws.cognito.signin.user.admin"
_DEFAULT_DIAGNOSTIC_PATH = "/v1/pessoas/conta-conectada"


def _streamlit_secret(key: str) -> str:
    """Lê chave de st.secrets quando disponível; falha silenciosa fora do Streamlit."""
    try:
        import streamlit as st  # import tardio: evita dependência pesada em scripts/testes

        sec = getattr(st, "secrets", None)
        if sec is None or key not in sec:
            return ""
        val = sec[key]
        if val is None:
            return ""
        return str(val).strip()
    except Exception:
        return ""


def _resolve(key: str, *, default: str) -> str:
    """
    Prioridade:
    1. Variável de ambiente (inclui valores vindos do .env via load_dotenv).
    2. Streamlit secrets (deploy Community Cloud).
    3. default
    """
    raw = os.getenv(key)
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip()
    from_secrets = _streamlit_secret(key)
    if from_secrets:
        return from_secrets
    return default


@dataclass
class Settings:
    CONTA_AZUL_CLIENT_ID: str
    CONTA_AZUL_CLIENT_SECRET: str
    CONTA_AZUL_REDIRECT_URI: str
    CONTA_AZUL_AUTH_URL: str
    CONTA_AZUL_TOKEN_URL: str
    CONTA_AZUL_API_BASE_URL: str
    CONTA_AZUL_SCOPE: str
    CONTA_AZUL_DIAGNOSTIC_PATH: str


def get_settings() -> Settings:
    return Settings(
        CONTA_AZUL_CLIENT_ID=_resolve("CONTA_AZUL_CLIENT_ID", default=""),
        CONTA_AZUL_CLIENT_SECRET=_resolve("CONTA_AZUL_CLIENT_SECRET", default=""),
        CONTA_AZUL_REDIRECT_URI=_resolve("CONTA_AZUL_REDIRECT_URI", default=""),
        CONTA_AZUL_AUTH_URL=_resolve("CONTA_AZUL_AUTH_URL", default=_DEFAULT_AUTH_URL),
        CONTA_AZUL_TOKEN_URL=_resolve("CONTA_AZUL_TOKEN_URL", default=_DEFAULT_TOKEN_URL),
        CONTA_AZUL_API_BASE_URL=_resolve(
            "CONTA_AZUL_API_BASE_URL", default=_DEFAULT_API_BASE_URL
        ),
        CONTA_AZUL_SCOPE=_resolve("CONTA_AZUL_SCOPE", default=_DEFAULT_SCOPE),
        CONTA_AZUL_DIAGNOSTIC_PATH=_resolve(
            "CONTA_AZUL_DIAGNOSTIC_PATH", default=_DEFAULT_DIAGNOSTIC_PATH
        ),
    )
