import streamlit as st

from services.mock_data import get_mock_fluxo_caixa


def render_fluxo_caixa() -> None:
    st.title("Fluxo de Caixa")
    df_fluxo = get_mock_fluxo_caixa()

    st.dataframe(df_fluxo, use_container_width=True)
    st.subheader("Evolução do Saldo")
    col_saldo = "saldo_acumulado" if "saldo_acumulado" in df_fluxo.columns else "saldo"
    st.line_chart(df_fluxo.set_index("data")[col_saldo])
