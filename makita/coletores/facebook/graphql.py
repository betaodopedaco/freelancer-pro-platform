"""
makita/coletores/facebook/graphql.py
======================================
Coletor do Facebook via GraphQL direto.
Usa curl-cffi para imitar o browser sem abrir Chromium.

Fluxo adaptado para o Makita:
  1. Lê tokens do banco via db.ler_sessao("facebook")
  2. Busca palavras ativas via db.get_palavras_ativas()
  3. Para cada palavra, faz POST /api/graphql/
  4. Parseia serpResponse.results.edges
  5. Verifica dedup via db.ja_visto()
  6. Publica SinalBruto na fila via fila.publicar()
"""

import asyncio
import hashlib
import json
import os
import urllib.parse
import logging
from datetime import datetime, timezone
from typing import List, Dict

from curl_cffi.requests import AsyncSession

from makita.comum.db import (
    get_palavras_ativas,
    ja_visto,
    ler_sessao,
    salvar_sessao,
)
from makita.comum.fila import publicar
from makita.comum.modelos import SinalBruto

log = logging.getLogger("facebook.graphql")

FB_C_USER = os.getenv("FB_C_USER", "")
FB_XS = os.getenv("FB_XS", "")
FB_FR = os.getenv("FB_FR", "")

# doc_id é lido dinamicamente dos tokens capturados pelo session_manager
DOC_ID_FALLBACK = "27711418425128380"

# Máximo de posts por keyword por ciclo
MAX_POSTS_PER_KEYWORD = 5

# Intervalo entre keywords no mesmo ciclo (evita rate limit)
INTER_KEYWORD_SLEEP = 1.5  # segundos

# Intervalo do ciclo completo
POLL_INTERVAL = int(os.getenv("FB_POLL_INTERVAL", "1800"))  # 30 min


# ── helpers de sessão ─────────────────────────────────────────────

async def get_tokens() -> dict | None:
    """Lê tokens do Facebook do banco via db.py."""
    return await ler_sessao("facebook")


# ── construção da request ─────────────────────────────────────────

def _build_request(keyword: str, tokens: dict) -> tuple[dict, str]:
    """
    Constrói headers e body para o POST GraphQL.
    Retorna (headers, body_str).
    """
    variables = {
        "args": {
            "callsite": "COMET_GLOBAL_SEARCH",
            "config": {"exact_match": False},
            "context": {"bsid": "search"},
            "experience": {"type": "POSTS_TAB"},
            "filters": [],
            "text": keyword,
        },
        "count": MAX_POSTS_PER_KEYWORD,
        "cursor": "{}",
        "feedLocation": "SEARCH",
        "feedbackSource": 23,
        "fetch_filters": True,
        "focusCommentID": None,
        "locale": None,
        "renderLocation": "search_results_page",
        "scale": 1,
        "stream_initial_count": 0,
        "useDefaultActor": False,
    }

    body_params = {
        "av": FB_C_USER,
        "__user": FB_C_USER,
        "__a": "1",
        "__req": "1",
        "__hs": tokens.get("__hs", ""),
        "dpr": "1",
        "__ccg": tokens.get("__ccg", "GOOD"),
        "__rev": tokens.get("__rev", ""),
        "__s": tokens.get("__s", ""),
        "__hsi": tokens.get("__hsi", ""),
        "__dyn": tokens.get("__dyn", ""),
        "__csr": tokens.get("__csr", ""),
        "__comet_req": "15",
        "fb_dtsg": tokens.get("fb_dtsg", ""),
        "jazoest": tokens.get("jazoest", ""),
        "lsd": tokens.get("lsd", ""),
        "__spin_r": tokens.get("__spin_r", ""),
        "__spin_b": "trunk",
        "__spin_t": tokens.get("__spin_t", ""),
        "__hsdp": tokens.get("__hsdp", ""),
        "__hblp": tokens.get("__hblp", ""),
        "__sjsp": tokens.get("__sjsp", ""),
        "fb_api_req_friendly_name": "SearchCometResultsPaginatedResultsQuery",
        "variables": json.dumps(variables),
        "server_timestamps": "true",
        "fb_api_caller_class": "RelayModern",
        "doc_id": tokens.get("doc_id", DOC_ID_FALLBACK),
    }

    body_str = "&".join(
        f"{k}={urllib.parse.quote(str(v))}"
        for k, v in body_params.items()
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.facebook.com",
        "Referer": f"https://www.facebook.com/search/posts/?q={urllib.parse.quote(keyword)}",
        "x-fb-lsd": tokens.get("lsd", ""),
        "x-fb-friendly-name": "SearchCometResultsPaginatedResultsQuery",
        "Cookie": f"c_user={FB_C_USER}; xs={FB_XS}; fr={FB_FR};",
    }

    return headers, body_str


# ── parse da resposta ─────────────────────────────────────────────

def _parse_posts(response_text: str, keyword: str) -> List[Dict]:
    """
    Parseia a resposta GraphQL e extrai posts relevantes.
    Retorna lista de dicts com url, author, text, ts.
    """
    posts = []

    # Detectar token expirado
    if "1357004" in response_text:
        log.warning("Token expirado detectado na resposta do Facebook.")
        return posts

    if "serpResponse" not in response_text:
        log.debug(f"Resposta sem serpResponse para keyword '{keyword}'.")
        return posts

    try:
        cleaned = response_text
        for prefix in ["for (;;);", "while(1);", ")]}'", ")]}'"]:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):]
                break

        decoder = json.JSONDecoder()
        parsed, _ = decoder.raw_decode(cleaned.strip())
        edges = (
            parsed
            .get("data", {})
            .get("serpResponse", {})
            .get("results", {})
            .get("edges", [])
        )

        for edge in edges:
            try:
                vm = edge.get("rendering_strategy", {}).get("view_model", {})
                story = (
                    vm.get("click_model", {}).get("story", None)
                    or vm.get("story", {})
                )

                # --- Extrai texto do post ---
                text = ""
                try:
                    cs = story.get("comet_sections", {})
                    if isinstance(cs, dict):
                        content = cs.get("content", {})
                        if isinstance(content, dict):
                            content_story = content.get("story", {})
                            if isinstance(content_story, dict):
                                msg = content_story.get("message", {})
                                if isinstance(msg, dict):
                                    text = msg.get("text", "") or ""

                                if not text or len(text) < 30:
                                    content_cs = content_story.get("comet_sections", {})
                                    if isinstance(content_cs, dict):
                                        msg_section = content_cs.get("message", {})
                                        if isinstance(msg_section, dict):
                                            msg_story = msg_section.get("story", {})
                                            if isinstance(msg_story, dict):
                                                msg_nested = msg_story.get("message", {})
                                                if isinstance(msg_nested, dict):
                                                    text = msg_nested.get("text", "") or ""
                except Exception:
                    text = ""

                if not text or len(text) < 30:
                    try:
                        direct_msg = story.get("message", {})
                        if isinstance(direct_msg, dict):
                            text = direct_msg.get("text", "") or ""
                    except Exception:
                        pass

                if not text or len(text) < 30:
                    try:
                        attachments = story.get("attachments", [])
                        if attachments and isinstance(attachments[0], dict):
                            title = attachments[0].get("title_with_entities", {})
                            if isinstance(title, dict):
                                text = title.get("text", "") or ""
                    except Exception:
                        pass

                if not text or len(text) < 30:
                    continue

                # Filtra posts que não contêm a keyword
                if keyword.lower() not in text.lower():
                    continue

                # --- Extrai URL do post ---
                url = story.get("permalink_url", "") or story.get("url", "")

                # --- Extrai autor ---
                actors = story.get("actors", [])
                author = "unknown"
                if actors and isinstance(actors[0], dict):
                    author = actors[0].get("name", "unknown")

                posts.append({
                    "text": text[:1200],
                    "url": url or f"https://www.facebook.com/search/posts/?q={urllib.parse.quote(keyword)}",
                    "author": author,
                    "ts": datetime.now(timezone.utc).timestamp(),
                })

            except Exception as e:
                log.debug(f"Erro ao parsear edge: {e}")
                continue

    except json.JSONDecodeError as e:
        log.error(f"JSON inválido na resposta do Facebook: {e}")
    except Exception as e:
        log.error(f"Erro ao parsear resposta do Facebook: {e}")

    return posts


# ── busca por keyword ─────────────────────────────────────────────

async def _search_keyword(keyword: str, tokens: dict) -> List[Dict]:
    """
    Faz uma requisição GraphQL para uma keyword.
    Retorna lista de posts ou lista vazia em caso de erro.
    """
    headers, body_str = _build_request(keyword, tokens)

    try:
        async with AsyncSession(impersonate="chrome110") as session:
            response = await session.post(
                "https://www.facebook.com/api/graphql/",
                headers=headers,
                data=body_str,
                timeout=15,
            )

        if response.status_code != 200:
            log.warning(f"Status {response.status_code} para keyword '{keyword}'.")
            return []

        posts = _parse_posts(response.text, keyword)
        log.info(f"Facebook GraphQL '{keyword}': {len(posts)} posts.")
        return posts

    except Exception as e:
        log.error(f"Erro na requisição GraphQL para '{keyword}': {e}")
        return []


# ── publicação na fila ────────────────────────────────────────────

async def _publicar_sinal(post: dict, keyword: str) -> bool:
    """
    Cria SinalBruto, verifica dedup e publica na fila.
    Retorna True se publicou, False se já visto.
    """
    source_id = (
        "fbgql_"
        + hashlib.md5(
            (post["url"] + post["text"][:40]).encode()
        ).hexdigest()[:12]
    )

    # Dedup
    if await ja_visto(source_id):
        log.debug(f"Já visto: {source_id}")
        return False

    sinal = SinalBruto(
        plataforma="facebook",
        source_id=source_id,
        texto=post["text"][:800],
        url=post["url"],
        autor=post["author"],
        palavra_chave=keyword,
        usuario_id=0,  # 0 = sinal sem usuário específico (broadcast)
        publicado_em=datetime.fromtimestamp(post["ts"], tz=timezone.utc).isoformat(),
    )

    await publicar(sinal)
    return True


# ── loop principal ────────────────────────────────────────────────

async def colect_facebook() -> None:
    """
    Loop principal do coletor Facebook GraphQL para o Makita.

    A cada ciclo:
    1. Lê tokens do banco
    2. Lê palavras ativas via db.get_palavras_ativas()
    3. Para cada palavra, faz busca GraphQL
    4. Para cada post, verifica ja_visto e publica SinalBruto na fila
    """
    log.info("Facebook GraphQL coletor iniciado (Makita).")

    # Aguarda sessão inicial
    await asyncio.sleep(5)

    while True:
        log.info("Facebook GraphQL: iniciando ciclo de coleta...")

        # 1. Lê tokens do banco
        tokens = await get_tokens()
        if not tokens:
            log.warning("Tokens do Facebook não disponíveis. Aguardando 30s...")
            await asyncio.sleep(30)
            continue

        if not tokens.get("fb_dtsg"):
            log.warning("fb_dtsg vazio — sessão inválida. Aguardando renovação...")
            await asyncio.sleep(30)
            continue

        # 2. Lê palavras ativas
        try:
            palavras = await get_palavras_ativas()
        except Exception as e:
            log.error(f"Erro ao buscar palavras do banco: {e}")
            await asyncio.sleep(60)
            continue

        if not palavras:
            log.info("Nenhuma palavra ativa no banco. Aguardando...")
            await asyncio.sleep(60)
            continue

        log.info(f"Facebook GraphQL: {len(palavras)} palavras para coletar.")
        total_publicados = 0
        total_vistos = 0

        # 3. Busca por palavra
        for palavra in palavras:
            try:
                posts = await _search_keyword(palavra, tokens)

                for post in posts:
                    publicado = await _publicar_sinal(post, palavra)
                    if publicado:
                        total_publicados += 1
                    else:
                        total_vistos += 1

            except Exception as e:
                log.error(f"Erro ao coletar palavra '{palavra}': {e}")

            await asyncio.sleep(INTER_KEYWORD_SLEEP)

        log.info(
            f"Facebook GraphQL: ciclo concluído. "
            f"{total_publicados} novos sinais, {total_vistos} já vistos. "
            f"Próximo ciclo em {POLL_INTERVAL}s."
        )
        await asyncio.sleep(POLL_INTERVAL)