"""
coletores/twitter_graphql.py

Coletor do Twitter/X via GraphQL direto (SearchTimeline).
Usa curl-cffi para imitar o browser sem abrir Chromium.

Fluxo:
  1. Lê tokens do banco (capturados pelo twitter_session_manager.py)
  2. Para cada keyword ativa no DB, faz GET SearchTimeline
  3. Parseia search_by_raw_query.search_timeline.timeline.instructions[].entries
  4. Envia tweets para o pipeline

Não abre browser. Não renderiza JS. Não usa DOM.
Playwright só existe no session_manager.
"""

import asyncio
import hashlib
import json
import os
import urllib.parse
from datetime import datetime, timezone
from typing import List, Dict

import aiohttp
from curl_cffi.requests import AsyncSession

import config
import db as database
from coletores.twitter_session_manager import get_tokens, refresh_loop
from coletores.twitter_cookie_loader import load_twitter_cookies
from models import Lead, Platform
from pipeline import process_lead
from logger import get_logger
from watchdog import report_result

log = get_logger("twitter_graphql")

# Máximo de tweets por keyword por ciclo
MAX_TWEETS_PER_KEYWORD = 5

# Intervalo entre keywords no mesmo ciclo (evita rate limit)
INTER_KEYWORD_SLEEP = 1.5  # segundos

# Intervalo do ciclo completo
POLL_INTERVAL = int(os.getenv("TW_POLL_INTERVAL", str(config.POLL_INTERVAL)))


def _build_url(keyword: str, tokens: dict) -> str:
    """
    Constrói a URL completa para o GET SearchTimeline.
    """
    operation_id = tokens.get("operation_id", "")
    if not operation_id:
        log.error("operation_id não disponível nos tokens.")
        return ""

    # Variables — usa as capturadas, mas substitui a query
    try:
        variables = json.loads(tokens.get("variables", "{}"))
    except (json.JSONDecodeError, TypeError):
        variables = {}

    variables["rawQuery"] = keyword
    variables["count"] = MAX_TWEETS_PER_KEYWORD
    variables["querySource"] = "typed_query"
    variables["product"] = "Latest"

    # Features — usa as capturadas ou fallback
    try:
        features = json.loads(tokens.get("features", "{}"))
    except (json.JSONDecodeError, TypeError):
        features = {}

    params = {
        "variables": json.dumps(variables),
        "features": json.dumps(features),
    }

    url = f"https://x.com/i/api/graphql/{operation_id}/SearchTimeline?{urllib.parse.urlencode(params)}"
    return url


def _parse_tweets(response_text: str, keyword: str) -> List[Dict]:
    """
    Parseia a resposta SearchTimeline e extrai tweets relevantes.
    Retorna lista de dicts com url, author, text, ts.

    Estrutura real do JSON:
        data.search_by_raw_query.search_timeline.timeline.instructions[]
            └── entries[]
                └── content.itemContent.tweet_results.result
                    └── legacy.full_text       <-- texto do tweet
                    └── legacy.screen_name     <-- autor
                    └── legacy.created_at      <-- timestamp
                    └── legacy.id_str          <-- id para montar URL
    """
    tweets = []

    if "search_by_raw_query" not in response_text:
        log.debug(f"Resposta sem search_by_raw_query para keyword '{keyword}'.")
        return tweets

    try:
        parsed = json.loads(response_text)

        instructions = (
            parsed.get("data", {})
            .get("search_by_raw_query", {})
            .get("search_timeline", {})
            .get("timeline", {})
            .get("instructions", [])
        )

        if not instructions:
            log.debug(f"Nenhuma instruction encontrada para '{keyword}'.")
            return tweets

        for instruction in instructions:
            entries = instruction.get("entries", [])
            for entry in entries:
                try:
                    # Pula entradas que não são tweets (cursor, etc)
                    content = entry.get("content", {})
                    item_content = content.get("itemContent", {})
                    if not item_content:
                        continue

                    tweet_result = item_content.get("tweet_results", {}).get("result", {})
                    if not tweet_result:
                        continue

                    legacy = tweet_result.get("legacy", {})
                    if not legacy:
                        continue

                    text = legacy.get("full_text", "")
                    if not text or len(text) < 10:
                        continue

                    # Filtra posts que não contêm a keyword
                    if keyword.lower() not in text.lower():
                        continue

                    # Extrai autor
                    screen_name = legacy.get("screen_name", "unknown")
                    user = tweet_result.get("core", {}).get("user_results", {}).get("result", {})
                    author = user.get("legacy", {}).get("name", screen_name) or screen_name

                    # Extrai URL do tweet
                    tweet_id = legacy.get("id_str", "")
                    url = f"https://x.com/{screen_name}/status/{tweet_id}" if tweet_id else ""

                    # Timestamp
                    created_at = legacy.get("created_at", "")
                    try:
                        ts = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").timestamp()
                    except (ValueError, TypeError):
                        ts = datetime.now(timezone.utc).timestamp()

                    tweets.append({
                        "text": text[:1200],
                        "url": url or f"https://x.com/search?q={urllib.parse.quote(keyword)}",
                        "author": author,
                        "screen_name": screen_name,
                        "ts": ts,
                        "tweet_id": tweet_id,
                    })

                except Exception as e:
                    log.debug(f"Erro ao parsear entry: {e}")
                    continue

    except json.JSONDecodeError as e:
        log.error(f"JSON inválido na resposta do Twitter: {e}")
    except Exception as e:
        log.error(f"Erro ao parsear resposta do Twitter: {e}")

    return tweets


async def _search_keyword(keyword: str, tokens: dict) -> List[Dict]:
    """
    Faz uma requisição SearchTimeline para uma keyword.
    Retorna lista de tweets ou lista vazia em caso de erro.
    """
    url = _build_url(keyword, tokens)
    if not url:
        return []

    # Prepara headers
    ct0 = tokens.get("ct0", "")
    
    # Carrega cookies via loader centralizado (TWITTER_COOKIES_B64 > twitter_cookies.json)
    try:
        cookies_list = load_twitter_cookies()
        if not cookies_list:
            log.error("Nenhum cookie disponível para a requisição GraphQL.")
            return []
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies_list)
    except Exception as e:
        log.error(f"Erro ao carregar cookies: {e}")
        return []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://x.com",
        "Referer": "https://x.com/search",
        "Authorization": tokens.get("bearer_token", ""),
        "x-csrf-token": ct0,
        "Cookie": cookie_str,
    }

    try:
        async with AsyncSession(impersonate="chrome110") as session:
            response = await session.get(
                url,
                headers=headers,
                timeout=15,
            )

        if response.status_code != 200:
            log.warning(f"Status {response.status_code} para keyword '{keyword}'.")
            if response.status_code == 404:
                log.error("operation_id expirado! Session manager precisa renovar.")
            return []

        tweets = _parse_tweets(response.text, keyword)
        log.info(f"Twitter GraphQL '{keyword}': {len(tweets)} tweets.")
        return tweets

    except Exception as e:
        log.error(f"Erro na requisição SearchTimeline para '{keyword}': {e}")
        return []


async def _push_lead(
    http_session: aiohttp.ClientSession,
    tweet: Dict,
    keyword: str,
) -> None:
    """Cria um Lead e envia para o pipeline."""
    try:
        source_id = (
            "twgql_"
            + hashlib.md5(
                (tweet["url"] + tweet["text"][:40]).encode()
            ).hexdigest()[:12]
        )

        lead = Lead(
            source=Platform.TWITTER,
            source_id=source_id,
            title=tweet["text"][:120],
            text=tweet["text"][:800],
            url=tweet["url"],
            author=tweet["author"],
            posted_at=datetime.fromtimestamp(tweet["ts"], tz=timezone.utc),
            keyword_matched=keyword,
        )

        await process_lead(lead, http_session)

    except Exception as e:
        log.error(f"Erro ao processar lead do Twitter GraphQL: {e}")


async def collect_twitter_graphql(http_session: aiohttp.ClientSession) -> None:
    """
    Loop principal do coletor Twitter GraphQL.

    A cada ciclo:
    1. Lê tokens do banco (capturados pelo session_manager)
    2. Lê keywords ativas do banco
    3. Para cada keyword, faz GET SearchTimeline
    4. Envia tweets relevantes para o pipeline
    """
    log.info("Twitter GraphQL coletor iniciado.")

    # Garante que o session_manager já rodou ao menos uma vez
    await asyncio.sleep(5)

    while True:
        log.info("Twitter GraphQL: iniciando ciclo de coleta...")

        # 1. Lê tokens
        tokens = await get_tokens()
        if not tokens:
            log.warning("Tokens do Twitter não disponíveis. Aguardando 30s...")
            await asyncio.sleep(30)
            continue

        # Detecta token inválido
        if not tokens.get("operation_id"):
            log.warning("operation_id vazio — tokens inválidos. Aguardando renovação...")
            await asyncio.sleep(30)
            continue

        # 2. Lê keywords ativas do banco
        try:
            keywords = await database.get_all_active_keywords()
        except Exception as e:
            log.error(f"Erro ao buscar keywords do banco: {e}")
            await asyncio.sleep(60)
            continue

        if not keywords:
            log.info("Nenhuma keyword ativa no banco. Usando keywords padrão do config.")
            keywords = config.KEYWORDS

        log.info(f"Twitter GraphQL: {len(keywords)} keywords para coletar.")
        total_leads = 0

        # 3. Busca por keyword
        for keyword in keywords:
            try:
                tweets = await _search_keyword(keyword, tokens)
                report_result("twitter", len(tweets))

                for tweet in tweets:
                    await _push_lead(http_session, tweet, keyword)
                    total_leads += 1

            except Exception as e:
                log.error(f"Erro ao coletar keyword '{keyword}': {e}")

            await asyncio.sleep(INTER_KEYWORD_SLEEP)

        log.info(
            f"Twitter GraphQL: ciclo concluído. "
            f"{total_leads} leads processados. "
            f"Próximo ciclo em {POLL_INTERVAL}s."
        )
        await asyncio.sleep(POLL_INTERVAL)