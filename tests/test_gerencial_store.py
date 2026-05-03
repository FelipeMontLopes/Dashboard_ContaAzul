"""Testes do store gerencial (SQLite)."""

from __future__ import annotations

import app_paths
from services import gerencial_store as gs


def test_init_gerencial_db_cria_tabelas(monkeypatch, tmp_path):
    db = tmp_path / "g.db"
    monkeypatch.setattr(app_paths, "get_gerencial_db_path", lambda: db)
    gs.init_gerencial_db()
    gs.create_socio("Teste", percentual_participacao=50.0)
    rows = gs.list_socios()
    assert len(rows) == 1
    assert rows[0]["nome"] == "Teste"


def test_socio_crud(monkeypatch, tmp_path):
    db = tmp_path / "g.db"
    monkeypatch.setattr(app_paths, "get_gerencial_db_path", lambda: db)
    gs.init_gerencial_db()
    sid = gs.create_socio("A", papel="sócio", percentual_participacao=40.0)
    gs.update_socio(sid, nome="A2", percentual_participacao=60.0)
    r = gs.get_socio(sid)
    assert r is not None
    assert r["nome"] == "A2"
    assert r["percentual_participacao"] == 60.0
    gs.delete_socio(sid)
    assert gs.get_socio(sid) is None


def test_custo_fixo_crud(monkeypatch, tmp_path):
    db = tmp_path / "g.db"
    monkeypatch.setattr(app_paths, "get_gerencial_db_path", lambda: db)
    gs.init_gerencial_db()
    cid = gs.create_custo_fixo("Aluguel", valor_mensal=3000.0, categoria="aluguel")
    rows = gs.list_custos_fixos(apenas_ativos=True)
    assert len(rows) == 1
    assert rows[0]["valor_mensal"] == 3000.0
    gs.delete_custo_fixo(cid)
    assert gs.list_custos_fixos() == []


def test_premissas_set_get(monkeypatch, tmp_path):
    db = tmp_path / "g.db"
    monkeypatch.setattr(app_paths, "get_gerencial_db_path", lambda: db)
    gs.init_gerencial_db()
    gs.set_premissa("imposto_percentual", "15")
    assert gs.get_premissa("imposto_percentual") == "15"


def test_obra_manual(monkeypatch, tmp_path):
    db = tmp_path / "g.db"
    monkeypatch.setattr(app_paths, "get_gerencial_db_path", lambda: db)
    gs.init_gerencial_db()
    oid = gs.create_obra_manual(
        "Obra X",
        receita_realizada_manual=10000.0,
        custo_realizado_manual=4000.0,
    )
    rows = gs.list_obras_manuais(apenas_ativas=True)
    assert len(rows) == 1
    gs.delete_obra_manual(oid)
    assert gs.list_obras_manuais() == []
