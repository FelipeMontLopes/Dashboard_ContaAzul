"""Caminhos estáveis para dados locais (independente do diretório de trabalho)."""

from __future__ import annotations

from pathlib import Path


def get_project_root() -> Path:
    """Raiz do pacote da aplicação (pasta que contém `app.py`)."""
    return Path(__file__).resolve().parent


def get_data_dir() -> Path:
    """Diretório para SQLite e outros artefatos locais (criado se não existir)."""
    d = get_project_root() / ".local_data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_token_db_path() -> Path:
    return get_data_dir() / "conta_azul_tokens.db"


def get_oauth_state_db_path() -> Path:
    return get_data_dir() / "conta_azul_oauth_state.db"


def get_app_settings_db_path() -> Path:
    return get_data_dir() / "conta_azul_app_settings.db"


def get_snapshot_db_path() -> Path:
    """Banco SQLite para snapshots brutos de chamadas à API (explorador / diagnóstico)."""
    return get_data_dir() / "conta_azul_api_snapshots.db"


def get_gerencial_db_path() -> Path:
    """Banco SQLite para cadastros gerenciais e dados do relatório MVP."""
    return get_data_dir() / "conta_azul_gerencial.db"
