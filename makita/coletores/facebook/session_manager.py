"""
makita/coletores/facebook/session_manager.py
============================================
Renovação automática dos tokens do Facebook via DOM scraping (Browserless).
Persiste em makita.comum.db e é chamado por main.py.

Estratégia: DOM scraping ao invés de GraphQL
- Mais estável
- Não depende de tokens GraphQL
- Usa role="article" para extrair posts
"""
import asyncio
import json
import logging
import os
import re
import urllib.parse

from playwright.async_api import async_playwright

from makita.comum.db import salvar_sessao, ler_sessao

log = logging.getLogger("fb_session_manager")

FB_C_USER = os.getenv("FB_C_USER", "")
FB_XS = os.getenv("FB_XS", "")
FB_FR = os.getenv("FB_FR", "")

# ── Config Browserless ──────────────────────────────────────────────
BROWSERLESS_TOKEN = os.getenv("BROWSERLESS_TOKEN", "2UkpDDNQOGhjTpu8d724215942577713a7322a27c52af0bf0")
BROWSERLESS_HOST = os.getenv("BROWSERLESS_HOST", "chrome.browserless.io")
WS_ENDPOINT = f"wss://{BROWSERLESS_HOST}?token={BROWSERLESS_TOKEN}&timeout=120000"

REFRESH_INTERVAL = int(os.getenv("FB_TOKEN_REFRESH_SECS", "600"))  # 10 min


def limpar_valor_cookie(valor: str) -> str:
    if not valor:
        return ""
    try:
        valor = urllib.parse.unquote(valor)
    except Exception:
        pass
    valor = valor.replace(";", "").replace(",", "").replace(" ", "")
    valor = re.sub(r'%(?![0-9a-fA-F]{2})', '', valor)
    return valor


FB_XS_CLEAN = limpar_valor_cookie(FB_XS) if FB_XS else ""
FB_FR_CLEAN = limpar_valor_cookie(FB_FR) if FB_FR else ""

_FB_COOKIES = [
    {"name": "c_user", "value": FB_C_USER, "domain": ".facebook.com", "path": "/"},
    {"name": "xs",     "value": FB_XS_CLEAN, "domain": ".facebook.com", "path": "/"},
    {"name": "fr",     "value": FB_FR_CLEAN, "domain": ".facebook.com", "path": "/"},
]


def normalizar_sameSite(valor) -> str:
    mapeamento = {
        "strict": "Strict", "lax": "Lax", "none": "None",
        "no_restriction": "None", "unspecified": "Lax",
        "": "Lax", None: "Lax",
    }
    if valor is None:
        return "Lax"
    return mapeamento.get(valor.lower().strip(), "Lax")


def normalizar_cookies(cookies: list) -> list:
    normalizados = []
    for c in cookies:
        copia = dict(c)
        copia["sameSite"] = normalizar_sameSite(c.get("sameSite"))
        normalizados.append(copia)
    return normalizados


async def _extrair_posts_dom(page) -> list[dict]:
    """Extrai posts via DOM scraping (role='article')."""
    posts = []
    
    try:
        articles = await page.query_selector_all("[role='article']")
        
        for article in articles:
            try:
                # Verifica se é anúncio
                attrs = await article.get_attribute("class") or ""
                if any(ind in attrs.lower() for ind in ['ad', 'sponsored', 'advertisement']):
                    continue
                
                # Extrai texto
                texto_completo = await article.inner_text()
                linhas = [l.strip() for l in texto_completo.split('\n') if l.strip()]
                
                if len(linhas) < 2:
                    continue
                
                autor = linhas[0] if linhas else ""
                texto = '\n'.join(linhas[2:]) if len(linhas) > 2 else ""
                
                if not autor or len(autor) > 100 or not texto:
                    continue
                
                posts.append({
                    "author": autor,
                    "text": texto,
                    "length": len(texto)
                })
                
            except Exception:
                continue
    except Exception as e:
        log.debug(f"Erro ao extrair posts: {e}")
    
    return posts


async def _validar_sessao() -> bool:
    """
    Valida se a sessão do Facebook está funcionando.
    Abre Facebook, aguarda carregamento e verifica se há posts.
    """
    log.info("Validando sessão Facebook via DOM scraping...")
    
    pw = None
    browser = None
    context = None
    page = None
    
    try:
        pw = await async_playwright().start()
        
        # Conecta via Browserless ou fallback
        if BROWSERLESS_TOKEN and BROWSERLESS_TOKEN != "2UkpDDNQOGhjTpu8d724215942577713a7322a27c52af0bf0":
            browser = await pw.chromium.connect_over_cdp(WS_ENDPOINT)
        else:
            browser = await pw.chromium.launch(headless=True)
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        
        fb_cookies_norm = normalizar_cookies(_FB_COOKIES)
        await context.add_cookies(fb_cookies_norm)
        
        page = await context.new_page()
        
        # Abre Facebook
        resp = await page.goto(
            "https://www.facebook.com/",
            wait_until="domcontentloaded",
            timeout=45000
        )
        
        if not resp or resp.status != 200:
            log.error(f"Facebook retornou status {resp.status if resp else 'N/A'}")
            return False
        
        # Aguarda carregamento
        await asyncio.sleep(20)
        
        # Tenta encontrar posts
        posts = await _extrair_posts_dom(page)
        
        if posts:
            log.info(f"Sessão válida! {len(posts)} posts encontrados.")
            return True
        else:
            log.warning("Nenhum post encontrado. Sessão pode estar inválida.")
            return False
    
    except Exception as e:
        log.error(f"Erro ao validar sessão: {e}")
        return False
    
    finally:
        if page and not page.is_closed():
            try:
                await page.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if pw:
            try:
                await pw.stop()
            except Exception:
                pass


async def refresh_loop() -> None:
    """
    Loop que valida sessão do Facebook a cada REFRESH_INTERVAL.
    Não captura mais tokens GraphQL — usa DOM scraping.
    """
    log.info(f"Session manager FB iniciado (DOM scraping). "
             f"Validação a cada {REFRESH_INTERVAL}s.")
    
    # Validação inicial
    sessao_valida = await _validar_sessao()
    if sessao_valida:
        await salvar_sessao("facebook", {"status": "active", "method": "dom_scraping"})
        log.info("Sessão FB validada e salva.")
    else:
        log.warning("Validação inicial falhou — tentando novamente em 60s.")
        await asyncio.sleep(60)
    
    while True:
        await asyncio.sleep(REFRESH_INTERVAL)
        
        log.info("Validando sessão Facebook...")
        sessao_valida = await _validar_sessao()
        
        if sessao_valida:
            await salvar_sessao("facebook", {"status": "active", "method": "dom_scraping"})
            log.info("Sessão FB renovada com sucesso.")
        else:
            log.error("Falha na validação da sessão FB — "
                      "coletor pode parar até próxima tentativa.")
            await salvar_sessao("facebook", {"status": "invalid", "method": "dom_scraping"})