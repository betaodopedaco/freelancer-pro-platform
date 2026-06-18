"""
makita/processamento/filtro.py
================================
Consome sinais da fila e decide o que vale a pena
entregar. O que passar pelo filtro vai para a fila
de aprovados.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from makita.comum.modelos import SinalBruto
from makita.comum.fila import publicar, consumir, tamanho

log = logging.getLogger("filtro")

# ── palavras que indicam intenção de compra ──────────────────────

PALAVRAS_INTENCAO = {
    "preciso", "procuro", "busco", "quero",
    "need", "looking", "hire", "want", "searching",
    "precisando", "procurando", "necessito",
}

# ── palavras que indicam vendedor (anti-filtro) ──────────────────

PALAVRAS_VENDEDOR = {
    "portfolio", "portfólio", "portifolio",
    "freelancer", "freela",
    "i do", "eu faço", "ofereço",
    "disponível", "disponivel",
    "contrate", "hiring myself",
}


def _ttl_expirado(sinal: SinalBruto) -> bool:
    """Se valido_ate está preenchido e já passou, descarta."""
    if not sinal.valido_ate:
        return False
    try:
        limite = datetime.fromisoformat(sinal.valido_ate)
        return limite < datetime.now(timezone.utc)
    except Exception:
        return False


def _muito_curto(sinal: SinalBruto) -> bool:
    """Texto menor que 50 caracteres? Descarta."""
    return len(sinal.texto.strip()) < 50


def _tem_intencao(sinal: SinalBruto) -> bool:
    """Texto contém pelo menos uma palavra de intenção?"""
    texto_lower = sinal.texto.lower()
    for palavra in PALAVRAS_INTENCAO:
        if palavra in texto_lower:
            return True
    return False


def _anti_vendedor(sinal: SinalBruto) -> bool:
    """Texto contém palavra de vendedor? Descarta."""
    texto_lower = sinal.texto.lower()
    for palavra in PALAVRAS_VENDEDOR:
        if palavra in texto_lower:
            return True
    return False


def _aplicar_filtros(sinal: SinalBruto) -> tuple[bool, str]:
    """
    Aplica regras de filtro em ordem.
    Retorna (aprovado, motivo_rejeicao).
    """
    # 1. TTL
    if _ttl_expirado(sinal):
        return False, "TTL expirado"

    # 2. Tamanho mínimo
    if _muito_curto(sinal):
        return False, "texto < 50 chars"

    # 3. Intenção de compra
    if not _tem_intencao(sinal):
        return False, "sem intenção de compra"

    # 4. Anti-vendedor
    if _anti_vendedor(sinal):
        return False, "anti-vendedor ativado"

    return True, ""


# ── loop principal ────────────────────────────────────────────────

async def loop_filtro() -> None:
    """
    Consome sinais da fila principal e publica aprovados
    na fila de aprovados.
    """
    log.info("Filtro iniciado. Aguardando sinais...")

    while True:
        sinal = await consumir()
        if sinal is None:
            await asyncio.sleep(1)
            continue

        aprovado, motivo = _aplicar_filtros(sinal)

        if not aprovado:
            log.debug(f"Rejeitado [{motivo}]: {sinal.source_id} — {sinal.texto[:60]}...")
            continue

        log.info(f"Aprovado: {sinal.plataforma}/{sinal.source_id} — {sinal.texto[:80]}...")

        # Publica na fila de aprovados (prefixo "aprovado_")
        sinal_aprovado = SinalBruto(
            plataforma=sinal.plataforma,
            source_id=sinal.source_id,
            texto=sinal.texto,
            url=sinal.url,
            autor=sinal.autor,
            palavra_chave=sinal.palavra_chave,
            usuario_id=sinal.usuario_id,
            publicado_em=sinal.publicado_em,
            valido_ate=sinal.valido_ate,
        )
        await publicar_aprovado(sinal_aprovado)


# ── fila de aprovados COMPARTILHADA ──────────────────────────────
# Usa deque global em vez de atributo de função
from collections import deque

_fila_aprovados_memoria: deque[SinalBruto] = deque(maxlen=5000)


async def publicar_aprovado(sinal: SinalBruto) -> None:
    """Publica sinal aprovado na fila de saída."""
    import json
    import os

    dados = {
        "plataforma": sinal.plataforma,
        "source_id": sinal.source_id,
        "texto": sinal.texto,
        "url": sinal.url,
        "autor": sinal.autor,
        "palavra_chave": sinal.palavra_chave,
        "usuario_id": sinal.usuario_id,
        "publicado_em": sinal.publicado_em,
        "valido_ate": sinal.valido_ate,
    }

    # Tenta Redis primeiro
    try:
        import redis.asyncio as aioredis
        redis_url = os.environ.get("REDIS_URL", "")
        if redis_url:
            r = aioredis.from_url(redis_url, decode_responses=True)
            await r.lpush("makita:fila_aprovados", json.dumps(dados, ensure_ascii=False))
            return
    except Exception:
        pass

    # Fallback em memória (deque global)
    _fila_aprovados_memoria.appendleft(sinal)


async def consumir_aprovado() -> Optional[SinalBruto]:
    """Consome um sinal da fila de aprovados."""
    import json
    import os

    # Tenta Redis primeiro
    try:
        import redis.asyncio as aioredis
        redis_url = os.environ.get("REDIS_URL", "")
        if redis_url:
            r = aioredis.from_url(redis_url, decode_responses=True)
            raw = await r.rpop("makita:fila_aprovados")
            if raw:
                dados = json.loads(raw)
                return SinalBruto(**dados)
    except Exception:
        pass

    # Fallback em memória (mesmo deque global)
    if not _fila_aprovados_memoria:
        return None
    return _fila_aprovados_memoria.pop()


async def tamanho_aprovados() -> int:
    """Quantos sinais aprovados estão esperando."""
    import os
    try:
        import redis.asyncio as aioredis
        redis_url = os.environ.get("REDIS_URL", "")
        if redis_url:
            r = aioredis.from_url(redis_url, decode_responses=True)
            return await r.llen("makita:fila_aprovados")
    except Exception:
        pass
    return len(_fila_aprovados_memoria)
