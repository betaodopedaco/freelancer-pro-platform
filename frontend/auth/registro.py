"""
makita/auth/registro.py
========================
Sistema de cadastro simples (email + senha).

Uso:
    from makita.auth.registro import cadastrar_usuario
    
    usuario = cadastrar_usuario(
        email="user@example.com",
        senha="senha123",
        nome="João Silva"
    )
"""

import re
import hashlib
import secrets
from typing import Optional, Dict, Any
from datetime import datetime
import logging

try:
    from logger import get_logger
    log = get_logger("auth.registro")
except ImportError:
    import logging
    log = logging.getLogger("auth.registro")
    log.setLevel(logging.INFO)


# Validação de email
def validar_email(email: str) -> bool:
    """
    Valida formato de email.
    
    Args:
        email: Email para validar
    
    Returns:
        True se válido, False caso contrário
    """
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(padrao, email))


# Validação de senha
def validar_senha(senha: str) -> tuple[bool, str]:
    """
    Valida força da senha.
    
    Args:
        senha: Senha para validar
    
    Returns:
        (válido, mensagem_erro)
    """
    if len(senha) < 8:
        return False, "Senha deve ter no mínimo 8 caracteres"
    
    if not any(c.isupper() for c in senha):
        return False, "Senha deve conter pelo menos uma letra maiúscula"
    
    if not any(c.islower() for c in senha):
        return False, "Senha deve conter pelo menos uma letra minúscula"
    
    if not any(c.isdigit() for c in senha):
        return False, "Senha deve conter pelo menos um número"
    
    return True, "Senha válida"


# Hash de senha (simplificado - em produção usar bcrypt)
def hash_senha(senha: str, salt: Optional[str] = None) -> str:
    """
    Gera hash da senha.
    
    Args:
        senha: Senha em texto plano
        salt: Salt opcional (gerado automaticamente se não fornecido)
    
    Returns:
        Hash no formato: salt$hash
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    # Usa SHA-256 (em produção, usar bcrypt ou argon2)
    hash_obj = hashlib.sha256((salt + senha).encode())
    hash_hex = hash_obj.hexdigest()
    
    return f"{salt}${hash_hex}"


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """
    Verifica se a senha corresponde ao hash armazenado.
    
    Args:
        senha: Senha em texto plano
        hash_armazenado: Hash no formato salt$hash
    
    Returns:
        True se corresponder, False caso contrário
    """
    try:
        salt, hash_esperado = hash_armazenado.split('$')
        hash_calculado = hashlib.sha256((salt + senha).encode()).hexdigest()
        return hash_calculado == hash_esperado
    except:
        return False


# Armazenamento em memória (em produção, usar banco de dados)
_USUARIOS: Dict[str, Dict[str, Any]] = {}  # email -> usuario
_USUARIOS_POR_ID: Dict[str, Dict[str, Any]] = {}  # id -> usuario


def cadastrar_usuario(
    email: str,
    senha: str,
    nome: str,
    nicho: Optional[str] = None,
    convite: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cadastra um novo usuário.
    
    Args:
        email: Email do usuário
        senha: Senha em texto plano
        nome: Nome completo
        nicho: Nicho escolhido (opcional)
        convite: Código de convite (opcional)
    
    Returns:
        Dict com dados do usuário criado
    
    Raises:
        ValueError: Se dados inválidos
    """
    # Validações
    email = email.strip().lower()
    
    if not validar_email(email):
        raise ValueError("Email inválido")
    
    if email in _USUARIOS:
        raise ValueError("Email já cadastrado")
    
    senha_valida, msg_erro = validar_senha(senha)
    if not senha_valida:
        raise ValueError(msg_erro)
    
    if not nome or len(nome.strip()) < 2:
        raise ValueError("Nome deve ter no mínimo 2 caracteres")
    
    # Validar convite se fornecido
    if convite:
        from makita.auth.convites import validar_convite, marcar_convite_usado
        if not validar_convite(convite):
            raise ValueError("Código de convite inválido ou já usado")
    
    # Gerar ID único
    usuario_id = secrets.token_urlsafe(16)
    
    # Hash da senha
    senha_hash = hash_senha(senha)
    
    # Criar usuário
    usuario = {
        "id": usuario_id,
        "email": email,
        "senha_hash": senha_hash,
        "nome": nome.strip(),
        "nicho": nicho,
        "criado_em": datetime.now().isoformat(),
        "ativo": True,
        "telegram_chat_id": None,
        "telegram_username": None,
    }
    
    # Salvar
    _USUARIOS[email] = usuario
    _USUARIOS_POR_ID[usuario_id] = usuario
    
    # Marcar convite como usado
    if convite:
        from makita.auth.convites import marcar_convite_usado
        marcar_convite_usado(convite, usuario_id)
    
    log.info(f"Usuário cadastrado: {email} (ID: {usuario_id})")
    
    # Retornar dados (sem senha)
    return {
        "id": usuario_id,
        "email": email,
        "nome": nome.strip(),
        "nicho": nicho,
        "criado_em": usuario["criado_em"],
    }


def login(email: str, senha: str) -> Optional[Dict[str, Any]]:
    """
    Autentica um usuário.
    
    Args:
        email: Email do usuário
        senha: Senha em texto plano
    
    Returns:
        Dict com dados do usuário se autenticado, None caso contrário
    """
    email = email.strip().lower()
    
    usuario = _USUARIOS.get(email)
    if not usuario:
        log.warning(f"Tentativa de login com email inexistente: {email}")
        return None
    
    if not verificar_senha(senha, usuario["senha_hash"]):
        log.warning(f"Senha incorreta para: {email}")
        return None
    
    if not usuario["ativo"]:
        log.warning(f"Tentativa de login com conta inativa: {email}")
        return None
    
    log.info(f"Login bem-sucedido: {email}")
    
    # Retornar dados (sem senha)
    return {
        "id": usuario["id"],
        "email": usuario["email"],
        "nome": usuario["nome"],
        "nicho": usuario["nicho"],
        "criado_em": usuario["criado_em"],
    }


def buscar_por_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Busca usuário por email.
    
    Args:
        email: Email do usuário
    
    Returns:
        Dict com dados do usuário ou None
    """
    email = email.strip().lower()
    usuario = _USUARIOS.get(email)
    
    if not usuario:
        return None
    
    return {
        "id": usuario["id"],
        "email": usuario["email"],
        "nome": usuario["nome"],
        "nicho": usuario["nicho"],
        "criado_em": usuario["criado_em"],
        "ativo": usuario["ativo"],
    }


def buscar_por_id(usuario_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca usuário por ID.
    
    Args:
        usuario_id: ID do usuário
    
    Returns:
        Dict com dados do usuário ou None
    """
    usuario = _USUARIOS_POR_ID.get(usuario_id)
    
    if not usuario:
        return None
    
    return {
        "id": usuario["id"],
        "email": usuario["email"],
        "nome": usuario["nome"],
        "nicho": usuario["nicho"],
        "criado_em": usuario["criado_em"],
        "ativo": usuario["ativo"],
    }


def listar_usuarios() -> list[Dict[str, Any]]:
    """
    Lista todos os usuários (sem senhas).
    
    Returns:
        Lista de usuários
    """
    return [
        {
            "id": u["id"],
            "email": u["email"],
            "nome": u["nome"],
            "nicho": u["nicho"],
            "criado_em": u["criado_em"],
            "ativo": u["ativo"],
        }
        for u in _USUARIOS.values()
    ]


# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE DE REGISTRO ===\n")
    
    # Cadastrar usuário
    print("Cadastrando usuário...")
    try:
        usuario = cadastrar_usuario(
            email="teste@example.com",
            senha="Senha123",
            nome="João Silva",
            nicho="saas"
        )
        print(f"✅ Usuário cadastrado: {usuario['nome']} ({usuario['email']})\n")
    except ValueError as e:
        print(f"❌ Erro: {e}\n")
    
    # Login
    print("Fazendo login...")
    usuario_logado = login("teste@example.com", "Senha123")
    if usuario_logado:
        print(f"✅ Login bem-sucedido: {usuario_logado['nome']}\n")
    else:
        print("❌ Login falhou\n")
    
    # Login com senha errada
    print("Testando senha errada...")
    usuario_logado = login("teste@example.com", "SenhaErrada")
    print(f"Resultado: {usuario_logado}\n")
    
    # Listar usuários
    print(f"Total de usuários: {len(listar_usuarios())}")