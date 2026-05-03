"""Montagem do relatório gerencial MVP: cadastros manuais + metadados Conta Azul (sem inventar KPIs)."""

from __future__ import annotations

from typing import Any

from services import gerencial_store as gs
from services.api_snapshot_store import get_latest_snapshot, list_api_snapshots

FONTE_CONTA_AZUL = "Conta Azul"
FONTE_MANUAL = "Cadastro Manual"
FONTE_CALCULADO = "Calculado"
FONTE_MOCK = "Mock/Fallback"
FONTE_PENDENTE = "Não configurado"


def _parse_float(val: str | None, default: float = 0.0) -> float:
    if val is None or str(val).strip() == "":
        return default
    try:
        return float(str(val).replace(",", "."))
    except (TypeError, ValueError):
        return default


def _snapshot_financeiro_disponivel() -> dict[str, Any]:
    """Indica se há snapshots recentes da API (sem extrair totais não normalizados)."""
    nomes = (
        "financeiro_alteracoes",
        "financeiro_saldo_inicial",
        "eventos_financeiros_alteracoes",
        "eventos_financeiros_saldo_inicial",
    )
    encontrados: list[dict[str, Any]] = []
    for nome in nomes:
        snap = get_latest_snapshot(nome)
        if snap and snap.get("success"):
            encontrados.append(
                {
                    "resource_name": nome,
                    "snapshot_id": snap.get("id"),
                    "fetched_at": snap.get("fetched_at"),
                    "tem_corpo": bool(snap.get("response_json")),
                }
            )
    if not encontrados:
        recent = list_api_snapshots(limit=30)
        for row in recent:
            path = str(row.get("path") or "")
            if "financeiro" in path.lower() or "eventos-financeiros" in path.lower():
                if row.get("success"):
                    encontrados.append(
                        {
                            "resource_name": row.get("resource_name"),
                            "snapshot_id": row.get("id"),
                            "fetched_at": row.get("fetched_at"),
                            "tem_corpo": bool(row.get("response_json")),
                        }
                    )
    tem_snap = len(encontrados) > 0
    return {
        "disponivel": tem_snap,
        "snapshots": encontrados[:10],
        "fonte_resumo": FONTE_CONTA_AZUL if tem_snap else FONTE_PENDENTE,
        "total_extraido_normalizado": False,
        "mensagem": (
            "Há snapshots sanitizados da API no explorador; totais ainda não são normalizados para KPIs."
            if tem_snap
            else "Sem snapshots financeiros recentes. Use cadastros manuais ou capture dados no Explorador da API."
        ),
    }


def get_relatorio_context(
    periodo_inicio: str | None = None,
    periodo_fim: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Carrega dados manuais e metadados Conta Azul. Não inventa valores financeiros da API."""
    gs.init_gerencial_db(db_path)
    gs.seed_premissas_padrao(db_path)

    premissas = gs.list_premissas(db_path)
    socios = gs.list_socios(db_path, apenas_ativos=True)
    custos_fixos = gs.list_custos_fixos(db_path, apenas_ativos=True)
    obras = gs.list_obras_manuais(db_path, apenas_ativas=True)
    investimentos = gs.list_investimentos(db_path)
    ajustes = gs.list_socio_ajustes(db_path=db_path)
    indicadores = gs.list_indicadores(db_path)
    justificativas = gs.list_justificativas(db_path)
    mapeamentos = gs.list_mapeamentos(db_path)

    conta_azul = _snapshot_financeiro_disponivel()

    return {
        "periodo_inicio": periodo_inicio,
        "periodo_fim": periodo_fim,
        "premissas": premissas,
        "socios": socios,
        "custos_fixos": custos_fixos,
        "obras": obras,
        "investimentos": investimentos,
        "ajustes": ajustes,
        "indicadores": indicadores,
        "justificativas": justificativas,
        "mapeamentos": mapeamentos,
        "conta_azul": conta_azul,
    }


def calcular_custos_fixos(context: dict[str, Any]) -> dict[str, Any]:
    linhas = context.get("custos_fixos") or []
    total = 0.0
    por_categoria: dict[str, float] = {}
    for row in linhas:
        vm = float(row.get("valor_mensal") or 0)
        total += vm
        cat = (row.get("categoria") or "outros").strip() or "outros"
        por_categoria[cat] = por_categoria.get(cat, 0.0) + vm

    prem = context.get("premissas") or {}
    manual_override = _parse_float(prem.get("custo_fixo_mensal_manual"), 0.0)
    fonte_total = FONTE_MANUAL if linhas else FONTE_PENDENTE
    if manual_override > 0 and not linhas:
        total = manual_override
        fonte_total = FONTE_MANUAL

    return {
        "total_mensal": total,
        "por_categoria": por_categoria,
        "fonte_total": fonte_total,
        "tem_cadastro": bool(linhas) or manual_override > 0,
    }


def calcular_resultado_obras(context: dict[str, Any]) -> dict[str, Any]:
    obras = context.get("obras") or []
    linhas: list[dict[str, Any]] = []
    for o in obras:
        rec = float(o.get("receita_realizada_manual") or 0)
        cust = float(o.get("custo_realizado_manual") or 0)
        saldo = rec - cust
        margem = (saldo / rec * 100.0) if rec > 0 else None
        linhas.append(
            {
                "id": o.get("id"),
                "nome": o.get("nome"),
                "cliente": o.get("cliente"),
                "receita_realizada": rec,
                "custo_realizado": cust,
                "receita_a_realizar": float(o.get("receita_a_realizar_manual") or 0),
                "saldo": saldo,
                "margem_pct": margem,
                "status": o.get("status"),
                "fonte_receita_custo": FONTE_MANUAL if (rec != 0 or cust != 0) else FONTE_PENDENTE,
            }
        )

    total_rec = sum(float(x["receita_realizada"]) for x in linhas)
    total_cust_obras = sum(float(x["custo_realizado"]) for x in linhas)
    total_a_realizar = sum(float(x["receita_a_realizar"]) for x in linhas)

    ca = context.get("conta_azul") or {}
    fonte_agregada = FONTE_MANUAL if linhas and (total_rec != 0 or total_cust_obras != 0) else FONTE_PENDENTE
    if fonte_agregada == FONTE_PENDENTE and ca.get("disponivel") and not ca.get("total_extraido_normalizado"):
        fonte_agregada = FONTE_PENDENTE

    return {
        "linhas": linhas,
        "total_receitas_realizadas_obras": total_rec,
        "total_custos_obras": total_cust_obras,
        "total_receitas_a_realizar": total_a_realizar,
        "fonte_receitas_realizadas": fonte_agregada,
        "fonte_conta_azul_normalizada": False,
    }


def calcular_resumo_gerencial(context: dict[str, Any]) -> dict[str, Any]:
    obras_res = calcular_resultado_obras(context)
    cf = calcular_custos_fixos(context)

    receitas_r = float(obras_res["total_receitas_realizadas_obras"])
    custos_obras = float(obras_res["total_custos_obras"])
    custo_fixo_m = float(cf["total_mensal"])

    prem = context.get("premissas") or {}
    if not cf["tem_cadastro"] and _parse_float(prem.get("custo_fixo_mensal_manual"), 0) > 0:
        custo_fixo_m = _parse_float(prem.get("custo_fixo_mensal_manual"))

    custos_totais = custos_obras + custo_fixo_m
    resultado_liquido = receitas_r - custos_totais
    margem = (resultado_liquido / receitas_r * 100.0) if receitas_r > 0 else None

    rec_a_realizar = float(obras_res["total_receitas_a_realizar"])

    return {
        "receitas_realizadas": receitas_r,
        "custos_totais": custos_totais,
        "resultado_liquido": resultado_liquido,
        "margem_liquida_pct": margem,
        "receitas_a_realizar": rec_a_realizar,
        "custo_fixo_mensal": custo_fixo_m,
        "fonte_receitas_realizadas": obras_res["fonte_receitas_realizadas"],
        "fonte_custos_obras": FONTE_MANUAL if custos_obras != 0 else FONTE_PENDENTE,
        "fonte_custo_fixo": cf["fonte_total"],
        "fonte_resultado": FONTE_CALCULADO,
        "fonte_margem": FONTE_CALCULADO if receitas_r > 0 else FONTE_PENDENTE,
    }


def calcular_resultado_socios(context: dict[str, Any], resumo: dict[str, Any] | None = None) -> dict[str, Any]:
    if resumo is None:
        resumo = calcular_resumo_gerencial(context)
    socios = context.get("socios") or []
    resultado = float(resumo.get("resultado_liquido") or 0)
    ajustes = context.get("ajustes") or []

    tot_pct = sum(float(s.get("percentual_participacao") or 0) for s in socios)
    if tot_pct <= 0 and socios:
        tot_pct = 100.0

    linhas: list[dict[str, Any]] = []
    for s in socios:
        sid = int(s["id"])
        pct = float(s.get("percentual_participacao") or 0)
        quota = resultado * (pct / tot_pct) if tot_pct > 0 else 0.0
        adj_sum = sum(float(a.get("valor") or 0) for a in ajustes if int(a.get("socio_id") or 0) == sid)
        saldo_final = quota + adj_sum
        linhas.append(
            {
                "socio_id": sid,
                "nome": s.get("nome"),
                "percentual": pct,
                "quota_resultado": quota,
                "ajustes": adj_sum,
                "saldo_final": saldo_final,
                "fonte_percentual": FONTE_MANUAL,
                "fonte_quota": FONTE_CALCULADO if socios else FONTE_PENDENTE,
                "fonte_ajustes": FONTE_MANUAL if adj_sum != 0 else FONTE_PENDENTE,
            }
        )

    total_ajustes = sum(float(a.get("valor") or 0) for a in ajustes)

    return {
        "linhas": linhas,
        "total_ajustes_socios": total_ajustes,
        "fonte": FONTE_CALCULADO if socios else FONTE_PENDENTE,
    }


def calcular_break_even(context: dict[str, Any]) -> dict[str, Any]:
    prem = context.get("premissas") or {}
    cf = calcular_custos_fixos(context)
    custo_fixo = float(cf["total_mensal"])
    if not cf["tem_cadastro"]:
        custo_fixo = _parse_float(prem.get("custo_fixo_mensal_manual"), custo_fixo)

    imp = _parse_float(prem.get("imposto_percentual"), 0.0) / 100.0
    cv = _parse_float(prem.get("custo_variavel_percentual"), 0.0) / 100.0
    denominador = 1.0 - cv - imp
    if denominador <= 0:
        ponto_eq: float | None = None
        msg = "Premissas levam a denominador ≤ 0; ajuste imposto/custo variável."
    else:
        ponto_eq = custo_fixo / denominador
        msg = ""

    meta = _parse_float(prem.get("ponto_equilibrio_meta"), 0.0)

    return {
        "custo_fixo_mensal": custo_fixo,
        "imposto_percentual": imp * 100.0,
        "custo_variavel_percentual": cv * 100.0,
        "ponto_equilibrio_receita": ponto_eq,
        "ponto_equilibrio_meta": meta if meta > 0 else None,
        "mensagem": msg,
        "fonte_custo_fixo": cf["fonte_total"],
        "fonte_calculo": FONTE_CALCULADO if (custo_fixo > 0 and denominador > 0) else FONTE_PENDENTE,
    }


def montar_relatorio_completo(
    periodo_inicio: str | None = None,
    periodo_fim: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Dict consolidado para a UI (chaves estáveis para testes)."""
    ctx = get_relatorio_context(periodo_inicio, periodo_fim, db_path)
    resumo = calcular_resumo_gerencial(ctx)
    obras = calcular_resultado_obras(ctx)
    socios = calcular_resultado_socios(ctx, resumo)
    break_even = calcular_break_even(ctx)

    total_inv = sum(float(i.get("valor") or 0) for i in (ctx.get("investimentos") or []))

    out: dict[str, Any] = {
        "contexto": ctx,
        "resumo": resumo,
        "obras": obras,
        "socios": socios,
        "custos_fixos": calcular_custos_fixos(ctx),
        "break_even": break_even,
        "total_investimentos": total_inv,
        "fonte_total_investimentos": FONTE_MANUAL if total_inv != 0 else FONTE_PENDENTE,
    }
    return out
