"""
Diagnóstico do pipeline completo.
Mostra TODAS as etapas com nível DEBUG para o filtro.
"""
import asyncio, logging, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Garante que o token está disponível
os.environ.setdefault("TELEGRAM_TOKEN", os.environ.get("TELEGRAM_TOKEN", ""))

# Configura logging: filtro e entregador em DEBUG
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("filtro").setLevel(logging.DEBUG)
logging.getLogger("entregador").setLevel(logging.DEBUG)
logging.getLogger("facebook.graphql").setLevel(logging.INFO)

from makita.comum.db import init_db
from makita.coletores.facebook.graphql import get_tokens, _search_keyword, _publicar_sinal
from makita.processamento.filtro import _aplicar_filtros, publicar_aprovado, consumir_aprovado
from makita.comum.fila import consumir
from makita.comum.modelos import SinalBruto
from datetime import datetime, timezone
import hashlib

async def main():
    print("=" * 70)
    print("  DIAGNÓSTICO DO PIPELINE MAKITA")
    print("=" * 70)

    await init_db()

    # 1. Tokens
    tokens = await get_tokens()
    print(f"\n1. Tokens Facebook: {'✅' if tokens else '❌'}")
    if not tokens:
        print("   Execute makita/migrar_tokens.py primeiro")
        return

    # 2. Palavras
    from makita.comum.db import get_palavras_ativas
    palavras = await get_palavras_ativas()
    print(f"2. Palavras ativas: {len(palavras)} → {palavras}")

    # 3. Coleta UM ciclo
    print(f"\n3. Coletando {len(palavras)} palavras...")
    total_novos = 0
    todos_sinais = []

    for palavra in palavras:
        try:
            posts = await _search_keyword(palavra, tokens)
            if not posts:
                print(f"   '{palavra}': 0 posts")
                continue

            for post in posts:
                publicado = await _publicar_sinal(post, palavra)
                if publicado:
                    total_novos += 1
                    # Cria o SinalBruto para o filtro
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

            print(f"   '{palavra}': {len(posts)} posts → {sum(1 for p in posts if not None)} novos")

        except Exception as e:
            print(f"   ERRO '{palavra}': {e}")

        await asyncio.sleep(0.3)

    print(f"\n   Total novos sinais na fila: {total_novos}")

    # 4. FILTRO - processa cada sinal
    print(f"\n4. FILTRO — processando {len(todos_sinais)} sinais:\n")
    aprovados = []
    rejeitados = []

    for sinal in todos_sinais:
        aprovado, motivo = _aplicar_filtros(sinal)
        if aprovado:
            aprovados.append(sinal)
            await publicar_aprovado(sinal)
            print(f"   ✅ APROVADO | palavra='{sinal.palavra_chave}' | autor={sinal.autor}")
        else:
            rejeitados.append((sinal, motivo))
            print(f"   ❌ REJEITADO [{motivo}] | palavra='{sinal.palavra_chave}' | autor={sinal.autor}")

    # 5. ENTREGADOR - mostra como seria a mensagem
    print(f"\n5. ENTREGADOR — {len(aprovados)} sinais aprovados:\n")
    from makita.comum.db import get_chat_ids_por_palavra

    for sinal in aprovados:
        chat_ids = await get_chat_ids_por_palavra(sinal.palavra_chave)
        if chat_ids:
            print(f"   📨 {len(chat_ids)} destinatário(s) para '{sinal.palavra_chave}': {chat_ids}")
        else:
            print(f"   📭 Sem destinatários para '{sinal.palavra_chave}' (configure chat_id no banco)")

    # 6. CONTEÚDO COMPLETO dos 2 primeiros aprovados
    if aprovados:
        print(f"\n6. CONTEÚDO COMPLETO DOS SINAIS APROVADOS:\n")
        for i, s in enumerate(aprovados[:2], 1):
            print(f"   {'='*60}")
            print(f"   SINAL APROVADO #{i}")
            print(f"   {'='*60}")
            print(f"   Plataforma:  {s.plataforma}")
            print(f"   Palavra:     {s.palavra_chave}")
            print(f"   Autor:       {s.autor}")
            print(f"   URL:         {s.url}")
            print(f"   Source ID:   {s.source_id}")
            print(f"   Publicado:   {s.publicado_em}")
            print(f"   Texto:")
            for linha in s.texto.split('\n'):
                print(f"      {linha}")
            print()
    else:
        print(f"\n6. Nenhum sinal aprovado para mostrar conteúdo.")

    # 7. RESUMO
    print(f"\n{'='*70}")
    print(f"   📊 RESUMO")
    print(f"   {'='*70}")
    print(f"   Coletados:  {len(todos_sinais)}")
    print(f"   Aprovados:  {len(aprovados)}")
    print(f"   Rejeitados: {len(rejeitados)}")
    if rejeitados:
        from collections import Counter
        motivos = Counter(m for _, m in rejeitados)
        print(f"   Motivos:")
        for motivo, qtd in motivos.most_common():
            print(f"      {motivo}: {qtd}")
    print(f"{'='*70}")


if __name__ == "__main__":
    asyncio.run(main())