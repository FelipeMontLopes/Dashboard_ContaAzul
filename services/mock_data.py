"""Dados fictícios para desenvolvimento da interface (sem API real)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd


def _hoje() -> date:
    return date.today()


def get_mock_contas_receber() -> pd.DataFrame:
    hoje = _hoje()
    rows = [
        {
            "cliente": "Cliente Alfa",
            "data_vencimento": (hoje + timedelta(days=12)).isoformat(),
            "valor": 4200.00,
            "status": "aberto",
        },
        {
            "cliente": "Cliente Beta",
            "data_vencimento": (hoje - timedelta(days=5)).isoformat(),
            "valor": 980.50,
            "status": "aberto",
        },
        {
            "cliente": "Cliente Gama",
            "data_vencimento": (hoje - timedelta(days=30)).isoformat(),
            "valor": 750.00,
            "status": "vencido",
        },
        {
            "cliente": "Cliente Delta",
            "data_vencimento": (hoje + timedelta(days=45)).isoformat(),
            "valor": 3100.00,
            "status": "pago",
        },
        {
            "cliente": "Cliente Épsilon",
            "data_vencimento": (hoje + timedelta(days=7)).isoformat(),
            "valor": 400.00,
            "status": "cancelado",
        },
    ]
    return pd.DataFrame(rows)


def get_mock_contas_pagar() -> pd.DataFrame:
    hoje = _hoje()
    rows = [
        {
            "fornecedor": "Fornecedor 1",
            "data_vencimento": (hoje + timedelta(days=8)).isoformat(),
            "valor": 2100.00,
            "status": "aberto",
        },
        {
            "fornecedor": "Fornecedor 2",
            "data_vencimento": (hoje - timedelta(days=3)).isoformat(),
            "valor": 430.75,
            "status": "aberto",
        },
        {
            "fornecedor": "Fornecedor 3",
            "data_vencimento": (hoje - timedelta(days=60)).isoformat(),
            "valor": 190.00,
            "status": "vencido",
        },
        {
            "fornecedor": "Fornecedor 4",
            "data_vencimento": (hoje + timedelta(days=20)).isoformat(),
            "valor": 5600.00,
            "status": "pago",
        },
        {
            "fornecedor": "Fornecedor 5",
            "data_vencimento": (hoje + timedelta(days=90)).isoformat(),
            "valor": 120.00,
            "status": "cancelado",
        },
    ]
    return pd.DataFrame(rows)


def get_mock_fluxo_caixa() -> pd.DataFrame:
    """Projeção diária (≥30 dias) com entradas, saídas e saldo acumulado."""
    hoje = _hoje()
    rows: list[dict] = []
    saldo = 14000.0
    for i in range(38):
        d = hoje + timedelta(days=i)
        entradas = 450.0 + (i % 6) * 40.0
        # Saídas aumentam no horizonte para permitir saldo projetado negativo em 30 dias
        saidas = 380.0 + i * 35.0
        saldo = saldo + entradas - saidas
        rows.append(
            {
                "data": d.isoformat(),
                "entradas": round(entradas, 2),
                "saidas": round(saidas, 2),
                "saldo_acumulado": round(saldo, 2),
            }
        )
    return pd.DataFrame(rows)
