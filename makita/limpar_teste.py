"""
Remove o usuário/keyword fictício 999_test do banco real.
"""
import asyncio
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from makita.comum.db import DB_PATH

_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env):
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


async def limpar():
    import aiosqlite
    if not os.path.exists(DB_PATH):
        print(f"DB não encontrado: {DB_PATH}")
        return

    async with aiosqlite.connect(DB_PATH) as db:
        # Buscar IDs de 999_test
        rows = await db.execute_fetchall(
            "SELECT id FROM usuarios WHERE telegram_chat_id = '999_test'"
        )
        ids = [r[0] for r in rows]

        if not ids:
            print("Nenhum 999_test encontrado no banco.")
            return

        for uid in ids:
            await db.execute(
                "DELETE FROM palavras_chave WHERE usuario_id = ?", (uid,)
            )
        await db.execute(
            "DELETE FROM usuarios WHERE telegram_chat_id = '999_test'"
        )
        await db.commit()
        print(f"Removido 999_test: {len(ids)} usuário(s), keywords apagadas.")

        # Mostrar estado final
        rows = await db.execute_fetchall("SELECT telegram_chat_id FROM usuarios")
        print(f"Usuários restantes: {[r[0] for r in rows]}")


if __name__ == "__main__":
    asyncio.run(limpar())