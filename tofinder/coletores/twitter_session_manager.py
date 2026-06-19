"""
coletores/twitter_session_manager.py

Responsabilidade única: capturar tokens de sessão do Twitter/X via Playwright
e persistir no banco de dados.

Captura:
  - operation_id do SearchTimeline (muda frequentemente)
  - ct0 do cookie
  - auth_token do cookie
  - features object completo
  - variables object padrão

Fluxo:
  1. Lê auth_token e ct0 do twitter_cookies.json
  2. Abre x.com/search via Playwright
  3. Intercepta o request SearchTimeline
  4. Extrai operation_id, features, variables da URL
  5. Salva tudo na tabela platform_sessions com platform='twitter'
  6. Fecha o browser
  7. Renova a cada 5 minutos
"""

import asyncio
import json
import os
import urllib.parse
from datetime import datetime, timezone

import aiosqlite
from playwright.async_api import async_playwright

from logger import get_logger
from coletores.twitter_cookie_loader import load_twitter_cookies, get_cookie_value

log = get_logger("tw_session_manager")

DB_PATH = os.getenv("DB_PATH", "tofinder.db")
REFRESH_INTERVAL = int(os.getenv("TW_TOKEN_REFRESH_SECS", "300"))  # 5 min — op_id vive pouco
COOKIES_FILE = "tofinder/twitter_cookies.json"  # fallback path (não usado pelo loader, mas mantido para legado)

BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"

# Objeto features padrão (necessário para SearchTimeline)
DEFAULT_FEATURES = {
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": True,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}


def _load_cookies() -> list | None:
    """
    Carrega cookies usando o loader centralizado.
    Prioridade: TWITTER_COOKIES_B64 > twitter_cookies.json
    """
    cookies = load_twitter_cookies()
    if cookies:
        log.info(f"Cookies carregados com sucesso pelo loader centralizado ({len(cookies)} cookies).")
    else:
        log.error("Loader centralizado não retornou cookies.")
    return cookies


async def _capture_tokens() -> dict | None:
    """
    Abre x.com/search no Playwright, intercepta SearchTimeline,
    extrai operation_id, features, variables.
    """
    cookies = _load_cookies()
    if not cookies:
        return None

    # Extrai auth_token e ct0 dos cookies
    auth_token = ""
    ct0 = ""
    for c in cookies:
        if c["name"] == "auth_token":
            auth_token = c["value"]
        if c["name"] == "ct0":
            ct0 = c["value"]

    if not auth_token or not ct0:
        log.error("auth_token ou ct0 não encontrados nos cookies.")
        return None

    log.info("Playwright iniciando para captura de tokens do Twitter...")
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
            )
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768},
            )
            await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            await ctx.add_cookies(cookies)
            page = await ctx.new_page()

            loop = asyncio.get_event_loop()
            capture_future: asyncio.Future = loop.create_future()

            def on_request(req):
                url = req.url
                # Procura por SearchTimeline
                if "SearchTimeline" in url and not capture_future.done():
                    req_headers = dict(req.headers)
                    # Extrai ct0 das headers da request (valor ATUAL, não do cookie)
                    captured_ct0 = req_headers.get("x-csrf-token", ct0)
                    capture_future.set_result({
                        "url": url,
                        "method": req.method,
                        "headers": req_headers,
                        "captured_ct0": captured_ct0,
                    })

            page.on("request", on_request)
            await page.goto(
                "https://x.com/search?q=test&f=live",
                wait_until="domcontentloaded",
                timeout=30000,
            )

            try:
                request_data = await asyncio.wait_for(capture_future, timeout=30)
            except asyncio.TimeoutError:
                log.error("Timeout aguardando request SearchTimeline do Twitter.")
                await browser.close()
                return None

            await browser.close()

        # Parse da URL para extrair operation_id, variables, features
        full_url = request_data["url"]
        log.info(f"URL capturada: {full_url[:200]}...")

        # Extrai operation_id: /graphql/{operation_id}/SearchTimeline
        op_id = ""
        if "/graphql/" in full_url:
            parts = full_url.split("/graphql/")[1].split("/")
            if parts:
                op_id = parts[0]

        # Extrai query params da URL
        parsed_url = urllib.parse.urlparse(full_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)

        variables_str = query_params.get("variables", [""])[0]
        features_str = query_params.get("features", [""])[0]

        # Decodifica
        try:
            variables_obj = json.loads(urllib.parse.unquote(variables_str)) if variables_str else {}
        except json.JSONDecodeError:
            variables_obj = {"rawQuery": "test", "count": 20, "product": "Latest"}

        try:
            features_obj = json.loads(urllib.parse.unquote(features_str)) if features_str else {}
        except json.JSONDecodeError:
            features_obj = DEFAULT_FEATURES

        # Usa ct0 capturado da request (que o browser atualizou) ou fallback do cookie
        captured_ct0 = request_data.get("captured_ct0", ct0)
        
        tokens = {
            "operation_id": op_id or "",
            "auth_token": auth_token,
            "ct0": captured_ct0,
            "variables": json.dumps(variables_obj),
            "features": json.dumps(features_obj),
            "bearer_token": BEARER_TOKEN,
        }

        if not tokens["operation_id"]:
            log.error("operation_id não encontrado na URL.")
            return None

        log.info(f"Tokens capturados. operation_id={tokens['operation_id'][:20]}...")
        return tokens

    except Exception as e:
        log.error(f"Erro ao capturar tokens do Twitter: {e}")
        return None


async def _save_tokens(tokens: dict) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS platform_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL UNIQUE,
                tokens TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute(
            """
            INSERT INTO platform_sessions (platform, tokens, updated_at)
            VALUES ('twitter', ?, ?)
            ON CONFLICT(platform) DO UPDATE SET
                tokens = excluded.tokens,
                updated_at = excluded.updated_at
            """,
            (json.dumps(tokens), datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()
    log.info("Tokens do Twitter salvos no banco.")


async def get_tokens() -> dict | None:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT tokens FROM platform_sessions WHERE platform = 'twitter'"
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return None
        return json.loads(row[0])
    except Exception as e:
        log.error(f"Erro ao ler tokens do Twitter do banco: {e}")
        return None


async def refresh_loop() -> None:
    log.info(f"Twitter session manager iniciado. Renovação a cada {REFRESH_INTERVAL}s.")
    while True:
        tokens = await _capture_tokens()
        if tokens:
            await _save_tokens(tokens)
            log.info(f"operation_id={tokens.get('operation_id','?')[:30]}... capturado com sucesso.")
        else:
            log.warning("Falha na captura de tokens do Twitter. Tentando novamente em 60s.")
            await asyncio.sleep(60)
            continue
        log.info(f"Próxima renovação em {REFRESH_INTERVAL}s.")
        await asyncio.sleep(REFRESH_INTERVAL)