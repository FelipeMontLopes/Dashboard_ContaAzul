import streamlit as st


def selecionar_pagina() -> str:
    st.sidebar.title("Conta Azul Dashboard")
    return st.sidebar.radio(
        "Navegação",
        [
            "Resumo Executivo",
            "Contas a Receber",
            "Contas a Pagar",
            "Fluxo de Caixa",
            "Explorador da API",
            "Contratos de Dados",
            "Configurações",
        ],
    )
