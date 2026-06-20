"""
makita/comum/healthcheck.py
============================
Endpoint HTTP simples (http.server) que expõe:
  - "/" → landing page (makita/landing.html)
  - "/saude" → health check JSON
Usado pelo Render para monitorar se o worker está vivo.
Escuta na porta definida por HEALTHCHECK_PORT (padrão 8080).
"""
import asyncio
import json
import logging
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Import json no topo para evitar UnboundLocalError
import json as _json

from makita.comum.saude import alerta_ativo

log = logging.getLogger("healthcheck")

PORT = int(os.getenv("PORT", os.getenv("HEALTHCHECK_PORT", "8080")))
FRONTEND_PATH = Path(__file__).parent.parent.parent.parent / "frontend.html"

# Timestamps dos últimos ciclos de cada coletor
_ultimos_ciclos: dict[str, float] = {}
_healthcheck_iniciado = 0.0


def marcar_ciclo(coletor: str) -> None:
    """Registra timestamp do último ciclo de um coletor."""
    _ultimos_ciclos[coletor] = time.time()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Rota "/" → serve frontend.html (página principal)
        if self.path == "/" or self.path == "/index.html":
            log.info(f"Servindo frontend.html de: {FRONTEND_PATH}")
            log.info(f"Arquivo existe? {FRONTEND_PATH.exists()}")
            log.info(f"Caminho absoluto: {FRONTEND_PATH.absolute()}")
            
            try:
                html_content = FRONTEND_PATH.read_text(encoding="utf-8")
                log.info(f"Frontend carregado com sucesso! Tamanho: {len(html_content)} bytes")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))
                return
            except Exception as e:
                log.error(f"Erro ao servir frontend.html: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Erro ao carregar frontend: {e}".encode("utf-8"))
                return
        
        # Rota POST "/api/cadastro" → cadastrar usuário
        if self.path == "/api/cadastro" and self.command == "POST":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                dados = _json.loads(post_data.decode('utf-8'))
                
                email = dados.get('email', '').strip().lower()
                senha = dados.get('senha', '')
                nome = dados.get('nome', '').strip() or None
                
                # Validações básicas
                if not email or not senha:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"erro": "Email e senha são obrigatórios"}).encode())
                    return
                
                # Cadastrar no banco
                from makita.auth.servico import cadastrar_usuario
                usuario = cadastrar_usuario(email=email, senha=senha, nome=nome)
                
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(usuario).encode())
                log.info(f"Usuário cadastrado via API: {email}")
                return
                
            except ValueError as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"erro": str(e)}).encode())
                log.warning(f"Erro no cadastro: {e}")
                return
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"erro": "Erro interno do servidor"}).encode())
                log.error(f"Erro ao processar cadastro: {e}")
                return
        
        # Rota POST "/api/login" → login usuário
        if self.path == "/api/login" and self.command == "POST":
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                post_data = self.rfile.read(content_length)
                dados = _json.loads(post_data.decode('utf-8'))
                
                email = dados.get('email', '').strip().lower()
                senha = dados.get('senha', '')
                
                if not email or not senha:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"erro": "Email e senha são obrigatórios"}).encode())
                    return
                
                from makita.auth.servico import login_usuario
                usuario = login_usuario(email=email, senha=senha)
                
                if usuario:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(usuario).encode())
                    log.info(f"Login realizado via API: {email}")
                else:
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"erro": "Email ou senha inválidos"}).encode())
                    log.warning(f"Login falhou via API: {email}")
                return
                
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"erro": "Erro interno do servidor"}).encode())
                log.error(f"Erro ao processar login: {e}")
                return

        # Rota "/saude" → health check JSON
        agora = time.time()
        body = {
            "status": "ok",
            "uptime_seg": round(agora - _healthcheck_iniciado, 1),
            "ciclos": {},
        }
        status_code = 200

        # Se o loop_saude detectou coletores mortos → 503
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
        self.wfile.write(_json.dumps(body, indent=2).encode())

    def log_message(self, fmt, *args):
        # Silencia logs do HTTP server
        pass


async def loop_healthcheck() -> None:
    """
    Inicia servidor HTTP na porta definida.
    Responde 200 OK em /saude se coletores estão vivos.
    """
    global _healthcheck_iniciado
    _healthcheck_iniciado = time.time()

    loop = asyncio.get_event_loop()
    server = HTTPServer(("0.0.0.0", PORT), _Handler)
    log.info(f"Healthcheck HTTP ouvindo em :{PORT}/ (frontend) e :{PORT}/saude (health)")
    log.info(f"Frontend path: {FRONTEND_PATH.absolute()}")
    log.info(f"Frontend existe? {FRONTEND_PATH.exists()}")

    while True:
        loop.call_soon(server.handle_request)
        await asyncio.sleep(0.1)