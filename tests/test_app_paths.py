"""Caminhos de dados locais estáveis."""

from pathlib import Path

import app_paths


def test_get_project_root_is_dir():
    root = app_paths.get_project_root()
    assert root.is_dir()
    assert (root / "app_paths.py").is_file()


def test_get_data_dir_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(app_paths, "get_project_root", lambda: tmp_path / "proj")
    d = app_paths.get_data_dir()
    assert d == tmp_path / "proj" / ".local_data"
    assert d.is_dir()


def test_db_paths_under_data_dir(monkeypatch, tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    monkeypatch.setattr(app_paths, "get_project_root", lambda: proj)
    assert app_paths.get_token_db_path() == proj / ".local_data" / "conta_azul_tokens.db"
    assert app_paths.get_oauth_state_db_path() == proj / ".local_data" / "conta_azul_oauth_state.db"
    assert app_paths.get_app_settings_db_path() == proj / ".local_data" / "conta_azul_app_settings.db"
    assert app_paths.get_snapshot_db_path() == proj / ".local_data" / "conta_azul_api_snapshots.db"
