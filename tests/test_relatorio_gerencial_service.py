"""Testes do serviço de relatório gerencial MVP."""

from __future__ import annotations

import app_paths
from services import gerencial_store as gs
from services.relatorio_gerencial_service import (
    calcular_break_even,
    calcular_resumo_gerencial,
    calcular_resultado_obras,
    calcular_resultado_socios,
    get_relatorio_context,
    montar_relatorio_completo,
)


def _iso_db(monkeypatch, tmp_path):
    db = tmp_path / "ger.db"
    monkeypatch.setattr(app_paths, "get_gerencial_db_path", lambda: db)
    gs.init_gerencial_db(db_path=str(db))
    return str(db)


def test_calcular_resumo_vazio_nao_quebra(monkeypatch, tmp_path):
    db = _iso_db(monkeypatch, tmp_path)
    gs.seed_premissas_padrao(db_path=db)
    context = get_relatorio_context(db_path=db)
    r = calcular_resumo_gerencial(context)
    assert "receitas_realizadas" in r
    assert "custos_totais" in r
    assert r["receitas_realizadas"] == 0.0


def test_calcular_obras_saldo_margem(monkeypatch, tmp_path):
    db = _iso_db(monkeypatch, tmp_path)
    gs.create_obra_manual(
        "P1",
        receita_realizada_manual=1000.0,
        custo_realizado_manual=400.0,
        db_path=db,
    )
    ctx = get_relatorio_context(db_path=db)
    o = calcular_resultado_obras(ctx)
    assert o["total_receitas_realizadas_obras"] == 1000.0
    linha = o["linhas"][0]
    assert linha["saldo"] == 600.0
    assert abs(linha["margem_pct"] - 60.0) < 0.01


def test_socio_quota(monkeypatch, tmp_path):
    db = _iso_db(monkeypatch, tmp_path)
    gs.create_socio("S1", percentual_participacao=50.0, db_path=db)
    gs.create_socio("S2", percentual_participacao=50.0, db_path=db)
    gs.create_obra_manual(
        "O",
        receita_realizada_manual=2000.0,
        custo_realizado_manual=0.0,
        db_path=db,
    )
    ctx = get_relatorio_context(db_path=db)
    resumo = calcular_resumo_gerencial(ctx)
    soc = calcular_resultado_socios(ctx, resumo)
    quotas = [x["quota_resultado"] for x in soc["linhas"]]
    assert len(quotas) == 2
    assert abs(quotas[0] - 1000.0) < 0.01
    assert abs(quotas[1] - 1000.0) < 0.01


def test_break_even(monkeypatch, tmp_path):
    db = _iso_db(monkeypatch, tmp_path)
    gs.set_premissa("imposto_percentual", "0", db_path=db)
    gs.set_premissa("custo_variavel_percentual", "20", db_path=db)
    gs.set_premissa("custo_fixo_mensal_manual", "800", db_path=db)
    ctx = get_relatorio_context(db_path=db)
    be = calcular_break_even(ctx)
    assert be["ponto_equilibrio_receita"] is not None
    assert abs(be["ponto_equilibrio_receita"] - 1000.0) < 0.01


def test_montar_relatorio_chaves(monkeypatch, tmp_path):
    db = _iso_db(monkeypatch, tmp_path)
    rep = montar_relatorio_completo(db_path=db)
    assert set(rep.keys()) >= {
        "contexto",
        "resumo",
        "obras",
        "socios",
        "custos_fixos",
        "break_even",
        "total_investimentos",
        "fonte_total_investimentos",
    }
