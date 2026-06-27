"""
makita — orquestrador principal
=================================
Inicia todos os 5 coletores + filtro + entregador +
backup (com expurgo e Telegram) + saude (vigia) +
healthcheck HTTP + renovação automática de tokens FB.
"""
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("makita")

from makita.comum.db import init_db
from makita.coletores.facebook.dom import colect_facebook
from makita.coletores.twitter.adaptador import colect_twitter
from makita.coletores.reddit.adaptador import colect_reddit
from makita.coletores.bluesky.adaptador import colect_bluesky
from makita.coletores.hn.adaptador import colect_hn
from makita.processamento.filtro import loop_filtro
from makita.processamento.entregador import loop_entregador
from makita.comum.backup import loop_backup
from makita.comum.saude import loop_saude
from makita.comum.healthcheck import start_healthcheck_thread

from makita.entrega.bot import loop_bot


async def main():
    log.info("=" * 50)
    log.info("  MAKITA — todos os 5 coletores + infra + bot Telegram")
    log.info("  Facebook | Twitter | Reddit | Bluesky | HN")
    log.info("  + Filtro + Entregador + Backup/Expurgo/Telegram")
    log.info("  + Saúde + Healthcheck HTTP + Renovação FB + Bot Telegram")
    log.info("=" * 50)

    await init_db()

    # Healthcheck em thread separada — NUNCA trava o event loop
    start_healthcheck_thread()

    log.info("Disparando todos os loops concorrentemente...")
    await asyncio.gather(
        colect_facebook(),
        colect_twitter(),
        colect_reddit(),
        colect_bluesky(),
        colect_hn(),
        loop_filtro(),
        loop_entregador(),
        loop_backup(),       # backup 6h + expurgo 24h + envio Telegram
        loop_saude(),        # health check interno
        # loop_healthcheck() REMOVIDO — agora é thread separada (start_healthcheck_thread)

        loop_bot(),          # bot Telegram — comandos /start, /add, /list, etc
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Makita encerrado pelo usuário.")
    except Exception as e:
        log.error(f"Erro fatal: {e}")
        raise