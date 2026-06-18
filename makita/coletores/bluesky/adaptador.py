"""
Adaptador do Bluesky para o pipeline Makita.
WebSocket contínuo, publica SinalBruto na fila.
"""
import asyncio, hashlib, json, logging
from datetime import datetime, timezone

import websockets

from makita.comum.db import get_palavras_ativas, ja_visto
from makita.comum.fila import publicar
from makita.comum.modelos import SinalBruto

log = logging.getLogger("bluesky.adaptador")

WS_URL = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"


async def _atualizar_palavras() -> set:
    """Retorna set de palavras ativas para filtro."""
    try:
        palavras = await get_palavras_ativas()
        return {p.lower() for p in palavras}
    except Exception:
        return set()


async def colect_bluesky() -> None:
    """WebSocket contínuo do Bluesky para o Makita."""
    log.info("Bluesky adaptador iniciado.")
    palavras_ativas: set[str] = set()
    ultima_atualizacao = 0.0

    while True:
        try:
            # Atualiza palavras a cada 60s
            agora = datetime.now(timezone.utc).timestamp()
            if agora - ultima_atualizacao > 60:
                palavras_ativas = await _atualizar_palavras()
                ultima_atualizacao = agora
                log.info(f"Bluesky: {len(palavras_ativas)} palavras ativas")

            if not palavras_ativas:
                await asyncio.sleep(10)
                continue

            async with websockets.connect(
                WS_URL, ping_interval=20, ping_timeout=10, max_size=2**20
            ) as ws:
                log.info("Bluesky conectado.")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        if msg.get("kind") != "commit":
                            continue
                        commit = msg.get("commit", {})
                        if commit.get("operation") != "create":
                            continue
                        record = commit.get("record", {})
                        texto = (record.get("text", "") or "").strip()
                        if not texto or len(texto) < 30:
                            continue

                        texto_lower = texto.lower()
                        palavra_match = ""
                        for p in palavras_ativas:
                            if p in texto_lower:
                                palavra_match = p
                                break
                        if not palavra_match:
                            continue

                        did = msg.get("did", "unknown")
                        rkey = commit.get("rkey", "")
                        source_id = f"bsky_{did}_{rkey}"
                        source_id_hash = "bsky_" + hashlib.md5(
                            source_id.encode()
                        ).hexdigest()[:12]

                        if await ja_visto(source_id_hash):
                            continue

                        sinal = SinalBruto(
                            plataforma="bluesky",
                            source_id=source_id_hash,
                            texto=texto[:800],
                            url=f"https://bsky.app/profile/{did}/post/{rkey}",
                            autor=did,
                            palavra_chave=palavra_match,
                            usuario_id=0,
                            publicado_em=datetime.now(timezone.utc).isoformat(),
                        )
                        await publicar(sinal)
                        log.info(
                            f"Bluesky: sinal {palavra_match} — {texto[:60]}..."
                        )

                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        log.debug(f"Bluesky erro msg: {e}")

        except Exception as e:
            log.error(f"Bluesky reconectando: {e}")
            await asyncio.sleep(5)