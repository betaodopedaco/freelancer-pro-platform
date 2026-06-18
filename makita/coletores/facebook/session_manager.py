"""
makita/coletores/facebook/session_manager.py
=============================================
Renovação automática dos tokens do Facebook via Playwright.
Persiste em makita.comum.db e é chamado por main.py.
"""
import asyncio
import json
import logging
import os
import urllib.parse

from playwright.async_api import async_playwright

from makita.comum.db import salvar_sessao, ler_sessao

log = logging.getLogger("fb_session_manager")

FB_C_USER = os.getenv("FB_C_USER", "")
FB_XS = os.getenv("FB_XS", "")
FB_FR = os.getenv("FB_FR", "")

_COOKIES = [
    {"name": "c_user", "value": FB_C_USER, "domain": ".facebook.com", "path": "/"},
    {"name": "xs",     "value": FB_XS,     "domain": ".facebook.com", "path": "/"},
    {"name": "fr",     "value": FB_FR,     "domain": ".facebook.com", "path": "/"},
]

_TOKEN_KEYS = [
    "fb_dtsg", "lsd", "jazoest", "__hs", "__rev", "__s", "__hsi",
    "__dyn", "__csr", "__spin_r", "__spin_t", "__hblp", "__hsdp",
    "__sjsp", "__ccg", "doc_id",
]

DOC_ID_FALLBACK = "27711418425128380"
REFRESH_INTERVAL = int(os.getenv("FB_TOKEN_REFRESH_SECS", "600"))  # 10 min


async def _capture_tokens() -> dict | None:
    """Abre Playwright, navega até busca FB, captura tokens GraphQL."""
    log.info("Capturando tokens do Facebook via Playwright...")
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled",
                       "--no-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 768},
                locale="pt-BR",
            )
            await ctx.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', "
                "{get: () => undefined})"
            )
            await ctx.add_cookies(_COOKIES)
            page = await ctx.new_page()
            loop = asyncio.get_event_loop()
            token_future: asyncio.Future = loop.create_future()

            def on_request(req):
                if (
                    "/api/graphql/" in req.url
                    and req.post_data
                    and "SearchCometResults" in req.post_data
                    and not token_future.done()
                ):
                    token_future.set_result(req.post_data)

            page.on("request", on_request)
            await page.goto(
                "https://www.facebook.com/search/posts/?q=design",
                wait_until="domcontentloaded",
                timeout=30000,
            )

            try:
                raw_post_data = await asyncio.wait_for(
                    token_future, timeout=35
                )
            except asyncio.TimeoutError:
                log.error("Timeout capturando request GraphQL.")
                await browser.close()
                return None

            await browser.close()

        # Parse form data
        params = {}
        for pair in raw_post_data.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                params[k] = urllib.parse.unquote_plus(v)

        tokens = {k: params[k] for k in _TOKEN_KEYS if k in params}

        if "fb_dtsg" not in tokens or not tokens["fb_dtsg"]:
            log.error("fb_dtsg não encontrado na resposta.")
            return None

        if "doc_id" not in tokens or not tokens["doc_id"]:
            log.warning(f"doc_id ausente. Usando fallback {DOC_ID_FALLBACK}.")
            tokens["doc_id"] = DOC_ID_FALLBACK
        else:
            log.info(f"doc_id capturado: {tokens['doc_id']}")

        log.info(f"Tokens OK — fb_dtsg={tokens['fb_dtsg'][:20]}...")
        return tokens

    except Exception as e:
        log.error(f"Erro capturando tokens: {e}")
        return None


async def refresh_loop() -> None:
    """
    Loop que captura e persiste tokens do Facebook a cada REFRESH_INTERVAL.
    A primeira captura é imediata.
    """
    log.info(f"Session manager FB iniciado. "
             f"Renovação a cada {REFRESH_INTERVAL}s.")

    # Tenta uma captura inicial imediata
    tokens = await _capture_tokens()
    if tokens:
        await salvar_sessao("facebook", tokens)
        log.info("Tokens FB salvos no banco (primeira captura).")
    else:
        log.warning("Captura inicial falhou — tentando novamente em 60s.")
        await asyncio.sleep(60)

    while True:
        await asyncio.sleep(REFRESH_INTERVAL)
        tokens = await _capture_tokens()
        if tokens:
            await salvar_sessao("facebook", tokens)
            log.info("Tokens FB renovados com sucesso.")
        else:
            log.error("Falha na renovação dos tokens FB — "
                      "coletor pode parar até próxima tentativa.")