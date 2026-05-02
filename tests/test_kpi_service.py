"""Testes unitários mínimos para services.kpi_service."""

from datetime import date

import pandas as pd
import pytest

from services import kpi_service
from services.kpi_service import (
    calcular_fluxo_periodo,
    calcular_resumo_executivo,
    calcular_total_aberto,
    calcular_total_pago,
    calcular_total_vencido,
    formatar_moeda,
)


@pytest.fixture
def dia_fixo(monkeypatch):
    """Congela 'hoje' para datas determinísticas nos asserts."""

    class _DataFake:
        @staticmethod
        def today():
            return date(2026, 5, 15)

    monkeypatch.setattr(kpi_service, "date", _DataFake)


def test_total_aberto_soma_so_aberto():
    df = pd.DataFrame(
        [
            {"valor": 100.0, "status": "aberto"},
            {"valor": 40.0, "status": "Em aberto"},
            {"valor": 999.0, "status": "pago"},
            {"valor": 50.0, "status": "vencido"},
        ]
    )
    assert calcular_total_aberto(df) == pytest.approx(140.0)


def test_total_pago():
    df = pd.DataFrame(
        [
            {"valor": 200.0, "status": "pago"},
            {"valor": 10.0, "status": "aberto"},
        ]
    )
    assert calcular_total_pago(df) == pytest.approx(200.0)


def test_total_vencido_por_status():
    df = pd.DataFrame(
        [
            {"valor": 300.0, "status": "vencido", "data_vencimento": "2026-01-01"},
            {"valor": 100.0, "status": "pago", "data_vencimento": "2025-01-01"},
        ]
    )
    assert calcular_total_vencido(df) == pytest.approx(300.0)


def test_total_vencido_por_data_aberto_atrasado(dia_fixo):
    df = pd.DataFrame(
        [
            {"valor": 250.0, "status": "aberto", "data_vencimento": "2026-05-10"},
            {"valor": 999.0, "status": "aberto", "data_vencimento": "2026-06-01"},
        ]
    )
    assert calcular_total_vencido(df) == pytest.approx(250.0)


def test_dataframe_vazio_retorna_zero():
    vazio = pd.DataFrame()
    assert calcular_total_aberto(vazio) == 0.0
    assert calcular_total_pago(vazio) == 0.0
    assert calcular_total_vencido(vazio) == 0.0
    r = calcular_fluxo_periodo(vazio, 7)
    assert r["total_entradas"] == 0.0
    assert r["saldo_periodo"] == 0.0


def test_fluxo_7_dias_saldo_periodo_correto(dia_fixo):
    df = pd.DataFrame(
        [
            {"data": "2026-05-15", "entradas": 100.0, "saidas": 40.0, "saldo_acumulado": 1000.0},
            {"data": "2026-05-16", "entradas": 50.0, "saidas": 10.0, "saldo_acumulado": 1040.0},
            {"data": "2026-05-20", "entradas": 200.0, "saidas": 100.0, "saldo_acumulado": 1140.0},
        ]
    )
    r = calcular_fluxo_periodo(df, 7)
    assert r["total_entradas"] == pytest.approx(350.0)
    assert r["total_saidas"] == pytest.approx(150.0)
    assert r["saldo_periodo"] == pytest.approx(200.0)


def test_formatar_moeda():
    assert formatar_moeda(None) == "R$ 0,00"
    assert formatar_moeda(float("nan")) == "R$ 0,00"
    assert formatar_moeda(1234.56) == "R$ 1.234,56"
    assert formatar_moeda(-99.5) == "-R$ 99,50"


def test_calcular_resumo_executivo_chaves(dia_fixo):
    cr = pd.DataFrame([{"valor": 10.0, "status": "aberto", "data_vencimento": "2026-06-01"}])
    cp = pd.DataFrame([{"valor": 5.0, "status": "pago", "data_vencimento": "2026-06-01"}])
    flux = pd.DataFrame(
        [
            {
                "data": "2026-05-15",
                "entradas": 100.0,
                "saidas": 20.0,
                "saldo_acumulado": 5000.0,
            },
        ]
    )
    out = calcular_resumo_executivo(cr, cp, flux)
    assert "total_receber_aberto" in out
    assert "saldo_30_dias" in out
    assert out["total_receber_aberto"] == pytest.approx(10.0)
