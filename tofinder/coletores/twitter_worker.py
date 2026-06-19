import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from playwright.async_api import async_playwright
import config
from models import Lead, Platform
from pipeline import process_lead
from keyword_grouper import group_keywords
from logger import get_logger
from coletores.twitter_cookie_loader import load_twitter_cookies

log = get_logger("twitter_worker")

# Limite de buscas por sessao antes de renovar
MAX_SEARCHES_PER_SESSION = 40


class TwitterWorker:
    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._search_count = 0          # buscas na sessao atual
        self._total_searches = 0        # buscas totais (todas as sessoes)
        self._session_renewals = 0
        self._total_renewal_time = 0.0
        self._tweets_before_renewal = 0  # tweets coletados antes da ultima renovacao

    async def start(self):
        """Inicia o Playwright e carrega cookies via loader centralizado."""
        try:
            if self._pw is None:
                self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)
            self._context = await self._browser.new_context()
            
            # Usa o loader centralizado (TWITTER_COOKIES_B64 > twitter_cookies.json)
            cookies = load_twitter_cookies()
            if not cookies:
                log.error("Twitter Worker: nenhum cookie disponível. Execute login_twitter.py ou defina TWITTER_COOKIES_B64.")
                return False
            
            await self._context.add_cookies(cookies)
            log.info(f"Twitter Worker: {len(cookies)} cookies carregados via loader centralizado.")
            return True
        except Exception as e:
            log.error(f"Twitter Worker: erro ao iniciar - {e}")
            return False

    def _is_context_valid(self):
        """Verifica se browser e context ainda estao abertos."""
        return self._browser is not None and self._context is not None

    async def _safe_close_browser(self, timeout=10):
        """Fecha browser com timeout para evitar hang."""
        if self._browser is None:
            return
        try:
            await asyncio.wait_for(self._browser.close(), timeout=timeout)
        except (asyncio.TimeoutError, Exception) as e:
            log.warning(f"Twitter Worker: timeout ao fechar browser ({e}), forçando...")
            # Força fechamento dos processos filhos do chromium
            try:
                if hasattr(self._browser, '_impl_obj'):
                    proc = self._browser._impl_obj._connection._transport._proc
                    if proc and proc.poll() is None:
                        proc.kill()
            except Exception:
                pass
        self._browser = None
        self._context = None

    async def _safe_stop_pw(self, timeout=10):
        """Para Playwright com timeout para evitar hang."""
        if self._pw is None:
            return
        try:
            await asyncio.wait_for(self._pw.stop(), timeout=timeout)
        except (asyncio.TimeoutError, Exception) as e:
            log.warning(f"Twitter Worker: timeout ao parar Playwright ({e})")
        self._pw = None

    async def _renew_session(self):
        """Fecha browser e reabre uma nova sessao."""
        t0 = time.time()
        self._session_renewals += 1
        log.info(f"Twitter Worker: renovando sessao #{self._session_renewals} (apos {self._search_count} buscas)...")
        
        # Fecha browser atual com timeout
        await self._safe_close_browser(timeout=10)
        
        # Para Playwright com timeout
        await self._safe_stop_pw(timeout=10)
        
        # Aguarda limpeza completa
        await asyncio.sleep(2)
        
        ok = await self.start()
        t_renewal = time.time() - t0
        self._total_renewal_time += t_renewal
        
        if ok:
            self._search_count = 0  # RESET do contador apos renovacao bem-sucedida
            log.info(f"Twitter Worker: sessao renovada em {t_renewal:.2f}s (counter resetado)")
        else:
            log.error(f"Twitter Worker: falha ao renovar sessao")
        
        return ok

    async def search(self, keyword: str, _retry=False):
        """Busca uma keyword. Renova sessao automaticamente a cada 40 buscas."""
        # Verifica se precisa renovar (so se nao veio de retry)
        if not _retry and self._search_count >= MAX_SEARCHES_PER_SESSION:
            await self._renew_session()
        
        # Verifica se context ainda esta valido
        if not self._is_context_valid():
            log.warning("Twitter Worker: context invalido, renovando...")
            await self._renew_session()
        
        try:
            page = await self._context.new_page()
        except Exception as e:
            # Context fechado durante busca - renova e tenta 1 vez
            if not _retry:
                log.warning(f"Twitter Worker: context fechado ao criar pagina, renovando... ({e})")
                await self._renew_session()
                return await self.search(keyword, _retry=True)
            raise
        
        self._search_count += 1
        self._total_searches += 1
        try:
            url = f"https://twitter.com/search?q={keyword}&f=live"
            
            # Intercepta SearchTimeline ANTES de navegar
            search_data = None
            async def on_response(response):
                nonlocal search_data
                if "SearchTimeline" in response.url:
                    try:
                        search_data = await response.json()
                    except:
                        pass
            
            page.on("response", lambda r: asyncio.ensure_future(on_response(r)))
            
            await page.goto(url, wait_until="load", timeout=30000)

            # Espera pelas celulas de tweet
            try:
                await page.wait_for_selector('div[data-testid="cellInnerDiv"]', timeout=10000)
            except:
                return []

            # Espera dados chegarem
            await asyncio.sleep(1)
            
            if search_data:
                return self._extract_tweets_from_json(search_data)
            
            # Fallback: DOM scraping
            await asyncio.sleep(2)
            cells = await page.query_selector_all('div[data-testid="cellInnerDiv"]')
            tweets = []
            for cell in cells[:5]:
                text_el = await cell.query_selector('div[data-testid="tweetText"]')
                if not text_el:
                    text_el = await cell.query_selector('div[lang]')
                text = (await text_el.inner_text()).strip() if text_el else ""

                author_el = await cell.query_selector('div[data-testid="User-Name"]')
                author = (await author_el.inner_text()).strip() if author_el else "unknown"

                link_el = await cell.query_selector('a[href*="/status/"]')
                link = await link_el.get_attribute("href") if link_el else ""
                if link.startswith("/"):
                    link = f"https://twitter.com{link}"

                if text and link:
                    tweets.append({"url": link, "author": author, "text": text})

            return tweets
        except Exception as e:
            log.error(f"Twitter Worker busca: {e}")
            return []
        finally:
            await page.close()

    def _extract_tweets_from_json(self, data):
        """Extrai tweets da resposta SearchTimeline JSON."""
        tweets = []
        try:
            instructions = data["data"]["search_by_raw_query"]["search_timeline"]["timeline"]["instructions"]
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
                    sn = tr.get("core", {}).get("user_results", {}).get("result", {}).get("core", {}).get("screen_name", "")
                    if rid and ft:
                        url = f"https://twitter.com/{sn}/status/{rid}"
                        tweets.append({"url": url, "author": sn, "text": ft})
        except Exception:
            pass
        return tweets

    def get_stats(self):
        """Retorna estatisticas da sessao."""
        return {
            "search_count": self._search_count,
            "total_searches": self._total_searches,
            "session_renewals": self._session_renewals,
            "total_renewal_time": self._total_renewal_time,
            "tweets_before_renewal": self._tweets_before_renewal,
        }

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()