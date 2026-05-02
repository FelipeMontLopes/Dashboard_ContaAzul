import streamlit as st

from services.kpi_service import (
    calcular_resumo_executivo,
    formatar_moeda,
    montar_tabela_fluxo_resumo,
)
from services.mock_data import (
    get_mock_contas_pagar,
    get_mock_contas_receber,
    get_mock_fluxo_caixa,
)


def render_resumo() -> None:
    st.title("Resumo Executivo")

    contas_receber = get_mock_contas_receber()
    contas_pagar = get_mock_contas_pagar()
    fluxo = get_mock_fluxo_caixa()

    kpi = calcular_resumo_executivo(contas_receber, contas_pagar, fluxo)

    c1, c2, c3 = st.columns(3)
    c4, c5, c6 = st.columns(3)

    c1.metric("A receber em aberto", formatar_moeda(kpi["total_receber_aberto"]))
    c2.metric("A pagar em aberto", formatar_moeda(kpi["total_pagar_aberto"]))
    c3.metric("Recebíveis vencidos", formatar_moeda(kpi["total_receber_vencido"]))
    c4.metric("Pagamentos vencidos", formatar_moeda(kpi["total_pagar_vencido"]))
    c5.metric("Saldo 7 dias", formatar_moeda(kpi["saldo_7_dias"]))
    c6.metric("Saldo 30 dias", formatar_moeda(kpi["saldo_30_dias"]))

    if kpi["total_receber_vencido"] > 0:
        st.warning("Existem recebíveis vencidos.")
    if kpi["total_pagar_vencido"] > 0:
        st.error("Existem pagamentos vencidos.")
    if kpi["saldo_30_dias"] < 0:
        st.error("Saldo projetado de 30 dias negativo.")

    st.subheader("Fluxo de caixa (projeção simplificada)")
    tb = montar_tabela_fluxo_resumo(fluxo)
    display = tb.copy()
    for col in ("entradas", "saidas", "saldo_dia", "saldo_acumulado"):
        if col in display.columns:
            display[col] = display[col].map(formatar_moeda)
    st.dataframe(display, use_container_width=True)
