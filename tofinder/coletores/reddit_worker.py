"""
coletores/reddit_worker.py — Coletor do Reddit via Playwright + intercept

FLUXO:
  1. Playwright abre reddit.com/search/?q={keyword}&sort=new
  2. Tenta capturar POST /svc/shreddit/graphql (JSON)
  3. Fallback: DOM scraping da estrutura SDU (Server-Driven UI)
  4. Renova sessão a cada 40 buscas

ARQUITETURA:
  Idêntica ao twitter_worker.py — Playwright roda headless,
  intercepta response de rede, extrai dados direto.
"""

import asyncio
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import List, Dict
from playwright.async_api import async_playwright

# Garante que o diretório raiz do projeto está no path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import config
from models import Lead, Platform
from pipeline import process_lead
from logger import get_logger

log = get_logger("reddit_worker")

MAX_SEARCHES_PER_SESSION = 40


class RedditWorker:
    def __init__(self):
        self._pw = None
        self._browser = None
        self._context = None
        self._search_count = 0
        self._total_searches = 0
        self._session_renewals = 0
        self._total_renewal_time = 0.0

    async def start(self):
        try:
            if self._pw is None:
                self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 768},
            )

            cookie_path = "tofinder/reddit_cookies.json"
            if os.path.exists(cookie_path):
                with open(cookie_path, "r") as f:
                    await self._context.add_cookies(json.load(f))
                log.info(f"Reddit Worker: cookies carregados.")

            log.info("Reddit Worker: Playwright iniciado.")
            return True
        except Exception as e:
            log.error(f"Reddit Worker: erro ao iniciar - {e}")
            return False

    def _is_context_valid(self):
        return self._browser is not None and self._context is not None

    async def _safe_close_browser(self, timeout=10):
        if self._browser is None:
            return
        try:
            await asyncio.wait_for(self._browser.close(), timeout=timeout)
        except (asyncio.TimeoutError, Exception) as e:
            log.warning(f"Reddit Worker: timeout ao fechar browser ({e})")
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
        if self._pw is None:
            return
        try:
            await asyncio.wait_for(self._pw.stop(), timeout=timeout)
        except (asyncio.TimeoutError, Exception) as e:
            log.warning(f"Reddit Worker: timeout ao parar Playwright ({e})")
        self._pw = None

    async def _renew_session(self):
        t0 = time.time()
        self._session_renewals += 1
        log.info(
            f"Reddit Worker: renovando sessao #{self._session_renewals} "
            f"(apos {self._search_count} buscas)..."
        )
        await self._safe_close_browser(timeout=10)
        await self._safe_stop_pw(timeout=10)
        await asyncio.sleep(2)
        ok = await self.start()
        t_renewal = time.time() - t0
        self._total_renewal_time += t_renewal
        if ok:
            self._search_count = 0
            log.info(f"Reddit Worker: sessao renovada em {t_renewal:.2f}s")
        else:
            log.error("Reddit Worker: falha ao renovar sessao")
        return ok

    async def search(self, keyword: str, _retry=False, enrich_selftext=True) -> List[Dict]:
        """
        Busca uma keyword no Reddit.
        
        Args:
            keyword: termo de busca
            _retry: uso interno para retry
            enrich_selftext: se True, abre os top 5 posts para extrair selftext
        
        Retorna lista de dicts com title, text, author, url, subreddit, timestamp, score.
        """
        if not _retry and self._search_count >= MAX_SEARCHES_PER_SESSION:
            await self._renew_session()

        if not self._is_context_valid():
            log.warning("Reddit Worker: context invalido, renovando...")
            await self._renew_session()

        try:
            page = await self._context.new_page()
        except Exception as e:
            if not _retry:
                log.warning(f"Reddit Worker: context fechado, renovando... ({e})")
                await self._renew_session()
                return await self.search(keyword, _retry=True)
            raise

        self._search_count += 1
        self._total_searches += 1

        try:
            url = f"https://www.reddit.com/search/?q={keyword}&sort=new&t=all"

            # Intercepta GraphQL e HTML parcial
            graphql_data = None
            partial_html = None

            async def on_response(response):
                nonlocal graphql_data, partial_html

                if "shreddit/graphql" in response.url:
                    try:
                        data = await response.json()
                        if isinstance(data, dict) and data.get("data"):
                            graphql_data = data
                    except Exception:
                        pass

                if "shreddit/search" in response.url and "partial+html" in (
                    response.headers.get("content-type", "")
                ):
                    try:
                        partial_html = await response.text()
                    except Exception:
                        pass

            page.on("response", lambda r: asyncio.ensure_future(on_response(r)))
            try:
                await page.goto(url, wait_until="load", timeout=30000)
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
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)

            # TENTATIVA 1: GraphQL JSON
            if graphql_data:
                posts = self._extract_posts_from_graphql(graphql_data)
                if posts:
                    log.info(f"Reddit '{keyword}': {len(posts)} posts via GraphQL.")
                    return posts

            # TENTATIVA 2: DOM scraping SDU (Server-Driven UI)
            posts = await self._scrape_sdu_posts(page)
            if posts:
                log.info(f"Reddit '{keyword}': {len(posts)} posts via DOM SDU.")

                # Enriquecimento: selftext para top 5 posts
                if enrich_selftext and len(posts) > 0:
                    enriched = 0
                    top_posts = sorted(
                        posts, key=lambda p: p.get("score", 0), reverse=True
                    )[:5]

                    for tp in top_posts:
                        selftext = await self._fetch_selftext(page, tp["url"])
                        if selftext:
                            # Atualiza o texto no post original
                            for p in posts:
                                if p["url"] == tp["url"]:
                                    p["text"] = selftext
                                    enriched += 1
                                    break

                    if enriched:
                        log.info(
                            f"Reddit '{keyword}': {enriched}/{len(top_posts)} "
                            f"posts enriquecidos com selftext."
                        )

                return posts

            return []

        except Exception as e:
            log.error(f"Reddit Worker busca '{keyword}': {e}")
            return []
        finally:
            await page.close()

    # ─────────────────────────────────────────────────────────────
    # ESTRATÉGIA 1: GraphQL JSON
    # ─────────────────────────────────────────────────────────────

    def _extract_posts_from_graphql(self, data: dict) -> List[Dict]:
        posts = []
        try:
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
                edges = self._find_edges_in_json(data)

            if not edges:
                return []

            for edge in edges:
                try:
                    node = edge.get("node", {})
                    if not node or not node.get("title"):
                        continue

                    title = node.get("title", "")
                    selftext = node.get("selftext", "") or ""
                    text_body = node.get("textBody", "") or ""

                    author_obj = node.get("author", {})
                    author = ""
                    if isinstance(author_obj, dict):
                        author = author_obj.get("name", author_obj.get("_id", ""))
                    elif isinstance(author_obj, str):
                        author = author_obj
                    if not author:
                        author = "[deleted]"

                    sr_obj = node.get("subreddit", {})
                    subreddit = ""
                    if isinstance(sr_obj, dict):
                        subreddit = sr_obj.get("name", sr_obj.get("displayName", ""))
                    elif isinstance(sr_obj, str):
                        subreddit = sr_obj

                    permalink = node.get("permalink", "") or node.get("url", "")
                    if permalink and not permalink.startswith("http"):
                        permalink = "https://www.reddit.com" + permalink

                    ts = node.get("created_utc", 0)
                    if ts and isinstance(ts, (int, float)) and ts > 1e9:
                        posted_at = datetime.fromtimestamp(ts, tz=timezone.utc)
                    else:
                        posted_at = datetime.now(timezone.utc)

                    score = node.get("score", 0) or node.get("ups", 0)
                    post_id = node.get("_id", node.get("id", ""))

                    if not permalink and post_id:
                        if subreddit:
                            permalink = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/"
                        else:
                            permalink = f"https://www.reddit.com/comments/{post_id}/"

                    if not title or not permalink:
                        continue

                    text = selftext or text_body or title
                    posts.append({
                        "title": title,
                        "text": text,
                        "author": author,
                        "url": permalink,
                        "subreddit": subreddit,
                        "timestamp": posted_at.timestamp(),
                        "score": int(score),
                    })

                except Exception as e:
                    log.debug(f"Reddit Worker: erro ao parsear edge: {e}")
                    continue

        except Exception as e:
            log.debug(f"Reddit Worker: erro no parse GraphQL: {e}")

        return posts

    def _find_edges_in_json(self, obj, depth=0, max_depth=6):
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
                result = self._find_edges_in_json(v, depth + 1, max_depth)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_edges_in_json(item, depth + 1, max_depth)
                if result:
                    return result
        return None

    # ─────────────────────────────────────────────────────────────
    # ESTRATÉGIA 2: DOM scraping SDU (estrutura atual do Reddit)
    # ─────────────────────────────────────────────────────────────

    async def _scrape_sdu_posts(self, page) -> List[Dict]:
        """
        Extrai posts da estrutura SDU do Reddit (Server-Driven UI, Jun/2026).
        Usa o container [data-testid="search-post-unit"] como âncora principal.
        """
        try:
            posts_data = await page.evaluate("""
                () => {
                    const posts = [];
                    // Container principal de cada resultado de busca
                    const containers = document.querySelectorAll(
                        '[data-testid="search-post-unit"], ' +
                        '[data-testid="sdui-post-unit"]'
                    );
                    
                    containers.forEach(container => {
                        // Título - selector mais específico
                        const titleEl = container.querySelector(
                            'a[data-testid="post-title-text"], ' +
                            'a[data-testid="post-title"], ' +
                            'a[id^="search-post-title-"]'
                        );
                        const title = titleEl ? titleEl.innerText.trim() : null;
                        if (!title) return;
                        
                        // URL do post
                        let url = '';
                        if (titleEl) {
                            url = titleEl.getAttribute('href') || '';
                            if (url && !url.startsWith('http')) {
                                url = 'https://www.reddit.com' + url;
                            }
                        }
                        
                        // Subreddit - linha de crédito do post
                        const creditRow = container.querySelector('[class*="post-credit-row"]');
                        let subreddit = '';
                        if (creditRow) {
                            const subLink = creditRow.querySelector('a[href^="/r/"]');
                            if (subLink) {
                                subreddit = subLink.innerText.trim().replace(/^r\\//, '');
                            }
                        }
                        
                        // Autor - procura no container todo
                        let author = '[deleted]';
                        const authorLink = container.querySelector('a[href^="/user/"]');
                        if (authorLink) {
                            author = authorLink.innerText.trim().replace(/^u\\//, '');
                        }
                        
                        // Score (faceplate-number)
                        let score = 0;
                        const scoreEl = container.querySelector('faceplate-number');
                        if (scoreEl) {
                            const scoreText = scoreEl.innerText.trim().replace(/[^0-9k]/g, '');
                            if (scoreText.includes('k')) {
                                score = parseInt(scoreText) * 1000 || 0;
                            } else {
                                score = parseInt(scoreText) || 0;
                            }
                        }
                        
                        // Timestamp
                        let timestamp = '';
                        const timeEl = container.querySelector('time');
                        if (timeEl) {
                            timestamp = timeEl.getAttribute('datetime') || '';
                        }
                        
                        // Texto do post - procura o container de preview
                        let text = title;
                        const textPreview = container.querySelector('[id^="post-preview-"]');
                        if (textPreview) {
                            text = textPreview.innerText.trim();
                        }
                        // Alternativa: procura por parágrafos ou divs de texto
                        if (text === title) {
                            const textDivs = container.querySelectorAll(
                                'p, div[class*="text"], div[class*="content"]'
                            );
                            for (const div of textDivs) {
                                const t = div.innerText.trim();
                                if (t && t !== title && t.length < 500) {
                                    text = t;
                                    break;
                                }
                            }
                        }
                        
                        posts.push({
                            title: title,
                            url: url,
                            subreddit: subreddit,
                            author: author,
                            score: score,
                            timestamp: timestamp,
                            text: text.substring(0, 2000),
                        });
                    });
                    
                    // Fallback title-only
                    if (posts.length === 0) {
                        document.querySelectorAll('a[data-testid="post-title-text"], a[id^="search-post-title-"]').forEach(el => {
                            const title = el.innerText.trim();
                            let url = el.getAttribute('href') || '';
                            if (url && !url.startsWith('http')) {
                                url = 'https://www.reddit.com' + url;
                            }
                            posts.push({
                                title: title,
                                url: url,
                                subreddit: '',
                                author: '[deleted]',
                                score: 0,
                                timestamp: '',
                                text: title,
                            });
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

                text = p.get("text") or p.get("title") or ""

                ts_str = p.get("timestamp", "")
                ts = time.time()
                if ts_str:
                    try:
                        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        ts = dt.timestamp()
                    except Exception:
                        pass

                try:
                    score = int(p.get("score", "0"))
                except Exception:
                    score = 0

                posts.append({
                    "title": p["title"],
                    "text": text,
                    "author": p.get("author", "[deleted]"),
                    "url": p["url"],
                    "subreddit": p.get("subreddit", ""),
                    "timestamp": ts,
                    "score": score,
                })

            return posts

        except Exception as e:
            log.debug(f"Reddit Worker: erro no DOM SDU: {e}")
            return []

    # ─────────────────────────────────────────────────────────────
    # ENRIQUECIMENTO: Selftext via página individual do post
    # ─────────────────────────────────────────────────────────────

    async def _fetch_selftext(self, page, post_url: str, max_retries=2) -> str:
        """
        Abre a página individual de um post e extrai o selftext.
        Usa o mesmo padrão do TwitterWorker para replies.
        """
        for attempt in range(max_retries):
            try:
                try:
                    await page.goto(post_url, wait_until="load", timeout=30000)
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
                await asyncio.sleep(2)
                # Scroll para forçar renderização
                await page.evaluate("window.scrollTo(0, 500)")
                await asyncio.sleep(1)

                selftext = await page.evaluate("""
                    () => {
                        // Tenta múltiplos seletores
                        const selectors = [
                            'shreddit-post [slot="text-body"]',
                            'shreddit-post .md',
                            'div[data-testid="post"] .md',
                            'div[class*="post"] div[class*="text"]',
                            'div[data-testid="sdui-post"] .md',
                            'script[type="application/ld+json"]',
                        ];
                        for (const sel of selectors) {
                            const el = document.querySelector(sel);
                            if (el) {
                                if (sel.includes('json')) {
                                    try {
                                        const data = JSON.parse(el.innerText);
                                        return data.articleBody || data.description || data.text || '';
                                    } catch(e) { continue; }
                                }
                                const text = el.innerText.trim();
                                if (text.length > 50) return text;
                            }
                        }
                        // Fallback: maior div com texto relevante
                        const allDivs = document.querySelectorAll('div');
                        let best = '';
                        for (const div of allDivs) {
                            const text = div.innerText.trim();
                            if (text.length > 100 && text.length < 50000 && text.length > best.length) {
                                best = text;
                            }
                        }
                        return best || '';
                    }
                """)
                if selftext and len(selftext) > 50:
                    return selftext
            except Exception as e:
                log.debug(f"Reddit Worker: erro ao buscar selftext ({attempt+1}/{max_retries}): {e}")
                await asyncio.sleep(1)
        return ""

    # ─────────────────────────────────────────────────────────────
    # INTEGRAÇÃO COM PIPELINE
    # ─────────────────────────────────────────────────────────────

    async def search_and_push(self, keyword: str, http_session) -> List[Dict]:
        posts = await self.search(keyword)
        for post in posts:
            try:
                source_id = "rd_" + hashlib.md5(
                    (post["url"] + post["title"][:40]).encode()
                ).hexdigest()[:12]

                posted_at = datetime.fromtimestamp(
                    post.get("timestamp", time.time()), tz=timezone.utc,
                )

                lead = Lead(
                    source=Platform.REDDIT,
                    source_id=source_id,
                    title=post["title"][:120],
                    text=post["text"][:800],
                    url=post["url"],
                    author=post["author"],
                    posted_at=posted_at,
                    keyword_matched=keyword,
                    score=post.get("score", 0),
                )
                await process_lead(lead, http_session)
            except Exception as e:
                log.error(f"Reddit Worker: erro ao processar lead: {e}")
        return posts

    def get_stats(self):
        return {
            "search_count": self._search_count,
            "total_searches": self._total_searches,
            "session_renewals": self._session_renewals,
            "total_renewal_time": self._total_renewal_time,
        }

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()