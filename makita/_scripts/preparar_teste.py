"""
Prepara o ambiente para o teste completo do Makita.
Adiciona palavras com intenção de compra e configura chat de teste.
"""
import asyncio, logging, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)

from makita.comum.db import init_db, DB_PATH
import aiosqlite

CHAT_ID_TESTE = os.environ.get("TELEGRAM_CHAT_ID", "999_test")

async def main():
    print("=" * 60)
    print("MAKITA — Preparar ambiente de teste")
    print("=" * 60)

    await init_db()

    async with aiosqlite.connect(DB_PATH) as db:
        # Usuário de teste (ou usa do .env)
        rows = await db.execute_fetchall(
            "SELECT id, telegram_chat_id, plano, max_keywords FROM usuarios WHERE telegram_chat_id = ?",
            (CHAT_ID_TESTE,)
        )
        if rows:
            uid = rows[0][0]
            print(f"Usuário encontrado: {rows[0][1]} (plano: {rows[0][2]}, max: {rows[0][3]})")
        else:
            await db.execute(
                "INSERT INTO usuarios (telegram_chat_id, ativo, plano, max_keywords, criado_em) "
                "VALUES (?, 1, 'pro', 20, ?)",
                (CHAT_ID_TESTE, "2025-01-01T00:00:00Z"),
            )
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT id FROM usuarios WHERE telegram_chat_id = ?", (CHAT_ID_TESTE,)
            )
            uid = rows[0][0]
            print(f"Usuário criado: {CHAT_ID_TESTE} (plano pro, 20 palavras)")

        # Palavras de teste com intenção de compra
        palavras_teste = [
            "logo design",
            "need a designer",
            "looking for a logo",
            "preciso de um designer",
        ]

        adicionadas = 0
        for p in palavras_teste:
            try:
                await db.execute(
                    "INSERT INTO palavras_chave (usuario_id, palavra, ativa, criado_em) VALUES (?, ?, 1, ?)",
                    (uid, p.lower().strip(), "2025-01-01T00:00:00Z"),
                )
                adicionadas += 1
                print(f"  + {p}")
            except Exception:
                print(f"  = {p} (já existe)")

        await db.commit()

    print(f"\n✅ {adicionadas} novas palavras adicionadas.")
    print(f"Total de palavras ativas para '{CHAT_ID_TESTE}': pronto para teste.")
    print(f"\nAgora execute: python makita/main.py")
    print(f"Deixe rodar por 3 minutos para testar o fluxo completo.")

if __name__ == "__main__":
    asyncio.run(main())