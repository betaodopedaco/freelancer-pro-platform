"""
Roda o pipeline Makita por 90 segundos,
captura e mostra APENAS as linhas do filtro e entregador.
"""
import asyncio, logging, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)

from makita.comum.db import init_db
from makita.coletores.facebook.graphql import colect_facebook
from makita.processamento.filtro import loop_filtro
from makita.processamento.entregador import loop_entregador

# Handler que filtra só filtro e entregador
class FiltroHandler(logging.Handler):
    def emit(self, record):
        if record.name in ("filtro", "entregador"):
            print(self.format(record))

filtro_handler = FiltroHandler()
filtro_handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(message)s"))
logging.getLogger("filtro").addHandler(filtro_handler)
logging.getLogger("filtro").propagate = False
logging.getLogger("entregador").addHandler(filtro_handler)
logging.getLogger("entregador").propagate = False

# Coletor só no terminal
logging.getLogger("facebook.graphql").propagate = True

async def main():
    print("=" * 70)
    print("  MAKITA — Pipeline completo rodando por 90s")
    print("  Mostrando APENAS filtro + entregador")
    print("  (Coletor roda em background)")
    print("=" * 70)

    await init_db()

    print("\n📡 Coletor, 🔍 Filtro e 📨 Entregador iniciados...\n")

    # Roda por 90 segundos e depois cancela
    try:
        await asyncio.wait_for(
            asyncio.gather(
                colect_facebook(),
                loop_filtro(),
                loop_entregador(),
            ),
            timeout=90,
        )
    except asyncio.TimeoutError:
        pass

    print("\n" + "=" * 70)
    print("  ⏱ TEMPO ESGOTADO (90s)")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())