"""
makita — backup automático do banco
====================================
VACUUM INTO do SQLite a cada 6h e envia o arquivo
como documento para o ADMIN_CHAT_ID no Telegram.
Expurga registros de sinais_vistos com mais de 90 dias.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta

log = logging.getLogger("backup")

BACKUP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backups"
)
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "makita.db"
)
INTERVALO = 6 * 3600  # 6 horas
EXPURGO_INTERVALO = 86400  # 1 dia
MAX_BACKUPS = 7

_admin_chat_id = os.environ.get("ADMIN_CHAT_ID", "")
_token = os.environ.get("TELEGRAM_TOKEN", "")


async def _enviar_backup_telegram(caminho: str) -> bool:
    """Envia arquivo de backup como documento para o admin no Telegram."""
    if not _admin_chat_id or not _token:
        log.warning("ADMIN_CHAT_ID ou TELEGRAM_TOKEN não configurados "
                     "— backup externo desativado.")
        return False

    try:
        from telegram import Bot, InputFile

        bot = Bot(token=_token)
        with open(caminho, "rb") as f:
            await bot.send_document(
                chat_id=_admin_chat_id,
                document=InputFile(f, filename=os.path.basename(caminho)),
                caption=f"📦 Backup automático — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
            )
        log.info(f"Backup enviado para Telegram admin: {caminho}")
        return True
    except Exception as e:
        log.error(f"Erro ao enviar backup para Telegram: {e}")
        return False


async def _expurgar_sinais_vistos() -> None:
    """
    Remove registros de sinais_vistos com mais de 90 dias.
    Executa 1x ao dia junto com o backup.
    """
    try:
        from makita.comum.db import executar
        from makita.comum.db import USE_PG

        corte = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

        if USE_PG:
            sql = "DELETE FROM sinais_vistos WHERE visto_em < $1"
        else:
            sql = "DELETE FROM sinais_vistos WHERE visto_em < ?"

        await executar(sql, (corte,))
        log.info(f"Expurgo: registros anteriores a {corte[:10]} removidos.")
    except Exception as e:
        log.error(f"Erro no expurgo de sinais_vistos: {e}")


async def _fazer_backup() -> None:
    """Faz VACUUM INTO do SQLite e envia para Telegram."""
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)

        if not os.path.exists(DB_PATH):
            log.warning(f"DB não encontrado: {DB_PATH}")
            return

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome = f"makita_{ts}.db"
        destino = os.path.join(BACKUP_DIR, nome)

        # VACUUM INTO para backup consistente
        import aiosqlite
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(f"VACUUM INTO '{destino}'")
            log.info(f"Backup VACUUM: {destino}")
        except Exception:
            import shutil
            shutil.copy2(DB_PATH, destino)
            log.info(f"Backup cópia: {destino}")

        # Envia para Telegram
        await _enviar_backup_telegram(destino)

        # Remove backups locais antigos (mantém só MAX_BACKUPS)
        backups = sorted(
            [f for f in os.listdir(BACKUP_DIR)
             if f.startswith("makita_") and f.endswith(".db")]
        )
        while len(backups) > MAX_BACKUPS:
            antigo = backups.pop(0)
            os.remove(os.path.join(BACKUP_DIR, antigo))

        log.info(f"Backups locais mantidos: {len(backups)}/{MAX_BACKUPS}")

    except Exception as e:
        log.error(f"Erro no backup: {e}")


async def loop_backup() -> None:
    """
    Loop infinito que:
    - Faz backup a cada 6h e envia para Telegram
    - Expurga sinais_vistos a cada 24h
    """
    log.info("Backup automático iniciado (6h, Telegram admin).")
    ultimo_expurgo = 0.0

    # Primeiro backup imediato + primeiro expurgo
    await _fazer_backup()
    await _expurgar_sinais_vistos()
    ultimo_expurgo = datetime.now().timestamp()

    while True:
        await asyncio.sleep(INTERVALO)
        await _fazer_backup()

        # Expurgo a cada 24h
        agora = datetime.now().timestamp()
        if agora - ultimo_expurgo >= EXPURGO_INTERVALO:
            await _expurgar_sinais_vistos()
            ultimo_expurgo = agora