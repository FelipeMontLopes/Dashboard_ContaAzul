"""Testes do serviço de identidade OAuth (Client ID mascarado / fingerprint)."""

from services.oauth_identity_service import (
    fingerprint_client_id,
    mask_client_id,
    short_fingerprint,
)


def test_mask_vazio():
    assert mask_client_id(None) == "não configurado"
    assert mask_client_id("") == "não configurado"
    assert mask_client_id("   ") == "não configurado"


def test_mask_curto():
    assert mask_client_id("short") == "***"
    assert mask_client_id("123456789") == "***"


def test_mask_longo():
    assert mask_client_id("abcdefghijklmnop") == "abcdef...mnop"


def test_fingerprint_estavel_e_distinta():
    a = fingerprint_client_id("client-a")
    b = fingerprint_client_id("client-b")
    assert a is not None and b is not None
    assert a == fingerprint_client_id("client-a")
    assert a != b


def test_fingerprint_vazio_none():
    assert fingerprint_client_id(None) is None
    assert fingerprint_client_id("") is None


def test_short_fingerprint():
    h = "abcdef0123456789"
    assert short_fingerprint(h) == "abcdef01"
    assert short_fingerprint(None) == "não informado"
