import streamlit as st

from services.mock_data import get_mock_contas_pagar


def render_contas_pagar() -> None:
    st.title("Contas a Pagar")
    st.dataframe(get_mock_contas_pagar(), use_container_width=True)
