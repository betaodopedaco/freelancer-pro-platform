"""
Teste completo do pipeline Makita.
Roda coleta → filtro → entrega por 3 minutos.
Reporta: coletados, filtrados, aprovados, conteúdo dos primeiros 2 aprovados.
"""
import asyncio, logging, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)

from makita.comum.db import init_db
from makita.comum.fila import tamanho
from makita.coletores.facebook.graphql import get_tokens, _search_keyword, _publicar_sinal
from makita.processamento.filtro import (
    _aplicar_filtros,
    publicar_aprovado,
    consumir_aprovado,
    tamanho_aprovados,
)
from makita.comum.modelos import SinalBruto

# ── estatísticas ──────────────────────────────────────────────────

class Stats:
    def __init__(self):
        self.coletados = 0
        self.rejeitados = 0
        self.aprovados = 0
        self.erros = 0
        self.motivos = {}
        self.primeiros_aprovados = []

stats = Stats()


async def testar_filtro(sinal: SinalBruto) -> bool:
    """Testa filtro e registra estatísticas."""
    aprovado, motivo = _aplicar_filtros(sinal)
    if aprovado:
        stats.aprovados += 1
        if len(stats.primeiros_aprovados) < 2:
            stats.primeiros_aprovados.append(sinal)
        await publicar_aprovado(sinal)
        return True
    else:
        stats.rejeitados += 1
        stats.motivos[motivo] = stats.motivos.get(motivo, 0) + 1
        return False


async def main():
    print("=" * 70)
    print("  MAKITA — Teste completo do pipeline")
    print("  Coleta → Filtro → Entrega (logada)")
    print("  Duração: 3 minutos")
    print("=" * 70)

    await init_db()

    # 1. Tokens
    tokens = await get_tokens()
    if not tokens:
        print("❌ Nenhum token do Facebook. Execute makita/migrar_tokens.py primeiro.")
        return
    print(f"✅ Tokens OK. fb_dtsg={tokens.get('fb_dtsg','')[:20]}...")

    # 2. Palavras ativas
    from makita.comum.db import get_palavras_ativas
    palavras = await get_palavras_ativas()
    print(f"✅ {len(palavras)} palavras ativas: {palavras}")

    # 3. Loop por 3 minutos
    print(f"\n{'=' * 70}")
    print("  INICIANDO COLETA (3 minutos)...")
    print(f"{'=' * 70}")

    inicio = time.time()
    ciclos = 0

    while time.time() - inicio < 180:  # 3 minutos
        ciclos += 1
        print(f"\n--- Ciclo {ciclos} ---")

        for palavra in palavras:
            try:
                posts = await _search_keyword(palavra, tokens)
                if not posts:
                    continue

                for post in posts:
                    # Publica na fila principal (simula o coletor)
                    publicado = await _publicar_sinal(post, palavra)
                    if publicado:
                        stats.coletados += 1

                        # Cria SinalBruto para testar o filtro
                        import hashlib
                        from datetime import datetime, timezone
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

                        await testar_filtro(sinal)

            except Exception as e:
                stats.erros += 1
                print(f"  ERRO '{palavra}': {e}")

            await asyncio.sleep(0.5)

        # Pausa entre ciclos
        await asyncio.sleep(5)

    # 4. Relatório final
    print(f"\n{'=' * 70}")
    print("  📊 RELATÓRIO FINAL")
    print(f"{'=' * 70}")
    print(f"  Ciclos executados:     {ciclos}")
    print(f"  Sinais coletados:      {stats.coletados}")
    print(f"  Aprovados pelo filtro: {stats.aprovados}")
    print(f"  Rejeitados:            {stats.rejeitados}")
    print(f"  Erros:                 {stats.erros}")
    print(f"\n  📋 Motivos de rejeição:")
    for motivo, qtd in sorted(stats.motivos.items(), key=lambda x: -x[1]):
        print(f"     {motivo}: {qtd}")

    fila_principal = await tamanho()
    fila_aprovados = await tamanho_aprovados()
    print(f"\n  📦 Filas:")
    print(f"     Principal: {fila_principal} sinais")
    print(f"     Aprovados: {fila_aprovados} sinais")

    print(f"\n  📋 Primeiros 2 sinais aprovados:")
    for i, s in enumerate(stats.primeiros_aprovados, 1):
        print(f"\n     --- Sinal aprovado #{i} ---")
        print(f"     Plataforma:  {s.plataforma}")
        print(f"     Palavra:     {s.palavra_chave}")
        print(f"     Autor:       {s.autor}")
        print(f"     Texto:       {s.texto[:150]}...")
        print(f"     URL:         {s.url}")

    print(f"\n{'=' * 70}")
    print("  TESTE CONCLUÍDO")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())