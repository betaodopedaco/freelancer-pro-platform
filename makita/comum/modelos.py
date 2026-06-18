"""
makita — modelos de dados
===========================
Objeto que trafega entre os setores: coleta → processamento → entrega.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SinalBruto:
    """Sinal de oportunidade bruto, antes de qualquer enriquecimento."""

    plataforma: str          # ex: "facebook", "twitter", "reddit", "bluesky", "hn"
    source_id: str           # ID único na plataforma — usado para dedup
    texto: str               # conteúdo textual do post/tweet/comentário
    url: str                 # link direto para o conteúdo
    autor: str               # nome de usuário / handle
    palavra_chave: str       # palavra que disparou a coleta
    usuario_id: int          # ID do usuário dono da keyword (para roteamento)
    publicado_em: str        # ISO 8601 — data de publicação original
    valido_ate: str = ""     # ISO 8601 — janela de relevância (calculado depois)