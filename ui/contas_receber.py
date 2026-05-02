import streamlit as st

from services.mock_data import get_mock_contas_receber


def render_contas_receber() -> None:
    st.title("Contas a Receber")
    st.dataframe(get_mock_contas_receber(), use_container_width=True)
