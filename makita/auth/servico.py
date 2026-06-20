"""
makita/auth/servico.py
=======================
Serviço de cadastro e autenticação com banco de dados real.

Uso:
    from makita.auth.servico import cadastrar_usuario, login_usuario
    
    # Cadastrar
    usuario = cadastrar_usuario(email="user@example.com", senha="Senha123", nome="João")
    
    # Login
    usuario = login_usuario(email="user@example.com", senha="Senha123")
"""

import re
import hashlib
import secrets
import sys
import os
from typing import Optional, Dict, Any
from datetime import datetime
import logging

# Adicionar diretório raiz ao path para imports funcionarem
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from logger import get_logger
    log = get_logger("auth.servico")
except ImportError:
    import logging
    log = logging.getLogger("auth.servico")
    log.setLevel(logging.INFO)


# Validação de email
def validar_email(email: str) -> bool:
    """Valida formato de email."""
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(padrao, email))


# Validação de senha
def validar_senha(senha: str) -> tuple[bool, str]:
    """
    Valida força da senha.
    
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


# Hash de senha
def hash_senha(senha: str, salt: Optional[str] = None) -> str:
    """
    Gera hash da senha com salt.
    
    Returns:
        Hash no formato: salt$hash
    """
    if salt is None:
        salt = secrets.token_hex(16)
    
    hash_obj = hashlib.sha256((salt + senha).encode())
    hash_hex = hash_obj.hexdigest()
    
    return f"{salt}${hash_hex}"


def verificar_senha(senha: str, hash_armazenado: str) -> bool:
    """Verifica se a senha corresponde ao hash armazenado."""
    try:
        salt, hash_esperado = hash_armazenado.split('$')
        hash_calculado = hashlib.sha256((salt + senha).encode()).hexdigest()
        return hash_calculado == hash_esperado
    except:
        return False


def cadastrar_usuario(
    email: str,
    senha: str,
    nome: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cadastra um novo usuário no banco de dados.
    
    Args:
        email: Email do usuário
        senha: Senha em texto plano
        nome: Nome completo (opcional)
    
    Returns:
        Dict com dados do usuário criado
    
    Raises:
        ValueError: Se dados inválidos ou email duplicado
    """
    # Validações
    email = email.strip().lower()
    
    if not validar_email(email):
        raise ValueError("Email inválido")
    
    if not senha or len(senha.strip()) < 8:
        raise ValueError("Senha deve ter no mínimo 8 caracteres")
    
    senha_valida, msg_erro = validar_senha(senha)
    if not senha_valida:
        raise ValueError(msg_erro)
    
    # Verificar se email já existe
    try:
        from makita.comum.db import get_db
        from makita.comum.modelos import Usuario
        
        db = get_db()
        
        usuario_existente = db.query(Usuario).filter(
            Usuario.email == email
        ).first()
        
        if usuario_existente:
            raise ValueError("Email já cadastrado")
        
        # Gerar hash da senha
        senha_hash = hash_senha(senha)
        
        # Criar usuário
        usuario = Usuario(
            email=email,
            password_hash=senha_hash,
            nome=nome.strip() if nome else None,
            ativo=True,
        )
        
        # Salvar no banco
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        
        log.info(f"Usuário cadastrado: {email} (ID: {usuario.id})")
        
        # Retornar dados (sem senha)
        return {
            "id": usuario.id,
            "email": usuario.email,
            "nome": usuario.nome,
            "criado_em": usuario.criado_em.isoformat() if usuario.criado_em else None,
            "mensagem": "Usuário cadastrado com sucesso"
        }
    
    except Exception as e:
        log.error(f"Erro ao cadastrar usuário: {e}")
        raise ValueError(f"Erro ao cadastrar: {str(e)}")


def login_usuario(email: str, senha: str) -> Optional[Dict[str, Any]]:
    """
    Autentica um usuário.
    
    Args:
        email: Email do usuário
        senha: Senha em texto plano
    
    Returns:
        Dict com dados do usuário se autenticado, None caso contrário
    """
    email = email.strip().lower()
    
    try:
        from makita.comum.db import get_db
        from makita.comum.modelos import Usuario
        
        db = get_db()
        
        usuario = db.query(Usuario).filter(
            Usuario.email == email,
            Usuario.ativo == True
        ).first()
        
        if not usuario:
            log.warning(f"Tentativa de login com email inexistente: {email}")
            return None
        
        if not verificar_senha(senha, usuario.password_hash):
            log.warning(f"Senha incorreta para: {email}")
            return None
        
        log.info(f"Login bem-sucedido: {email}")
        
        return {
            "id": usuario.id,
            "email": usuario.email,
            "nome": usuario.nome,
            "criado_em": usuario.criado_em.isoformat() if usuario.criado_em else None,
            "mensagem": "Login realizado com sucesso"
        }
    
    except Exception as e:
        log.error(f"Erro ao fazer login: {e}")
        return None


# Exemplo de uso
if __name__ == "__main__":
    print("=== TESTE DE CADASTRO COM BANCO REAL ===\n")
    
    # Cadastrar usuário
    print("Cadastrando usuário...")
    try:
        usuario = cadastrar_usuario(
            email="teste@example.com",
            senha="Senha123",
            nome="João Silva"
        )
        print(f"✅ Usuário cadastrado: {usuario['nome']} ({usuario['email']})")
        print(f"   ID: {usuario['id']}")
        print(f"   Criado em: {usuario['criado_em']}\n")
    except ValueError as e:
        print(f"❌ Erro: {e}\n")
    
    # Login
    print("Fazendo login...")
    usuario_logado = login_usuario("teste@example.com", "Senha123")
    if usuario_logado:
        print(f"✅ Login bem-sucedido: {usuario_logado['nome']}\n")
    else:
        print("❌ Login falhou\n")
    
    # Testar email duplicado
    print("Testando email duplicado...")
    try:
        cadastrar_usuario(
            email="teste@example.com",
            senha="Senha123",
            nome="Outro Nome"
        )
    except ValueError as e:
        print(f"✅ Duplicado bloqueado: {e}\n")