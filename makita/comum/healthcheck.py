"""
makita/comum/healthcheck.py
============================
Endpoint HTTP simples (http.server) que expõe:
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
import json as _json

from makita.comum.saude import alerta_ativo

log = logging.getLogger("healthcheck")

PORT = int(os.getenv("PORT", os.getenv("HEALTHCHECK_PORT", "8080")))

# Timestamps dos últimos ciclos de cada coletor
_ultimos_ciclos: dict[str, float] = {}
_healthcheck_iniciado = 0.0


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
    log.info(f"Healthcheck HTTP ouvindo em :{PORT}/saude")

    while True:
        loop.call_soon(server.handle_request)
        await asyncio.sleep(0.1)