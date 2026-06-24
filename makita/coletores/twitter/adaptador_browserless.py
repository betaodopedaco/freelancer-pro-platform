"""
Adaptador do Twitter para o pipeline Makita — VIA BROWSERLESS (connect_over_cdp).
Cópia do adaptador.py original, mas usando connect_over_cdp com Browserless
ao invés de launch().

Variáveis de ambiente:
  BROWSERLESS_TOKEN  — token de autenticação do Browserless (obrigatório)
  BROWSERLESS_HOST   — host do Browserless (padrão: chrome.browserless.io)
  BROWSERLESS_PORT   — porta do Browserless (padrão: 9222)
"""
import asyncio, hashlib, json, logging, os, sys
from datetime import datetime, timezone
from playwright.async_api import async_playwright

from makita.comum.db import get_palavras_ativas, ja_visto
from makita.comum.fila import publicar
from makita.comum.modelos import SinalBruto

# Adiciona raiz do projeto ao path para importar o loader centralizado
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from tofinder.coletores.twitter_cookie_loader import load_twitter_cookies

log = logging.getLogger("twitter.adaptador_browserless")

INTERVALO = int(os.getenv("TWITTER_POLL_INTERVAL", "1800"))
SLEEP_ENTRE = 3
MAX_POR_PALAVRA = 5

COOKIE_PATH = os.path.join(RAIZ, "tofinder", "twitter_cookies.json")  # fallback legado

# ── Config Browserless ──────────────────────────────────────────────
BROWSERLESS_TOKEN = os.getenv("BROWSERLESS_TOKEN", "2UkpDDNQOGhjTpu8d724215942577713a7322a27c52af0bf0")
BROWSERLESS_HOST = os.getenv("BROWSERLESS_HOST", "chrome.browserless.io")

# Browserless v2 — sem porta, token vai na query string
# Timeout de 120s (120000ms) para evitar corte em 65s
WS_ENDPOINT = f"wss://{BROWSERLESS_HOST}?token={BROWSERLESS_TOKEN}&timeout=120000"


async def _search_palavra(page, palavra: str) -> list[dict]:
    """Busca uma palavra no Twitter e retorna lista de tweets."""
    tweets_list: list[dict] = []

    async def on_response(resp):
        if "SearchTimeline" in resp.url:
            try:
                body = await resp.body()
                data = json.loads(body.decode("utf-8"))
                instructions = (
                    data.get("data", {})
                    .get("search_by_raw_query", {})
                    .get("search_timeline", {})
                    .get("timeline", {})
                    .get("instructions", [])
                )
                for inst in instructions:
                    for entry in inst.get("entries", []):
                        c = entry.get("content", {})
                        if c.get("entryType") != "TimelineTimelineItem":
                            continue
                        ic = c.get("itemContent", {})
                        if ic.get("itemType") != "TimelineTweet":
                            continue
                        tr = ic.get("tweet_results", {}).get("result", {})
                        rid = tr.get("rest_id", "")
                        legacy = tr.get("legacy", {})
                        ft = legacy.get("full_text", "")
                        sn = (
                            tr.get("core", {})
                            .get("user_results", {})
                            .get("result", {})
                            .get("legacy", {})
                            .get("screen_name", "")
                        )
                        if rid and ft:
                            tweets_list.append({
                                "url": f"https://x.com/{sn}/status/{rid}",
                                "author": sn,
                                "text": ft,
                            })
            except Exception:
                pass

    page.on("response", on_response)

    try:
        await page.goto(
            f"https://x.com/search?q={palavra}&f=live",
            wait_until="load",
            timeout=30000,
        )
    except Exception:
        log.error(
            "TIMEOUT DEBUG twitter: url=%s html=%s",
            page.url,
            (await page.content())[:500],
        )
        raise
    try:
        await page.wait_for_selector('div[data-testid="cellInnerDiv"]', timeout=10000)
    except Exception:
        pass
    await asyncio.sleep(2)

    # Fallback DOM se não veio JSON
    if not tweets_list:
        cells = await page.query_selector_all('div[data-testid="cellInnerDiv"]')
        for cell in cells[:MAX_POR_PALAVRA]:
            try:
                text_el = await cell.query_selector('div[data-testid="tweetText"]') or await cell.query_selector('div[lang]')
                text = (await text_el.inner_text()).strip() if text_el else ""
                author_el = await cell.query_selector('div[data-testid="User-Name"]')
                author = (await author_el.inner_text()).strip() if author_el else "unknown"
                link_el = await cell.query_selector('a[href*="/status/"]')
                link = await link_el.get_attribute("href") if link_el else ""
                if link.startswith("/"):
                    link = f"https://x.com{link}"
                if text and link:
                    tweets_list.append({"url": link, "author": author, "text": text})
            except Exception:
                pass

    return tweets_list


async def colect_twitter_browserless() -> None:
    """
    Versão Browserless do coletor Twitter.
    Conecta via connect_over_cdp ao invés de launch().
    Fallback para launch() se BROWSERLESS_TOKEN não estiver definida.
    """
    log.info("Twitter adaptador BROWSERLESS iniciado (connect_over_cdp).")
    
    # Usa o loader centralizado (TWITTER_COOKIES_B64 > twitter_cookies.json)
    cookies = load_twitter_cookies()
    if not cookies:
        log.warning("Twitter: nenhum cookie disponível (loader centralizado falhou). Desativando.")
        return

    pw = await async_playwright().start()
    
    # ── connect_over_cdp ou launch() com fallback ──────────────────
    if BROWSERLESS_TOKEN and BROWSERLESS_TOKEN != "2UkpDDNQOGhjTpu8d724215942577713a7322a27c52af0bf0":
        log.info(f"Conectando via Browserless: {WS_ENDPOINT[:60]}...")
        browser = await pw.chromium.connect_over_cdp(WS_ENDPOINT)
    else:
        log.info("BROWSERLESS_TOKEN não configurada. Usando launch() local.")
        browser = await pw.chromium.launch(headless=True)
    # Cria um contexto isolado (não afeta outras sessões)
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
    )

    await context.add_cookies(cookies)
    log.info(f"Twitter: {len(cookies)} cookies carregados via loader centralizado.")

    await asyncio.sleep(5)

    try:
        while True:
            log.info("Twitter: iniciando ciclo...")
            try:
                palavras = await get_palavras_ativas()
            except Exception as e:
                log.error(f"Twitter: erro palavras: {e}")
                await asyncio.sleep(60)
                continue
            if not palavras:
                await asyncio.sleep(60)
                continue

            total = 0
            for palavra in palavras[:5]:
                try:
                    page = await context.new_page()
                    tweets = await _search_palavra(page, palavra)
                    await page.close()

                    for tw in tweets[:MAX_POR_PALAVRA]:
                        source_id = "tw_" + hashlib.md5(
                            (tw["url"] + tw["text"][:40]).encode()
                        ).hexdigest()[:12]
                        if await ja_visto(source_id):
                            continue
                        sinal = SinalBruto(
                            plataforma="twitter",
                            source_id=source_id,
                            texto=tw["text"][:800],
                            url=tw["url"],
                            autor=tw["author"],
                            palavra_chave=palavra,
                            usuario_id=0,
                            publicado_em=datetime.now(timezone.utc).isoformat(),
                        )
                        await publicar(sinal)
                        total += 1

                    log.info(f"Twitter '{palavra}': {len(tweets)} tweets → {total} novos")

                except Exception as e:
                    log.error(f"Twitter erro '{palavra}': {e}")
                    try:
                        await page.close()
                    except Exception:
                        pass

                await asyncio.sleep(SLEEP_ENTRE)

            log.info(f"Twitter ciclo: {total} novos. Próximo em {INTERVALO}s.")
            await asyncio.sleep(INTERVALO)

    finally:
        await context.close()
        # Não fecha o browser — ele é gerenciado pelo Browserless
        await pw.stop()