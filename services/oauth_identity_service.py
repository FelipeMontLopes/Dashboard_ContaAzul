"""Identidade OAuth Conta Azul: mascaramento e fingerprint de Client ID (sem segredos)."""

from __future__ import annotations

import hashlib


def mask_client_id(client_id: str | None) -> str:
    if client_id is None or not str(client_id).strip():
        return "não configurado"
    s = str(client_id).strip()
    if len(s) < 10:
        return "***"
    return f"{s[:6]}...{s[-4:]}"


def fingerprint_client_id(client_id: str | None) -> str | None:
    if client_id is None or not str(client_id).strip():
        return None
    raw = str(client_id).strip().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def short_fingerprint(value: str | None) -> str:
    if value is None or not str(value).strip():
        return "não informado"
    s = str(value).strip()
    return s[:8] if len(s) >= 8 else s
