"""
render_env_extractor.py
=======================
Extrai variáveis de ambiente do Render via API.

Uso:
    1. Gere um API Key no Render Dashboard → Settings → API Keys
    2. Execute: python render_env_extractor.py
    3. Cole o API Key quando solicitado
    4. Cole o Service ID quando solicitado

O script vai mostrar todas as variáveis com seus valores (mascarados).
"""

import os
import sys
import json
import base64
import getpass
import urllib.request
import urllib.error


def get_render_api_key() -> str:
    """Solicita o API Key do Render."""
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    if api_key:
        return api_key
    
    print("=" * 60)
    print("RENDER API KEY")
    print("=" * 60)
    print("Gere em: Render Dashboard → Settings → API Keys")
    print("Cole abaixo (não será exibida):")
    api_key = getpass.getpass("> ").strip()
    return api_key


def get_service_id() -> str:
    """Solicita o Service ID do Render."""
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()
    if service_id:
        return service_id
    
    print("\n" + "=" * 60)
    print("SERVICE ID")
    print("=" * 60)
    print("Encontre em: Render Dashboard → Seu serviço → Settings")
    print("URL: https://dashboard.render.com/web/srv-xxxxxx/settings")
    print("Cole o ID (ex: srv-abc123xyz):")
    service_id = input("> ").strip()
    return service_id


def mask_value(key: str, value: str) -> str:
    """Mascara valores sensíveis para exibição."""
    sensitive_keys = ["TOKEN", "SECRET", "PASSWORD", "COOKIE", "B64", "URL"]
    
    for sk in sensitive_keys:
        if sk in key.upper():
            if len(value) > 20:
                return value[:10] + "..." + value[-10:]
            elif len(value) > 8:
                return value[:4] + "..." + value[-4:]
            else:
                return "***"
    
    return value


def list_env_vars(api_key: str, service_id: str) -> dict:
    """Lista variáveis de ambiente do serviço no Render."""
    url = f"https://api.render.com/v1/services/{service_id}/env-vars"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            return {item["key"]: item["value"] for item in data}
    except urllib.error.HTTPError as e:
        print(f"\n❌ Erro HTTP {e.code}: {e.reason}")
        if e.code == 401:
            print("API Key inválida ou expirada.")
        elif e.code == 404:
            print("Service ID não encontrado.")
        return {}
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        return {}


def decode_b64_if_possible(value: str) -> str:
    """Tenta decodificar Base64 para mostrar o conteúdo real."""
    try:
        decoded = base64.b64decode(value).decode("utf-8")
        # Verifica se é JSON
        json.loads(decoded)
        return f"BASE64_JSON:{decoded[:100]}..."
    except:
        pass
    return value


def main():
    print("\n" + "=" * 60)
    print("EXTRATOR DE VARIÁVEIS DE AMBIENTE — RENDER")
    print("=" * 60)
    
    api_key = get_render_api_key()
    if not api_key:
        print("❌ API Key não fornecida.")
        return
    
    service_id = get_service_id()
    if not service_id:
        print("❌ Service ID não fornecido.")
        return
    
    print("\n⏳ Buscando variáveis...")
    env_vars = list_env_vars(api_key, service_id)
    
    if not env_vars:
        print("❌ Nenhuma variável encontrada ou erro na API.")
        return
    
    print(f"\n✅ {len(env_vars)} variáveis encontradas:\n")
    print("-" * 60)
    
    for key, value in sorted(env_vars.items()):
        masked = mask_value(key, value)
        
        # Se for TWITTER_COOKIES_B64, tenta decodificar
        if key == "TWITTER_COOKIES_B64":
            display = decode_b64_if_possible(value)
        else:
            display = masked
        
        print(f"{key:30s} = {display}")
    
    print("-" * 60)
    
    # Salva em arquivo (valores reais)
    output_file = "render_env_vars.json"
    with open(output_file, "w") as f:
        json.dump(env_vars, f, indent=2)
    
    print(f"\n✅ Valores completos salvos em: {output_file}")
    print("   (NÃO comite este arquivo no git!)")
    
    # Mostra resumo
    print("\n" + "=" * 60)
    print("RESUMO PARA O RENDER:")
    print("=" * 60)
    
    required = [
        "TELEGRAM_TOKEN",
        "TELEGRAM_CHAT_ID",
        "ADMIN_CHAT_ID",
        "FB_C_USER",
        "FB_XS",
        "FB_FR",
        "TWITTER_COOKIES_B64",
        "INVITE_CODES",
        "REDIS_URL",
        "DATABASE_URL",
        "DEBUG",
    ]
    
    missing = [r for r in required if r not in env_vars or not env_vars[r]]
    
    if missing:
        print(f"\n⚠️  Variáveis FALTANDO ou VAZIAS:")
        for m in missing:
            print(f"   - {m}")
    else:
        print("\n✅ Todas as variáveis obrigatórias estão configuradas!")
    
    print("\n" + "=" * 60)
    print("Próximo passo:")
    print("1. Verifique se todas as variáveis estão preenchidas")
    print("2. Se faltar alguma, adicione no Render Dashboard")
    print("3. NÃO delete o serviço (isso reseta as variáveis)")
    print("=" * 60)


if __name__ == "__main__":
    main()