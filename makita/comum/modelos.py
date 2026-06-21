"""
makita/comum/modelos.py
=======================
Modelos de dados para o pipeline Makita.

Apenas dataclasses simples — sem SQLAlchemy.
O banco SQLite/PostgreSQL é gerenciado via db.py com SQL direto.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SinalBruto:
    """Modelo para sinais brutos na fila de processamento."""
    plataforma: str
    source_id: str
    texto: str
    url: str
    autor: str
    palavra_chave: str
    usuario_id: str = "0"
    publicado_em: str = ""
    valido_ate: str = ""