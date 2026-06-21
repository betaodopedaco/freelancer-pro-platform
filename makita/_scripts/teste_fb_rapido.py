"""
Teste rápido do coletor Facebook GraphQL no Makita.

1. Inicializa banco + tabelas
2. Adiciona 3 palavras de teste
3. Tenta ler tokens do Facebook
4. Roda UM ciclo de coleta (não o loop infinito)
5. Mostra quantos sinais foram publicados na fila
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)

from makita.comum.db import init_db, get_palavras_ativas
from makita.comum.fila import tamanho
from makita.coletores.facebook.graphql import (
    get_tokens,
    _search_keyword,
    _publicar_sinal,
)


async def main():
    print("=" * 60)
    print("MAKITA — Teste rápido do coletor Facebook")
    print("=" * 60)

    # 1. Init banco
    print("\n[1/4] Inicializando banco...")
    await init_db()
    print("  OK")

    # 2. Verificar palavras ativas
    print("\n[2/4] Buscando palavras ativas...")
    palavras = await get_palavras_ativas()
    if not palavras:
        print("  Nenhuma palavra ativa encontrada no banco.")
        print("  Use o bot Telegram para adicionar: /add <palavra>")
        print("  Ou insira manualmente no SQLite.")
        return
    print(f"  Palavras: {palavras}")

    # 3. Tokens
    print("\n[3/4] Buscando tokens do Facebook...")
    tokens = await get_tokens()
    if not tokens:
        print("  ❌ Nenhum token encontrado.")
        print("  Execute o session_manager primeiro para capturar tokens:")
        print("  python -m makita.coletores.facebook.session_manager")
        return
    print(f"  ✅ Tokens encontrados. fb_dtsg={tokens.get('fb_dtsg', 'N/A')[:20]}...")
    print(f"     doc_id={tokens.get('doc_id', 'N/A')}")

    # 4. Coleta UM ciclo
    print(f"\n[4/4] Coletando {len(palavras)} palavra(s)...")
    total_publicados = 0
    total_erros = 0

    for palavra in palavras:
        print(f"  🔍 '{palavra}'...", end=" ", flush=True)
        try:
            posts = await _search_keyword(palavra, tokens)
            if not posts:
                print("0 posts")
                continue

            qtd = 0
            for post in posts:
                publicado = await _publicar_sinal(post, palavra)
                if publicado:
                    qtd += 1

            print(f"{qtd} sinais publicados")
            total_publicados += qtd

        except Exception as e:
            print(f"ERRO: {e}")
            total_erros += 1

        await asyncio.sleep(0.5)

    # 5. Resumo
    print("\n" + "=" * 60)
    fila_atual = await tamanho()
    print(f"📊 Resumo do teste:")
    print(f"   Sinais publicados neste ciclo: {total_publicados}")
    print(f"   Erros: {total_erros}")
    print(f"   Fila atual: {fila_atual} sinais aguardando")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())