"""Testes de api_snapshot_store."""

import json
from pathlib import Path

import pytest

from services import api_snapshot_store as snap


@pytest.fixture
def db(tmp_path: Path) -> str:
    return str(tmp_path / "snap.db")


def test_init_creates_table(db: str) -> None:
    snap.init_snapshot_db(db)
    assert Path(db).is_file()


def test_save_success_snapshot(db: str) -> None:
    snap.init_snapshot_db(db)
    sid = snap.save_api_snapshot(
        "t",
        "GET",
        "/v1/x",
        {"a": 1},
        True,
        data={"hello": "world"},
        status_code=200,
        db_path=db,
    )
    assert sid > 0
    rows = snap.list_api_snapshots(limit=10, db_path=db)
    assert len(rows) == 1
    assert rows[0]["success"] == 1
    assert rows[0]["status"] == "ok"


def test_save_error_snapshot(db: str) -> None:
    snap.save_api_snapshot(
        "t",
        "GET",
        "/v1/x",
        {},
        False,
        data=None,
        error_message="falhou",
        status_code=404,
        db_path=db,
    )
    rows = snap.list_api_snapshots(limit=10, db_path=db)
    assert rows[0]["success"] == 0
    assert rows[0]["error_message"] == "falhou"


def test_list_filter_resource(db: str) -> None:
    snap.save_api_snapshot("a", "GET", "/p", {}, True, {"x": 1}, db_path=db)
    snap.save_api_snapshot("b", "GET", "/q", {}, True, {"y": 2}, db_path=db)
    only_a = snap.list_api_snapshots(limit=10, resource_name="a", db_path=db)
    assert len(only_a) == 1
    assert only_a[0]["resource_name"] == "a"


def test_get_latest_and_by_id(db: str) -> None:
    snap.save_api_snapshot("x", "GET", "/a", {}, True, {"n": 1}, db_path=db)
    snap.save_api_snapshot("x", "GET", "/b", {}, True, {"n": 2}, db_path=db)
    latest = snap.get_latest_snapshot("x", db_path=db)
    assert latest is not None
    assert json.loads(latest["response_json"])["n"] == 2
    row = snap.get_snapshot_by_id(int(latest["id"]), db_path=db)
    assert row is not None
    assert row["path"] == "/b"


def test_no_raw_access_token_in_stored_json(db: str) -> None:
    secret = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9-secret-part"
    snap.save_api_snapshot(
        "tok",
        "GET",
        "/v1/x",
        {},
        True,
        data={"access_token": secret, "name": "ok"},
        db_path=db,
    )
    row = snap.list_api_snapshots(limit=1, db_path=db)[0]
    dumped = row["response_json"] or ""
    assert secret not in dumped
