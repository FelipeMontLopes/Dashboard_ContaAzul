"""Página — análise de contratos a partir de snapshots reais."""

from __future__ import annotations

import streamlit as st

from services.data_contract_service import infer_contract_from_snapshot, infer_latest_contract
from services.financial_candidate_mapper import suggest_financial_fields
from services.api_snapshot_store import init_snapshot_db, list_api_snapshots


def render_data_contracts() -> None:
    init_snapshot_db()
    st.title("Contratos de Dados Reais")
    st.info(
        "Análise dos **snapshots** já coletados pelo Explorador da API. "
        "Objetivo: entender estrutura e candidatos a campos **antes** da normalização e das telas finais."
    )

    snaps = list_api_snapshots(limit=300)
    if not snaps:
        st.warning("Nenhum snapshot no banco local. Use **Explorador da API** em produção primeiro.")
        return

    names = sorted({s["resource_name"] for s in snaps}, key=str.lower)
    res_pick = st.selectbox("resource_name (último snapshot)", options=names, key="dc_res")

    if st.button("Analisar último snapshot", type="primary", key="dc_last"):
        with st.spinner("Inferindo contrato…"):
            result = infer_latest_contract(res_pick)
        st.session_state["dc_result"] = result

    st.divider()
    st.subheader("Selecionar snapshot por ID")
    labels = [f"{s['id']} · {s['resource_name']} · {s['path']} · {s['fetched_at']}" for s in snaps[:80]]
    id_by_label = {labels[i]: int(snaps[i]["id"]) for i in range(len(labels))}
    choice = st.selectbox("Snapshots recentes", options=labels, key="dc_pick_snap")
    if st.button("Analisar snapshot selecionado", key="dc_by_id"):
        sid = id_by_label.get(choice)
        if sid is not None:
            with st.spinner("Inferindo contrato…"):
                st.session_state["dc_result"] = infer_contract_from_snapshot(sid)

    result = st.session_state.get("dc_result")
    if not result:
        return

    if result.get("error"):
        st.error(result["error"])
        return

    c = result.get("contract")
    if not c:
        st.warning("Sem contrato inferido.")
        return

    st.subheader("Metadados do snapshot")
    st.write(f"- **resource_name:** `{result.get('resource_name')}`")
    st.write(f"- **path:** `{result.get('path')}`")
    st.write(f"- **fetched_at:** `{result.get('fetched_at')}`")

    st.subheader("Contrato inferido")
    st.write(f"- **root_type:** `{c.get('root_type')}`")
    st.write(f"- **total_items:** {c.get('total_items')}")
    st.write("**Chaves principais (top_level / agregadas):**")
    keys = c.get("top_level_keys") or []
    st.code(", ".join(keys) if keys else "(nenhuma)", language=None)
    st.write("**Tipos por chave (amostra):**")
    st.json(c.get("key_types") or {})
    st.write("**Candidatos — data:**", ", ".join(c.get("candidate_date_fields") or []) or "—")
    st.write("**Candidatos — valor:**", ", ".join(c.get("candidate_money_fields") or []) or "—")
    st.write("**Candidatos — status:**", ", ".join(c.get("candidate_status_fields") or []) or "—")
    st.write("**Candidatos — id:**", ", ".join(c.get("candidate_id_fields") or []) or "—")
    st.write(
        "**Candidatos — nome/descrição:**",
        ", ".join(c.get("candidate_name_description_fields") or []) or "—",
    )
    if c.get("nested_hints"):
        st.write("**Aninhamento (1º nível):**")
        st.json(c["nested_hints"])

    ex = c.get("safe_examples") or []
    if ex:
        st.subheader("Exemplos sanitizados")
        for i, block in enumerate(ex):
            with st.expander(f"Exemplo {i + 1}", expanded=(i == 0)):
                st.json(block)

    st.divider()
    st.subheader("Sugestão de mapeamento financeiro")
    suggestions = suggest_financial_fields(c)
    for role, items in suggestions.items():
        st.markdown(f"**{role}**")
        if not items:
            st.caption("— nenhum candidato —")
        else:
            st.dataframe(items, use_container_width=True, hide_index=True)
