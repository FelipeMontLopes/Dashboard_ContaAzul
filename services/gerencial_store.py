"""Persistência SQLite para cadastros gerenciais (relatório MVP)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from app_paths import get_gerencial_db_path


def _resolve_db_path(db_path: str | None) -> str:
    return db_path if db_path is not None else str(get_gerencial_db_path())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_gerencial_db(db_path: str | None = None) -> None:
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS socios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                papel TEXT,
                percentual_participacao REAL NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS socio_ajustes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                socio_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                descricao TEXT,
                valor REAL NOT NULL DEFAULT 0,
                data TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (socio_id) REFERENCES socios(id)
            );

            CREATE TABLE IF NOT EXISTS investimentos_gerenciais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                socio_id INTEGER,
                descricao TEXT NOT NULL,
                valor REAL NOT NULL DEFAULT 0,
                data TEXT,
                categoria TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (socio_id) REFERENCES socios(id)
            );

            CREATE TABLE IF NOT EXISTS custos_fixos_gerenciais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                categoria TEXT,
                cargo_funcao TEXT,
                valor_mensal REAL NOT NULL DEFAULT 0,
                ativo INTEGER NOT NULL DEFAULT 1,
                observacao TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS premissas_gerenciais (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS indicadores_patrimoniais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                valor REAL NOT NULL DEFAULT 0,
                descricao TEXT,
                data_referencia TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS justificativas_gerenciais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                texto TEXT,
                categoria TEXT,
                data_referencia TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS obras_projetos_manuais (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                cliente TEXT,
                receita_realizada_manual REAL DEFAULT 0,
                custo_realizado_manual REAL DEFAULT 0,
                receita_a_realizar_manual REAL DEFAULT 0,
                status TEXT,
                observacao TEXT,
                ativo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS mapeamento_conta_azul (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                valor_origem TEXT NOT NULL,
                valor_destino TEXT NOT NULL,
                observacao TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


# --- Sócios ---


def create_socio(
    nome: str,
    papel: str | None = None,
    percentual_participacao: float = 0.0,
    ativo: bool = True,
    db_path: str | None = None,
) -> int:
    init_gerencial_db(db_path)
    now = _now_iso()
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        cur = conn.execute(
            """
            INSERT INTO socios (nome, papel, percentual_participacao, ativo, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nome.strip(), (papel or "").strip() or None, float(percentual_participacao), 1 if ativo else 0, now, now),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def update_socio(
    socio_id: int,
    nome: str | None = None,
    papel: str | None = None,
    percentual_participacao: float | None = None,
    ativo: bool | None = None,
    db_path: str | None = None,
) -> None:
    init_gerencial_db(db_path)
    now = _now_iso()
    p = _resolve_db_path(db_path)
    row = get_socio(int(socio_id), db_path)
    if not row:
        raise ValueError("sócio não encontrado")
    nome_f = nome.strip() if nome is not None else row["nome"]
    papel_f = row["papel"]
    if papel is not None:
        papel_f = papel.strip() or None
    pct_f = float(row["percentual_participacao"])
    if percentual_participacao is not None:
        pct_f = float(percentual_participacao)
    ativo_f = int(row["ativo"])
    if ativo is not None:
        ativo_f = 1 if ativo else 0
    with sqlite3.connect(p) as conn:
        conn.execute(
            """
            UPDATE socios SET nome=?, papel=?, percentual_participacao=?, ativo=?, updated_at=?
            WHERE id=?
            """,
            (nome_f, papel_f, pct_f, ativo_f, now, int(socio_id)),
        )
        conn.commit()


def get_socio(socio_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM socios WHERE id = ?", (int(socio_id),)).fetchone()
    return dict(row) if row else None


def list_socios(db_path: str | None = None, apenas_ativos: bool = False) -> list[dict[str, Any]]:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        if apenas_ativos:
            rows = conn.execute(
                "SELECT * FROM socios WHERE ativo = 1 ORDER BY nome"
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM socios ORDER BY nome").fetchall()
    return [dict(r) for r in rows]


def delete_socio(socio_id: int, db_path: str | None = None) -> None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.execute("DELETE FROM socio_ajustes WHERE socio_id = ?", (int(socio_id),))
        conn.execute("DELETE FROM investimentos_gerenciais WHERE socio_id = ?", (int(socio_id),))
        conn.execute("DELETE FROM socios WHERE id = ?", (int(socio_id),))
        conn.commit()


# --- Ajustes ---


def create_socio_ajuste(
    socio_id: int,
    tipo: str,
    valor: float,
    descricao: str | None = None,
    data: str | None = None,
    db_path: str | None = None,
) -> int:
    init_gerencial_db(db_path)
    now = _now_iso()
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        cur = conn.execute(
            """
            INSERT INTO socio_ajustes (socio_id, tipo, descricao, valor, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (int(socio_id), tipo.strip(), (descricao or "").strip() or None, float(valor), data, now, now),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def list_socio_ajustes(socio_id: int | None = None, db_path: str | None = None) -> list[dict[str, Any]]:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        if socio_id is not None:
            rows = conn.execute(
                "SELECT * FROM socio_ajustes WHERE socio_id = ? ORDER BY id DESC",
                (int(socio_id),),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM socio_ajustes ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def delete_socio_ajuste(ajuste_id: int, db_path: str | None = None) -> None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.execute("DELETE FROM socio_ajustes WHERE id = ?", (int(ajuste_id),))
        conn.commit()


# --- Investimentos ---


def create_investimento(
    descricao: str,
    valor: float,
    socio_id: int | None = None,
    data: str | None = None,
    categoria: str | None = None,
    db_path: str | None = None,
) -> int:
    init_gerencial_db(db_path)
    now = _now_iso()
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        cur = conn.execute(
            """
            INSERT INTO investimentos_gerenciais
            (socio_id, descricao, valor, data, categoria, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(socio_id) if socio_id is not None else None,
                descricao.strip(),
                float(valor),
                data,
                (categoria or "").strip() or None,
                now,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def list_investimentos(db_path: str | None = None) -> list[dict[str, Any]]:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM investimentos_gerenciais ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def delete_investimento(inv_id: int, db_path: str | None = None) -> None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.execute("DELETE FROM investimentos_gerenciais WHERE id = ?", (int(inv_id),))
        conn.commit()


# --- Custos fixos ---


def create_custo_fixo(
    nome: str,
    valor_mensal: float,
    categoria: str | None = None,
    cargo_funcao: str | None = None,
    ativo: bool = True,
    observacao: str | None = None,
    db_path: str | None = None,
) -> int:
    init_gerencial_db(db_path)
    now = _now_iso()
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        cur = conn.execute(
            """
            INSERT INTO custos_fixos_gerenciais
            (nome, categoria, cargo_funcao, valor_mensal, ativo, observacao, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nome.strip(),
                (categoria or "").strip() or None,
                (cargo_funcao or "").strip() or None,
                float(valor_mensal),
                1 if ativo else 0,
                (observacao or "").strip() or None,
                now,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def update_custo_fixo(
    custo_id: int,
    nome: str | None = None,
    categoria: str | None = None,
    cargo_funcao: str | None = None,
    valor_mensal: float | None = None,
    ativo: bool | None = None,
    observacao: str | None = None,
    db_path: str | None = None,
) -> None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    row = get_custo_fixo(int(custo_id), db_path)
    if not row:
        raise ValueError("custo fixo não encontrado")
    now = _now_iso()
    nome_f = nome.strip() if nome is not None else row["nome"]
    cat_f = row["categoria"]
    if categoria is not None:
        cat_f = categoria.strip() or None
    cargo_f = row["cargo_funcao"]
    if cargo_funcao is not None:
        cargo_f = cargo_funcao.strip() or None
    vm_f = float(row["valor_mensal"])
    if valor_mensal is not None:
        vm_f = float(valor_mensal)
    at_f = int(row["ativo"])
    if ativo is not None:
        at_f = 1 if ativo else 0
    obs_f = row["observacao"]
    if observacao is not None:
        obs_f = observacao.strip() or None
    with sqlite3.connect(p) as conn:
        conn.execute(
            """
            UPDATE custos_fixos_gerenciais
            SET nome=?, categoria=?, cargo_funcao=?, valor_mensal=?, ativo=?, observacao=?, updated_at=?
            WHERE id=?
            """,
            (nome_f, cat_f, cargo_f, vm_f, at_f, obs_f, now, int(custo_id)),
        )
        conn.commit()


def get_custo_fixo(custo_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM custos_fixos_gerenciais WHERE id = ?", (int(custo_id),)
        ).fetchone()
    return dict(row) if row else None


def list_custos_fixos(db_path: str | None = None, apenas_ativos: bool = False) -> list[dict[str, Any]]:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        if apenas_ativos:
            rows = conn.execute(
                "SELECT * FROM custos_fixos_gerenciais WHERE ativo = 1 ORDER BY nome"
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM custos_fixos_gerenciais ORDER BY nome").fetchall()
    return [dict(r) for r in rows]


def delete_custo_fixo(custo_id: int, db_path: str | None = None) -> None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.execute("DELETE FROM custos_fixos_gerenciais WHERE id = ?", (int(custo_id),))
        conn.commit()


# --- Obras manuais ---


def create_obra_manual(
    nome: str,
    cliente: str | None = None,
    receita_realizada_manual: float = 0.0,
    custo_realizado_manual: float = 0.0,
    receita_a_realizar_manual: float = 0.0,
    status: str | None = None,
    observacao: str | None = None,
    ativo: bool = True,
    db_path: str | None = None,
) -> int:
    init_gerencial_db(db_path)
    now = _now_iso()
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        cur = conn.execute(
            """
            INSERT INTO obras_projetos_manuais (
                nome, cliente, receita_realizada_manual, custo_realizado_manual,
                receita_a_realizar_manual, status, observacao, ativo, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nome.strip(),
                (cliente or "").strip() or None,
                float(receita_realizada_manual),
                float(custo_realizado_manual),
                float(receita_a_realizar_manual),
                (status or "").strip() or None,
                (observacao or "").strip() or None,
                1 if ativo else 0,
                now,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def update_obra_manual(
    obra_id: int,
    nome: str | None = None,
    cliente: str | None = None,
    receita_realizada_manual: float | None = None,
    custo_realizado_manual: float | None = None,
    receita_a_realizar_manual: float | None = None,
    status: str | None = None,
    observacao: str | None = None,
    ativo: bool | None = None,
    db_path: str | None = None,
) -> None:
    init_gerencial_db(db_path)
    row = get_obra_manual(int(obra_id), db_path)
    if not row:
        raise ValueError("obra não encontrada")
    now = _now_iso()
    nome_f = nome.strip() if nome is not None else row["nome"]
    cli_f = row["cliente"]
    if cliente is not None:
        cli_f = cliente.strip() or None
    rr = float(row["receita_realizada_manual"])
    if receita_realizada_manual is not None:
        rr = float(receita_realizada_manual)
    cr = float(row["custo_realizado_manual"])
    if custo_realizado_manual is not None:
        cr = float(custo_realizado_manual)
    rar = float(row["receita_a_realizar_manual"])
    if receita_a_realizar_manual is not None:
        rar = float(receita_a_realizar_manual)
    st_f = row["status"]
    if status is not None:
        st_f = status.strip() or None
    obs_f = row["observacao"]
    if observacao is not None:
        obs_f = observacao.strip() or None
    at_f = int(row["ativo"])
    if ativo is not None:
        at_f = 1 if ativo else 0
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.execute(
            """
            UPDATE obras_projetos_manuais SET
                nome=?, cliente=?, receita_realizada_manual=?, custo_realizado_manual=?,
                receita_a_realizar_manual=?, status=?, observacao=?, ativo=?, updated_at=?
            WHERE id=?
            """,
            (nome_f, cli_f, rr, cr, rar, st_f, obs_f, at_f, now, int(obra_id)),
        )
        conn.commit()


def get_obra_manual(obra_id: int, db_path: str | None = None) -> dict[str, Any] | None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM obras_projetos_manuais WHERE id = ?", (int(obra_id),)
        ).fetchone()
    return dict(row) if row else None


def list_obras_manuais(db_path: str | None = None, apenas_ativas: bool = False) -> list[dict[str, Any]]:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        if apenas_ativas:
            rows = conn.execute(
                "SELECT * FROM obras_projetos_manuais WHERE ativo = 1 ORDER BY nome"
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM obras_projetos_manuais ORDER BY nome").fetchall()
    return [dict(r) for r in rows]


def delete_obra_manual(obra_id: int, db_path: str | None = None) -> None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.execute("DELETE FROM obras_projetos_manuais WHERE id = ?", (int(obra_id),))
        conn.commit()


# --- Premissas ---


def set_premissa(key: str, value: str | None, db_path: str | None = None) -> None:
    init_gerencial_db(db_path)
    now = _now_iso()
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.execute(
            """
            INSERT INTO premissas_gerenciais (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
            """,
            (key.strip(), value, now),
        )
        conn.commit()


def get_premissa(key: str, db_path: str | None = None) -> str | None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        row = conn.execute(
            "SELECT value FROM premissas_gerenciais WHERE key = ?", (key.strip(),)
        ).fetchone()
    return row[0] if row else None


def list_premissas(db_path: str | None = None) -> dict[str, str | None]:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        rows = conn.execute("SELECT key, value FROM premissas_gerenciais ORDER BY key").fetchall()
    return {str(k): v for k, v in rows}


# --- Indicadores ---


def create_indicador(
    nome: str,
    valor: float,
    descricao: str | None = None,
    data_referencia: str | None = None,
    db_path: str | None = None,
) -> int:
    init_gerencial_db(db_path)
    now = _now_iso()
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        cur = conn.execute(
            """
            INSERT INTO indicadores_patrimoniais (nome, valor, descricao, data_referencia, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                nome.strip(),
                float(valor),
                (descricao or "").strip() or None,
                data_referencia,
                now,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def list_indicadores(db_path: str | None = None) -> list[dict[str, Any]]:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM indicadores_patrimoniais ORDER BY nome").fetchall()
    return [dict(r) for r in rows]


def delete_indicador(indicador_id: int, db_path: str | None = None) -> None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.execute("DELETE FROM indicadores_patrimoniais WHERE id = ?", (int(indicador_id),))
        conn.commit()


# --- Justificativas ---


def create_justificativa(
    titulo: str,
    texto: str | None = None,
    categoria: str | None = None,
    data_referencia: str | None = None,
    db_path: str | None = None,
) -> int:
    init_gerencial_db(db_path)
    now = _now_iso()
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        cur = conn.execute(
            """
            INSERT INTO justificativas_gerenciais (titulo, texto, categoria, data_referencia, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                titulo.strip(),
                (texto or "").strip() or None,
                (categoria or "").strip() or None,
                data_referencia,
                now,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def list_justificativas(db_path: str | None = None) -> list[dict[str, Any]]:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM justificativas_gerenciais ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def delete_justificativa(jid: int, db_path: str | None = None) -> None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.execute("DELETE FROM justificativas_gerenciais WHERE id = ?", (int(jid),))
        conn.commit()


# --- Mapeamentos ---


def create_mapeamento(
    tipo: str,
    valor_origem: str,
    valor_destino: str,
    observacao: str | None = None,
    db_path: str | None = None,
) -> int:
    init_gerencial_db(db_path)
    now = _now_iso()
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        cur = conn.execute(
            """
            INSERT INTO mapeamento_conta_azul (tipo, valor_origem, valor_destino, observacao, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                tipo.strip(),
                valor_origem.strip(),
                valor_destino.strip(),
                (observacao or "").strip() or None,
                now,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)


def list_mapeamentos(db_path: str | None = None) -> list[dict[str, Any]]:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM mapeamento_conta_azul ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def delete_mapeamento(map_id: int, db_path: str | None = None) -> None:
    init_gerencial_db(db_path)
    p = _resolve_db_path(db_path)
    with sqlite3.connect(p) as conn:
        conn.execute("DELETE FROM mapeamento_conta_azul WHERE id = ?", (int(map_id),))
        conn.commit()


def seed_premissas_padrao(db_path: str | None = None) -> None:
    """Garante chaves conhecidas existentes (valores vazios até o usuário preencher)."""
    keys = [
        "imposto_percentual",
        "custo_variavel_percentual",
        "ponto_equilibrio_meta",
        "margem_alvo",
        "custo_fixo_mensal_manual",
    ]
    init_gerencial_db(db_path)
    for k in keys:
        if get_premissa(k, db_path) is None:
            set_premissa(k, "", db_path)
