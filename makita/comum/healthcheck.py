"""
makita/comum/healthcheck.py
============================
Endpoint HTTP simples (http.server) que expõe:
  - "/saude" → health check JSON
Usado pelo Render para monitorar se o worker está vivo.
Roda em THREAD SEPARADA para nunca travar o event loop.
Escuta na porta definida por HEALTHCHECK_PORT (padrão 8080).
"""
import json
import logging
import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from makita.comum.saude import alerta_ativo

log = logging.getLogger("healthcheck")

PORT = int(os.getenv("PORT", os.getenv("HEALTHCHECK_PORT", "8080")))

# Timestamps dos últimos ciclos de cada coletor
_ultimos_ciclos: dict[str, float] = {}
_healthcheck_iniciado = 0.0
_server_thread: threading.Thread | None = None


def marcar_ciclo(coletor: str) -> None:
    """Registra timestamp do último ciclo de um coletor."""
    _ultimos_ciclos[coletor] = time.time()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Apenas rota /saude
        if self.path != "/saude":
            self.send_response(404)
            self.end_headers()
            return

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
        self.wfile.write(json.dumps(body, indent=2).encode())

    def log_message(self, fmt, *args):
        # Silencia logs do HTTP server
        pass


def _run_server() -> None:
    """Função que roda na thread — bloqueia com serve_forever()."""
    server = HTTPServer(("0.0.0.0", PORT), _Handler)
    log.info(f"Healthcheck HTTP ouvindo em :{PORT}/saude (thread separada)")
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