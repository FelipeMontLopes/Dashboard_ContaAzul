"""Cadastros manuais para o relatório gerencial MVP."""

from __future__ import annotations

import streamlit as st

from services import gerencial_store as gs


def render_cadastros_gerenciais() -> None:
    st.title("Cadastros Gerenciais")
    st.caption(
        "Dados cadastrados aqui alimentam o Relatório Gerencial MVP com fonte **Cadastro Manual**. "
        "Nada é inventado automaticamente."
    )

    gs.init_gerencial_db()
    gs.seed_premissas_padrao()

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
        [
            "Sócios",
            "Obras / Projetos",
            "Custos Fixos",
            "Investimentos",
            "Premissas",
            "Indicadores Patrimoniais",
            "Justificativas",
            "Mapeamentos Conta Azul",
        ]
    )

    with tab1:
        _tab_socios()
    with tab2:
        _tab_obras()
    with tab3:
        _tab_custos()
    with tab4:
        _tab_investimentos()
    with tab5:
        _tab_premissas()
    with tab6:
        _tab_indicadores()
    with tab7:
        _tab_justificativas()
    with tab8:
        _tab_mapeamentos()


def _tab_socios() -> None:
    st.subheader("Sócios")
    with st.form("novo_socio"):
        n1, n2, n3 = st.columns(3)
        nome = n1.text_input("Nome")
        papel = n2.text_input("Papel")
        pct = n3.number_input("% participação", min_value=0.0, max_value=100.0, value=0.0)
        sub = st.form_submit_button("Cadastrar")
        if sub:
            try:
                if not nome.strip():
                    st.error("Informe o nome.")
                else:
                    gs.create_socio(nome=nome, papel=papel or None, percentual_participacao=pct)
                    st.success("Sócio cadastrado.")
                    st.rerun()
            except Exception as e:
                st.error(str(e))

    rows = gs.list_socios()
    if rows:
        with st.expander("Ajustes de sócio (antecipação, investimento, etc.)"):
            adj_rows = gs.list_socio_ajustes()
            aj_map = {s["id"]: s["nome"] for s in rows}
            with st.form("novo_ajuste"):
                sid = st.selectbox("Sócio", list(aj_map.keys()), format_func=lambda x: aj_map.get(x, str(x)))
                tipo = st.selectbox(
                    "Tipo",
                    ["antecipacao_lucro", "investimento", "ajuste_manual", "retirada", "outro"],
                )
                val = st.number_input("Valor", format="%.2f")
                desc = st.text_input("Descrição")
                dta = st.text_input("Data")
                if st.form_submit_button("Registrar ajuste"):
                    try:
                        gs.create_socio_ajuste(
                            socio_id=int(sid),
                            tipo=tipo,
                            valor=val,
                            descricao=desc or None,
                            data=dta or None,
                        )
                        st.success("Ajuste registrado.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            if adj_rows:
                for a in adj_rows:
                    ac1, ac2 = st.columns([4, 1])
                    with ac1:
                        st.caption(
                            f"Sócio {a.get('socio_id')} — {a.get('tipo')} — R$ {a.get('valor'):,.2f}"
                        )
                    with ac2:
                        if st.button("Excluir", key=f"del_adj_{a['id']}"):
                            try:
                                gs.delete_socio_ajuste(int(a["id"]))
                                st.success("Removido.")
                                st.rerun()
                            except Exception as ex:
                                st.error(str(ex))

    if not rows:
        st.info("Nenhum sócio cadastrado.")
        return
    for r in rows:
        c1, c2 = st.columns([4, 1])
        with c1:
            ativo = "sim" if r.get("ativo") else "não"
            st.write(
                f"**{r.get('nome')}** — {r.get('papel') or '—'} — "
                f"{r.get('percentual_participacao')}% — ativo: {ativo}"
            )
        with c2:
            if st.button("Excluir", key=f"del_socio_{r['id']}"):
                try:
                    gs.delete_socio(int(r["id"]))
                    st.success("Removido.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


def _tab_obras() -> None:
    st.subheader("Obras / projetos (manual)")
    with st.form("nova_obra"):
        o1, o2 = st.columns(2)
        nome = o1.text_input("Nome da obra/projeto")
        cliente = o2.text_input("Cliente")
        r1, r2, r3 = st.columns(3)
        rr = r1.number_input("Receita realizada", value=0.0, format="%.2f")
        cr = r2.number_input("Custo realizado", value=0.0, format="%.2f")
        rar = r3.number_input("Receita a realizar", value=0.0, format="%.2f")
        st4, st5 = st.columns(2)
        status = st4.text_input("Status")
        obs = st5.text_input("Observação")
        sub = st.form_submit_button("Cadastrar")
        if sub:
            try:
                if not nome.strip():
                    st.error("Informe o nome.")
                else:
                    gs.create_obra_manual(
                        nome=nome,
                        cliente=cliente or None,
                        receita_realizada_manual=rr,
                        custo_realizado_manual=cr,
                        receita_a_realizar_manual=rar,
                        status=status or None,
                        observacao=obs or None,
                    )
                    st.success("Obra cadastrada.")
                    st.rerun()
            except Exception as e:
                st.error(str(e))

    rows = gs.list_obras_manuais()
    if not rows:
        st.info("Nenhuma obra cadastrada.")
        return
    for r in rows:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.write(
                f"**{r.get('nome')}** ({r.get('cliente') or '—'}) — "
                f"R realizada {r.get('receita_realizada_manual')} | "
                f"C realizado {r.get('custo_realizado_manual')} | "
                f"A realizar {r.get('receita_a_realizar_manual')}"
            )
        with c2:
            if st.button("Excluir", key=f"del_obra_{r['id']}"):
                try:
                    gs.delete_obra_manual(int(r["id"]))
                    st.success("Removido.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


def _tab_custos() -> None:
    st.subheader("Custos fixos")
    with st.form("novo_custo"):
        n1, n2 = st.columns(2)
        nome = n1.text_input("Nome")
        cat = n2.selectbox(
            "Categoria",
            ["diretoria", "obras", "administrativo", "aluguel", "operacional", "outros"],
        )
        c1, c2 = st.columns(2)
        cargo = c1.text_input("Cargo/função")
        vm = c2.number_input("Valor mensal", min_value=0.0, value=0.0, format="%.2f")
        obs = st.text_input("Observação")
        sub = st.form_submit_button("Cadastrar")
        if sub:
            try:
                if not nome.strip():
                    st.error("Informe o nome.")
                else:
                    gs.create_custo_fixo(
                        nome=nome,
                        valor_mensal=vm,
                        categoria=cat,
                        cargo_funcao=cargo or None,
                        observacao=obs or None,
                    )
                    st.success("Custo cadastrado.")
                    st.rerun()
            except Exception as e:
                st.error(str(e))

    rows = gs.list_custos_fixos()
    if not rows:
        st.info("Nenhum custo fixo cadastrado.")
        return
    for r in rows:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.write(
                f"**{r.get('nome')}** — {r.get('categoria')} — "
                f"R$ {r.get('valor_mensal'):,.2f}/mês"
            )
        with c2:
            if st.button("Excluir", key=f"del_cf_{r['id']}"):
                try:
                    gs.delete_custo_fixo(int(r["id"]))
                    st.success("Removido.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


def _tab_investimentos() -> None:
    st.subheader("Investimentos")
    socios = gs.list_socios(apenas_ativos=True)
    opts = {s["nome"]: s["id"] for s in socios}
    with st.form("novo_inv"):
        desc = st.text_input("Descrição")
        val = st.number_input("Valor", format="%.2f")
        data = st.text_input("Data (YYYY-MM-DD ou vazio)")
        cat = st.text_input("Categoria")
        sid_label = st.selectbox("Sócio (opcional)", ["—"] + list(opts.keys()))
        sub = st.form_submit_button("Cadastrar")
        if sub:
            try:
                if not desc.strip():
                    st.error("Informe a descrição.")
                else:
                    sid = None if sid_label == "—" else int(opts[sid_label])
                    gs.create_investimento(
                        descricao=desc,
                        valor=val,
                        socio_id=sid,
                        data=data or None,
                        categoria=cat or None,
                    )
                    st.success("Investimento cadastrado.")
                    st.rerun()
            except Exception as e:
                st.error(str(e))

    rows = gs.list_investimentos()
    if not rows:
        st.info("Nenhum investimento cadastrado.")
        return
    for r in rows:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.write(f"**{r.get('descricao')}** — R$ {r.get('valor'):,.2f} — sócio_id {r.get('socio_id')}")
        with c2:
            if st.button("Excluir", key=f"del_inv_{r['id']}"):
                try:
                    gs.delete_investimento(int(r["id"]))
                    st.success("Removido.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


def _tab_premissas() -> None:
    st.subheader("Premissas")
    prem = gs.list_premissas()
    keys = [
        "imposto_percentual",
        "custo_variavel_percentual",
        "ponto_equilibrio_meta",
        "margem_alvo",
        "custo_fixo_mensal_manual",
    ]
    with st.form("salvar_premissas"):
        vals = {}
        for k in keys:
            vals[k] = st.text_input(k.replace("_", " "), value=str(prem.get(k) or ""))
        if st.form_submit_button("Salvar premissas"):
            try:
                for k, v in vals.items():
                    gs.set_premissa(k, v.strip() or None)
                st.success("Premissas salvas.")
                st.rerun()
            except Exception as e:
                st.error(str(e))


def _tab_indicadores() -> None:
    st.subheader("Indicadores patrimoniais")
    with st.form("novo_ind"):
        nome = st.text_input("Nome")
        valor = st.number_input("Valor", format="%.2f")
        desc = st.text_input("Descrição")
        dref = st.text_input("Data referência")
        sub = st.form_submit_button("Cadastrar")
        if sub:
            try:
                if not nome.strip():
                    st.error("Informe o nome.")
                else:
                    gs.create_indicador(nome=nome, valor=valor, descricao=desc or None, data_referencia=dref or None)
                    st.success("Indicador cadastrado.")
                    st.rerun()
            except Exception as e:
                st.error(str(e))

    rows = gs.list_indicadores()
    if not rows:
        st.info("Nenhum indicador cadastrado.")
        return
    for r in rows:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.write(f"**{r.get('nome')}** — R$ {r.get('valor'):,.2f}")
        with c2:
            if st.button("Excluir", key=f"del_ind_{r['id']}"):
                try:
                    gs.delete_indicador(int(r["id"]))
                    st.success("Removido.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


def _tab_justificativas() -> None:
    st.subheader("Justificativas")
    with st.form("nova_just"):
        tit = st.text_input("Título")
        texto = st.text_area("Texto")
        cat = st.text_input("Categoria")
        dref = st.text_input("Data referência")
        sub = st.form_submit_button("Cadastrar")
        if sub:
            try:
                if not tit.strip():
                    st.error("Informe o título.")
                else:
                    gs.create_justificativa(
                        titulo=tit,
                        texto=texto or None,
                        categoria=cat or None,
                        data_referencia=dref or None,
                    )
                    st.success("Justificativa cadastrada.")
                    st.rerun()
            except Exception as e:
                st.error(str(e))

    rows = gs.list_justificativas()
    if not rows:
        st.info("Nenhuma justificativa cadastrada.")
        return
    for r in rows:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{r.get('titulo')}**  \n{r.get('texto') or ''}")
        with c2:
            if st.button("Excluir", key=f"del_just_{r['id']}"):
                try:
                    gs.delete_justificativa(int(r["id"]))
                    st.success("Removido.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


def _tab_mapeamentos() -> None:
    st.subheader("Mapeamentos Conta Azul → relatório")
    st.caption("Registros auxiliares para futura normalização; não alteram KPIs sozinhos.")
    with st.form("novo_map"):
        tipo = st.selectbox(
            "Tipo",
            [
                "categoria_para_grupo",
                "cliente_para_obra",
                "projeto_para_obra",
                "fornecedor_para_categoria",
            ],
        )
        vo = st.text_input("Valor origem (Conta Azul)")
        vd = st.text_input("Valor destino (gerencial)")
        obs = st.text_input("Observação")
        sub = st.form_submit_button("Cadastrar")
        if sub:
            try:
                if not vo.strip() or not vd.strip():
                    st.error("Preencha origem e destino.")
                else:
                    gs.create_mapeamento(tipo=tipo, valor_origem=vo, valor_destino=vd, observacao=obs or None)
                    st.success("Mapeamento cadastrado.")
                    st.rerun()
            except Exception as e:
                st.error(str(e))

    rows = gs.list_mapeamentos()
    if not rows:
        st.info("Nenhum mapeamento cadastrado.")
        return
    for r in rows:
        c1, c2 = st.columns([4, 1])
        with c1:
            st.write(f"{r.get('tipo')}: **{r.get('valor_origem')}** → **{r.get('valor_destino')}**")
        with c2:
            if st.button("Excluir", key=f"del_map_{r['id']}"):
                try:
                    gs.delete_mapeamento(int(r["id"]))
                    st.success("Removido.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
