"""
makita/processamento/entregador.py
====================================
Pega sinais aprovados e entrega no Telegram
para cada usuário que monitora a palavra-chave.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

from telegram import Bot

from makita.comum.db import get_chat_ids_por_palavra
from makita.processamento.filtro import consumir_aprovado, tamanho_aprovados
from makita.comum.modelos import SinalBruto
from makita.comum.saude import registrar_falha_telegram, registrar_sucesso_telegram

log = logging.getLogger("entregador")

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

# Rate limit: 1 mensagem por segundo (Telegram permite ~30/seg, mas segurança)
MSG_INTERVAL = 1.0


def _minutos_desde(publicado_em: str) -> str:
    """Calcula há quantos minutos o sinal foi publicado."""
    try:
        pub = datetime.fromisoformat(publicado_em)
        agora = datetime.now(timezone.utc)
        diff = agora - pub
        minutos = int(diff.total_seconds() / 60)
        if minutos < 1:
            return "menos de 1 minuto"
        if minutos == 1:
            return "1 minuto"
        if minutos < 60:
            return f"{minutos} minutos"
        horas = int(minutos / 60)
        return f"{horas} hora(s)"
    except Exception:
        return "recentemente"


def _montar_mensagem(sinal: SinalBruto) -> str:
    """Monta a mensagem formatada para o Telegram."""
    texto_curto = sinal.texto[:300]
    if len(sinal.texto) > 300:
        texto_curto += "..."

    sugestao = (
        f'Vi seu post sobre {sinal.palavra_chave}. '
        f'Já tem briefing ou ainda está definindo?'
    )

    tempo = _minutos_desde(sinal.publicado_em)

    msg = (
        f"🔔 Nova oportunidade — {sinal.plataforma}\n\n"
        f'"{texto_curto}"\n\n'
        f"💬 Sugestão:\n"
        f'"{sugestao}"\n\n'
        f"🔗 {sinal.url}\n"
        f"⏳ Publicado há {tempo}"
    )
    return msg


async def _enviar_para_usuarios(
    bot: Bot, sinal: SinalBruto
) -> int:
    """
    Envia o sinal para todos os usuários que monitoram a palavra.
    Retorna quantos receberam.
    """
    chat_ids = await get_chat_ids_por_palavra(sinal.palavra_chave)
    if not chat_ids:
        log.debug(
            f"Ninguém monitora '{sinal.palavra_chave}'. "
            f"Sinal {sinal.source_id} descartado para entrega."
        )
        return 0

    mensagem = _montar_mensagem(sinal)
    entregues = 0

    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id=chat_id, text=mensagem)
            entregues += 1
            registrar_sucesso_telegram()
            log.info(
                f"✅ Entregue para {chat_id}: "
                f"{sinal.plataforma}/{sinal.palavra_chave}"
            )
        except Exception as e:
            registrar_falha_telegram()
            log.error(f"Falha ao entregar para {chat_id}: {e}")

        # Rate limit
        await asyncio.sleep(MSG_INTERVAL)

    return entregues


# ── loop principal ────────────────────────────────────────────────

async def loop_entregador() -> None:
    """
    Consome sinais aprovados e entrega no Telegram.
    """
    if not TOKEN:
        log.error("TELEGRAM_TOKEN não definido. Entregador desligado.")
        return

    bot = Bot(token=TOKEN)
    log.info("Entregador iniciado. Aguardando sinais aprovados...")

    while True:
        sinal = await consumir_aprovado()
        if sinal is None:
            await asyncio.sleep(1)
            continue

        entregues = await _enviar_para_usuarios(bot, sinal)
        log.info(
            f"📨 Sinal {sinal.source_id}: "
            f"{entregues} entrega(s), "
            f"palavra '{sinal.palavra_chave}'"
        )

        # Pequena pausa entre sinais diferentes
        await asyncio.sleep(0.5)