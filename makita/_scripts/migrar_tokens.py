"""Migra tokens do banco antigo tofinder.db para o novo makita.db."""
import asyncio, json, aiosqlite
from makita.comum.db import init_db, salvar_sessao

async def main():
    await init_db()
    try:
        async with aiosqlite.connect("tofinder.db") as old:
            rows = await old.execute_fetchall(
                "SELECT tokens FROM platform_sessions WHERE platform='facebook'"
            )
            if rows:
                tokens = json.loads(rows[0][0])
                await salvar_sessao("facebook", tokens)
                print(f"Tokens migrados. fb_dtsg={tokens.get('fb_dtsg','')[:20]}...")
            else:
                print("Nenhum token no banco antigo")
    except Exception as e:
        print(f"Erro ao migrar: {e}")

asyncio.run(main())