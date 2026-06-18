"""
Teste de envio manual para o Telegram.
Verifica se o bot consegue enviar para o chat_id 8081681015.
"""
import asyncio, sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carrega .env
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

from telegram import Bot

async def main():
    token = os.getenv("TELEGRAM_TOKEN", "")
    chat_id_str = os.getenv("TELEGRAM_CHAT_ID", "")
    
    print(f"Token: {token[:20]}...")
    print(f"Chat ID: {chat_id_str}")
    
    if not token or not chat_id_str:
        print("ERRO: Token ou Chat ID não configurados")
        return
    
    bot = Bot(token=token)
    
    # 1. Tenta getMe (verifica se token é válido)
    try:
        me = await bot.get_me()
        print(f"\n✅ Bot conectado: @{me.username} (id={me.id})")
    except Exception as e:
        print(f"\n❌ Token inválido: {e}")
        return
    
    # 2. Tenta enviar mensagem
    print(f"\n📨 Enviando mensagem de teste para {chat_id_str}...")
    try:
        msg = await bot.send_message(
            chat_id=chat_id_str,
            text="🧪 Teste Makita — funcionando!\n\n"
                 "Se você está vendo esta mensagem, o bot "
                 "consegue te enviar leads automaticamente.\n\n"
                 "✅ Envio funcionando!",
        )
        print(f"✅ Mensagem enviada! message_id={msg.message_id}")
        print(f"   Conteúdo: {msg.text[:60]}...")
    except Exception as e:
        print(f"❌ Erro ao enviar: {e}")
        if "chat not found" in str(e).lower():
            print("\n🔑 SOLUÇÃO: O usuário PRECISA iniciar conversa com o bot primeiro.")
            print(f"   Envie /start para @{me.username} no Telegram.")
        elif "bot was blocked" in str(e).lower():
            print("\n🔑 SOLUÇÃO: O usuário bloqueou o bot. Desbloqueie e envie /start")
        elif "can't send" in str(e).lower():
            print("\n🔑 SOLUÇÃO: Inicie conversa enviando /start para o bot no Telegram.")

asyncio.run(main())