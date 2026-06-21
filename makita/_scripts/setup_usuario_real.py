"""
Configura o usuário real 8081681015 com palavras de teste.
Remove dados antigos e prepara para teste no Telegram.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from makita.comum.db import init_db, DB_PATH
import aiosqlite

CHAT_ID = "8081681015"
PALAVRAS = ["preciso de um designer", "logo design", "need a designer"]

async def main():
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        # Limpa dados anteriores do chat
        await db.execute("DELETE FROM sinais_vistos")
        rows = await db.execute_fetchall(
            "SELECT id FROM usuarios WHERE telegram_chat_id = ?", (CHAT_ID,)
        )
        if rows:
            uid = rows[0][0]
            await db.execute("DELETE FROM palavras_chave WHERE usuario_id = ?", (uid,))
            await db.execute("UPDATE usuarios SET ativo = 1 WHERE id = ?", (uid,))
            print(f"Usuário {CHAT_ID} já existia (id={uid}). Palavras resetadas.")
        else:
            await db.execute(
                "INSERT INTO usuarios (telegram_chat_id, ativo, plano, max_keywords, criado_em) "
                "VALUES (?, 1, 'pro', 20, ?)",
                (CHAT_ID, "2025-01-01T00:00:00Z"),
            )
            rows = await db.execute_fetchall(
                "SELECT id FROM usuarios WHERE telegram_chat_id = ?", (CHAT_ID,)
            )
            uid = rows[0][0]
            print(f"Usuário {CHAT_ID} criado (id={uid}, plano pro, 20 palavras)")

        # Adiciona palavras
        for p in PALAVRAS:
            await db.execute(
                "INSERT INTO palavras_chave (usuario_id, palavra, ativa, criado_em) VALUES (?, ?, 1, ?)",
                (uid, p, "2025-01-01T00:00:00Z"),
            )
        await db.commit()

        # Verifica
        palavras = await db.execute_fetchall(
            "SELECT palavra FROM palavras_chave WHERE usuario_id = ? AND ativa = 1",
            (uid,),
        )
        print(f"Palavras configuradas: {[r[0] for r in palavras]}")
        print(f"Total: {len(palavras)} palavras")
        print(f"\nAgora execute: set FB_POLL_INTERVAL=30 && python makita/main.py")
        print(f"Deixe rodar por 5 minutos. O lead chegará no Telegram.")

if __name__ == "__main__":
    asyncio.run(main())