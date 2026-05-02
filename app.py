import streamlit as st

from oauth_callback_handler import handle_oauth_callback
from ui.sidebar import selecionar_pagina
from ui.resumo import render_resumo
from ui.contas_receber import render_contas_receber
from ui.contas_pagar import render_contas_pagar
from ui.fluxo_caixa import render_fluxo_caixa
from ui.configuracoes import render_configuracoes


def main() -> None:
    st.set_page_config(page_title="Conta Azul Dashboard", layout="wide")

    callback_result = handle_oauth_callback()
    if callback_result.get("handled"):
        st.session_state["oauth_callback_result"] = callback_result
        try:
            st.query_params.clear()
        except Exception:
            pass

        if callback_result.get("success"):
            st.success(callback_result["message"])
        else:
            st.error(callback_result["message"])

    pagina = selecionar_pagina()

    if pagina == "Resumo Executivo":
        render_resumo()
    elif pagina == "Contas a Receber":
        render_contas_receber()
    elif pagina == "Contas a Pagar":
        render_contas_pagar()
    elif pagina == "Fluxo de Caixa":
        render_fluxo_caixa()
    else:
        render_configuracoes()


if __name__ == "__main__":
    main()
