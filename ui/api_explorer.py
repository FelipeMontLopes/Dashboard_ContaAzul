"""Página Streamlit — explorador de endpoints da API Conta Azul."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from services.api_explorer_service import (
    call_api_endpoint,
    summarize_response_shape,
    test_default_endpoints,
)
from services.api_snapshot_store import (
    get_snapshot_by_id,
    init_snapshot_db,
    list_api_snapshots,
)


def render_api_explorer() -> None:
    init_snapshot_db()
    st.title("Explorador da API Conta Azul")
    st.warning(
        "Ferramenta de **diagnóstico** para endpoints reais da API. "
        "Os resultados são snapshots brutos (sanitizados); não há normalização para telas finais."
    )

    if st.button("Testar endpoints padrão", type="primary"):
        with st.spinner("Chamando endpoints…"):
            results = test_default_endpoints()
        st.session_state["api_explorer_last_batch"] = results

    batch = st.session_state.get("api_explorer_last_batch")
    if batch:
        rows = []
        for r in batch:
            rows.append(
                {
                    "resource_name": r["resource_name"],
                    "method": r["method"],
                    "path": r["path"],
                    "success": r["success"],
                    "status_code": r.get("status_code"),
                    "error_message": r.get("error_message") or "",
                }
            )
        st.subheader("Resultado — endpoints padrão")
        st.dataframe(rows, use_container_width=True, hide_index=True)

        for i, r in enumerate(batch):
            title = f"{r['resource_name']} ({'ok' if r['success'] else 'erro'})"
            with st.expander(title, expanded=False):
                st.json(r.get("response_shape") or {})
                if r["success"] and r.get("data") is not None:
                    st.markdown("**JSON sanitizado**")
                    st.json(r["data"])
                elif r.get("error_message"):
                    st.error(r["error_message"])

    st.divider()
    st.subheader("Teste manual (GET)")
    col_a, col_b = st.columns(2)
    with col_a:
        manual_name = st.text_input("resource_name", value="custom", key="ae_res_name")
        manual_path = st.text_input("path", value="/v1/pessoas", key="ae_path")
    with col_b:
        params_raw = st.text_area(
            "params_json (opcional, objeto JSON)",
            value="{}",
            height=100,
            key="ae_params",
        )

    if st.button("Executar GET", key="ae_run_manual"):
        err: str | None = None
        if not manual_path.strip().startswith("/"):
            err = "Path deve começar com /"
            st.session_state["api_explorer_manual_result"] = None
            st.session_state["api_explorer_manual_err"] = err
        else:
            try:
                pdict = json.loads(params_raw or "{}")
                if not isinstance(pdict, dict):
                    err = "params_json deve ser um objeto JSON (dicionário)."
                else:
                    st.session_state["api_explorer_manual_err"] = None
                    with st.spinner("Executando…"):
                        res = call_api_endpoint(
                            manual_name.strip() or "custom",
                            "GET",
                            manual_path.strip(),
                            pdict,
                            save_snapshot=True,
                        )
                    st.session_state["api_explorer_manual_result"] = res
            except json.JSONDecodeError:
                st.session_state["api_explorer_manual_result"] = None
                st.session_state["api_explorer_manual_err"] = "JSON inválido em params_json."
        if err:
            st.error(err)

    man_err = st.session_state.get("api_explorer_manual_err")
    if man_err:
        st.error(man_err)

    man = st.session_state.get("api_explorer_manual_result")
    if man:
        st.json(
            {
                "success": man["success"],
                "status_code": man.get("status_code"),
                "response_shape": man.get("response_shape"),
                "error_message": man.get("error_message"),
            }
        )
        if man.get("success") and man.get("data") is not None:
            st.json(man["data"])

    st.divider()
    st.subheader("Snapshots recentes")
    snaps = list_api_snapshots(limit=100)
    names = sorted({s["resource_name"] for s in snaps})
    filt = st.selectbox(
        "Filtrar por resource_name",
        options=["(todos)"] + names,
        key="ae_snap_filter",
    )
    lim = 20
    if filt == "(todos)":
        shown = list_api_snapshots(limit=lim)
    else:
        shown = list_api_snapshots(limit=lim, resource_name=filt)

    if not shown:
        st.caption("Nenhum snapshot ainda.")
    else:
        opt_labels = [
            f"{s['id']} · {s['resource_name']} · {s['path']} · "
            f"{'ok' if s['success'] else 'erro'} · {s['fetched_at']}"
            for s in shown
        ]
        label_to_id = {opt_labels[i]: shown[i]["id"] for i in range(len(shown))}
        choice = st.selectbox("Selecionar snapshot", options=opt_labels, key="ae_pick_snap")
        tbl = [
            {
                "id": s["id"],
                "resource_name": s["resource_name"],
                "path": s["path"],
                "success": bool(s["success"]),
                "status_code": s["status_code"],
                "fetched_at": s["fetched_at"],
            }
            for s in shown[:lim]
        ]
        st.dataframe(tbl, use_container_width=True, hide_index=True)

        sid = label_to_id.get(choice)
        if sid is not None:
            row = get_snapshot_by_id(int(sid))
            if row and row.get("response_json"):
                try:
                    parsed: Any = json.loads(row["response_json"])
                    st.markdown("**Shape (recomputado)**")
                    st.json(summarize_response_shape(parsed))
                    st.markdown("**response_json (sanitizado armazenado)**")
                    st.json(parsed)
                except json.JSONDecodeError:
                    st.text(row["response_json"])
