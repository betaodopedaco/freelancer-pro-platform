"""
validar_cookies_twitter.py
==========================
Script de validação completa dos cookies do Twitter/X.

O que faz:
  1. Carrega cookies via loader centralizado (TWITTER_COOKIES_B64 > twitter_cookies.json)
  2. Valida JSON e presença de auth_token + ct0
  3. Abre Playwright com os cookies
  4. Navega até x.com/search?q=test&f=live
  5. Verifica se a página carrega (não redireciona para login)
  6. Retorna sucesso/falha com logs detalhados

Uso:
    python validar_cookies_twitter.py

    # Com variável de ambiente (simula Render):
    set TWITTER_COOKIES_B64=<base64> && python validar_cookies_twitter.py

    # Ou apenas com arquivo local:
    python validar_cookies_twitter.py
"""

import asyncio
import json
import os
import sys

# Garante que o diretório raiz está no path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tofinder.coletores.twitter_cookie_loader import load_twitter_cookies, get_cookie_value
from playwright.async_api import async_playwright


async def validar_cookies() -> dict:
    """
    Valida os cookies do Twitter/X.

    Returns:
        dict com:
            - success: bool
            - source: str (B64 | file | none)
            - cookies_count: int
            - has_auth_token: bool
            - has_ct0: bool
            - auth_token_preview: str
            - ct0_preview: str
            - playwright_ok: bool
            - page_title: str
            - redirected_to_login: bool
            - errors: list[str]
    """
    result = {
        "success": False,
        "source": "none",
        "cookies_count": 0,
        "has_auth_token": False,
        "has_ct0": False,
        "auth_token_preview": "",
        "ct0_preview": "",
        "playwright_ok": False,
        "page_title": "",
        "redirected_to_login": True,
        "errors": [],
    }

    # --- PASSO 1: Carregar cookies ---
    print("\n" + "=" * 60)
    print("  VALIDAÇÃO DE COOKIES DO TWITTER/X")
    print("=" * 60)

    b64_var = os.environ.get("TWITTER_COOKIES_B64", "")
    if b64_var:
        print(f"\n[1/5] Fonte: TWITTER_COOKIES_B64 ({len(b64_var)} caracteres)")
        result["source"] = "B64"
    else:
        print("\n[1/5] Fonte: twitter_cookies.json (arquivo local)")
        result["source"] = "file"

    cookies = load_twitter_cookies()
    if not cookies:
        result["errors"].append("Nenhum cookie carregado.")
        print("  ❌ FALHA: Nenhum cookie disponível.")
        print("\n  Dica: Defina TWITTER_COOKIES_B64 ou crie twitter_cookies.json")
        return result

    result["cookies_count"] = len(cookies)
    print(f"  ✅ {len(cookies)} cookies carregados.")

    # --- PASSO 2: Validar campos obrigatórios ---
    print("\n[2/5] Validando campos obrigatórios...")

    auth_token = get_cookie_value(cookies, "auth_token")
    ct0 = get_cookie_value(cookies, "ct0")

    result["has_auth_token"] = bool(auth_token)
    result["has_ct0"] = bool(ct0)

    if auth_token:
        masked = auth_token[:8] + "..." + auth_token[-4:] if len(auth_token) > 12 else "***"
        result["auth_token_preview"] = masked
        print(f"  ✅ auth_token: {masked}")
    else:
        result["errors"].append("auth_token ausente.")
        print("  ❌ auth_token: AUSENTE")

    if ct0:
        masked = ct0[:8] + "..." + ct0[-4:] if len(ct0) > 12 else "***"
        result["ct0_preview"] = masked
        print(f"  ✅ ct0: {masked}")
    else:
        result["errors"].append("ct0 ausente.")
        print("  ❌ ct0: AUSENTE")

    if not auth_token or not ct0:
        print("\n  ❌ VALIDAÇÃO FALHOU: auth_token e ct0 são obrigatórios.")
        return result

    # --- PASSO 3: Abrir Playwright e testar sessão ---
    print("\n[3/5] Abrindo Playwright com os cookies...")

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
            )
            await context.add_cookies(cookies)
            page = await context.new_page()

            print("\n[4/5] Navegando para x.com/search?q=test&f=live...")

            # Monitora redirecionamentos
            redirects = []
            page.on("response", lambda resp: redirects.append({
                "url": resp.url,
                "status": resp.status,
            }))

            try:
                await page.goto(
                    "https://x.com/search?q=test&f=live",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await asyncio.sleep(3)
            except Exception as e:
                result["errors"].append(f"Timeout ou erro na navegação: {e}")
                print(f"  ⚠️  Timeout/erro: {e}")

            # --- PASSO 5: Analisar resultado ---
            print("\n[5/5] Analisando resultado...")

            current_url = page.url
            page_title = await page.title()
            result["page_title"] = page_title

            print(f"  URL final: {current_url[:100]}")
            print(f"  Título: {page_title[:100]}")

            # Verifica se foi redirecionado para login
            if "login" in current_url or "login" in page_title.lower() or "i/flow" in current_url:
                result["redirected_to_login"] = True
                result["errors"].append("Redirecionado para página de login — cookies inválidos/expirados.")
                print("  ❌ REDIRECIONADO PARA LOGIN — cookies inválidos ou expirados.")
            else:
                result["redirected_to_login"] = False
                result["playwright_ok"] = True
                result["success"] = True
                print("  ✅ SESSÃO VÁLIDA — não foi redirecionado para login.")

            # Mostra alguns redirecionamentos
            if redirects:
                print(f"\n  Redirecionamentos ({len(redirects)}):")
                for r in redirects[:5]:
                    print(f"    {r['status']} {r['url'][:80]}...")

            await browser.close()

    except Exception as e:
        result["errors"].append(f"Erro no Playwright: {e}")
        print(f"  ❌ Erro no Playwright: {e}")

    # --- RESUMO ---
    print("\n" + "=" * 60)
    if result["success"]:
        print("  ✅ VALIDAÇÃO COMPLETA — SESSÃO DO TWITTER FUNCIONANDO")
        print(f"  Fonte: {result['source']}")
        print(f"  Cookies: {result['cookies_count']}")
        print(f"  auth_token: {result['auth_token_preview']}")
        print(f"  ct0: {result['ct0_preview']}")
    else:
        print("  ❌ VALIDAÇÃO FALHOU")
        for err in result["errors"]:
            print(f"  - {err}")
    print("=" * 60)

    return result


def main():
    result = asyncio.run(validar_cookies())
    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()