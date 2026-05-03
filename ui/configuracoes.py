import os
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from app_paths import get_oauth_state_db_path, get_token_db_path
from app_settings_store import init_settings_db
from auth_client_factory import AuthClientError, get_authenticated_client
from config import get_settings
from oauth_readiness import get_oauth_readiness
from services.oauth_identity_service import mask_client_id
from oauth_service import build_authorization_url, generate_state
from oauth_state_store import clear_state, init_oauth_state_db, save_state
from redirect_uri_service import (
    clear_redirect_uri_override,
    get_effective_redirect_uri,
    get_env_redirect_uri,
    get_saved_redirect_uri,
    save_redirect_uri_override,
    validate_redirect_uri_format,
)
from services.connected_company_service import (
    fetch_conta_conectada_live,
    metadata_matches_live,
    refresh_connected_company_metadata,
)
from services.diagnostico_api_service import call_diagnostic_endpoint
from token_store import clear_tokens, get_connection_status, init_token_db, load_tokens

SCOPE_PADRAO = "openid profile aws.cognito.signin.user.admin"


def _status(value: str) -> str:
    return "configurado" if value else "não configurado"


def _formatar_expira(expires_at: str | None) -> str:
    if not expires_at:
        return "não informado"
    try:
        dt = expires_at.replace("Z", "+00:00")
        d = datetime.fromisoformat(dt)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.strftime("%d/%m/%Y %H:%M UTC")
    except (ValueError, TypeError):
        return "não informado"


def render_configuracoes() -> None:
    init_token_db()
    init_oauth_state_db()
    init_settings_db()

    if st.session_state.pop("auth_client_test_success", False):
        st.success("Cliente autenticado criado com sucesso.")
    auth_test_error = st.session_state.pop("auth_client_test_error", None)
    if auth_test_error:
        st.error(auth_test_error)
    oauth_connect_err = st.session_state.pop("oauth_connect_error", None)
    if oauth_connect_err:
        st.error(oauth_connect_err)
    if st.session_state.pop("config_meta_updated_flash", False):
        st.success("Metadata da empresa conectada atualizada com dados da API ao vivo.")

    settings = get_settings()

    scope_efetivo = settings.CONTA_AZUL_SCOPE.strip() or SCOPE_PADRAO
    diagnostic_path = settings.CONTA_AZUL_DIAGNOSTIC_PATH.strip() or "/v1/pessoas/conta-conectada"

    effective_redirect = get_effective_redirect_uri()
    vr_redirect = validate_redirect_uri_format(effective_redirect)
    token_db_abs = str(Path(get_token_db_path()).resolve())
    oauth_state_db_abs = str(Path(get_oauth_state_db_path()).resolve())
    conn = get_connection_status()
    oauth_readiness = get_oauth_readiness(
        settings, effective_redirect, vr_redirect, db_path=token_db_abs
    )
    oauth_ready = oauth_readiness["ready"]
    token_binding = oauth_readiness.get("oauth_token_binding") or {}

    ocr = st.session_state.get("oauth_callback_result")
    if ocr and ocr.get("handled"):
        with st.expander("Último callback OAuth (resumo)", expanded=False):
            ts = ocr.get("token_saved")
            ts_txt = "sim" if ts is True else ("não" if ts is False else "—")
            st.caption(
                f"Status: `{ocr.get('status')}` · sucesso: `{ocr.get('success')}` · "
                f"tokens gravados: `{ts_txt}` · DB: `{ocr.get('token_db_path') or token_db_abs}` "
                "— detalhe exibido no topo da aplicação após o retorno."
            )

    st.title("Configurações")

    st.subheader("URL de Redirecionamento OAuth")

    env_redirect_display = get_env_redirect_uri() or "não configurada"
    saved_redirect_display = get_saved_redirect_uri() or "não configurada"
    st.write(f"- **URL no .env (`CONTA_AZUL_REDIRECT_URI`):** `{env_redirect_display}`")
    st.write(f"- **URL salva na aplicação:** `{saved_redirect_display}`")

    st.markdown("**URL efetiva que será usada (copie para o Portal da Conta Azul):**")
    st.code(effective_redirect if effective_redirect else "(vazio)", language=None)

    if vr_redirect.get("is_placeholder"):
        st.warning(
            "**Esta URL parece ser apenas um exemplo.** Para testar localmente:\n\n"
            "1. Rode no terminal: `ngrok http 8501`\n"
            "2. Copie a URL HTTPS gerada pelo ngrok.\n"
            "3. Cole no campo **URL pública de redirecionamento**.\n"
            "4. Clique em **Salvar URL pública**.\n"
            "5. Copie a **URL efetiva** exibida aqui para o Portal da Conta Azul.\n"
            "6. A URL no Portal e no app precisam ser **idênticas**, inclusive barra final."
        )
        st.code("ngrok http 8501", language="bash")
        st.caption("Exemplo de URL real de túnel (formato típico):")
        st.code("https://a1b2c3d4.ngrok-free.app/", language=None)

    if vr_redirect["errors"]:
        for e in vr_redirect["errors"]:
            st.error(e)
    elif vr_redirect["warnings"]:
        for w in vr_redirect["warnings"]:
            st.warning(w)
        st.info("Formato da URL efetiva aceito, com os avisos acima.")
    else:
        st.success("URL efetiva com formato válido.")

    st.info(
        "Copie **exatamente** a URL efetiva acima para o campo **URL de redirecionamento** no Portal da Conta Azul."
    )

    redirect_input = st.text_input(
        "URL pública de redirecionamento",
        value=get_saved_redirect_uri(),
        placeholder="Cole a URL HTTPS pública (ex.: saída do ngrok)",
    )
    rs1, rs2 = st.columns(2)
    with rs1:
        if st.button("Salvar URL pública"):
            try:
                save_redirect_uri_override(redirect_input)
                st.success("URL pública salva.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    with rs2:
        if st.button("Limpar URL salva e usar .env"):
            clear_redirect_uri_override()
            st.success("URL salva removida. A aplicação usará `CONTA_AZUL_REDIRECT_URI` do .env, se existir.")
            st.rerun()

    st.divider()
    st.write("**Variáveis de ambiente (sem exibir segredos):**")
    st.write(f"- CONTA_AZUL_CLIENT_ID: {_status(settings.CONTA_AZUL_CLIENT_ID)}")
    st.write(f"- CONTA_AZUL_CLIENT_SECRET: {_status(settings.CONTA_AZUL_CLIENT_SECRET)}")
    st.write(f"- CONTA_AZUL_REDIRECT_URI: {settings.CONTA_AZUL_REDIRECT_URI or '(vazio)'}")
    st.write(f"- CONTA_AZUL_AUTH_URL: {settings.CONTA_AZUL_AUTH_URL or '(vazio)'}")
    st.write(f"- CONTA_AZUL_TOKEN_URL: {settings.CONTA_AZUL_TOKEN_URL or '(vazio)'}")
    st.write(f"- CONTA_AZUL_API_BASE_URL: {_status(settings.CONTA_AZUL_API_BASE_URL)}")
    st.write(f"- CONTA_AZUL_SCOPE: {scope_efetivo}")

    st.info(
        "Alterou secrets no Streamlit Cloud? Reinicie o app (Manage app → Reboot app) "
        "antes de reconectar — o processo em execução pode ainda estar com credenciais antigas."
    )

    st.divider()
    st.subheader("Conexão Conta Azul")

    st.info(
        "**Client ID** identifica a **aplicação OAuth** cadastrada no portal, não a empresa. "
        "A **empresa conectada** depende do **usuário/conta** que você autoriza no login da Conta Azul."
    )
    st.warning(
        "Se a empresa exibida estiver incorreta, use **Reconectar Conta Azul / Trocar cliente** e "
        "autorize com o usuário da empresa certa. Se o navegador reaproveitar sessão antiga, "
        "tente uma **aba anônima/privada** ao abrir o link de autorização."
    )

    _auth_u = settings.CONTA_AZUL_AUTH_URL.strip()
    _tok_u = settings.CONTA_AZUL_TOKEN_URL.strip()
    _api_u = settings.CONTA_AZUL_API_BASE_URL.strip()
    _scope_cfg = "configurado" if settings.CONTA_AZUL_SCOPE.strip() else "usando padrão"

    _motivo_bloqueio = "—"
    if vr_redirect.get("is_placeholder"):
        _motivo_bloqueio = (
            "URL de redirecionamento parece ser placeholder; configure a URL pública real."
        )
    elif not vr_redirect.get("valid") and vr_redirect.get("errors"):
        _motivo_bloqueio = str(vr_redirect["errors"][0])
    elif not oauth_ready and oauth_readiness.get("missing"):
        _motivo_bloqueio = str(oauth_readiness["missing"][0])

    with st.expander("Diagnóstico OAuth (seguro)", expanded=not oauth_ready):
        st.write(f"- **Client ID:** {_status(settings.CONTA_AZUL_CLIENT_ID)}")
        st.write(f"- **Client Secret:** {_status(settings.CONTA_AZUL_CLIENT_SECRET)}")
        st.write(
            f"- **Auth URL:** `{_auth_u}`"
            if _auth_u
            else "- **Auth URL:** não configurada"
        )
        st.write(
            f"- **Token URL:** `{_tok_u}`"
            if _tok_u
            else "- **Token URL:** não configurada"
        )
        st.write(
            f"- **API Base URL:** `{_api_u}`"
            if _api_u
            else "- **API Base URL:** não configurada"
        )
        st.write(f"- **Scope:** {_scope_cfg} (`{scope_efetivo}`)")
        st.markdown("**URL efetiva de redirecionamento:**")
        st.code(effective_redirect if effective_redirect else "(vazio)", language=None)
        st.write(f"- **URL efetiva válida:** {'sim' if vr_redirect.get('valid') else 'não'}")
        st.write(
            f"- **URL parece placeholder:** "
            f"{'sim' if vr_redirect.get('is_placeholder') else 'não'}"
        )
        st.write(f"- **Motivo do bloqueio:** {_motivo_bloqueio}")
        if oauth_readiness["warnings"]:
            st.write("**Avisos (URL de redirecionamento):**")
            for w in oauth_readiness["warnings"]:
                st.caption(f"- {w}")
        if not oauth_ready:
            st.write("**Itens que impedem habilitar \"Conectar Conta Azul\":**")
            for m in oauth_readiness["missing"]:
                st.write(f"- {m}")
        else:
            st.success("Requisitos obrigatórios para OAuth atendidos.")

        st.markdown("**Persistência local (tokens)**")
        st.write(f"- **Client ID atual (mascarado):** `{mask_client_id(settings.CONTA_AZUL_CLIENT_ID)}`")
        st.write(
            f"- **Client ID da conexão salva (mascarado):** "
            f"`{conn.get('client_id_masked') or 'não informado'}`"
        )
        st.write(
            f"- **Fingerprint bate com configuração atual:** "
            f"{'sim' if token_binding.get('fingerprints_match') else 'não'}"
        )
        st.write(
            "- **Empresa (metadata local no `token_store`, última captura salva):** "
            f"{conn.get('connected_account_name') or '—'} · id `{conn.get('connected_account_id') or '—'}` · "
            f"documento `{conn.get('connected_account_document_masked') or '—'}` · "
            f"metadata atualizada em `{conn.get('connected_metadata_updated_at') or 'não informado'}` "
            "(não é chamada ao vivo; veja **Verificação da empresa conectada** abaixo)."
        )
        st.write(f"- **Token DB (absoluto):** `{token_db_abs}`")
        st.write(f"- **Arquivo do token DB existe:** {'sim' if os.path.isfile(token_db_abs) else 'não'}")
        st.write(f"- **OAuth state DB (absoluto):** `{oauth_state_db_abs}`")
        st.write(f"- **Conectado (token_store):** {'sim' if conn['connected'] else 'não'}")
        st.write(f"- **Possui refresh token:** {'sim' if conn['has_refresh_token'] else 'não'}")
        st.write(
            f"- **Última atualização (tokens):** {conn['updated_at'] or 'não informado'}"
        )
        if token_binding.get("legacy_no_fingerprint") or token_binding.get("client_mismatch"):
            st.error(
                "A conexão salva pertence a outro Client ID ou é OAuth antigo sem vínculo. "
                "Limpe a conexão local e conecte novamente."
            )

    if not oauth_ready:
        st.info(
            "Corrija os itens listados em **Diagnóstico OAuth (seguro)**. "
            "Verifique também se o arquivo `.env` está na pasta do projeto e se você reiniciou o Streamlit após alterações."
        )

    if vr_redirect.get("is_placeholder"):
        st.warning(
            "URL de redirecionamento inválida: parece ser um placeholder. "
            "Use a URL real gerada pelo ngrok."
        )

    if conn["connected"] and not token_binding.get("binding_ok", True):
        st.error(
            "A conexão salva pertence a outro Client ID ou é OAuth antigo sem vínculo "
            "ao aplicativo atual. Use **Reconectar Conta Azul / Trocar cliente** ou "
            "**Limpar conexão local**, depois autorize novamente."
        )

    st.subheader("Verificação da empresa conectada")
    st.caption(
        "Esta seção separa **metadata salva no SQLite** (`token_store`) de uma **consulta ao vivo** "
        "ao endpoint configurado. **Não usa snapshots** do Explorador da API."
    )

    st.markdown("**A) Empresa salva no token_store**")
    st.write(f"- **Nome:** {conn.get('connected_account_name') or '—'}")
    st.write(f"- **ID:** `{conn.get('connected_account_id') or '—'}`")
    st.write(f"- **Documento (mascarado):** `{conn.get('connected_account_document_masked') or '—'}`")
    st.write(
        f"- **Momento da metadata (`connected_metadata_updated_at`):** "
        f"{conn.get('connected_metadata_updated_at') or 'não informado'}"
    )
    st.write(
        f"- **Última alteração da linha OAuth (`updated_at`, pode incluir refresh de token):** "
        f"{conn.get('updated_at') or 'não informado'}"
    )

    can_probe = oauth_ready and conn.get("connected") and token_binding.get("binding_ok", True)
    col_pv, col_up = st.columns(2)
    with col_pv:
        if st.button(
            "Verificar empresa conectada agora",
            disabled=not can_probe,
            help="Chama /conta-conectada ao vivo; não altera o banco.",
        ):
            st.session_state["empresa_live_last_probe"] = fetch_conta_conectada_live(
                db_path=token_db_abs
            )
    with col_up:
        if st.button(
            "Atualizar metadata da empresa conectada",
            disabled=not can_probe,
            help="Consulta a API e grava apenas nome/id/documento no token_store.",
        ):
            meta_up = refresh_connected_company_metadata(db_path=token_db_abs)
            if meta_up.get("success"):
                st.session_state["empresa_live_last_probe"] = None
                st.session_state["config_meta_updated_flash"] = True
                st.rerun()
            else:
                st.error(meta_up.get("error") or "Não foi possível atualizar metadata.")

    probe = st.session_state.get("empresa_live_last_probe")
    if probe is not None:
        st.markdown("**B) Empresa retornada agora pela API (ao vivo)**")
        if probe.get("success"):
            st.success(f"Verificação em `{probe.get('checked_at')}` · path `{probe.get('path')}`")
            st.write(f"- **Nome:** {probe.get('name') or '—'}")
            st.write(f"- **ID:** `{probe.get('id') or '—'}`")
            st.write(f"- **Documento:** `{probe.get('document') or '—'}`")
            if isinstance(probe.get("data"), dict):
                with st.expander("JSON sanitizado (resumo)", expanded=False):
                    st.json(probe.get("data"))
        else:
            st.error(probe.get("error") or "Falha na verificação ao vivo.")
            if probe.get("status_code"):
                st.caption(f"HTTP {probe.get('status_code')}")

    lt_cmp = load_tokens(token_db_abs)
    saved_doc_plain = lt_cmp.get("connected_account_document") if lt_cmp else None

    if probe is not None and probe.get("success"):
        st.markdown("**C) Comparação (alerta operacional — não indica falha técnica de OAuth)**")
        match = metadata_matches_live(
            saved_name=conn.get("connected_account_name"),
            saved_id=conn.get("connected_account_id"),
            saved_document=saved_doc_plain,
            live_name=probe.get("name"),
            live_id=probe.get("id"),
            live_document=probe.get("document"),
        )
        if match:
            st.success("Metadata salva e resposta ao vivo coincidem.")
        else:
            st.warning(
                "Metadata salva difere da empresa retornada pela API. "
                "Use **Atualizar metadata** ou **Reconectar Conta Azul** se o usuário autorizado não for o desejado."
            )

    status_txt = "conectado" if conn["connected"] else "desconectado"
    refresh_txt = "sim" if conn["has_refresh_token"] else "não"
    expira_txt = _formatar_expira(conn["expires_at"])
    expirado_txt = "sim" if conn["expired"] else "não"
    atual_txt = conn["updated_at"] if conn["updated_at"] else "não informado"

    st.write(f"- **Status:** {status_txt}")
    st.write(f"- **Possui refresh token:** {refresh_txt}")
    st.write(f"- **Expira em:** {expira_txt}")
    st.write(f"- **Token expirado:** {expirado_txt}")
    st.write(f"- **Última atualização:** {atual_txt}")

    auth_url_pending = st.session_state.get("oauth_auth_url")

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Inicializar armazenamento local"):
            init_token_db()
            init_oauth_state_db()
            init_settings_db()
            st.success("Armazenamento local inicializado.")
            st.rerun()
    with b2:
        if st.button("Limpar conexão local"):
            tp_clear = str(Path(get_token_db_path()).resolve())
            sp_clear = str(Path(get_oauth_state_db_path()).resolve())
            clear_tokens(tp_clear)
            clear_state(sp_clear)
            st.session_state.pop("oauth_auth_url", None)
            st.success(
                "Conexão local limpa nos bancos: "
                f"`{tp_clear}` (tokens) e `{sp_clear}` (OAuth state)."
            )
            st.rerun()
    with b3:
        connect = st.button("Conectar Conta Azul", disabled=not oauth_ready)
        if connect:
            eff_connect = get_effective_redirect_uri()
            vr_connect = validate_redirect_uri_format(eff_connect)
            if not vr_connect["valid"]:
                st.session_state["oauth_connect_error"] = " ".join(vr_connect["errors"]) or (
                    "URL de redirecionamento inválida. Configure a URL pública ou o .env."
                )
                st.rerun()
            else:
                state_val = generate_state()
                save_state(state_val, redirect_uri=eff_connect)
                url = build_authorization_url(
                    client_id=settings.CONTA_AZUL_CLIENT_ID.strip(),
                    redirect_uri=eff_connect,
                    auth_url=settings.CONTA_AZUL_AUTH_URL.strip(),
                    scope=scope_efetivo,
                    state=state_val,
                )
                st.session_state["oauth_auth_url"] = url
                st.rerun()

    if st.button("Reconectar Conta Azul / Trocar cliente"):
        tp_rc = str(Path(get_token_db_path()).resolve())
        sp_rc = str(Path(get_oauth_state_db_path()).resolve())
        clear_tokens(tp_rc)
        clear_state(sp_rc)
        for _k in (
            "oauth_auth_url",
            "oauth_callback_result",
            "oauth_last_processed_code_fp",
        ):
            st.session_state.pop(_k, None)
        st.success(
            "Conexão antiga removida. Clique em **Conectar Conta Azul** para autorizar o novo cliente."
        )
        st.rerun()

    test_client = st.button("Testar cliente autenticado", disabled=not oauth_ready)
    if test_client:
        try:
            _ = get_authenticated_client()
            st.session_state["auth_client_test_success"] = True
            st.session_state.pop("auth_client_test_error", None)
        except AuthClientError as exc:
            st.session_state["auth_client_test_error"] = str(exc)
            st.session_state.pop("auth_client_test_success", None)
        st.rerun()

    if auth_url_pending:
        st.markdown(f"[Abrir autorização da Conta Azul]({auth_url_pending})")
        try:
            st.link_button("Abrir autorização da Conta Azul", auth_url_pending)
        except Exception:
            pass

    st.divider()
    st.subheader("Diagnóstico da API Conta Azul")
    st.write(f"- **Endpoint configurado:** `{diagnostic_path}`")

    if st.button("Testar chamada real de diagnóstico", disabled=not oauth_ready):
        result = call_diagnostic_endpoint()
        if result.get("success"):
            st.success("Chamada de diagnóstico realizada com sucesso.")
            st.write(f"Path chamado: `{result.get('path')}`")
            st.json(result.get("data"))
        else:
            st.error(result.get("error") or "Falha no diagnóstico da API.")
            if result.get("status_code") is not None:
                status_code = int(result["status_code"])
                st.write(f"Status code: `{status_code}`")
                if status_code == 401:
                    st.info("401: token inválido/expirado. Tente reconectar a Conta Azul.")
                elif status_code == 403:
                    st.info("403: verifique permissões e escopos da aplicação.")
                elif status_code == 404:
                    st.info("404: confira o endpoint configurado em CONTA_AZUL_DIAGNOSTIC_PATH.")
                elif status_code == 429:
                    st.info("429: limite de chamadas atingido. Aguarde e tente novamente.")
                elif status_code >= 500:
                    st.info("500+: instabilidade ou erro interno da API.")

    conn_diag = get_connection_status()
    with st.expander("Diagnóstico técnico seguro"):
        st.write(f"- conectado: {'sim' if conn_diag['connected'] else 'não'}")
        st.write(f"- token expirado: {'sim' if conn_diag['expired'] else 'não'}")
        st.write(f"- possui refresh: {'sim' if conn_diag['has_refresh_token'] else 'não'}")
        st.write(f"- updated_at: {conn_diag['updated_at'] or 'não informado'}")
        st.write(f"- api_base_url configurada: {_status(settings.CONTA_AZUL_API_BASE_URL)}")
