"""
makita — bot Telegram
======================
Autenticação com invite code, gestão de palavras-chave
e limites por plano. Conectado ao banco via db.py
(SQLite local ou PostgreSQL via DATABASE_URL).
"""

import asyncio
import os
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from makita.comum.db import (
    init_db,
    get_palavras_ativas,
    get_chat_ids_por_palavra,
    ja_visto,
    salvar_sessao,
    ler_sessao,
    DB_PATH,
    executar,
    buscar,
)

# ── logging ───────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("bot")


# ── constantes ────────────────────────────────────────────────────

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
INVITE_CODES_ENV = os.environ.get(
    "INVITE_CODES",
    "MAKITA001,MAKITA002,MAKITA003,MAKITA004,MAKITA005,"
    "MAKITA006,MAKITA007,MAKITA008,MAKITA009,MAKITA010",
)
INVITE_CODES = {c.strip() for c in INVITE_CODES_ENV.split(",") if c.strip()}
USED_CODES: set[str] = set()  # códigos já usados (runtime + persistido)

LIMITES_PLANO = {
    "free": 3,
    "pro": 20,
}


# ── helpers ───────────────────────────────────────────────────────

def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extrair_codigo(texto: str) -> str | None:
    """Extrai código de invite do texto do comando."""
    partes = texto.strip().split(maxsplit=1)
    if len(partes) == 2:
        return partes[1].strip()
    return None


async def _get_usuario(chat_id: str) -> dict | None:
    """Retorna dados do usuario ou None."""
    rows = await buscar(
        "SELECT * FROM usuarios WHERE telegram_chat_id = $1",
        (chat_id,)
    )
    if not rows:
        return None
    row = rows[0]
    return {
        "id": row["id"],
        "telegram_chat_id": row["telegram_chat_id"],
        "ativo": row["ativo"],
        "plano": row["plano"],
        "max_keywords": row["max_keywords"],
    }


async def _contar_palavras(usuario_id: int) -> int:
    """Conta palavras ativas de um usuário."""
    rows = await buscar(
        "SELECT COUNT(*) as total FROM palavras_chave WHERE usuario_id = $1 AND ativa = 1",
        (usuario_id,)
    )
    return rows[0]["total"] if rows else 0


async def _listar_palavras(usuario_id: int) -> list[str]:
    """Lista palavras ativas de um usuário."""
    rows = await buscar(
        "SELECT palavra FROM palavras_chave WHERE usuario_id = $1 AND ativa = 1 ORDER BY palavra",
        (usuario_id,)
    )
    return [r["palavra"] for r in rows]


# ── comandos ──────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start [codigo] — autentica com invite code e cria usuário."""
    chat_id = str(update.effective_chat.id)
    args = context.args
    codigo = args[0] if args else None

    # Já cadastrado?
    usuario = await _get_usuario(chat_id)
    if usuario:
        await update.message.reply_text(
            f"👋 Bem-vindo de volta!\n"
            f"Plano: {usuario['plano']} | "
            f"Palavras: {usuario['max_keywords']}\n\n"
            f"Comandos:\n"
            f"/add <palavra> — adicionar\n"
            f"/remove <palavra> — remover\n"
            f"/list — listar ativas\n"
            f"/ping — teste de vida"
        )
        return

    # Precisa de código
    if not codigo:
        await update.message.reply_text(
            "🔑 Para usar o Makita, você precisa de um código de convite.\n\n"
            "Use: /start SEU_CODIGO\n\n"
            "Se não tem um código, peça para o administrador."
        )
        return

    # Valida código
    codigo = codigo.upper()
    if codigo not in INVITE_CODES:
        await update.message.reply_text(
            "❌ Código de convite inválido.\n"
            "Verifique se digitou corretamente ou peça um novo código."
        )
        return

    if codigo in USED_CODES:
        await update.message.reply_text(
            "❌ Este código de convite já foi usado."
        )
        return

    # Cria usuário
    USED_CODES.add(codigo)
    await executar(
        "INSERT INTO usuarios (telegram_chat_id, ativo, plano, max_keywords, criado_em) "
        "VALUES ($1, 1, 'free', 3, $2)",
        (chat_id, _agora()),
    )

    await update.message.reply_text(
        "✅ Conta criada com sucesso!\n"
        "Plano: free (3 palavras)\n\n"
        "Comandos:\n"
        "/add <palavra> — monitorar nova palavra\n"
        "/remove <palavra> — parar de monitorar\n"
        "/list — ver suas palavras\n"
        "/ping — teste de vida"
    )


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/add <palavra> — adiciona palavra-chave."""
    chat_id = str(update.effective_chat.id)
    usuario = await _get_usuario(chat_id)
    if not usuario:
        await update.message.reply_text(
            "❌ Você precisa se autenticar primeiro.\n"
            "Use /start SEU_CODIGO"
        )
        return

    palavra = " ".join(context.args) if context.args else ""
    if not palavra:
        await update.message.reply_text(
            "Uso: /add <palavra>\n"
            "Exemplo: /add iPhone 15"
        )
        return

    # Verifica limite
    total = await _contar_palavras(usuario["id"])
    limite = usuario["max_keywords"]
    if total >= limite:
        await update.message.reply_text(
            f"⚠️ Limite do seu plano atingido ({limite} palavras).\n"
            f"Remova alguma antes de adicionar ou faça upgrade do plano."
        )
        return

    # Tenta inserir
    try:
        await executar(
            "INSERT INTO palavras_chave (usuario_id, palavra, ativa, criado_em) "
            "VALUES ($1, $2, 1, $3)",
            (usuario["id"], palavra.lower().strip(), _agora()),
        )
        await update.message.reply_text(
            f"✅ '{palavra}' adicionada!\n"
            f"({total + 1}/{limite} palavras usadas)"
        )
    except Exception:
        await update.message.reply_text(
            f"⚠️ Você já monitora '{palavra}'."
        )


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/remove <palavra> — remove palavra-chave."""
    chat_id = str(update.effective_chat.id)
    usuario = await _get_usuario(chat_id)
    if not usuario:
        await update.message.reply_text(
            "❌ Use /start SEU_CODIGO primeiro."
        )
        return

    palavra = " ".join(context.args) if context.args else ""
    if not palavra:
        await update.message.reply_text("Uso: /remove <palavra>")
        return

    await executar(
        "UPDATE palavras_chave SET ativa = 0 "
        "WHERE usuario_id = $1 AND palavra = $2 AND ativa = 1",
        (usuario["id"], palavra.lower().strip()),
    )

    await update.message.reply_text(f"❌ '{palavra}' removida.")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/list — lista palavras-chave ativas."""
    chat_id = str(update.effective_chat.id)
    usuario = await _get_usuario(chat_id)
    if not usuario:
        await update.message.reply_text(
            "❌ Use /start SEU_CODIGO primeiro."
        )
        return

    palavras = await _listar_palavras(usuario["id"])
    if not palavras:
        await update.message.reply_text(
            "📭 Nenhuma palavra configurada.\n"
            "Use /add <palavra> para começar."
        )
        return

    limite = usuario["max_keywords"]
    texto = f"📋 Suas palavras ({len(palavras)}/{limite}):\n\n"
    texto += "\n".join(f"• {p}" for p in palavras)
    await update.message.reply_text(texto)


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/ping — teste de vida."""
    chat_id = update.effective_chat.id if update.effective_chat else "unknown"
    log.info("PING RECEBIDO de chat_id=%s", chat_id)
    await update.message.reply_text("funcionando")


# ── loop async para rodar junto com main.py ──────────────────────

async def loop_bot() -> None:
    """
    Loop async do bot Telegram para rodar concorrentemente no asyncio.gather().
    Usa a API assíncrona do python-telegram-bot v20+:
      initialize() → start() → updater.start_polling() → mantém vivo.
    """
    if not TOKEN:
        log.error("TELEGRAM_TOKEN não definido. Bot desligado.")
        return

    await init_db()

    log.info(
        "Bot Telegram iniciando (async) | %d códigos de convite disponíveis",
        len(INVITE_CODES),
    )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("ping", cmd_ping))

    # Wrapper para logar todo update recebido
    original_process_update = app.process_update

    async def logged_process_update(update: Update) -> None:
        if update.effective_message:
            log.info(
                "UPDATE RECEBIDO | chat_id=%s tipo=%s texto=%r",
                update.effective_chat.id if update.effective_chat else "unknown",
                update.effective_message.chat.type if update.effective_message else "unknown",
                update.effective_message.text if update.effective_message else "(sem texto)",
            )
        else:
            log.info("UPDATE RECEBIDO | (sem effective_message)")
        await original_process_update(update)

    app.process_update = logged_process_update

    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    log.info("Bot Telegram em polling — ouvindo comandos...")

    # Mantém vivo para não fechar o loop
    try:
        while True:
            await asyncio.sleep(60)
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


# ── main loop síncrono (para execução separada) ──────────────────

def main() -> None:
    """Inicializa banco, verifica configuração e sobe o bot (modo síncrono)."""
    if not TOKEN:
        log.error("TELEGRAM_TOKEN não definido no .env")
        return

    # Garante que tabelas existem
    asyncio.run(init_db())

    log.info(
        "Makita bot iniciado | %d códigos de convite disponíveis",
        len(INVITE_CODES),
    )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("ping", cmd_ping))

    # Wrapper para logar todo update recebido
    original_process_update = app.process_update

    async def logged_process_update(update: Update) -> None:
        if update.effective_message:
            log.info(
                "UPDATE RECEBIDO | chat_id=%s tipo=%s texto=%r",
                update.effective_chat.id if update.effective_chat else "unknown",
                update.effective_message.chat.type if update.effective_message else "unknown",
                update.effective_message.text if update.effective_message else "(sem texto)",
            )
        else:
            log.info("UPDATE RECEBIDO | (sem effective_message)")
        await original_process_update(update)

    app.process_update = logged_process_update

    log.info("Polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()