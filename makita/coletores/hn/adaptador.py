"""
Adaptador do Hacker News (Algolia) para o pipeline Makita.
Polling via HTTP, publica SinalBruto na fila.
"""
import asyncio, hashlib, logging, os
from datetime import datetime, timezone, timedelta

import aiohttp

from makita.comum.db import get_palavras_ativas, ja_visto
from makita.comum.fila import publicar
from makita.comum.modelos import SinalBruto

log = logging.getLogger("hn.adaptador")

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
INTERVALO = int(os.getenv("HN_POLL_INTERVAL", "600"))  # 10 min
SLEEP_ENTRE = 1


async def colect_hn() -> None:
    """Loop principal do HN para o Makita."""
    log.info("HN adaptador iniciado.")
    async with aiohttp.ClientSession() as session:
        while True:
            log.info("HN: polling...")
            try:
                palavras = await get_palavras_ativas()
            except Exception as e:
                log.error(f"HN: erro palavras: {e}")
                await asyncio.sleep(60)
                continue

            if not palavras:
                await asyncio.sleep(60)
                continue

            cutoff = int(
                (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
            )
            total = 0

            for palavra in palavras:
                try:
                    async with session.get(
                        ALGOLIA_URL,
                        params={
                            "query": palavra,
                            "tags": "story,comment",
                            "numericFilters": f"created_at_i>{cutoff}",
                            "hitsPerPage": 10,
                        },
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        hits = data.get("hits", [])

                        for hit in hits:
                            texto = (
                                hit.get("story_text")
                                or hit.get("comment_text")
                                or hit.get("title", "")
                            )
                            if not texto:
                                continue

                            object_id = hit["objectID"]
                            story_id = hit.get("story_id", object_id)
                            source_id = f"hn_{object_id}"

                            if await ja_visto(source_id):
                                continue

                            ts = datetime.fromtimestamp(cutoff, tz=timezone.utc)
                            sinal = SinalBruto(
                                plataforma="hn",
                                source_id=source_id,
                                texto=texto[:800],
                                url=f"https://news.ycombinator.com/item?id={story_id}",
                                autor=hit.get("author", "unknown"),
                                palavra_chave=palavra,
                                usuario_id=0,
                                publicado_em=ts.isoformat(),
                            )
                            await publicar(sinal)
                            total += 1

                except Exception as e:
                    log.error(f"HN erro '{palavra}': {e}")

                await asyncio.sleep(SLEEP_ENTRE)

            log.info(f"HN: {total} novos. Próximo ciclo em {INTERVALO}s.")
            await asyncio.sleep(INTERVALO)