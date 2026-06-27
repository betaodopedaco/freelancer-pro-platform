"""
makita/coletores/facebook/dom.py
=================================
Coletor do Facebook via DOM scraping (Browserless + Playwright).

FLUXO:
  Browserless -> Playwright -> facebook.com -> role="article" -> extracao -> SinalBruto -> publicar()

REUSO:
  - BROWSERLESS_TOKEN, BROWSERLESS_HOST  <- session_manager.py
  - normalizar_cookies(), _FB_COOKIES    <- session_manager.py
  - get_palavras_ativas(), ja_visto()    <- makita.comum.db
  - publicar(), SinalBruto               <- makita.comum
"""

import asyncio
import hashlib
import logging
import os
import time
from datetime import datetime, timezone

from playwright.async_api import async_playwright

from makita.comum.db import get_palavras_ativas, ja_visto
from makita.comum.fila import publicar
from makita.comum.modelos import SinalBruto

# --- Reuso do session_manager existente -------------------------------
from makita.coletores.facebook.session_manager import (
    BROWSERLESS_TOKEN as _BROWSERLESS_TOKEN_RAW,
    BROWSERLESS_HOST as _BROWSERLESS_HOST_RAW,
    normalizar_cookies,
    _FB_COOKIES as _FB_COOKIES_RAW,
)

log = logging.getLogger("facebook.dom")

# --- Constantes -------------------------------------------------------
INTERVALO = int(os.getenv("FB_POLL_INTERVAL", "1800"))  # 30 min
MAX_POR_CICLO = 10

BROWSERLESS_TOKEN = os.getenv("BROWSERLESS_TOKEN", _BROWSERLESS_TOKEN_RAW)
BROWSERLESS_HOST = os.getenv("BROWSERLESS_HOST", _BROWSERLESS_HOST_RAW)
WS_ENDPOINT = f"wss://{BROWSERLESS_HOST}?token={BROWSERLESS_TOKEN}&timeout=120000"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)

# --- Seletores de URL de post -----------------------------------------
_SELETORES_URL = [
    'a[href*="/posts/"]',
    'a[href*="/photo/"]',
    'a[href*="/videos/"]',
    'a[href*="/permalink/"]',
    'a[href*="/story.php"]',
    'a[href*="/groups/"]',
    'a[href*="/events/"]',
    'a[href*="/watch/"]',
    'a[href*="/reel/"]',
    'a[href*="/notes/"]',
]

async def _extrair_url_artigo(article) -> str:
    """Tenta extrair um permalink de post do elemento article.

    Percorre seletores conhecidos de links de post do Facebook.
    Retorna string vazia se nao encontrar nenhum.
    """
    for sel in _SELETORES_URL:
        try:
            link = await article.query_selector(sel)
            if link:
                href = await link.get_attribute("href")
                if href:
                    href = href.strip()
                    if href.startswith("/"):
                        return f"https://www.facebook.com{href}"
                    if href.startswith("http"):
                        return href
        except Exception:
            continue
    return ""


async def _extrair_posts(page) -> list[dict]:
    """Extrai todos os posts visiveis da pagina via role='article'.

    Retorna lista de dicts com:
      - author: nome do autor (primeira linha do inner_text)
      - text:   corpo do post (demais linhas)
      - url:    permalink do post (string vazia se nao encontrado)
    """
    posts: list[dict] = []
    sem_url = 0
    total = 0

    articles = await page.query_selector_all("[role='article']")

    for article in articles:
        total += 1
        try:
            # Pular anuncios
            attrs = (await article.get_attribute("class") or "").lower()
            outer = (await article.get_attribute("outerHTML") or "").lower()
            indicios_anuncio = ["ad", "sponsored", "advertisement", " Ad"]
            if any(ind in attrs or ind in outer for ind in indicios_anuncio):
                continue

            # Texto
            texto_completo = await article.inner_text()
            linhas = [l.strip() for l in texto_completo.split("\n") if l.strip()]

            if len(linhas) < 2:
                continue

            autor = linhas[0]
            texto = "\n".join(linhas[2:]) if len(linhas) > 2 else ""

            if not autor or len(autor) > 100 or not texto:
                continue

            # URL
            url = await _extrair_url_artigo(article)

            if not url:
                sem_url += 1

            posts.append({
                "author": autor,
                "text": texto,
                "url": url,
            })
        except Exception:
            continue

    if sem_url:
        log.info(f"DOM extracao: {len(posts)} posts de {total} articles, "
                 f"{sem_url} sem URL")
    else:
        log.info(f"DOM extracao: {len(posts)} posts de {total} articles")

    return posts
# --- Deteccao de palavras-chave e publicacao ---------------------------

async def _publicar_sinal(post: dict, palavra: str) -> bool:
    """Cria SinalBruto, verifica dedup e publica na fila.

    Retorna True se publicou, False se ja visto.
    """
    # source_id estavel: hash(url + texto[:40]) ou hash(autor + texto[:80])
    if post["url"]:
        base = post["url"] + post["text"][:40]
    else:
        base = post["author"] + post["text"][:80]

    source_id = "fb_dom_" + hashlib.md5(base.encode()).hexdigest()[:12]

    if await ja_visto(source_id):
        return False

    sinal = SinalBruto(
        plataforma="facebook",
        source_id=source_id,
        texto=post["text"][:800],
        url=post["url"],
        autor=post["author"],
        palavra_chave=palavra,
        usuario_id="0",
        publicado_em=datetime.now(timezone.utc).isoformat(),
    )

    await publicar(sinal)
    return True


# --- Coletor principal -------------------------------------------------

async def colect_facebook() -> None:
    """Loop principal do coletor Facebook via DOM scraping.

    A cada ciclo:
      1. Conecta Browserless (ou fallback local)
      2. Abre facebook.com (Home)
      3. Aguarda role="article"
      4. 1 scroll
      5. Extrai posts via DOM
      6. Para cada post, verifica palavras ativas
      7. Dedup + publica SinalBruto
      8. Logs de diagnostico
    """
    log.info("=" * 50)
    log.info("  Facebook DOM coletor iniciado (Browserless + Playwright)")
    log.info("=" * 50)

    pw = await async_playwright().start()

    browser = None
    context = None

    try:
        # --- Conexao Browserless -----------------------------------------
        token_valido = (
            BROWSERLESS_TOKEN
            and BROWSERLESS_TOKEN != "2UkpDDNQOGhjTpu8d724215942577713a7322a27c52af0bf0"
        )
        if token_valido:
            log.info(f"Browserless: conectando a {BROWSERLESS_HOST}...")
            browser = await pw.chromium.connect_over_cdp(WS_ENDPOINT)
            log.info("Conexao Browserless: OK")
        else:
            log.info("Browserless: token nao configurado. Usando launch() local.")
            browser = await pw.chromium.launch(headless=True)
            log.info("Conexao local: OK")

        context = await browser.new_context(
            user_agent=UA,
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
        )

        # Anti-deteccao
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # --- Cookies FB ---------------------------------------------------
        fb_cookies = normalizar_cookies(_FB_COOKIES_RAW)
        await context.add_cookies(fb_cookies)
        log.info(f"Cookies: {len(fb_cookies)} cookies aplicados")

        await asyncio.sleep(5)
# --- Loop principal ------------------------------------------------
        while True:
            inicio_ciclo = time.time()
            log.info("Facebook DOM: iniciando ciclo de coleta...")

            # 1. Palavras ativas
            try:
                palavras = await get_palavras_ativas()
            except Exception as e:
                log.error(f"Erro ao buscar palavras: {e}")
                await asyncio.sleep(60)
                continue

            if not palavras:
                log.info("Nenhuma palavra ativa. Aguardando 60s...")
                await asyncio.sleep(60)
                continue

            palavras_lower = [p.lower() for p in palavras]
            log.info(f"Palavras ativas: {len(palavras_lower)}")

            # 2. Abrir Facebook Home
            page = await context.new_page()
            try:
                log.info("Navegando para facebook.com...")
                resp = await page.goto(
                    "https://www.facebook.com/",
                    wait_until="domcontentloaded",
                    timeout=45000,
                )
                status = resp.status if resp else "N/A"
                log.info(f"Facebook Home: status {status}")

                # 3. Aguardar role="article"
                try:
                    await page.wait_for_selector("[role='article']", timeout=20000)
                    log.info("role='article' encontrado (JS renderizou o feed)")
                except Exception:
                    log.warning(
                        "wait_for_selector role='article' timeout - "
                        "tentando extrair mesmo assim"
                    )

                # 4. 1 scroll
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(3)

                # 5. Extrair posts
                posts = await _extrair_posts(page)
                log.info(f"Total artigos extraidos: {len(posts)}")

                # 6. Match com palavras ativas
                total_publicados = 0
                total_vistos = 0
                posts_com_keyword = 0

                for post in posts:
                    texto_post = (post["author"] + " " + post["text"]).lower()
                    palavras_match = [
                        p for p in palavras_lower
                        if p in texto_post
                    ]
                    if not palavras_match:
                        continue

                    posts_com_keyword += 1

                    for palavra_match in palavras_match:
                        publicado = await _publicar_sinal(post, palavra_match)
                        if publicado:
                            total_publicados += 1
                        else:
                            total_vistos += 1

                # 7. Logs de diagnostico do ciclo
                duracao = round(time.time() - inicio_ciclo, 1)
                log.info(
                    f"Ciclo concluido em {duracao}s | "
                    f"posts: {len(posts)} | "
                    f"c/ keyword: {posts_com_keyword} | "
                    f"publicados: {total_publicados} | "
                    f"ja vistos: {total_vistos} | "
                    f"proximo em {INTERVALO}s"
                )

            except Exception as e:
                log.error(f"Erro no ciclo de coleta: {e}")
            finally:
                try:
                    await page.close()
                except Exception:
                    pass

            await asyncio.sleep(INTERVALO)

    except Exception as e:
        log.error(f"Erro fatal no coletor Facebook DOM: {e}")
        raise
    finally:
        if context:
            try:
                await context.close()
            except Exception:
                pass
        if browser:
            try:
                if token_valido:
                    log.info("Browserless: nao fechando browser (gerenciado externamente)")
                else:
                    await browser.close()
            except Exception:
                pass
        await pw.stop()