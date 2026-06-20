"""
makita/comum/modelos.py
========================
Modelos de dados para o banco SQLite.

Tabelas:
- sinal: Sinais coletados dos coletores
- usuario: Usuários cadastrados
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, Any
from dataclasses import dataclass, field
from datetime import datetime as dt

try:
    from makita.comum.db import Base
except ImportError:
    from sqlalchemy.orm import declarative_base
    Base = declarative_base()


class Sinal(Base):
    """Tabela de sinais coletados."""
    __tablename__ = "sinais"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    plataforma = Column(String(50), nullable=False, index=True)
    tipo = Column(String(50), nullable=False)
    titulo = Column(String(500), nullable=False)
    descricao = Column(Text, nullable=True)
    autor = Column(String(200), nullable=True)
    relevancia = Column(Float, nullable=False, default=0.0, index=True)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)
    link = Column(String(500), nullable=True)
    nicho = Column(String(50), nullable=True, index=True)
    criado_em = Column(DateTime, nullable=False, default=func.now())
    
    def __repr__(self):
        return f"<Sinal(id={self.id}, plataforma={self.plataforma}, titulo={self.titulo[:50]})>"


@dataclass
class SinalBruto:
    """Modelo para sinais brutos na fila (não é uma tabela, só para type hints)."""
    plataforma: str
    source_id: str
    texto: str
    url: str
    autor: str
    palavra_chave: str
    usuario_id: str
    publicado_em: str
    valido_ate: str


class Usuario(Base):
    """Tabela de usuários cadastrados."""
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nome = Column(String(200), nullable=True)
    nicho = Column(String(50), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True, unique=True)
    telegram_username = Column(String(100), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime, nullable=False, default=func.now())
    atualizado_em = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Usuario(id={self.id}, email={self.email}, nome={self.nome})>"
    
    def to_dict(self):
        """Converte para dict (sem senha)."""
        return {
            "id": self.id,
            "email": self.email,
            "nome": self.nome,
            "nicho": self.nicho,
            "telegram_chat_id": self.telegram_chat_id,
            "telegram_username": self.telegram_username,
            "ativo": self.ativo,
            "criado_em": self.criado_em.isoformat() if self.criado_em else None,
            "atualizado_em": self.atualizado_em.isoformat() if self.atualizado_em else None,
        }