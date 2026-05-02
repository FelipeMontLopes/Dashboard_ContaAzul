"""URL de redirecionamento OAuth: override na app vs .env."""

from __future__ import annotations

from urllib.parse import urlparse

from config import get_settings

from app_paths import get_app_settings_db_path
from app_settings_store import delete_setting, get_setting, set_setting


def _resolve_settings_db(db_path: str | None) -> str:
    return db_path if db_path is not None else str(get_app_settings_db_path())

SETTING_REDIRECT_URI = "conta_azul_redirect_uri_override"

_PLACEHOLDER_ERROR = (
    "URL de redirecionamento parece ser um exemplo/placeholder. "
    "Rode ngrok http 8501 e cole a URL pública real gerada."
)

# Padrões comuns de documentação / tutoriais (não são URLs reais de túnel).
_PLACEHOLDER_SUBSTRINGS: tuple[str, ...] = (
    "abc123.ngrok-free.app",
    "seu-subdominio.ngrok-free.app",
    "your-subdomain",
    "localhost.ngrok",
    "placeholder",
    "<ngrok",
    "{ngrok",
    "minha-url",
    "sua-url",
    "url-publica",
    "url_publica",
)


def _is_example_com_host(u: str) -> bool:
    try:
        h = (urlparse(u).hostname or "").lower()
    except Exception:
        return False
    return h in ("example.com", "www.example.com")


def sanitize_redirect_uri(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_placeholder_redirect_uri(uri: str) -> bool:
    """True se a URL contém padrão de exemplo conhecido (não use no OAuth real)."""
    u = sanitize_redirect_uri(uri)
    if not u:
        return False
    low = u.lower()
    if any(s in low for s in _PLACEHOLDER_SUBSTRINGS):
        return True
    if _is_example_com_host(u):
        return True
    return False


def validate_redirect_uri_format(uri: str) -> dict:
    warnings: list[str] = []
    u = sanitize_redirect_uri(uri)

    if not u:
        return {
            "valid": False,
            "warnings": warnings,
            "errors": ["URL de redirecionamento não informada."],
            "is_placeholder": False,
        }

    lower = u.lower()
    if not (lower.startswith("http://") or lower.startswith("https://")):
        return {
            "valid": False,
            "warnings": warnings,
            "errors": ["A URL deve começar com http:// ou https://."],
            "is_placeholder": False,
        }

    if is_placeholder_redirect_uri(u):
        return {
            "valid": False,
            "warnings": warnings,
            "errors": [_PLACEHOLDER_ERROR],
            "is_placeholder": True,
        }

    errors: list[str] = []
    if lower.startswith("http://localhost") or lower.startswith("http://127.0.0.1"):
        warnings.append("localhost pode não ser aceito pelo Portal da Conta Azul em produção.")
    elif lower.startswith("http://"):
        warnings.append("Para produção, prefira HTTPS.")

    if u.endswith("/"):
        warnings.append(
            "Atenção: barra final precisa ser igual no Portal da Conta Azul e no app."
        )

    return {
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
        "is_placeholder": False,
    }


def get_env_redirect_uri() -> str:
    return sanitize_redirect_uri(get_settings().CONTA_AZUL_REDIRECT_URI)


def get_saved_redirect_uri(db_path: str | None = None) -> str:
    p = _resolve_settings_db(db_path)
    raw = get_setting(SETTING_REDIRECT_URI, default="", db_path=p)
    return sanitize_redirect_uri(raw if raw is not None else "")


def get_effective_redirect_uri(db_path: str | None = None) -> str:
    saved = get_saved_redirect_uri(db_path)
    if saved:
        return saved
    return get_env_redirect_uri()


def save_redirect_uri_override(uri: str, db_path: str | None = None) -> None:
    u = sanitize_redirect_uri(uri)
    result = validate_redirect_uri_format(u)
    if not result["valid"]:
        msg = " ".join(result["errors"]) if result["errors"] else "URL de redirecionamento inválida."
        raise ValueError(msg)
    p = _resolve_settings_db(db_path)
    set_setting(SETTING_REDIRECT_URI, u, db_path=p)


def clear_redirect_uri_override(db_path: str | None = None) -> None:
    p = _resolve_settings_db(db_path)
    delete_setting(SETTING_REDIRECT_URI, db_path=p)
