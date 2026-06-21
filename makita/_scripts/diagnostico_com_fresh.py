"""
Diagnóstico do pipeline completo com dados FRESCOS (limpa dedup antes).
"""
import asyncio, logging, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)

from makita.comum.db import init_db, DB_PATH
from makita.coletores.facebook.graphql import get_tokens, _search_keyword, _publicar_sinal
from makita.processamento.filtro import _aplicar_filtros, publicar_aprovado
from makita.comum.modelos import SinalBruto
from datetime import datetime, timezone
import hashlib
import aiosqlite
from collections import Counter

async def main():
    print("=" * 70)
    print("  DIAGNÓSTICO COMPLETO DO PIPELINE MAKITA")
    print("=" * 70)

    await init_db()

    # LIMPA dedup para garantir dados frescos
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sinais_vistos")
        await db.commit()
    print("\n✅ Dedup resetado (sinais_vistos limpa)")

    # 1. Tokens
    tokens = await get_tokens()
    print(f"✅ Tokens Facebook OK. fb_dtsg={tokens.get('fb_dtsg','')[:20]}...")

    # 2. Palavras
    from makita.comum.db import get_palavras_ativas
    palavras = await get_palavras_ativas()
    print(f"✅ {len(palavras)} palavras ativas: {palavras}")

    # 3. Coleta
    print(f"\n{'='*70}")
    print("  FASE 1 — COLETA")
    print(f"{'='*70}")

    total_novos = 0
    todos_sinais = []

    for palavra in palavras:
        try:
            posts = await _search_keyword(palavra, tokens)
            if not posts:
                print(f"   '{palavra}': 0 posts")
                continue

            qtd = 0
            for post in posts:
                # CRIA SINAL PRIMEIRO (antes do dedup)
                source_id = "fbgql_" + hashlib.md5(
                    (post["url"] + post["text"][:40]).encode()
                ).hexdigest()[:12]
                sinal = SinalBruto(
                    plataforma="facebook",
                    source_id=source_id,
                    texto=post["text"][:800],
                    url=post["url"],
                    autor=post["author"],
                    palavra_chave=palavra,
                    usuario_id=0,
                    publicado_em=datetime.fromtimestamp(
                        post["ts"], tz=timezone.utc
                    ).isoformat(),
                )
                todos_sinais.append(sinal)

                # Depois tenta publicar na fila
                publicado = await _publicar_sinal(post, palavra)
                if publicado:
                    qtd += 1
                    total_novos += 1

            print(f"   '{palavra}': {len(posts)} posts → {qtd} novos na fila")

        except Exception as e:
            print(f"   ERRO '{palavra}': {e}")

        await asyncio.sleep(0.3)

    print(f"\n   📦 Total: {len(todos_sinais)} sinais capturados, {total_novos} novos na fila")

    # 4. FILTRO
    print(f"\n{'='*70}")
    print("  FASE 2 — FILTRO")
    print(f"{'='*70}\n")

    aprovados = []
    rejeitados = []

    for sinal in todos_sinais:
        aprovado, motivo = _aplicar_filtros(sinal)
        if aprovado:
            aprovados.append(sinal)
            await publicar_aprovado(sinal)
            print(f"   ✅ APROVADO | '{sinal.palavra_chave}' | {sinal.autor}")
        else:
            rejeitados.append((sinal, motivo))
            print(f"   ❌ REJEITADO [{motivo}] | '{sinal.palavra_chave}' | {sinal.autor}")

    # 5. ENTREGADOR (simulado)
    print(f"\n{'='*70}")
    print("  FASE 3 — ENTREGADOR")
    print(f"{'='*70}\n")

    from makita.comum.db import get_chat_ids_por_palavra
    from makita.processamento.entregador import _montar_mensagem

    for sinal in aprovados:
        chat_ids = await get_chat_ids_por_palavra(sinal.palavra_chave)
        if chat_ids:
            print(f"   📨 '{sinal.palavra_chave}' → {len(chat_ids)} destinatário(s): {chat_ids}")
            msg = _montar_mensagem(sinal)
            print(f"      Mensagem:\n{msg}\n")
        else:
            print(f"   📭 '{sinal.palavra_chave}' → sem destinatários (configure TELEGRAM_CHAT_ID)")

    # 6. CONTEÚDO COMPLETO
    if aprovados:
        print(f"\n{'='*70}")
        print("  CONTEÚDO COMPLETO DOS 2 PRIMEIROS APROVADOS")
        print(f"{'='*70}\n")
        for i, s in enumerate(aprovados[:2], 1):
            print(f"   {'─'*60}")
            print(f"   SINAL #{i}")
            print(f"   {'─'*60}")
            print(f"   Plataforma:  {s.plataforma}")
            print(f"   Palavra:     {s.palavra_chave}")
            print(f"   Autor:       {s.autor}")
            print(f"   URL:         {s.url}")
            print(f"   Source ID:   {s.source_id}")
            print(f"   Publicado:   {s.publicado_em}")
            print(f"   Texto completo:")
            for linha in s.texto.split('\n'):
                print(f"      {linha}")
            print()

    # 7. RESUMO FINAL
    print(f"\n{'='*70}")
    print("  📊 RESUMO FINAL")
    print(f"{'='*70}")
    print(f"   Coletados:  {len(todos_sinais)}")
    print(f"   Aprovados:  {len(aprovados)}")
    print(f"   Rejeitados: {len(rejeitados)}")
    if rejeitados:
        print(f"   Motivos de rejeição:")
        for motivo, qtd in Counter(m for _, m in rejeitados).most_common():
            print(f"      {motivo}: {qtd}")
    print(f"{'='*70}")

if __name__ == "__main__":
    asyncio.run(main())