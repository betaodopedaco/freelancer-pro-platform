"""
Seed + teste rápido do coletor Facebook.
Cria 3 palavras de teste, roda um ciclo de coleta e mostra resultados.
"""
import asyncio, logging, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)

from makita.comum.db import init_db, get_palavras_ativas, ja_visto, DB_PATH
from makita.comum.fila import tamanho, consumir
from makita.coletores.facebook.graphql import get_tokens, _search_keyword, _publicar_sinal
import aiosqlite

async def seed_palavras():
    """Insere 3 palavras de teste se não existirem."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Cria usuario de teste (chat_id fixo para teste)
        rows = await db.execute_fetchall(
            "SELECT id FROM usuarios WHERE telegram_chat_id = ?", ("999_test",)
        )
        if not rows:
            await db.execute(
                "INSERT INTO usuarios (telegram_chat_id, ativo, plano, max_keywords, criado_em) "
                "VALUES (?, 1, 'free', 10, ?)",
                ("999_test", "2025-01-01T00:00:00Z"),
            )
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT id FROM usuarios WHERE telegram_chat_id = ?", ("999_test",)
            )
        uid = rows[0][0]

        # Palavras de teste
        palavras_teste = ["design", "logo", "branding"]
        for p in palavras_teste:
            try:
                await db.execute(
                    "INSERT INTO palavras_chave (usuario_id, palavra, ativa, criado_em) VALUES (?, ?, 1, ?)",
                    (uid, p, "2025-01-01T00:00:00Z"),
                )
            except Exception:
                pass  # já existe
        await db.commit()

async def main():
    print("=" * 60)
    print("MAKITA — Seed + Teste do coletor Facebook")
    print("=" * 60)

    await init_db()
    await seed_palavras()

    palavras = await get_palavras_ativas()
    print(f"\nPalavras ativas: {palavras}")

    tokens = await get_tokens()
    if not tokens:
        print("ERRO: Nenhum token do Facebook no banco. Execute makita/migrar_tokens.py primeiro.")
        return

    print(f"Tokens OK. fb_dtsg={tokens.get('fb_dtsg', 'N/A')[:20]}...")

    print(f"\nColetando {len(palavras)} palavra(s)...")
    total_pub = 0
    total_vistos = 0

    for palavra in palavras:
        print(f"\n  🔍 '{palavra}'...", end=" ", flush=True)
        try:
            posts = await _search_keyword(palavra, tokens)
            if not posts:
                print("0 posts encontrados")
                continue

            qtd = 0
            for post in posts:
                ok = await _publicar_sinal(post, palavra)
                if ok:
                    qtd += 1
            print(f"{qtd} novos sinais publicados de {len(posts)} posts")
            total_pub += qtd
        except Exception as e:
            print(f"ERRO: {e}")

        await asyncio.sleep(0.5)

    fila = await tamanho()
    print(f"\n{'=' * 60}")
    print(f"📊 RESULTADO")
    print(f"   Sinais novos publicados: {total_pub}")
    print(f"   Total na fila: {fila}")
    print(f"{'=' * 60}")

    # Mostra os primeiros sinais da fila
    if fila > 0:
        print(f"\n📋 Primeiros sinais na fila:")
        for i in range(min(3, fila)):
            s = await consumir()
            if s:
                print(f"   [{s.plataforma}] {s.palavra_chave} — {s.texto[:80]}...")

if __name__ == "__main__":
    asyncio.run(main())