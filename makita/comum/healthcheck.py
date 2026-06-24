"""
makita/comum/healthcheck.py
============================
Endpoint HTTP simples (http.server) que expõe:
  - "/saude" → health check JSON
  - "/health/coleta" → TAP real (Twitter + Reddit + Facebook)
Usado pelo Render para monitorar se o worker está vivo.
Roda em THREAD SEPARADA para nunca travar o event loop.
Escuta na porta definida por HEALTHCHECK_PORT (padrão 8080).
"""
import asyncio
import hashlib
import json
import logging
import os
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Adiciona raiz ao path para importar playwright
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from makita.comum.saude import alerta_ativo

log = logging.getLogger("healthcheck")

PORT = int(os.getenv("PORT", os.getenv("HEALTHCHECK_PORT", "8080")))

# Timestamps dos últimos ciclos de cada coletor
_ultimos_ciclos: dict[str, float] = {}
_healthcheck_iniciado = 0.0
_server_thread: threading.Thread | None = None

# Credenciais / Config
FB_C_USER = os.getenv("FB_C_USER", "")
FB_XS = os.getenv("FB_XS", "")
FB_FR = os.getenv("FB_FR", "")
BROWSERLESS_TOKEN = os.getenv("BROWSERLESS_TOKEN", "")
BROWSERLESS_HOST = os.getenv("BROWSERLESS_HOST", "chrome.browserless.io")
WS_ENDPOINT = f"wss://{BROWSERLESS_HOST}?token={BROWSERLESS_TOKEN}&timeout=120000"

TWITTER_COOKIES_PATH = os.path.join(RAIZ, "tofinder", "twitter_cookies.json")


def marcar_ciclo(coletor: str) -> None:
    """Registra timestamp do último ciclo de um coletor."""
    _ultimos_ciclos[coletor] = time.time()


async def _coletar_twitter(palavra: str) -> dict:
    """Coleta tweets — usa Browserless se token disponível."""
    from playwright.async_api import async_playwright
    
    inicio = time.time()
    resultado = {"posts": 0, "erro": None, "tempo": 0}
    
    try:
        pw = await async_playwright().start()
        
        if BROWSERLESS_TOKEN and BROWSERLESS_TOKEN != "2UkpDDNQOGhjTpu8d724215942577713a7322a27c52af0bf0":
            browser = await pw.chromium.connect_over_cdp(WS_ENDPOINT)
        else:
            browser = await pw.chromium.launch(headless=True)
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
        )
        
        # Cookies Twitter
        if os.path.exists(TWITTER_COOKIES_PATH):
            with open(TWITTER_COOKIES_PATH) as f:
                cookies = json.load(f)
                await context.add_cookies(cookies)
        
        page = await context.new_page()
        await page.goto(f"https://x.com/search?q={palavra}&f=live", wait_until="load", timeout=30000)
        await asyncio.sleep(3)
        
        cells = await page.query_selector_all('div[data-testid="cellInnerDiv"]')
        count = 0
        for cell in cells[:10]:
            try:
                text_el = await cell.query_selector('div[data-testid="tweetText"]') or await cell.query_selector('div[lang]')
                text = (await text_el.inner_text()).strip() if text_el else ""
                if text:
                    count += 1
            except Exception:
                pass
        
        resultado["posts"] = count
        await page.close()
        await context.close()
        await browser.close()
        await pw.stop()
        
    except Exception as e:
        resultado["erro"] = str(e)
    
    resultado["tempo"] = round(time.time() - inicio, 2)
    return resultado


async def _coletar_reddit(palavra: str) -> dict:
    """Coleta Reddit — acesso anônimo (sem cookies)."""
    from playwright.async_api import async_playwright
    
    inicio = time.time()
    resultado = {"posts": 0, "erro": None, "tempo": 0}
    
    try:
        pw = await async_playwright().start()
        
        if BROWSERLESS_TOKEN and BROWSERLESS_TOKEN != "2UkpDDNQOGhjTpu8d724215942577713a7322a27c52af0bf0":
            browser = await pw.chromium.connect_over_cdp(WS_ENDPOINT)
        else:
            browser = await pw.chromium.launch(headless=True)
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
        )
        
        page = await context.new_page()
        await page.goto(f"https://www.reddit.com/search/?q={palavra}&sort=new&t=all", 
                        wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(3)
        
        posts_data = await page.evaluate("""
            () => {
                const containers = document.querySelectorAll(
                    '[data-testid="search-post-unit"], [data-testid="sdui-post-unit"]'
                );
                return containers.length;
            }
        """)
        
        resultado["posts"] = posts_data or 0
        await page.close()
        await context.close()
        await browser.close()
        await pw.stop()
        
    except Exception as e:
        resultado["erro"] = str(e)
    
    resultado["tempo"] = round(time.time() - inicio, 2)
    return resultado


async def _coletar_facebook() -> dict:
    """Coleta Facebook via DOM scraping (1 scroll) com sessão autenticada."""
    from playwright.async_api import async_playwright
    import urllib.parse
    import re
    
    inicio = time.time()
    resultado = {"posts": 0, "erro": None, "tempo": 0}
    
    if not FB_C_USER or not FB_XS:
        return {"posts": 0, "erro": "FB_C_USER ou FB_XS não configurados", "tempo": 0}
    
    def limpar_cookie(valor):
        if not valor: return ""
        try: valor = urllib.parse.unquote(valor)
        except: pass
        return valor.replace(";", "").replace(",", "").replace(" ", "")
    
    try:
        pw = await async_playwright().start()
        
        if BROWSERLESS_TOKEN and BROWSERLESS_TOKEN != "2UkpDDNQOGhjTpu8d724215942577713a7322a27c52af0bf0":
            browser = await pw.chromium.connect_over_cdp(WS_ENDPOINT)
        else:
            browser = await pw.chromium.launch(headless=True)
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="pt-BR",
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        fb_cookies = [
            {"name": "c_user", "value": FB_C_USER, "domain": ".facebook.com", "path": "/"},
            {"name": "xs", "value": limpar_cookie(FB_XS), "domain": ".facebook.com", "path": "/"},
            {"name": "fr", "value": limpar_cookie(FB_FR), "domain": ".facebook.com", "path": "/"},
        ]
        await context.add_cookies(fb_cookies)
        
        page = await context.new_page()
        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(20)
        
        # 1 scroll
        await page.evaluate("window.scrollBy(0, 800)")
        await asyncio.sleep(5)
        
        articles = await page.query_selector_all("[role='article']")
        count = 0
        for article in articles:
            try:
                texto = await article.inner_text()
                linhas = [l.strip() for l in texto.split('\n') if l.strip()]
                if len(linhas) >= 2:
                    count += 1
            except Exception:
                pass
        
        resultado["posts"] = count
        await page.close()
        await context.close()
        await browser.close()
        await pw.stop()
        
    except Exception as e:
        resultado["erro"] = str(e)
    
    resultado["tempo"] = round(time.time() - inicio, 2)
    return resultado


async def _executar_tap() -> dict:
    """Executa TAP completo: Twitter + Reddit + Facebook."""
    inicio_total = time.time()
    
    log.info("[TAP] Iniciando coleta de teste com keyword 'developer'")
    log.info(f"[TAP] BROWSERLESS_TOKEN configurado: {'SIM' if BROWSERLESS_TOKEN else 'NÃO'}")
    
    # Twitter
    log.info("[TAP] Twitter: iniciando...")
    tw = await _coletar_twitter("developer")
    log.info(f"[TAP] Twitter: {tw['posts']} posts em {tw['tempo']}s")
    
    # Reddit
    log.info("[TAP] Reddit: iniciando...")
    rd = await _coletar_reddit("developer")
    log.info(f"[TAP] Reddit: {rd['posts']} posts em {rd['tempo']}s")
    
    # Facebook
    log.info("[TAP] Facebook: iniciando...")
    fb = await _coletar_facebook()
    log.info(f"[TAP] Facebook: {fb['posts']} posts em {fb['tempo']}s")
    
    tempo_total = round(time.time() - inicio_total, 2)
    browserless_ok = bool(BROWSERLESS_TOKEN and BROWSERLESS_TOKEN != "2UkpDDNQOGhjTpu8d724215942577713a7322a27c52af0bf0")
    
    resultado = {
        "status": "ok",
        "browserless_ok": browserless_ok,
        "ws_endpoint_used": WS_ENDPOINT[:50] + "..." if BROWSERLESS_TOKEN else "N/A (launch local)",
        "twitter_posts": tw["posts"],
        "reddit_posts": rd["posts"],
        "facebook_posts": fb["posts"],
        "tempo_total": tempo_total,
        "tempo_twitter": tw["tempo"],
        "tempo_reddit": rd["tempo"],
        "tempo_facebook": fb["tempo"],
        "erro_twitter": tw.get("erro"),
        "erro_reddit": rd.get("erro"),
        "erro_facebook": fb.get("erro"),
    }
    
    # Verifica timeout
    if tempo_total > 120:
        resultado["timeout_120s"] = True
        resultado["status"] = "timeout"
    else:
        resultado["timeout_120s"] = False
    
    log.info(f"[TAP] Completo: Twitter={tw['posts']} Reddit={rd['posts']} Facebook={fb['posts']} Total={tempo_total}s")
    
    return resultado


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/saude":
            self._handle_saude()
        elif self.path == "/health/coleta" or self.path == "/coleta":
            self._handle_coleta()
        else:
            self.send_response(404)
            self.end_headers()
    
    def _handle_saude(self):
        agora = time.time()
        body = {
            "status": "ok",
            "uptime_seg": round(agora - _healthcheck_iniciado, 1),
            "ciclos": {},
        }
        status_code = 200
        
        if alerta_ativo():
            body["status"] = "alerta_coletor_morto"
            status_code = 503
        
        for nome, ts in _ultimos_ciclos.items():
            idle = round(agora - ts, 1)
            body["ciclos"][nome] = {
                "ultimo_seg": idle,
                "status": "ok" if idle < 3600 else "alerta",
            }
            if idle > 3600:
                status_code = 503
        
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body, indent=2).encode())
    
    def _handle_coleta(self):
        """Executa TAP real com Browserless e retorna JSON."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            resultado = loop.run_until_complete(_executar_tap())
            loop.close()
            
            status_code = 200
            if resultado.get("status") == "timeout":
                status_code = 503
            
            # Verifica erros
            erros = [resultado.get(k) for k in ["erro_twitter", "erro_reddit", "erro_facebook"] if resultado.get(k)]
            if erros:
                status_code = 500
            
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resultado, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "erro", "erro": str(e)}).encode())
    
    def log_message(self, fmt, *args):
        # Silencia logs do HTTP server
        pass


def _run_server() -> None:
    """Função que roda na thread — bloqueia com serve_forever()."""
    server = HTTPServer(("0.0.0.0", PORT), _Handler)
    log.info(f"Healthcheck HTTP ouvindo em :{PORT}/saude e :{PORT}/health/coleta (thread separada)")
    server.serve_forever()


def start_healthcheck_thread() -> None:
    """
    Inicia o servidor HTTP em uma thread separada.
    NUNCA bloqueia o event loop asyncio.
    Chamar UMA VEZ no main.py, antes do asyncio.gather().
    """
    global _healthcheck_iniciado, _server_thread

    if _server_thread is not None and _server_thread.is_alive():
        log.info("Healthcheck thread já rodando.")
        return

    _healthcheck_iniciado = time.time()
    _server_thread = threading.Thread(
        target=_run_server,
        daemon=True,          # morre junto com o processo principal
        name="healthcheck-http",
    )
    _server_thread.start()
    log.info(f"Healthcheck thread iniciada na porta {PORT}")