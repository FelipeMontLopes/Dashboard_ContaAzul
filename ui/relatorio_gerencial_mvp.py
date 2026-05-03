"""Relatório gerencial MVP — layout inspirado no PDF, fontes explícitas."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.kpi_service import formatar_moeda
from services.relatorio_gerencial_service import (
    FONTE_CALCULADO,
    FONTE_CONTA_AZUL,
    FONTE_MANUAL,
    FONTE_PENDENTE,
    FONTE_MOCK,
    montar_relatorio_completo,
)


def _cap_fonte(label: str) -> str:
    return f"Fonte: **{label}**"


def render_relatorio_gerencial_mvp() -> None:
    st.title("Relatório Gerencial MVP")
    st.caption(
        "Valores reais vêm de **Cadastro Manual** ou de integrações explicitamente indicadas. "
        "Sem dado confiável, exibimos **Pendente** — nada é inventado."
    )

    rep = montar_relatorio_completo()
    ctx = rep["contexto"]
    resumo = rep["resumo"]
    obras = rep["obras"]
    socios_bloco = rep["socios"]
    cf = rep["custos_fixos"]
    be = rep["break_even"]
    ca = ctx.get("conta_azul") or {}

    with st.expander("Integração Conta Azul (metadados)", expanded=False):
        if ca.get("disponivel"):
            st.success(_cap_fonte(FONTE_CONTA_AZUL))
            st.write(ca.get("mensagem"))
            for s in ca.get("snapshots") or []:
                st.caption(f"snapshot_id={s.get('snapshot_id')} — {s.get('resource_name')} — {s.get('fetched_at')}")
        else:
            st.warning(_cap_fonte(FONTE_PENDENTE))
            st.write(ca.get("mensagem"))

    tabs = st.tabs(
        [
            "Resumo Executivo",
            "Obras / Projetos",
            "Pagamentos e Custos",
            "Sócios",
            "Investimentos e Break-even",
            "Indicadores Patrimoniais",
            "Justificativas",
        ]
    )

    with tabs[0]:
        st.subheader("Resumo executivo")
        m1, m2, m3 = st.columns(3)
        m4, m5, m6 = st.columns(3)

        rr = resumo.get("receitas_realizadas")
        pend_rr = resumo.get("fonte_receitas_realizadas") == FONTE_PENDENTE and (rr is None or rr == 0)

        m1.metric(
            "Receitas realizadas",
            "Pendente" if pend_rr else formatar_moeda(rr),
            help=resumo.get("fonte_receitas_realizadas"),
        )
        m1.caption(_cap_fonte(resumo.get("fonte_receitas_realizadas", FONTE_PENDENTE)))

        ct = resumo.get("custos_totais")
        m2.metric("Custos totais", formatar_moeda(ct), help="Obras + custo fixo mensal")
        m2.caption(_cap_fonte(FONTE_CALCULADO))

        rl = resumo.get("resultado_liquido")
        m3.metric("Resultado líquido", formatar_moeda(rl))
        m3.caption(_cap_fonte(resumo.get("fonte_resultado", FONTE_CALCULADO)))

        ml = resumo.get("margem_liquida_pct")
        m4.metric(
            "Margem líquida",
            "Pendente" if ml is None else f"{ml:.2f}%",
            help=resumo.get("fonte_margem"),
        )
        m4.caption(_cap_fonte(resumo.get("fonte_margem", FONTE_PENDENTE)))

        rar = resumo.get("receitas_a_realizar")
        m5.metric("Receitas a realizar", formatar_moeda(rar))
        m5.caption(_cap_fonte(FONTE_MANUAL if rar and rar != 0 else FONTE_PENDENTE))

        cfm = resumo.get("custo_fixo_mensal")
        m6.metric(
            "Custo fixo mensal",
            formatar_moeda(cfm),
            help=resumo.get("fonte_custo_fixo"),
        )
        m6.caption(_cap_fonte(resumo.get("fonte_custo_fixo", FONTE_PENDENTE)))

        st.info(
            "Blocos vazios ou “Pendente” indicam ausência de cadastro ou normalização Conta Azul. "
            f"{_cap_fonte(FONTE_MOCK)} só aparece na estrutura da página quando não há série para gráfico."
        )

    with tabs[1]:
        st.subheader("Obras / projetos")
        linhas = obras.get("linhas") or []
        if not linhas:
            st.warning("Pendente — cadastre obras em **Cadastros Gerenciais**.")
        else:
            df = pd.DataFrame(linhas)
            show = df[
                [
                    "nome",
                    "receita_realizada",
                    "custo_realizado",
                    "saldo",
                    "margem_pct",
                    "status",
                ]
            ].copy()
            def _fmt_marg(x: object) -> str:
                if x is None:
                    return "—"
                if isinstance(x, float) and pd.isna(x):
                    return "—"
                try:
                    return f"{float(x):.2f}%"
                except (TypeError, ValueError):
                    return "—"

            show["margem_pct"] = show["margem_pct"].apply(_fmt_marg)
            for c in ("receita_realizada", "custo_realizado", "saldo"):
                show[c] = show[c].map(lambda x: formatar_moeda(x))
            st.dataframe(show, use_container_width=True)
            st.caption(_cap_fonte(FONTE_MANUAL))

        chart_df = pd.DataFrame(
            [{"obra": x["nome"], "saldo": x["saldo"]} for x in linhas if x.get("nome")]
        )
        if chart_df.empty:
            st.caption(f"{_cap_fonte(FONTE_PENDENTE)} — sem dados para gráfico.")
        else:
            pos = chart_df[chart_df["saldo"] > 0].sort_values("saldo", ascending=False).head(5)
            neg = chart_df[chart_df["saldo"] < 0].sort_values("saldo", ascending=True).head(5)
            gc1, gc2 = st.columns(2)
            with gc1:
                st.markdown("**Top obras (saldo positivo)**")
                if pos.empty:
                    st.caption("Nenhuma.")
                else:
                    st.bar_chart(pos.set_index("obra")["saldo"])
            with gc2:
                st.markdown("**Top obras (saldo negativo)**")
                if neg.empty:
                    st.caption("Nenhuma.")
                else:
                    st.bar_chart(neg.set_index("obra")["saldo"])

    with tabs[2]:
        st.subheader("Pagamentos e custos fixos")
        st.metric("Total mensal (custos fixos)", formatar_moeda(cf.get("total_mensal")))
        st.caption(_cap_fonte(cf.get("fonte_total", FONTE_PENDENTE)))

        por = cf.get("por_categoria") or {}
        if not por:
            st.warning("Pendente — cadastre custos fixos ou premissa de custo fixo mensal.")
        else:
            cdf = pd.DataFrame([{"categoria": k, "valor": v} for k, v in por.items()])
            st.bar_chart(cdf.set_index("categoria")["valor"])
            st.dataframe(
                cdf.assign(valor_fmt=cdf["valor"].map(formatar_moeda))[["categoria", "valor_fmt"]],
                use_container_width=True,
            )

    with tabs[3]:
        st.subheader("Sócios e distribuição")
        slin = socios_bloco.get("linhas") or []
        if not slin:
            st.info("Pendente — cadastre sócios e percentuais.")
        else:
            sdf = pd.DataFrame(slin)
            disp = sdf[
                ["nome", "percentual", "quota_resultado", "ajustes", "saldo_final"]
            ].copy()
            for col in ("quota_resultado", "ajustes", "saldo_final"):
                disp[col] = disp[col].map(formatar_moeda)
            st.dataframe(disp, use_container_width=True)
            st.caption(_cap_fonte(FONTE_CALCULADO) + " (quota) · " + _cap_fonte(FONTE_MANUAL) + " (ajustes quando houver)")

    with tabs[4]:
        st.subheader("Investimentos e break-even")
        i1, i2, i3 = st.columns(3)
        tinvest = rep.get("total_investimentos")
        i1.metric("Investimento total", formatar_moeda(tinvest))
        i1.caption(_cap_fonte(rep.get("fonte_total_investimentos", FONTE_PENDENTE)))

        pe = be.get("ponto_equilibrio_receita")
        i2.metric(
            "Ponto de equilíbrio (receita)",
            "Pendente" if pe is None else formatar_moeda(pe),
            help=be.get("mensagem"),
        )
        i2.caption(_cap_fonte(be.get("fonte_calculo", FONTE_PENDENTE)))

        i3.metric("Custo fixo mensal (BE)", formatar_moeda(be.get("custo_fixo_mensal")))
        i3.caption(_cap_fonte(be.get("fonte_custo_fixo", FONTE_PENDENTE)))

        st.write(
            f"Imposto (%): **{be.get('imposto_percentual', 0):.2f}** — "
            f"Custo variável (%): **{be.get('custo_variavel_percentual', 0):.2f}** "
            f"(premissas — {_cap_fonte(FONTE_MANUAL)})"
        )
        meta = be.get("ponto_equilibrio_meta")
        if meta:
            st.caption(f"Meta declarada de break-even: {formatar_moeda(meta)}")

    with tabs[5]:
        st.subheader("Indicadores patrimoniais")
        inds = ctx.get("indicadores") or []
        if not inds:
            st.warning("Pendente — cadastre indicadores em **Cadastros Gerenciais**.")
        else:
            cols = st.columns(min(4, max(1, len(inds))))
            for i, row in enumerate(inds):
                with cols[i % len(cols)]:
                    st.metric(row.get("nome", "—"), formatar_moeda(row.get("valor")))
                    st.caption(_cap_fonte(FONTE_MANUAL))

    with tabs[6]:
        st.subheader("Justificativas")
        just = ctx.get("justificativas") or []
        if not just:
            st.info("Pendente — nenhum texto cadastrado.")
        for j in just:
            st.markdown(f"#### {j.get('titulo')}")
            st.write(j.get("texto") or "")
            st.caption(_cap_fonte(FONTE_MANUAL) + f" · ref: {j.get('data_referencia') or '—'}")
