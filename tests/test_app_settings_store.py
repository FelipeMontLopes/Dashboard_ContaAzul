import pytest

from app_settings_store import (
    delete_setting,
    get_all_settings,
    get_setting,
    init_settings_db,
    set_setting,
)


def test_get_setting_default_quando_vazio(tmp_path):
    db = tmp_path / "a.db"
    assert get_setting("k", default="x", db_path=str(db)) == "x"


def test_set_e_get(tmp_path):
    db = tmp_path / "b.db"
    set_setting("mykey", "myval", db_path=str(db))
    assert get_setting("mykey", db_path=str(db)) == "myval"


def test_delete_setting(tmp_path):
    db = tmp_path / "c.db"
    set_setting("k", "v", db_path=str(db))
    delete_setting("k", db_path=str(db))
    assert get_setting("k", db_path=str(db)) is None


def test_get_all_settings(tmp_path):
    db = tmp_path / "d.db"
    set_setting("a", "1", db_path=str(db))
    set_setting("b", "2", db_path=str(db))
    assert get_all_settings(db_path=str(db)) == {"a": "1", "b": "2"}


def test_key_vazia_levanta(tmp_path):
    db = tmp_path / "e.db"
    with pytest.raises(ValueError):
        set_setting("", "x", db_path=str(db))


def test_init_cria_arquivo(tmp_path):
    db = tmp_path / "f.db"
    assert not db.exists()
    init_settings_db(str(db))
    assert db.exists()
