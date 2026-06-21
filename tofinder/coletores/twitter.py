"""
coletores/twitter.py
Coletor do Twitter/X usando Playwright com cookies persistentes e agrupamento de keywords.
"""
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import List, Dict

from playwright.async_api import async_playwright

import config
from models import Lead, Platform
from pipeline import process_lead
from logger import get_logger
from keyword_grouper import group_keywords
from coletores.twitter_cookie_loader import load_twitter_cookies

log = get_logger("twitter")

# ---------------------------------------------------------------------------
# Motor de captura (instância única)
# ---------------------------------------------------------------------------
class _TwitterCapture:
    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self.ready = False

    async def start(self):
        try:
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)
            self._context = await self._browser.new_context()

            # Usa o loader centralizado (TWITTER_COOKIES_B64 > twitter_cookies.json)
            cookies = load_twitter_cookies()
            if not cookies:
                log.warning(
                    "twitter_cookies.json não encontrado e TWITTER_COOKIES_B64 não definida. "
                    "Execute login_twitter.py ou defina TWITTER_COOKIES_B64."
                )
                return
            await self._context.add_cookies(cookies)
            log.info(f"Twitter: {len(cookies)} cookies carregados via loader centralizado.")
            self.ready = True
            log.info("Twitter: Playwright iniciado.")
        except Exception as e:
            log.error(f"Twitter: erro ao iniciar Playwright - {e}")

    async def search(self, keyword: str, limit: int = 5) -> List[Dict]:
        if not self.ready:
            return []
        page = await self._context.new_page()
        tweets = []
        try:
            url = f"https://twitter.com/search?q={keyword}&f=live"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception:
                try:
                    current_url = page.url
                    html_preview = (await page.content())[:500]
                    log.error(
                        f"TIMEOUT DEBUG: url_atual={current_url} html_inicio={html_preview}"
                    )
                except Exception:
                    pass
                raise
            await asyncio.sleep(3)
            articles = await page.query_selector_all('article[data-testid="tweet"]')
            for article in articles[:limit]:
                text_elem = await article.query_selector('div[data-testid="tweetText"]')
                text = (await text_elem.inner_text()).strip() if text_elem else ""
                author_elem = await article.query_selector(
                    'div[data-testid="User-Name"]'
                )
                author = (
                    (await author_elem.inner_text()).strip() if author_elem else "unknown"
                )
                link_elem = await article.query_selector('a[href*="/status/"]')
                link = await link_elem.get_attribute("href") if link_elem else ""
                if link.startswith("/"):
                    link = "https://twitter.com" + link
                tweets.append(
                    {
                        "url": link,
                        "author": author,
                        "text": text,
                        "ts": datetime.now(timezone.utc).timestamp(),
                    }
                )
        except Exception as e:
            log.error(f"Twitter busca: {e}")
        finally:
            await page.close()
        return tweets


# ---------------------------------------------------------------------------
# Instância global única
# ---------------------------------------------------------------------------
_instance: _TwitterCapture = None


async def _get_instance() -> _TwitterCapture:
    global _instance
    if _instance is None:
        _instance = _TwitterCapture()
        await _instance.start()
    return _instance


# ---------------------------------------------------------------------------
# Coletor principal
# ---------------------------------------------------------------------------
async def collect_twitter():
    api = await _get_instance()
    if not api.ready:
        log.warning("Twitter: módulo não inicializado. Saindo do coletor.")
        return

    poll = int(os.getenv("TW_POLL_INTERVAL", config.POLL_INTERVAL))

    while True:
        log.info("Twitter polling...")

        # Agrupa keywords em baldes (Fase A do plano)
        groups = group_keywords(config.KEYWORDS)
        log.info(f"Twitter: {len(config.KEYWORDS)} keywords agrupadas em {len(groups)} baldes.")

        for root, keywords in groups.items():
            try:
                tweets = await api.search(root, limit=5)
                for t in tweets:
                    # Verifica qual keyword específica casou
                    matched_kw = None
                    for kw in keywords:
                        if kw.lower() in t["text"].lower():
                            matched_kw = kw
                            break
                    if not matched_kw:
                        continue

                    # Filtro antidirecional
                    if any(
                        word in t["text"].lower()
                        for word in ["[for hire]", "sou designer", "faço logos", "orçamento"]
                    ):
                        continue

                    source_id = (
                        f"tw_{hashlib.md5((t['url'] + t['text'][:40]).encode()).hexdigest()[:12]}"
                    )
                    lead = Lead(
                        source=Platform.TWITTER,
                        source_id=source_id,
                        title=t["text"][:120],
                        text=t["text"][:800],
                        url=t["url"],
                        author=t["author"],
                        posted_at=datetime.fromtimestamp(t["ts"], tz=timezone.utc),
                        keyword_matched=matched_kw,
                    )
                    await process_lead(lead, None)

            except Exception as e:
                log.error(f"Twitter '{root}': {e}")

            await asyncio.sleep(2)

        log.info(f"Twitter: ciclo concluído. Aguardando {poll}s.")
        await asyncio.sleep(poll)