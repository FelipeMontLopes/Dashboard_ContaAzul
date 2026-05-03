# conta_azul_dashboard

Projeto base em Streamlit para dashboard financeiro, com dados mockados e sem integração real com a Conta Azul nesta fase.

## Pré-requisitos

- Python 3.12+

## Como criar ambiente virtual

No Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

No macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Como instalar dependências

```bash
pip install -r requirements.txt
```

## Como rodar o Streamlit

```bash
streamlit run app.py
```

## Observação importante

Esta Fase 0 cria apenas a fundação do projeto:

- interface Streamlit;
- páginas separadas por módulo;
- dados mockados para validar a UI.

Ainda não existe conexão real com a API da Conta Azul, OAuth, banco de dados ou persistência de tokens.

## Fase 2 — Cliente HTTP genérico

Nesta fase foi adicionada uma camada HTTP reutilizável em `conta_azul_client.py`.

- ainda não há OAuth;
- ainda não há endpoint real da Conta Azul;
- o client não é usado diretamente pela UI do Streamlit;
- o client será usado nas próximas fases (token store/OAuth + integração real).

## Fase 3A — Token Store Local Seguro

Foi adicionado `token_store.py`, usando SQLite (`sqlite3`) para persistir tokens OAuth **em uma fase futura**.

- ainda **não** há OAuth real nem troca de código por token;
- os bancos SQLite (`tokens`, OAuth `state`, settings) ficam em **`.local_data/`** na raiz do projeto (caminhos absolutos via `app_paths.py`), para não depender do diretório de trabalho ao rodar o Streamlit;
- a pasta **`.local_data/`** e `*.db` estão no `.gitignore` (não versionar dados locais);
- a página **Configurações** só exibe **status seguro** da conexão (sem tokens).

## Fase 3B — OAuth Authorization Code

Foi implementado o fluxo OAuth2 Authorization Code da Conta Azul via `oauth_service.py`, persistência de `state` em `oauth_state_store.py` e gravação dos tokens em `token_store.py`.

### Como configurar

1. Copie `.env.example` para `.env` na **raiz do projeto** (mesma pasta que `config.py` e `app.py`).
2. O carregamento usa `python-dotenv` com caminho fixo para esse `.env`, para que variáveis sejam encontradas mesmo se o Streamlit for iniciado a partir de outro diretório. Valores já definidos no ambiente do sistema **não** são sobrescritos. Após alterar o `.env`, reinicie o processo do Streamlit.
3. Preencha no `.env` (valores idênticos ao cadastro no Portal do Desenvolvedor Conta Azul):
   - `CONTA_AZUL_CLIENT_ID`
   - `CONTA_AZUL_CLIENT_SECRET`
   - `CONTA_AZUL_REDIRECT_URI` (deve coincidir **exatamente** com o redirect cadastrado)
   - `CONTA_AZUL_AUTH_URL`, `CONTA_AZUL_TOKEN_URL`, `CONTA_AZUL_API_BASE_URL`, `CONTA_AZUL_SCOPE`

Em **Configurações**, o expander **Diagnóstico OAuth (seguro)** lista o que falta quando o botão **Conectar Conta Azul** está desabilitado (sem exibir segredos).

### Como rodar e conectar

```bash
streamlit run app.py
```

Em **Configurações**, use **Conectar Conta Azul**, abra o link de autorização, faça login e autorize. O retorno para `http://localhost:8501/?code=...&state=...` troca o código por tokens e exibe sucesso **sem mostrar tokens na tela**.

- **Ainda não** há consumo de endpoints financeiros da API.
- Tokens e bancos SQLite locais (`*.db`) permanecem **fora do git** (`.gitignore`).

## Fase 3C — Refresh Token + Client Autenticado

Esta fase adiciona renovação de sessão OAuth sem expor segredos:

- `oauth_service.refresh_access_token(...)` renova `access_token` via `grant_type=refresh_token`;
- `auth_client_factory.get_authenticated_client(...)` cria um `ContaAzulClient` pronto para uso;
- se o token estiver expirado, tenta refresh e atualiza o `token_store`;
- se o refresh falhar ou não houver sessão válida, retorna erro amigável pedindo reconexão.

Observações:

- esta fase **ainda não** consome dados financeiros da API;
- tokens e `client_secret` continuam ocultos na UI e nos logs;
- próximo passo natural: primeira chamada real de diagnóstico autenticado.

## Fase 3D — URL pública de redirecionamento

O Portal da Conta Azul pode **não aceitar** `localhost` como URL de redirecionamento em produção.

Para testar localmente com **ngrok** (fluxo recomendado):

1. Rode o Streamlit: `streamlit run app.py`
2. Em outro terminal, rode o túnel: `ngrok http 8501`
3. Copie a URL **HTTPS** real que o ngrok exibir (não use URLs de exemplo como `abc123.ngrok-free.app` — use a URL gerada na sua máquina).
4. Em **Configurações** → **URL pública de redirecionamento**, cole essa URL e clique em **Salvar URL pública**.
5. Copie a **URL efetiva** mostrada no app (bloco “URL efetiva que será usada”).
6. Cadastre **exatamente** essa URL no Portal do Desenvolvedor Conta Azul (incluindo barra final, se houver).
7. Só então use **Conectar Conta Azul**.

Outras notas:

- Se definir override na app, ele tem prioridade sobre `CONTA_AZUL_REDIRECT_URI` no `.env`.
- No OAuth, a mesma URL é gravada junto do `state` e usada na troca do `code` por tokens — evita mismatch entre autorização e token endpoint.
- **Plano gratuito do ngrok:** a URL pública pode mudar a cada execução. Se mudar, atualize **(1)** Configurações do app e **(2)** o Portal da Conta Azul para manterem a mesma URL.

Para teste local, rode `ngrok http 8501` e cole a URL pública **real** em Configurações (não use placeholders de documentação).

O arquivo `.env.example` mantém `CONTA_AZUL_REDIRECT_URI=` vazio para incentivar override público ou preenchimento manual coerente com o Portal.

## Deploy no Streamlit Community Cloud

Objetivo: URL pública estável (`*.streamlit.app`) para OAuth, sem depender de ngrok ou localhost.

### Passo a passo

1. Crie um repositório no **GitHub** e envie o código deste projeto.
2. **Não** versione `.env`, `.local_data/` nem `*.db` (já estão no `.gitignore`).
3. Acesse [Streamlit Community Cloud](https://streamlit.io/cloud), conecte o GitHub e **New app**.
4. Selecione o **repositório**, a **branch** e o arquivo principal **`app.py`** (na raiz do app).
5. Em **Settings → Secrets**, configure as variáveis (veja exemplo abaixo). Salve.
6. Use a URL do app gerada pelo Streamlit (ex.: `https://seu-app.streamlit.app`) como **URL de redirecionamento OAuth** no **Portal do Desenvolvedor Conta Azul** — **exatamente** igual à que o app usa (barra final inclusa, se aplicável).
7. Defina `CONTA_AZUL_REDIRECT_URI` nos secrets do Streamlit com **essa mesma** URL.
8. Se o Portal não permitir alterar a URL de uma app já criada, cadastre uma nova aplicação lá com o redirect correto.
9. Abra o app publicado e use **Conectar Conta Azul** em Configurações.

### Exemplo de secrets (painel do Streamlit)

Formato TOML no editor de secrets (ajuste os valores reais):

```toml
CONTA_AZUL_CLIENT_ID = "..."
CONTA_AZUL_CLIENT_SECRET = "..."
CONTA_AZUL_REDIRECT_URI = "https://seu-app.streamlit.app"
CONTA_AZUL_AUTH_URL = "https://auth.contaazul.com/login"
CONTA_AZUL_TOKEN_URL = "https://auth.contaazul.com/oauth2/token"
CONTA_AZUL_API_BASE_URL = "https://api-v2.contaazul.com"
CONTA_AZUL_SCOPE = "openid profile aws.cognito.signin.user.admin"
CONTA_AZUL_DIAGNOSTIC_PATH = "/v1/pessoas/conta-conectada"
```

As URLs de auth/token/API/scope/diagnóstico podem ser omitidas nos secrets se você aceitar os **defaults** embutidos no `config.py` (iguais ao `.env.example`). `CLIENT_ID`, `CLIENT_SECRET` e `REDIRECT_URI` são obrigatórios para o OAuth funcionar.

### Alertas importantes

- **Nunca** coloque `client_secret` ou tokens no GitHub; use apenas o painel **Secrets** do Streamlit ou variáveis do ambiente no provedor.
- O arquivo **`.env`** é para desenvolvimento **local**; no Cloud, prefira **Secrets**.
- A pasta **`.local_data/`** não deve ir para o repositório; no Streamlit Cloud o filesystem é **efêmero**: **SQLite local não é persistência confiável** — reinícios ou novos containers podem apagar tokens gravados localmente. Para produção séria, planeje migrar tokens/sessão para um banco gerenciado (ex.: Postgres/Supabase).
- Para testes locais após mudanças: `pip install -r requirements.txt` e `streamlit run app.py`.

## Troca de cliente / troca de credenciais Conta Azul

Alterar apenas `CONTA_AZUL_CLIENT_ID` e `CONTA_AZUL_CLIENT_SECRET` **não** troca automaticamente a sessão OAuth já gravada no SQLite local. Os **access/refresh tokens** continuam associados ao **Client ID** que foi usado na autorização original.

**Regra operacional**

1. Troque `CLIENT_ID` / `CLIENT_SECRET` (ou secrets no Streamlit Cloud).
2. **Reinicie o app** no Streamlit Cloud (**Manage app → Reboot app**) para o processo carregar os novos valores — mudar secrets no painel nem sempre atualiza o processo já em execução.
3. Em **Configurações**, use **Reconectar Conta Azul / Trocar cliente** ou **Limpar conexão local** para apagar tokens e estado OAuth locais.
4. Clique em **Conectar Conta Azul** e autorize de novo com o novo aplicativo/cliente.
5. Valide com **Testar chamada real de diagnóstico** (`/v1/pessoas/conta-conectada` ou o path configurado).

A aplicação passa a gravar um **fingerprint (SHA-256)** do Client ID junto com os tokens e **bloqueia** o uso de tokens salvos quando o Client ID atual não coincide — é obrigatório limpar a conexão local e refazer o OAuth. **Nunca** reutilize tokens obtidos com outro cliente/aplicativo.

## Client ID vs empresa conectada

- **Client ID** identifica a **aplicação OAuth** registrada no Portal do Desenvolvedor Conta Azul — não identifica qual empresa CNPJ será usada nos dados.
- A **empresa conectada** (nome/id/documento retornados por `/v1/pessoas/conta-conectada`) reflete a **conta/usuário que você autorizou** no fluxo de login OAuth da Conta Azul.
- **Trocar Client ID** garante apenas qual **app** está pedindo acesso; **não** garante trocar a empresa: você pode continuar com o mesmo usuário logado no navegador ou autorizar outra conta sem querer.
- Para **mudar a empresa**, limpe a conexão local (**Reconectar Conta Azul / Trocar cliente**), depois **Conectar Conta Azul** e autorize com o usuário da empresa correta. Se o navegador reutilizar sessão antiga, use **aba anônima/privada** ao abrir o link de autorização.
- Na página **Configurações**, a seção **Verificação da empresa conectada** separa **metadata salva no SQLite** (última captura gravada) de uma **consulta ao vivo** ao endpoint — ajuda a detectar divergência sem confundir com erro técnico de OAuth.

## Fase 5 — Explorador da API e snapshots

Esta fase adiciona o **Explorador da API** (menu lateral) para chamar endpoints GET reais com o cliente autenticado, registrar **sucesso ou erro** e gravar **snapshots sanitizados** das respostas em SQLite.

- Os endpoints **`/v1/financeiro/eventos-financeiros/saldo-inicial`** e **`/v1/financeiro/eventos-financeiros/alteracoes`** exigem **`data_inicio`** e **`data_fim`** (e aceitam paginação). Sem esses query params, a Conta Azul costuma responder **400** (“Requisição inválida”). O explorador envia um período padrão configurável na própria página.

- Serve para **descobrir quais endpoints respondem** e **qual formato de dados** retornam antes de normalizar dados para o dashboard.
- Os snapshots ficam em **`.local_data/`** (arquivo `conta_azul_api_snapshots.db`). Essa pasta **não** vai para o Git.
- No **Streamlit Community Cloud**, o filesystem é efêmero: **SQLite local pode não persistir** entre reinícios ou novos containers — use o explorador como diagnóstico; para produção estável, planeje migrar snapshots e tokens para **Postgres/Supabase** (ou outro backend gerenciado).

## Fase 6A — Contratos dos dados reais

Esta fase **não substitui os mocks** das telas do dashboard e **não define KPIs finais**.

- Usa os **snapshots brutos** já salvos pelo Explorador (JSON sanitizado no SQLite).
- A página **Contratos de Dados** infere um **contrato exploratório** (`infer_json_contract`): tipos, chaves, candidatos a data/valor/status/id/texto, **candidatos de paginação** (chaves como `pagina`, `total`, `tamanho_pagina`, etc.) e exemplos seguros. Cada análise referencia o **`snapshot_id`** usado.
- **`suggest_financial_fields`** propõe mapeamentos financeiros **candidatos** (confiança alta/média/baixa), sem aplicar normalização ao fluxo de negócio ainda.
- Objetivo: preparar a **Fase 6** (normalização) com base no JSON **real** da sua conta e permissões.
- Snapshots continuam em **`.local_data/`** (não versionados); no Streamlit Cloud o SQLite local **não é persistência confiável**.

## Fase 4 — Primeira chamada real de diagnóstico

Esta fase valida a conexão real autenticada sem sincronizar dados financeiros.

- Endpoint padrão de diagnóstico: `/v1/pessoas/conta-conectada`
- Configurável por `.env` via `CONTA_AZUL_DIAGNOSTIC_PATH`
- Resposta exibida na UI é sanitizada (campos sensíveis mascarados)
- Ainda não há contas a pagar/receber nem persistência de snapshots

### Interpretação rápida de erros

- `401`: reconectar a Conta Azul
- `403`: revisar permissões/escopos da aplicação
- `404`: conferir endpoint configurado/documentação
- `429`: aguardar e tentar novamente
- `500+`: instabilidade ou erro da API
