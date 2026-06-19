"""
twitter_cookie_loader.py
========================
Responsabilidade única: carregar cookies do Twitter/X a partir de:

1. Variável de ambiente TWITTER_COOKIES_B64 (Base64 do JSON)
2. Fallback: arquivo twitter_cookies.json

Se TWITTER_COOKIES_B64 for fornecida:
  - Decodifica o Base64
  - Valida o JSON
  - Valida presença de auth_token e ct0
  - Recria o arquivo twitter_cookies.json automaticamente
  - Retorna os cookies

Se não existir TWITTER_COOKIES_B64:
  - Tenta carregar do arquivo twitter_cookies.json
  - Se não existir, retorna None

Uso:
    from coletores.twitter_cookie_loader import load_twitter_cookies
    cookies = load_twitter_cookies()
    if cookies:
        await context.add_cookies(cookies)
"""

import base64
import json
import os
from typing import Optional

try:
    from logger import get_logger
    log = get_logger("tw_cookie_loader")
except ImportError:
    import logging
    log = logging.getLogger("tw_cookie_loader")
    log.setLevel(logging.INFO)


# Caminhos onde o arquivo de cookies pode estar
POSSIBLE_PATHS = [
    "tofinder/twitter_cookies.json",
    "twitter_cookies.json",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "twitter_cookies.json"),
]

ENV_VAR = "TWITTER_COOKIES_B64"

# Cookies obrigatórios para o Twitter/X funcionar
REQUIRED_COOKIES = ["auth_token", "ct0"]


def _find_cookie_file() -> Optional[str]:
    """Procura o arquivo de cookies nos caminhos possíveis."""
    for path in POSSIBLE_PATHS:
        expanded = os.path.expanduser(path)
        if os.path.exists(expanded):
            return expanded
    return None


def _validate_cookies(cookies: list) -> tuple[bool, str]:
    """
    Valida que os cookies contêm os campos obrigatórios.
    Retorna (valido, mensagem_erro).
    """
    if not isinstance(cookies, list):
        return False, "cookies não é uma lista"

    found = {c: False for c in REQUIRED_COOKIES}
    for c in cookies:
        name = c.get("name", "")
        if name in found:
            found[name] = True

    missing = [k for k, v in found.items() if not v]
    if missing:
        return False, f"Cookies obrigatórios ausentes: {', '.join(missing)}"

    # Log dos valores (parcial para não expor tokens completos)
    for c in cookies:
        name = c.get("name", "")
        val = c.get("value", "")
        if name in REQUIRED_COOKIES:
            masked = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
            log.info(f"Cookie '{name}' presente: {masked}")

    return True, "ok"


def _decode_b64(b64_str: str) -> Optional[list]:
    """Decodifica uma string Base64 para lista de cookies."""
    try:
        # Tenta decode padrão
        decoded = base64.b64decode(b64_str, validate=True).decode("utf-8")
    except Exception:
        try:
            # Tenta com padding automático
            b64_str_fixed = b64_str.strip()
            missing_padding = len(b64_str_fixed) % 4
            if missing_padding:
                b64_str_fixed += "=" * (4 - missing_padding)
            decoded = base64.b64decode(b64_str_fixed, validate=False).decode("utf-8")
        except Exception as e:
            log.error(f"Falha ao decodificar Base64: {e}")
            return None

    try:
        cookies = json.loads(decoded)
        return cookies
    except json.JSONDecodeError as e:
        log.error(f"Falha ao fazer parse do JSON dos cookies: {e}")
        return None


def _save_cookies_to_file(cookies: list, filepath: str) -> bool:
    """Salva cookies em arquivo JSON."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(cookies, f, indent=2)
        log.info(f"Cookies salvos em {filepath} ({len(cookies)} cookies)")
        return True
    except Exception as e:
        log.error(f"Erro ao salvar cookies em {filepath}: {e}")
        return False


def load_twitter_cookies() -> Optional[list]:
    """
    Função centralizada para carregar cookies do Twitter/X.

    Prioridade:
    1. TWITTER_COOKIES_B64 (variável de ambiente)
    2. twitter_cookies.json (arquivo local)

    Se TWITTER_COOKIES_B64 for fornecida:
      - Decodifica, valida, salva localmente
      - Retorna os cookies

    Returns:
        list | None: lista de cookies prontos para usar no Playwright
    """
    b64_data = os.environ.get(ENV_VAR, "").strip()

    # --- ESTRATÉGIA 1: TWITTER_COOKIES_B64 ---
    if b64_data:
        log.info(f"TWITTER_COOKIES_B64 encontrada ({len(b64_data)} caracteres)")

        cookies = _decode_b64(b64_data)
        if cookies is None:
            log.error("Falha na decodificação do TWITTER_COOKIES_B64")
            return None

        # Valida
        is_valid, msg = _validate_cookies(cookies)
        if not is_valid:
            log.error(f"TWITTER_COOKIES_B64 inválido: {msg}")
            log.error("Corrija a variável de ambiente e faça redeploy.")
            return None

        log.info(f"TWITTER_COOKIES_B64 válido: {msg}")

        # Salva em arquivo para outros módulos que dependem do arquivo
        saved = False
        for path in POSSIBLE_PATHS:
            if _save_cookies_to_file(cookies, path):
                saved = True
                break

        if not saved:
            # Garante que pelo menos o path principal existe
            _save_cookies_to_file(cookies, POSSIBLE_PATHS[0])

        return cookies

    # --- ESTRATÉGIA 2: Arquivo local ---
    log.info("TWITTER_COOKIES_B64 não definida. Tentando arquivo local...")
    filepath = _find_cookie_file()
    if not filepath:
        log.error(
            "Nenhuma fonte de cookies encontrada. "
            "Defina TWITTER_COOKIES_B64 no ambiente ou crie twitter_cookies.json."
        )
        return None

    try:
        with open(filepath, "r") as f:
            cookies = json.load(f)
        log.info(f"Cookies carregados do arquivo: {filepath} ({len(cookies)} cookies)")

        is_valid, msg = _validate_cookies(cookies)
        if not is_valid:
            log.error(f"Cookies do arquivo inválidos: {msg}")
            return None

        log.info(f"Cookies do arquivo válidos: {msg}")
        return cookies
    except Exception as e:
        log.error(f"Erro ao carregar cookies do arquivo {filepath}: {e}")
        return None


def get_cookie_value(cookies: list, name: str) -> str:
    """Extrai o valor de um cookie específico."""
    for c in cookies:
        if c.get("name") == name:
            return c.get("value", "")
    return ""