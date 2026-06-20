"""
makita/auth/convites.py
========================
Sistema de convites usando códigos.

Uso:
    from makita.auth.convites import validar_convite, gerar_convite
    
    # Validar um convite
    if validar_convite("CODIGO123"):
        print("Convite válido!")
    
    # Gerar novo convite
    codigo = gerar_convite()
"""

import secrets
import string
from typing import Optional
import logging

try:
    from logger import get_logger
    log = get_logger("auth.convites")
except ImportError:
    import logging
    log = logging.getLogger("auth.convites")
    log.setLevel(logging.INFO)


# Armazenamento em memória (em produção, usar banco de dados)
_CONVITES_ATIVOS: dict[str, bool] = {}
_CONVITES_USADOS: dict[str, str] = {}  # codigo -> usuario_id


def gerar_convite(tamanho: int = 12) -> str:
    """
    Gera um novo código de convite.
    
    Args:
        tamanho: Tamanho do código (padrão: 12 caracteres)
    
    Returns:
        Código de convite gerado
    """
    # Usa letras maiúsculas e números (evita caracteres ambíguos como 0/O, 1/I/l)
    caracteres = string.ascii_uppercase + string.digits
    caracteres = caracteres.replace('0', '').replace('O', '').replace('1', '').replace('I', '').replace('L', '')
    
    codigo = ''.join(secrets.choice(caracteres) for _ in range(tamanho))
    
    # Garante que não existe duplicata
    while codigo in _CONVITES_ATIVOS or codigo in _CONVITES_USADOS:
        codigo = ''.join(secrets.choice(caracteres) for _ in range(tamanho))
    
    _CONVITES_ATIVOS[codigo] = True
    log.info(f"Convite gerado: {codigo}")
    
    return codigo


def validar_convite(codigo: str) -> bool:
    """
    Valida se um convite existe e está ativo.
    
    Args:
        codigo: Código de convite para validar
    
    Returns:
        True se válido, False caso contrário
    """
    codigo = codigo.strip().upper()
    
    if codigo in _CONVITES_USADOS:
        log.warning(f"Convite já usado: {codigo} (usado por: {_CONVITES_USADOS[codigo]})")
        return False
    
    if codigo in _CONVITES_ATIVOS:
        log.info(f"Convite válido: {codigo}")
        return True
    
    log.warning(f"Convite inválido ou não encontrado: {codigo}")
    return False


def marcar_convite_usado(codigo: str, usuario_id: str) -> bool:
    """
    Marca um convite como usado por um usuário.
    
    Args:
        codigo: Código de convite
        usuario_id: ID do usuário que usou o convite
    
    Returns:
        True se marcado com sucesso, False caso contrário
    """
    codigo = codigo.strip().upper()
    
    if not validar_convite(codigo):
        return False
    
    # Remove de ativos e adiciona em usados
    del _CONVITES_ATIVOS[codigo]
    _CONVITES_USADOS[codigo] = usuario_id
    
    log.info(f"Convite marcado como usado: {codigo} (usuário: {usuario_id})")
    return True


def listar_convites_ativos() -> list[str]:
    """
    Lista todos os convites ativos.
    
    Returns:
        Lista de códigos de convite ativos
    """
    return list(_CONVITES_ATIVOS.keys())


def listar_convites_usados() -> dict[str, str]:
    """
    Lista todos os convites usados.
    
    Returns:
        Dict com codigo -> usuario_id
    """
    return _CONVITES_USADOS.copy()


def inicializar_convites_padrao() -> None:
    """
    Inicializa convites padrão a partir de variável de ambiente.
    """
    import os
    
    convites_env = os.environ.get("INVITE_CODES", "").strip()
    
    if not convites_env:
        log.info("Nenhum convite padrão configurado (INVITE_CODES vazio)")
        return
    
    # Separa por vírgula
    codigos = [c.strip().upper() for c in convites_env.split(",") if c.strip()]
    
    for codigo in codigos:
        _CONVITES_ATIVOS[codigo] = True
    
    log.info(f"{len(codigos)} convites padrão carregados")


# Inicializa convites padrão na importação
inicializar_convites_padrao()


# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE DE CONVITES ===\n")
    
    # Gerar alguns convites
    print("Gerando convites...")
    c1 = gerar_convite()
    c2 = gerar_convite()
    print(f"Convite 1: {c1}")
    print(f"Convite 2: {c2}\n")
    
    # Validar
    print("Validando convites...")
    print(f"{c1} válido? {validar_convite(c1)}")
    print(f"INEXISTENTE válido? {validar_convite('INEXISTENTE')}\n")
    
    # Marcar como usado
    print("Marcando convite como usado...")
    marcar_convite_usado(c1, "usuario_123")
    print(f"{c1} ainda válido? {validar_convite(c1)}\n")
    
    # Listar
    print(f"Convites ativos: {listar_convites_ativos()}")
    print(f"Convites usados: {listar_convites_usados()}")