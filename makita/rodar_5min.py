"""
Roda makita/main.py por 5 minutos com FB_POLL_INTERVAL=30.
Inclui todos os 5 coletores: Facebook, Twitter, Reddit, Bluesky, HN.
"""
import asyncio, logging, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carrega .env
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# Poll intervals curtos para teste
os.environ["FB_POLL_INTERVAL"] = "30"

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)

from makita.comum.db import init_db
from makita.coletores.facebook.graphql import colect_facebook
from makita.coletores.twitter.adaptador import colect_twitter
from makita.coletores.reddit.adaptador import colect_reddit
from makita.coletores.bluesky.adaptador import colect_bluesky
from makita.coletores.hn.adaptador import colect_hn
from makita.processamento.filtro import loop_filtro
from makita.processamento.entregador import loop_entregador


async def main():
    print("=" * 70)
    print("  MAKITA — Teste final: 5 coletores (3 min)")
    print("  Facebook | Twitter | Reddit | Bluesky | HN")
    print("  Chat ID: 8081681015")
    print("=" * 70)

    await init_db()

    from makita.comum.db import get_palavras_ativas, get_chat_ids_por_palavra
    palavras = await get_palavras_ativas()
    print(f"\nPalavras ativas: {palavras}")
    for p in palavras:
        chats = await get_chat_ids_por_palavra(p)
        print(f"  '{p}' → {len(chats)} chat(s): {chats}")

    print(f"\n📡 Iniciando TODOS os 5 coletores por 5 minutos...\n")

    try:
        await asyncio.wait_for(
            asyncio.gather(
                colect_facebook(),
                colect_twitter(),
                colect_reddit(),
                colect_bluesky(),
                colect_hn(),
                loop_filtro(),
                loop_entregador(),
            ),
            timeout=180,
        )
    except asyncio.TimeoutError:
        print(f"\n{'='*70}")
        print("  ⏱ 5 MINUTOS ESGOTADOS")
        print("  Verifique seu Telegram!")
        print(f"{'='*70}")
    except KeyboardInterrupt:
        print("\nEncerrado pelo usuário.")


if __name__ == "__main__":
    asyncio.run(main())