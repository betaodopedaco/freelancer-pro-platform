"""
makita — health check / vigia
===============================
Verifica a cada 5 minutos se cada coletor está publicando.
Se algum ficar 2 ciclos sem publicar, loga alerta CRÍTICO.
Se o Telegram entregador falhar 3 vezes seguidas, alerta CRÍTICO.
Alertas CRÍTICOS também são enviados para ADMIN_CHAT_ID no Telegram.
"""

import asyncio
import logging
import os
import time

log = logging.getLogger("saude")

INTERVALO = 5 * 60  # 5 minutos
JANELA = 2  # ciclos sem publicar = alerta
FALHA_TELEGRAM_LIMITE = 3

# Contador de falhas do Telegram
_falhas_telegram = 0
_ultima_falha_telegram = 0.0

# Coletores esperados
COLETORES = ["facebook", "twitter", "reddit", "bluesky", "hn"]

# Histórico de janelas
_janela_anterior: dict = {}

# Bot do Telegram para alertas admin
_bot = None
_admin_chat_id = os.environ.get("ADMIN_CHAT_ID", "")
_token = os.environ.get("TELEGRAM_TOKEN", "")


def _get_bot():
    """Retorna o bot do Telegram (lazy init)."""
    global _bot
    if _bot is None and _token:
        from telegram import Bot
        _bot = Bot(token=_token)
    return _bot


async def _enviar_alerta(mensagem: str) -> None:
    """Envia alerta CRÍTICO para o admin no Telegram."""
    if not _admin_chat_id:
        return
    bot = _get_bot()
    if bot is None:
        return
    try:
        await bot.send_message(chat_id=_admin_chat_id, text=f"🔴 ALERTA MAKITA: {mensagem}")
        log.info(f"Alerta enviado para admin: {mensagem[:80]}")
    except Exception as e:
        log.error(f"Falha ao enviar alerta admin: {e}")


def registrar_falha_telegram() -> None:
    """Chamado pelo entregador quando o Telegram falha."""
    global _falhas_telegram, _ultima_falha_telegram
    _falhas_telegram += 1
    _ultima_falha_telegram = time.time()


def registrar_sucesso_telegram() -> None:
    """Chamado pelo entregador quando o Telegram entrega com sucesso."""
    global _falhas_telegram
    _falhas_telegram = 0


async def loop_saude() -> None:
    """Loop infinito de health check."""
    log.info("Health check iniciado (intervalo: 5min).")
    await asyncio.sleep(30)  # Espera 30s para os coletores iniciarem

    while True:
        await asyncio.sleep(INTERVALO)
        await _verificar()


async def _verificar() -> None:
    """Verifica saúde de todos os coletores e do Telegram."""
    from makita.comum.fila import obter_stats, resetar_stats_janela

    stats = obter_stats()
    janela = resetar_stats_janela()

    alertas = []

    # Verificar coletores
    for coletor in COLETORES:
        info = janela.get(coletor, {"count": 0, "last": 0.0})
        count = info["count"]
        last = info["last"]

        if count == 0:
            anterior = _janela_anterior.get(coletor, 0)
            if anterior == 0 and last > 0:
                idle = time.time() - last
                if idle > INTERVALO * JANELA:
                    msg = f"{coletor} sem publicar há {idle/60:.1f}min!"
                    log.critical(f"🔴 ALERTA: {msg}")
                    alertas.append(msg)
            elif anterior == 0 and last == 0:
                log.warning(f"⚠️ {coletor}: sem sinais desde o início.")
        else:
            log.info(f"✅ {coletor}: {count} sinais na janela.")

    _janela_anterior.clear()
    for coletor in COLETORES:
        info = janela.get(coletor, {"count": 0})
        _janela_anterior[coletor] = info["count"]

    # Verificar Telegram
    global _falhas_telegram
    if _falhas_telegram >= FALHA_TELEGRAM_LIMITE:
        msg = f"Telegram falhou {_falhas_telegram} vezes seguidas!"
        log.critical(f"🔴 ALERTA: {msg}")
        alertas.append(msg)

    # Enviar alertas no Telegram
    for alerta in alertas:
        await _enviar_alerta(alerta)

    # Resumo
    total = sum(s.get("count", 0) for s in stats.values())
    log.info(f"📊 Health check: {total} sinais totais, {len(stats)} fontes ativas.")


from datetime import datetime