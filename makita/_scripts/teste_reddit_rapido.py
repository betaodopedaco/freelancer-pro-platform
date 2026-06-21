"""Testa o adaptador Reddit isoladamente com 2 keywords."""
import asyncio, logging, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env):
    with open(_env) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", level=logging.INFO)

from playwright.async_api import async_playwright
from makita.coletores.reddit.adaptador import _search_reddit, COOKIE_PATH, RAIZ


async def main():
    print(f"RAIZ: {RAIZ}")
    print(f"COOKIE_PATH: {COOKIE_PATH}")
    print(f"Cookies existem: {os.path.exists(COOKIE_PATH)}")
    print()

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
    )

    import json
    if os.path.exists(COOKIE_PATH):
        with open(COOKIE_PATH) as f:
            await context.add_cookies(json.load(f))
        print("Cookies carregados.\n")

    for kw in ["need a designer", "logo design"]:
        print(f"=== Testando: '{kw}' ===")
        page = await context.new_page()
        try:
            posts = await _search_reddit(page, kw)
            print(f"  Encontrados: {len(posts)} posts")
            for i, p in enumerate(posts[:5]):
                print(f"  {i+1}. {p['title'][:80]}")
                print(f"     URL: {p['url']}")
                print(f"     Autor: {p.get('author','?')}  Score: {p.get('score',0)}")
        except Exception as e:
            print(f"  ERRO: {e}")
        finally:
            await page.close()
        print()

    await browser.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())