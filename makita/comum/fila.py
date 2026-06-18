"""
makita — fila de processamento
================================
Redis real com persistência AOF+RDB. Fallback em memória se Redis cair.
Estísticas de publicação por coletor para o health check.
"""

import json
import os
import time
import logging
from collections import deque
from typing import Optional

from makita.comum.modelos import SinalBruto

log = logging.getLogger("fila")

# ── Redis ──────────────────────────────────────────────────────────

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

REDIS_URL = os.environ.get("REDIS_URL", "")

# Pool de conexão reutilizável
_pool: Optional["aioredis.Redis"] = None


async def _get_redis() -> Optional["aioredis.Redis"]:
    """Retorna conexão Redis do pool, criando se necessário."""
    global _pool
    if not REDIS_AVAILABLE or not REDIS_URL:
        return None
    if _pool is None:
        try:
            _pool = aioredis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_keepalive=True,
                retry_on_timeout=True,
            )
            # Testa a conexão
            await _pool.ping()
            log.info(f"Redis conectado: {REDIS_URL}")
        except Exception as e:
            log.warning(f"Redis indisponível: {e}")
            _pool = None
            return None
    # Verifica se ainda está vivo
    try:
        await _pool.ping()
        return _pool
    except Exception:
        log.warning("Redis caiu, reconectando...")
        _pool = None
        return await _get_redis()


# ── Estatísticas (para health check) ───────────────────────────────

_stats: dict[str, dict] = {}  # {"facebook": {"count": 10, "last": 1234567890}, ...}

def _registrar_publicacao(plataforma: str) -> None:
    """Registra que um coletor publicou algo."""
    agora = time.time()
    if plataforma not in _stats:
        _stats[plataforma] = {"count": 0, "last": 0.0, "total": 0}
    _stats[plataforma]["count"] += 1
    _stats[plataforma]["total"] += 1
    _stats[plataforma]["last"] = agora


def obter_stats() -> dict:
    """Retorna stats das publicações para o health check."""
    agora = time.time()
    resultado = {}
    for plat, info in _stats.items():
        resultado[plat] = {
            "count": info["count"],
            "total": info["total"],
            "last": info["last"],
            "idle_seg": round(agora - info["last"], 1) if info["last"] > 0 else None,
        }
    return resultado


def resetar_stats_janela() -> dict:
    """Reseta contadores de janela e retorna os valores anteriores."""
    antigos = {}
    for plat, info in _stats.items():
        antigos[plat] = {
            "count": info["count"],
            "last": info["last"],
        }
        info["count"] = 0  # Reseta só o contador da janela
    return antigos


# ── API pública — Redis OBRIGATÓRIO ────────────────

_redis_falhou = False


async def publicar(sinal: SinalBruto) -> None:
    """Coloca um SinalBruto na fila Redis. CRÍTICO se Redis offline."""
    global _redis_falhou
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

    r = await _get_redis()
    if r is None:
        _redis_falhou = True
        log.critical("REDIS INDISPONÍVEL — fila parada. "
                     "Sinais não serão processados até Redis reconectar.")
        return

    try:
        pipe = r.pipeline()
        pipe.lpush("makita:fila", json.dumps(dados, ensure_ascii=False))
        pipe.incr("makita:stats:total")
        pipe.incr(f"makita:stats:{sinal.plataforma}")
        await pipe.execute()
        _registrar_publicacao(sinal.plataforma)
        if _redis_falhou:
            _redis_falhou = False
            log.info("Redis reconectado — fila voltou a operar.")
    except Exception as e:
        _redis_falhou = True
        log.critical(f"Redis erro ao publicar: {e} — "
                     f"sinal {sinal.source_id} PERDIDO.")


async def consumir() -> Optional[SinalBruto]:
    """Retira um sinal da fila. Retorna None se vazia ou Redis offline."""
    r = await _get_redis()
    if r is None:
        return None
    try:
        raw = await r.rpop("makita:fila")
        if raw is None:
            return None
        dados = json.loads(raw)
        return SinalBruto(**dados)
    except Exception as e:
        log.error(f"Redis erro no consumo: {e}")
        return None


async def tamanho() -> int:
    """Quantos sinais estão esperando na fila Redis."""
    r = await _get_redis()
    if r is None:
        return 0
    try:
        return await r.llen("makita:fila")
    except Exception:
        return 0
