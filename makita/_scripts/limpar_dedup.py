"""Limpa tabela de dedup para novo teste."""
import asyncio
from makita.comum.db import init_db, DB_PATH
import aiosqlite

async def main():
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sinais_vistos")
        await db.commit()
    print("Dedup limpo. Pronto para novo teste.")

asyncio.run(main())