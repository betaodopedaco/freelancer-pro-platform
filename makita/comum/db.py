"""
makita — banco de dados (SQLite ou PostgreSQL)
==============================================
Camada de persistência permanente do sistema.
DATABASE_URL definida = PostgreSQL via asyncpg.
DATABASE_URL vazia    = SQLite via aiosqlite (fallback local).
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("db")

# ── detecção do backend ──────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL", "")
DB_PATH = os.environ.get("DB_PATH", "makita.db")

USE_PG = bool(DATABASE_URL)


def _agora() -> str:
    """ISO 8601 no UTC."""
    return datetime.now(timezone.utc).isoformat()


# ── init ──────────────────────────────────────────────────────────

async def init_db(path: str = DB_PATH) -> None:
    """Cria todas as tabelas se não existirem."""
    if USE_PG:
        await _init_pg()
    else:
        await _init_sqlite(path)


async def _init_sqlite(path: str) -> None:
    """SQLite: cria tabelas com aiosqlite."""
    import aiosqlite
    async with aiosqlite.connect(path) as db:
        await db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS usuarios (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_chat_id  TEXT    NOT NULL UNIQUE,
                ativo             INTEGER NOT NULL DEFAULT 1,
                plano             TEXT    NOT NULL DEFAULT 'basico',
                max_keywords      INTEGER NOT NULL DEFAULT 10,
                criado_em         TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS palavras_chave (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
                palavra     TEXT    NOT NULL,
                ativa       INTEGER NOT NULL DEFAULT 1,
                criado_em   TEXT    NOT NULL,
                UNIQUE(usuario_id, palavra)
            );
            CREATE TABLE IF NOT EXISTS sinais_vistos (
                source_id TEXT PRIMARY KEY,
                visto_em  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessoes_plataforma (
                plataforma    TEXT PRIMARY KEY,
                tokens_json   TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            );
        """)
        await db.commit()
    log.info(f"SQLite: tabelas criadas em {path}")


async def _init_pg() -> None:
    """PostgreSQL: cria tabelas com asyncpg."""
    import asyncpg
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id                SERIAL PRIMARY KEY,
            telegram_chat_id  TEXT    NOT NULL UNIQUE,
            ativo             INTEGER NOT NULL DEFAULT 1,
            plano             TEXT    NOT NULL DEFAULT 'basico',
            max_keywords      INTEGER NOT NULL DEFAULT 10,
            criado_em         TEXT    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS palavras_chave (
            id          SERIAL PRIMARY KEY,
            usuario_id  INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            palavra     TEXT    NOT NULL,
            ativa       INTEGER NOT NULL DEFAULT 1,
            criado_em   TEXT    NOT NULL,
            UNIQUE(usuario_id, palavra)
        );
        CREATE TABLE IF NOT EXISTS sinais_vistos (
            source_id TEXT PRIMARY KEY,
            visto_em  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessoes_plataforma (
            plataforma    TEXT PRIMARY KEY,
            tokens_json   TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        );
    """)
    await conn.close()
    log.info("PostgreSQL: tabelas criadas.")


# ── helpers de conexão ────────────────────────────────────────────

async def _get_conn():
    if USE_PG:
        import asyncpg
        return await asyncpg.connect(DATABASE_URL)
    else:
        import aiosqlite
        return await aiosqlite.connect(DB_PATH)


async def _fetchall(conn, sql: str, params=()):
    if USE_PG:
        rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]
    else:
        conn.row_factory = None
        cursor = await conn.execute(sql, params)
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description] if cursor.description else []
        return [dict(zip(cols, r)) for r in rows]


async def _execute(conn, sql: str, params=()):
    if USE_PG:
        await conn.execute(sql, *params)
    else:
        await conn.execute(sql, params)


async def _commit(conn):
    if not USE_PG:
        await conn.commit()


async def _close(conn):
    await conn.close()


# ── palavras-chave ────────────────────────────────────────────────

async def get_palavras_ativas(path: str = DB_PATH) -> list:
    """Retorna lista de palavras únicas ativas (sem duplicatas)."""
    conn = await _get_conn()
    try:
        rows = await _fetchall(conn,
            "SELECT DISTINCT palavra FROM palavras_chave WHERE ativa = 1"
        )
        return [r["palavra"] for r in rows]
    finally:
        await _close(conn)


async def get_chat_ids_por_palavra(palavra: str, path: str = DB_PATH) -> list:
    """Retorna chat_ids dos usuários que monitoram esta palavra."""
    conn = await _get_conn()
    try:
        if USE_PG:
            rows = await _fetchall(conn, """
                SELECT u.telegram_chat_id
                  FROM usuarios u
                  JOIN palavras_chave p ON p.usuario_id = u.id
                 WHERE p.palavra = $1 AND p.ativa = 1 AND u.ativo = 1
            """, (palavra,))
        else:
            rows = await _fetchall(conn, """
                SELECT u.telegram_chat_id
                  FROM usuarios u
                  JOIN palavras_chave p ON p.usuario_id = u.id
                 WHERE p.palavra = ? AND p.ativa = 1 AND u.ativo = 1
            """, (palavra,))
        return [r["telegram_chat_id"] for r in rows]
    finally:
        await _close(conn)


# ── dedup ─────────────────────────────────────────────────────────

async def ja_visto(source_id: str, path: str = DB_PATH) -> bool:
    """Retorna True se o source_id já foi registrado. Se não, registra e retorna False."""
    conn = await _get_conn()
    try:
        if USE_PG:
            row = await conn.fetch("SELECT 1 FROM sinais_vistos WHERE source_id = $1", source_id)
        else:
            cursor = await conn.execute("SELECT 1 FROM sinais_vistos WHERE source_id = ?", (source_id,))
            row = await cursor.fetchall()
        if row:
            return True
        await _execute(conn,
            "INSERT INTO sinais_vistos (source_id, visto_em) VALUES ($1, $2)" if USE_PG
            else "INSERT INTO sinais_vistos (source_id, visto_em) VALUES (?, ?)",
            (source_id, _agora()),
        )
        await _commit(conn)
        return False
    finally:
        await _close(conn)


# ── sessões de plataforma (tokens) ───────────────────────────────

async def salvar_sessao(plataforma: str, tokens: dict, path: str = DB_PATH) -> None:
    """Persiste os tokens de autenticação de uma plataforma."""
    conn = await _get_conn()
    try:
        dados = json.dumps(tokens)
        agora = _agora()
        if USE_PG:
            await conn.execute("""
                INSERT INTO sessoes_plataforma (plataforma, tokens_json, atualizado_em)
                VALUES ($1, $2, $3)
                ON CONFLICT(plataforma) DO UPDATE SET
                    tokens_json = EXCLUDED.tokens_json,
                    atualizado_em = EXCLUDED.atualizado_em
            """, plataforma, dados, agora)
        else:
            await conn.execute("""
                INSERT INTO sessoes_plataforma (plataforma, tokens_json, atualizado_em)
                VALUES (?, ?, ?)
                ON CONFLICT(plataforma) DO UPDATE SET
                    tokens_json = excluded.tokens_json,
                    atualizado_em = excluded.atualizado_em
            """, (plataforma, dados, agora))
        await _commit(conn)
    finally:
        await _close(conn)


async def ler_sessao(plataforma: str, path: str = DB_PATH) -> Optional[dict]:
    """Recupera os tokens de uma plataforma, ou None."""
    conn = await _get_conn()
    try:
        if USE_PG:
            rows = await _fetchall(conn,
                "SELECT tokens_json FROM sessoes_plataforma WHERE plataforma = $1",
                (plataforma,)
            )
        else:
            rows = await _fetchall(conn,
                "SELECT tokens_json FROM sessoes_plataforma WHERE plataforma = ?",
                (plataforma,)
            )
        if not rows:
            return None
        return json.loads(rows[0]["tokens_json"])
    finally:
        await _close(conn)


# ── utilitário ────────────────────────────────────────────────────

async def executar(sql: str, params=()) -> None:
    """Executa SQL genérico (INSERT/UPDATE/DELETE)."""
    conn = await _get_conn()
    try:
        await _execute(conn, sql, params)
        await _commit(conn)
    finally:
        await _close(conn)


async def buscar(sql: str, params=()) -> list:
    """Executa SELECT genérico."""
    conn = await _get_conn()
    try:
        return await _fetchall(conn, sql, params)
    finally:
        await _close(conn)