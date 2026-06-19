# Configuração do Render — Makita

## Problema
O build falha com:
```
su: Authentication failure
Failed to install browser dependencies
```

## Causa
O comando `playwright install-deps chromium` tenta instalar dependências do sistema operacional via `su`, mas o Render não permite isso.

## Solução

### No Dashboard do Render, configure:

**Build Command:**
```bash
pip install -r makita/requirements.txt && playwright install chromium
```

**⚠️ IMPORTANTE:** Remova a parte `&& playwright install-deps chromium`

**Start Command:**
```bash
python makita/main.py
```

**Root Directory:**
```
makita
```

---

## Por que funciona?

1. **`playwright install chromium`** — Apenas baixa o binário do Chromium (não precisa de root)
2. **`playwright install-deps chromium`** — Tenta instalar pacotes do sistema (precisa de root) → **REMOVER**
3. O Render já tem as dependências básicas do Playwright pré-instaladas na imagem base

---

## Variáveis de ambiente necessárias

No Render Dashboard → Environment, adicione:

```
TELEGRAM_TOKEN = <seu token>
TELEGRAM_CHAT_ID = <seu chat id>
ADMIN_CHAT_ID = <seu chat id admin>
FB_C_USER = <cookie facebook>
FB_XS = <cookie facebook>
FB_FR = <cookie facebook>
TWITTER_COOKIES_B64 = <base64 dos cookies twitter>
INVITE_CODES = <códigos de convite>
REDIS_URL = <url do redis>
DATABASE_URL = <url do postgresql>
DEBUG = false
```

**Todas com `sync: false`** (exceto PYTHON_VERSION e PLAYWRIGHT_BROWSERS_PATH)

---

## Após configurar

1. Clique em "Save Changes" no Render
2. O build vai rodar automaticamente
3. Aguarde ~2-3 minutos para o deploy
4. Verifique os logs procurando por:
   - `"MAKITA — todos os 5 coletores + infra"`
   - `"Entregador iniciado"`
   - `"Twitter adaptador iniciado"`

---

## Se ainda falhar

Verifique se o `makita/requirements.txt` existe e contém:
```
playwright>=1.40.0
python-telegram-bot>=20.0
aiosqlite>=0.19.0
asyncpg>=0.29.0
redis>=5.0.0
```

E se o `makita/runtime.txt` contém:
```
python-3.11.9