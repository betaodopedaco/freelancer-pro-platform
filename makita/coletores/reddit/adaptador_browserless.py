"""
Adaptador do Reddit para o pipeline Makita — VIA BROWSERLESS (connect_over_cdp).
Cópia do adaptador.py original, mas usando connect_over_cdp com Browserless
ao invés de launch().

Variáveis de ambiente:
  BROWSERLESS_TOKEN  — token de autenticação do Browserless (obrigatório)
  BROWSERLESS_HOST   — host do Browserless (padrão: chrome.browserless.io)
  BROWSERLESS_PORT   — porta do Browserless (padrão: 9222)
"""
import asyncio, hashlib, json, logging, os, time
from datetime import datetime, timezone
from playwright.async_api import async_playwright

from makita.comum.db import get_palavras_ativas, ja_visto
from makita.comum.fila import publicar
from makita.comum.modelos import SinalBruto

log = logging.getLogger("reddit.adaptador_browserless")

INTERVALO = int(os.getenv("REDDIT_POLL_INTERVAL", "1800"))
SLEEP_ENTRE = 3
MAX_POR_PALAVRA = 10

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
COOKIE_PATH = os.path.join(RAIZ, "tofinder", "reddit_cookies.json")

# ── Config Browserless ──────────────────────────────────────────────
BROWSERLESS_TOKEN = os.getenv("BROWSERLESS_TOKEN", "2UkpDDNQOGhjTpu8d724215942577713a7322a27c52af0bf0")
BROWSERLESS_HOST = os.getenv("BROWSERLESS_HOST", "chrome.browserless.io")

# Browserless v2 — sem porta, token vai na query string
# Timeout de 120s (120000ms) para evitar corte em 65s
WS_ENDPOINT = f"wss://{BROWSERLESS_HOST}?token={BROWSERLESS_TOKEN}&timeout=120000"


async def _search_reddit(page, palavra: str) -> list[dict]:
    """
    Busca no reddit.com/search e extrai posts.
    Usa wait_for_selector para aguardar JS renderizar antes de extrair.
    """
    url = f"https://www.reddit.com/search/?q={palavra}&sort=new&t=all"
    log.info(f"  Reddit: navegando para {url}")

    graphql_data = None

    async def on_response(response):
        nonlocal graphql_data
        if "shreddit/graphql" in response.url:
            try:
                data = await response.json()
                if isinstance(data, dict) and data.get("data"):
                    graphql_data = data
            except Exception:
                pass

    page.on("response", lambda r: asyncio.ensure_future(on_response(r)))

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log.warning(f"  Reddit goto timeout: {e}")

    log.info(f"  Reddit URL atual: {page.url}")

    # ── Aguarda JS renderizar os posts ─────────────────────────────
    selectors_espera = [
        "shreddit-post",                               # web component novo Reddit
        "article",                                     # tag semântica
        '[data-testid="post-container"]',              # data-testid genérico
        '[data-testid="search-post-unit"]',            # SDU antigo
        'a[data-testid="post-title-text"]',            # link de título
        'a[id^="search-post-title-"]',                 # fallback ID
    ]
    elemento_encontrado = None
    for sel in selectors_espera:
        try:
            log.info(f"  Reddit: esperando selector '{sel}' (timeout 10s)...")
            await page.wait_for_selector(sel, timeout=10000)
            elemento_encontrado = sel
            log.info(f"  Reddit: selector '{sel}' encontrado! JS renderizou.")
            break
        except Exception:
            log.info(f"  Reddit: selector '{sel}' não apareceu em 10s.")
            continue

    if not elemento_encontrado:
        log.warning("  ⚠️ Nenhum selector de post encontrado após 10s.")
        log.warning("  Reddit pode ter mudado a estrutura ou bloqueado o IP.")
        try:
            html = await page.content()
            log.warning(f"  HTML preview (1000 chars):\n{html[:1000]}")
        except Exception as ee:
            log.warning(f"  Erro ao capturar HTML: {ee}")
        return []

    # Scroll para carregar mais
    try:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(2)
    except Exception:
        pass

    # Tentar GraphQL primeiro (mais rico)
    if graphql_data:
        posts = _extract_from_graphql(graphql_data)
        if posts:
            log.info(f"  Reddit: {len(posts)} posts extraídos via GraphQL")
            return posts

    # DOM scraping
    posts = await _scrape_sdu(page)
    log.info(f"  Reddit: {len(posts)} posts extraídos via DOM")
    return posts


def _extract_from_graphql(data: dict) -> list[dict]:
    """Extrai posts do JSON GraphQL do shreddit."""
    posts = []
    edges = None
    for path in [
        ["data", "search", "results", "edges"],
        ["data", "subreddit", "search", "edges"],
    ]:
        try:
            d = data
            for k in path:
                d = d[k]
            edges = d
            if edges:
                break
        except Exception:
            pass

    if not edges:
        edges = _find_edges(data)
    if not edges:
        return []

    for edge in edges:
        try:
            node = edge.get("node", {})
            if not node or not node.get("title"):
                continue

            title = node.get("title", "")
            selftext = node.get("selftext", "") or node.get("textBody", "") or ""
            author_obj = node.get("author", {})
            author = author_obj.get("name", "") if isinstance(author_obj, dict) else str(author_obj)
            permalink = node.get("permalink", "")
            if permalink and not permalink.startswith("http"):
                permalink = "https://www.reddit.com" + permalink
            score = node.get("score", 0) or node.get("ups", 0)
            post_id = node.get("_id", node.get("id", ""))

            sr_obj = node.get("subreddit", {})
            subreddit = sr_obj.get("name", "") if isinstance(sr_obj, dict) else str(sr_obj)

            if not permalink and post_id and subreddit:
                permalink = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/"

            if title and permalink:
                posts.append({
                    "title": title,
                    "text": selftext or title,
                    "author": author or "[deleted]",
                    "url": permalink,
                    "subreddit": subreddit,
                    "score": int(score),
                })
        except Exception:
            continue

    return posts


def _find_edges(obj, depth=0, max_depth=6):
    if depth > max_depth:
        return None
    if isinstance(obj, dict):
        if "edges" in obj and isinstance(obj["edges"], list):
            edges = obj["edges"]
            if edges and isinstance(edges[0], dict):
                node = edges[0].get("node", {})
                if isinstance(node, dict) and "title" in node:
                    return edges
        for v in obj.values():
            result = _find_edges(v, depth + 1, max_depth)
            if result:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_edges(item, depth + 1, max_depth)
            if result:
                return result
    return None


async def _scrape_sdu(page) -> list[dict]:
    """Extrai posts via DOM SDU (data-testid=search-post-unit)."""
    try:
        posts_data = await page.evaluate("""
            () => {
                const posts = [];
                const containers = document.querySelectorAll(
                    '[data-testid="search-post-unit"], ' +
                    '[data-testid="sdui-post-unit"]'
                );
                
                containers.forEach(container => {
                    const titleEl = container.querySelector(
                        'a[data-testid="post-title-text"], ' +
                        'a[data-testid="post-title"], ' +
                        'a[id^="search-post-title-"]'
                    );
                    const title = titleEl ? titleEl.innerText.trim() : null;
                    if (!title) return;
                    
                    let url = '';
                    if (titleEl) {
                        url = titleEl.getAttribute('href') || '';
                        if (url && !url.startsWith('http')) {
                            url = 'https://www.reddit.com' + url;
                        }
                    }
                    
                    let author = '[deleted]';
                    const authorLink = container.querySelector('a[href^="/user/"]');
                    if (authorLink) {
                        author = authorLink.innerText.trim().replace(/^u\\//, '');
                    }
                    
                    let score = 0;
                    const scoreEl = container.querySelector('faceplate-number');
                    if (scoreEl) {
                        const scoreText = scoreEl.innerText.trim().replace(/[^0-9k]/g, '');
                        score = scoreText.includes('k')
                            ? parseInt(scoreText) * 1000 || 0
                            : parseInt(scoreText) || 0;
                    }
                    
                    let text = title;
                    const textPreview = container.querySelector('[id^="post-preview-"]');
                    if (textPreview) {
                        text = textPreview.innerText.trim();
                    }
                    
                    posts.push({ title, url, author, score, text: text.substring(0, 2000) });
                });
                
                // Fallback: título-only
                if (posts.length === 0) {
                    document.querySelectorAll('a[data-testid="post-title-text"], a[id^="search-post-title-"]').forEach(el => {
                        const title = el.innerText.trim();
                        let url = el.getAttribute('href') || '';
                        if (url && !url.startsWith('http')) url = 'https://www.reddit.com' + url;
                        posts.push({ title, url, author: '[deleted]', score: 0, text: title });
                    });
                }
                
                return posts;
            }
        """)

        if not posts_data:
            return []

        posts = []
        seen_urls = set()
        for p in posts_data:
            if not p.get("title") or not p.get("url"):
                continue
            if p["url"] in seen_urls:
                continue
            seen_urls.add(p["url"])
            posts.append({
                "title": p["title"],
                "text": p.get("text") or p["title"],
                "author": p.get("author", "[deleted]"),
                "url": p["url"],
                "score": p.get("score", 0),
            })
        return posts

    except Exception as e:
        log.debug(f"Reddit DOM scrape erro: {e}")
        return []


async def colect_reddit_browserless() -> None:
    """
    Versão Browserless do coletor Reddit.
    Conecta via connect_over_cdp ao invés de launch().
    Fallback para launch() se BROWSERLESS_TOKEN não estiver definida.
    """
    log.info("Reddit adaptador BROWSERLESS iniciado (connect_over_cdp).")
    
    pw = await async_playwright().start()
    
    # ── connect_over_cdp ou launch() com fallback ──────────────────
    if BROWSERLESS_TOKEN and BROWSERLESS_TOKEN != "2UkpDDNQOGhjTpu8d724215942577713a7322a27c52af0bf0":
        log.info(f"Conectando via Browserless: {WS_ENDPOINT[:60]}...")
        browser = await pw.chromium.connect_over_cdp(WS_ENDPOINT)
    else:
        log.info("BROWSERLESS_TOKEN não configurada. Usando launch() local.")
        browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1366, "height": 768},
    )

    if os.path.exists(COOKIE_PATH):
        with open(COOKIE_PATH) as f:
            await context.add_cookies(json.load(f))
        log.info("Reddit: cookies carregados.")
    else:
        log.info("Reddit: rodando sem login.")

    await asyncio.sleep(5)

    try:
        while True:
            log.info("Reddit: iniciando ciclo...")
            try:
                palavras = await get_palavras_ativas()
            except Exception as e:
                log.error(f"Reddit: erro palavras: {e}")
                await asyncio.sleep(60)
                continue
            if not palavras:
                await asyncio.sleep(60)
                continue

            total = 0
            for palavra in palavras[:5]:
                try:
                    page = await context.new_page()
                    posts = await _search_reddit(page, palavra)
                    await page.close()

                    for p in posts[:MAX_POR_PALAVRA]:
                        texto_completo = p["title"] + " " + p.get("text", "")
                        source_id = "rd_" + hashlib.md5(
                            (p["url"] + texto_completo[:40]).encode()
                        ).hexdigest()[:12]

                        if await ja_visto(source_id):
                            continue

                        sinal = SinalBruto(
                            plataforma="reddit",
                            source_id=source_id,
                            texto=texto_completo[:800],
                            url=p["url"],
                            autor=p.get("author", "[deleted]"),
                            palavra_chave=palavra,
                            usuario_id=0,
                            publicado_em=datetime.now(timezone.utc).isoformat(),
                        )
                        await publicar(sinal)
                        total += 1

                    log.info(f"Reddit '{palavra}': {len(posts)} posts → {total} novos")

                except Exception as e:
                    log.error(f"Reddit erro '{palavra}': {e}")
                    try:
                        await page.close()
                    except Exception:
                        pass

                await asyncio.sleep(SLEEP_ENTRE)

            log.info(f"Reddit ciclo: {total} novos. Próximo em {INTERVALO}s.")
            await asyncio.sleep(INTERVALO)

    finally:
        await context.close()
        # Não fecha o browser — ele é gerenciado pelo Browserless
        await pw.stop()