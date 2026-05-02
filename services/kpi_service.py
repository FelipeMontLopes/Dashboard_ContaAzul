"""Cálculos de KPI financeiros sobre DataFrames (sem dependência de UI)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd


def _normalize_status(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip().lower()
    aliases = {
        "em aberto": "aberto",
        "aberto": "aberto",
        "pago": "pago",
        "paga": "pago",
        "cancelado": "cancelado",
        "cancelada": "cancelado",
        "vencido": "vencido",
        "vencida": "vencido",
    }
    return aliases.get(s, s)


def _coluna_data(df: pd.DataFrame, preferida: str) -> str | None:
    if preferida in df.columns:
        return preferida
    if "vencimento" in df.columns:
        return "vencimento"
    return None


def calcular_total_aberto(df: pd.DataFrame, coluna_valor: str = "valor") -> float:
    if df is None or df.empty or coluna_valor not in df.columns or "status" not in df.columns:
        return 0.0
    st = df["status"].map(_normalize_status)
    mask = st == "aberto"
    valores = pd.to_numeric(df.loc[mask, coluna_valor], errors="coerce").fillna(0.0)
    return float(valores.sum())


def calcular_total_pago(df: pd.DataFrame, coluna_valor: str = "valor") -> float:
    if df is None or df.empty or coluna_valor not in df.columns or "status" not in df.columns:
        return 0.0
    st = df["status"].map(_normalize_status)
    mask = st == "pago"
    valores = pd.to_numeric(df.loc[mask, coluna_valor], errors="coerce").fillna(0.0)
    return float(valores.sum())


def calcular_total_vencido(
    df: pd.DataFrame,
    coluna_valor: str = "valor",
    coluna_data: str = "data_vencimento",
) -> float:
    if df is None or df.empty or coluna_valor not in df.columns or "status" not in df.columns:
        return 0.0
    col_dt = _coluna_data(df, coluna_data)
    if col_dt is None:
        return 0.0

    st = df["status"].map(_normalize_status)
    valores = pd.to_numeric(df[coluna_valor], errors="coerce").fillna(0.0)
    datas = pd.to_datetime(df[col_dt], errors="coerce").dt.normalize()

    excluir = st.isin(["pago", "cancelado"])
    hoje = pd.Timestamp(date.today()).normalize()

    por_status = st == "vencido"
    em_aberto_atrasado = (st == "aberto") & datas.notna() & (datas < hoje)

    mask = ~excluir & (por_status | em_aberto_atrasado)
    return float(valores.loc[mask].sum())


def calcular_fluxo_periodo(df_fluxo: pd.DataFrame, dias: int) -> dict[str, Any]:
    vazio: dict[str, Any] = {
        "total_entradas": 0.0,
        "total_saidas": 0.0,
        "saldo_periodo": 0.0,
        "menor_saldo": 0.0,
        "data_menor_saldo": None,
    }
    if df_fluxo is None or df_fluxo.empty or "data" not in df_fluxo.columns:
        return vazio.copy()

    df = df_fluxo.copy()
    df["_dt"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["_dt"])
    if df.empty:
        return vazio.copy()

    try:
        d = int(dias)
    except (TypeError, ValueError):
        d = 0

    hoje = pd.Timestamp(date.today()).normalize()
    fim = hoje + pd.Timedelta(days=d)
    periodo = df.loc[(df["_dt"] >= hoje) & (df["_dt"] <= fim)].sort_values("_dt")
    if periodo.empty:
        return vazio.copy()

    entradas_col = "entradas" if "entradas" in periodo.columns else None
    saidas_col = "saidas" if "saidas" in periodo.columns else None

    total_entradas = (
        float(pd.to_numeric(periodo[entradas_col], errors="coerce").fillna(0.0).sum())
        if entradas_col
        else 0.0
    )
    total_saidas = (
        float(pd.to_numeric(periodo[saidas_col], errors="coerce").fillna(0.0).sum())
        if saidas_col
        else 0.0
    )
    saldo_periodo = total_entradas - total_saidas

    if "saldo_acumulado" in periodo.columns:
        saldos = pd.to_numeric(periodo["saldo_acumulado"], errors="coerce").fillna(0.0)
        imin = saldos.idxmin()
        menor_saldo = float(saldos.loc[imin]) if imin is not None and pd.notna(imin) else 0.0
        dt_min = periodo.loc[imin, "_dt"]
        data_menor = dt_min.strftime("%Y-%m-%d") if pd.notna(dt_min) else None
    elif entradas_col and saidas_col:
        net = pd.to_numeric(periodo[entradas_col], errors="coerce").fillna(0.0) - pd.to_numeric(
            periodo[saidas_col], errors="coerce"
        ).fillna(0.0)
        cum = net.cumsum()
        imin = cum.idxmin()
        menor_saldo = float(cum.loc[imin])
        dt_min = periodo.loc[imin, "_dt"]
        data_menor = dt_min.strftime("%Y-%m-%d") if pd.notna(dt_min) else None
    else:
        menor_saldo = 0.0
        data_menor = None

    return {
        "total_entradas": total_entradas,
        "total_saidas": total_saidas,
        "saldo_periodo": saldo_periodo,
        "menor_saldo": menor_saldo,
        "data_menor_saldo": data_menor,
    }


def _saldo_final_no_periodo(df_fluxo: pd.DataFrame, dias: int) -> float:
    if df_fluxo is None or df_fluxo.empty or "data" not in df_fluxo.columns:
        return 0.0
    df = df_fluxo.copy()
    df["_dt"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["_dt"])
    try:
        d = int(dias)
    except (TypeError, ValueError):
        d = 0
    hoje = pd.Timestamp(date.today()).normalize()
    fim = hoje + pd.Timedelta(days=d)
    periodo = df.loc[(df["_dt"] >= hoje) & (df["_dt"] <= fim)].sort_values("_dt")
    if periodo.empty:
        return 0.0
    if "saldo_acumulado" in periodo.columns:
        ultimo = pd.to_numeric(periodo["saldo_acumulado"].iloc[-1], errors="coerce")
        return float(ultimo) if pd.notna(ultimo) else 0.0
    if "entradas" in periodo.columns and "saidas" in periodo.columns:
        net = pd.to_numeric(periodo["entradas"], errors="coerce").fillna(0.0) - pd.to_numeric(
            periodo["saidas"], errors="coerce"
        ).fillna(0.0)
        return float(net.sum())
    return 0.0


def calcular_resumo_executivo(
    contas_receber: pd.DataFrame,
    contas_pagar: pd.DataFrame,
    fluxo_caixa: pd.DataFrame,
) -> dict[str, Any]:
    f30 = calcular_fluxo_periodo(fluxo_caixa, 30)

    return {
        "total_receber_aberto": calcular_total_aberto(contas_receber),
        "total_pagar_aberto": calcular_total_aberto(contas_pagar),
        "total_receber_vencido": calcular_total_vencido(contas_receber),
        "total_pagar_vencido": calcular_total_vencido(contas_pagar),
        "total_recebido": calcular_total_pago(contas_receber),
        "total_pago": calcular_total_pago(contas_pagar),
        "saldo_7_dias": _saldo_final_no_periodo(fluxo_caixa, 7),
        "saldo_15_dias": _saldo_final_no_periodo(fluxo_caixa, 15),
        "saldo_30_dias": _saldo_final_no_periodo(fluxo_caixa, 30),
        "menor_saldo_30_dias": f30["menor_saldo"],
        "data_critica_30_dias": f30["data_menor_saldo"],
    }


def formatar_moeda(valor: Any) -> str:
    try:
        if valor is None:
            v = 0.0
        elif isinstance(valor, float) and pd.isna(valor):
            v = 0.0
        else:
            v = float(valor)
    except (TypeError, ValueError):
        v = 0.0

    neg = v < 0
    v = abs(round(v, 2))
    centavos = int(round(v * 100))
    inteiro = centavos // 100
    frac = centavos % 100
    parte = f"{inteiro:,}".replace(",", ".")
    s = f"R$ {parte},{frac:02d}"
    return f"-{s}" if neg else s


def montar_tabela_fluxo_resumo(df_fluxo: pd.DataFrame) -> pd.DataFrame:
    """Data + entradas/saídas diárias + saldo do dia + saldo acumulado (para exibição)."""
    if df_fluxo is None or df_fluxo.empty or "data" not in df_fluxo.columns:
        return pd.DataFrame(columns=["data", "entradas", "saidas", "saldo_dia", "saldo_acumulado"])

    df = df_fluxo.copy()
    df["_dt"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["_dt"]).sort_values("_dt")

    if "entradas" in df.columns:
        ent = pd.to_numeric(df["entradas"], errors="coerce").fillna(0.0)
    else:
        ent = pd.Series(0.0, index=df.index)
    if "saidas" in df.columns:
        sai = pd.to_numeric(df["saidas"], errors="coerce").fillna(0.0)
    else:
        sai = pd.Series(0.0, index=df.index)
    saldo_dia = ent - sai

    if "saldo_acumulado" in df.columns:
        acum = pd.to_numeric(df["saldo_acumulado"], errors="coerce").fillna(0.0)
    else:
        acum = saldo_dia.cumsum()

    return pd.DataFrame(
        {
            "data": df["_dt"].dt.strftime("%Y-%m-%d"),
            "entradas": ent,
            "saidas": sai,
            "saldo_dia": saldo_dia,
            "saldo_acumulado": acum,
        }
    )
