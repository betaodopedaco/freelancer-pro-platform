# STATUS ATUAL DO MAKITA NO RENDER — MAPA PARA VERIFICAÇÃO MANUAL
**Data:** 20/06/2026  
**Instrução:** NADA foi alterado no código. Apenas diagnose baseada no código local.

---

## 1. MAPA COMPLETO DE VARIÁVEIS DE AMBIENTE

Segue a lista exaustiva de todas as variáveis que o Makita lê via `os.getenv()` ou `os.environ`, ordenadas por arquivo.

### makita/main.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| *(nenhuma)* | | main.py não lê variáveis diretamente |

### makita/comum/db.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `DATABASE_URL` | `os.environ.get("DATABASE_URL", "")` (linha 19) | Usa SQLite (makita.db). **Seguro.** |
| `DB_PATH` | `os.environ.get("DB_PATH", "makita.db")` (linha 20) | Usa "makita.db" como fallback. **Seguro.** |

### makita/comum/fila.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `REDIS_URL` | `os.environ.get("REDIS_URL", "")` (linha 27) | **CRÍTICO.** Se vazia, `_get_redis()` retorna None. `publicar()` loga `CRITICAL "REDIS INDISPONÍVEL — fila parada"` e **perde o sinal**. Sistema não processa nada até Redis conectar. |

### makita/comum/healthcheck.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `PORT` | `os.getenv("PORT", os.getenv("HEALTHCHECK_PORT", "8080"))` (linha 25) | Usa 8080 como fallback. **Seguro.** |
| `HEALTHCHECK_PORT` | `os.getenv("PORT", os.getenv("HEALTHCHECK_PORT", "8080"))` (linha 25) | Usa 8080 como fallback. **Seguro.** |

### makita/comum/backup.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `ADMIN_CHAT_ID` | `os.environ.get("ADMIN_CHAT_ID", "")` (linha 25) | **Alerta.** Se vazia, backup não é enviado para Telegram. Loga warning: "ADMIN_CHAT_ID ou TELEGRAM_TOKEN não configurados — backup externo desativado." Backup local ainda funciona. |
| `TELEGRAM_TOKEN` | `os.environ.get("TELEGRAM_TOKEN", "")` (linha 26) | Mesmo do ADMIN_CHAT_ID. Se vazio, backup externo desativado. |

### makita/comum/saude.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `ADMIN_CHAT_ID` | `os.environ.get("ADMIN_CHAT_ID", "")` (linha 44) | Se vazia, `_enviar_alerta()` simplesmente retorna sem fazer nada. **Silencioso.** |
| `TELEGRAM_TOKEN` | `os.environ.get("TELEGRAM_TOKEN", "")` (linha 45) | Se vazio, `_get_bot()` retorna None, `_enviar_alerta()` retorna sem fazer nada. **Silencioso.** |

### makita/coletores/facebook/graphql.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `FB_C_USER` | `os.getenv("FB_C_USER", "")` (linha 38) | **CRÍTICO.** Usado no header Cookie e no body da requisição. Se vazio, a request GraphQL vai com Cookie incompleto (`c_user=; xs=...; fr=...`). Facebook rejeita. O coletor continua rodando mas nunca encontra posts. |
| `FB_XS` | `os.getenv("FB_XS", "")` (linha 39) | **CRÍTICO.** Mesmo caso do FB_C_USER. Cookie inválido → request rejeitada silenciosamente. |
| `FB_FR` | `os.getenv("FB_FR", "")` (linha 40) | **CRÍTICO.** Mesmo caso. |
| `FB_POLL_INTERVAL` | `int(os.getenv("FB_POLL_INTERVAL", "1800"))` (linha 52) | Usa 1800 (30 min) como fallback. **Seguro.** |

### makita/coletores/facebook/session_manager.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `FB_C_USER` | `os.getenv("FB_C_USER", "")` (linha 19) | **CRÍTICO.** Cookies do Playwright ficam com `value` vazio. Login no Facebook falha silenciosamente. `_capture_tokens()` retorna None. |
| `FB_XS` | `os.getenv("FB_XS", "")` (linha 20) | **CRÍTICO.** Mesmo caso. |
| `FB_FR` | `os.getenv("FB_FR", "")` (linha 21) | **CRÍTICO.** Mesmo caso. |
| `FB_TOKEN_REFRESH_SECS` | `os.getenv("FB_TOKEN_REFRESH_SECS", "600")` (linha 36) | Usa 600 (10 min) como fallback. **Seguro.** |

### makita/coletores/twitter/adaptador.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `TWITTER_POLL_INTERVAL` | `int(os.getenv("TWITTER_POLL_INTERVAL", "1800"))` (linha 22) | Usa 1800 (30 min) como fallback. **Seguro.** |

**Nota importante:** O Twitter depende de cookies carregados via `load_twitter_cookies()`, que por sua vez lê de:

`tofinder/coletores/twitter_cookie_loader.py` (não analisado, mas sabe-se que lê):
| Variável | Ocorre se vazia |
|---|---|
| `TWITTER_COOKIES_B64` | Provavelmente tenta fallback para arquivo local `twitter_cookies.json`. Se ambos falharem, `load_twitter_cookies()` retorna lista vazia e o coletor loga **warning** e desliga: "Twitter: nenhum cookie disponível (loader centralizado falhou). Desativando." |

### makita/coletores/reddit/adaptador.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `REDDIT_POLL_INTERVAL` | `int(os.getenv("REDDIT_POLL_INTERVAL", "1800"))` (linha 15) | Usa 1800 (30 min) como fallback. **Seguro.** |

**Reddit:** Tenta carregar cookies de `tofinder/reddit_cookies.json`. Se arquivo não existe, loga "rodando sem login" e continua. **Seguro.**

### makita/coletores/hn/adaptador.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `HN_POLL_INTERVAL` | `int(os.getenv("HN_POLL_INTERVAL", "600"))` (linha 17) | Usa 600 (10 min) como fallback. **Seguro.** |

### makita/entrega/bot.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `TELEGRAM_TOKEN` | `os.environ.get("TELEGRAM_TOKEN", "")` (linha 42) | **CRÍTICO.** Se vazio, `main()` loga erro e retorna imediatamente: "TELEGRAM_TOKEN não definido no .env". Bot não sobe. |
| `INVITE_CODES` | `os.environ.get("INVITE_CODES", "MAKITA001,...,MAKITA010")` (linha 43) | Usa fallback com 10 códigos padrão. **Seguro** porém **inseguro** (códigos públicos). |

### makita/processamento/entregador.py
| Variável | Onde lê | Ocorre se vazia |
|---|---|---|
| `TELEGRAM_TOKEN` | `os.environ.get("TELEGRAM_TOKEN", "")` (linha 22) | **CRÍTICO.** Se vazio, `loop_entregador()` loga erro e retorna imediatamente: "TELEGRAM_TOKEN não definido. Entregador desligado." Nenhum alerta é entregue. |

---

## 2. VARIÁVEIS DECLARADAS NO render.yaml (que precisam ser preenchidas)

Estas 14 variáveis estão listadas no `render.yaml` com `sync: false`, o que significa que você PRECISA configurá-las manualmente no dashboard do Render:

```
TELEGRAM_TOKEN          ← CRÍTICO (bot + entregador + backup + saude)
TELEGRAM_CHAT_ID        ← Usado pelo tofinder legado (não pelo Makita)
ADMIN_CHAT_ID           ← Backup + alertas de saúde
FB_C_USER               ← CRÍTICO (coletor Facebook)
FB_XS                   ← CRÍTICO (coletor Facebook)
FB_FR                   ← CRÍTICO (coletor Facebook)
TW_AUTH_TOKEN           ← Pode ser legado do tofinder
TW_CT0                  ← Pode ser legado do tofinder
TWITTER_COOKIES_B64     ← CRÍTICO (coletor Twitter)
INVITE_CODES            ← Códigos de convite
REDIS_URL               ← CRÍTICO (fila inteira depende disso)
DATABASE_URL            ← PostgreSQL (se vazio, usa SQLite — OK para teste)
DEBUG                   ← Opcional
```

---

## 3. CONFIRMAÇÃO: /api/cadastro e /api/login ESTÃO QUEBRADOS

**SIM. Confirmo que estão quebrados.**

### O problema exato:

**Arquivo:** `makita/auth/servico.py`, linhas 128-131:
```python
    try:
        from makita.comum.db import get_db          # <-- LINHA 128: get_db NÃO EXISTE
        from makita.comum.modelos import Usuario

        db = get_db()                                # <-- LINHA 131: CHAMADA VAI FALHAR
```

**Arquivo:** `makita/comum/db.py` — funções exportadas (lista real):
```python
async def init_db(...)      # ← existe
async def get_palavras_ativas(...)   # ← existe
async def get_chat_ids_por_palavra(...)  # ← existe
async def ja_visto(...)     # ← existe
async def salvar_sessao(...)  # ← existe
async def ler_sessao(...)   # ← existe
async def executar(...)     # ← existe
async def buscar(...)       # ← existe

# get_db() não está em lugar nenhum. NUNCA foi criada.
```

### O que acontece quando alguém tenta cadastrar:

```
1. Usuário preenche formulário na landing page
2. Frontend faz POST /api/cadastro
3. healthcheck.py recebe a request
4. healthcheck.py chama: from makita.auth.servico import cadastrar_usuario
5. cadastrar_usuario() chega na linha 128:
       from makita.comum.db import get_db
6. ImportError: cannot import name 'get_db' from 'makita.comum.db'
   → Exceção capturada pelo except Exception em healthcheck.py linha 98-104
   → Retorna 500 com {"erro": "Erro interno do servidor"}
```

**Além disso**, mesmo que `get_db()` existisse, o `cadastrar_usuario()` usa o modelo SQLAlchemy `Usuario` (que espera colunas `email`, `password_hash`, `nome`), enquanto a tabela criada pelo `init_db()` do Makita tem colunas completamente diferentes (`telegram_chat_id`, `plano`, `max_keywords`). Ou seja, mesmo consertando o import, a inserção SQL falharia porque as colunas não correspondem.

**Duplo problema:**
1. 🔴 `get_db()` não existe → ImportError
2. 🔴 Modelo SQLAlchemy vs tabela SQL direta são incompatíveis → SQLite error

---

## 4. RESUMO PARA VERIFICAÇÃO NO PAINEL DO RENDER

Se você for ao dashboard do Render agora, verifique estes pontos na seguinte ordem de criticidade:

### 🔴 CRÍTICO (sistema não funciona sem)

| # | O que verificar | Como |
|---|---|---|
| 1 | `TELEGRAM_TOKEN` está preenchido? | Services → makita → Environment |
| 2 | `REDIS_URL` está preenchido? | Services → makita → Environment |
| 3 | `FB_C_USER`, `FB_XS`, `FB_FR` estão preenchidos? | Services → makita → Environment |
| 4 | `TWITTER_COOKIES_B64` está preenchido? | Services → makita → Environment |

### 🟡 ALTO (partes do sistema quebram)

| # | O que verificar | Como |
|---|---|---|
| 5 | `ADMIN_CHAT_ID` está preenchido? | Services → makita → Environment |
| 6 | `INVITE_CODES` está preenchido? | Services → makita → Environment |
| 7 | `DATABASE_URL` está preenchido? (deixe vazio para SQLite em teste) | Services → makita → Environment |

### 🟢 BAIXO (fallbacks seguros existem)

| # | O que verificar | Como |
|---|---|---|
| 8 | O deploy buildou sem erros? | Events → último deploy |
| 9 | O healthcheck `/saude` responde? | Abrir `https://makita.onrender.com/saude` |
| 10 | A landing page `/` carrega? | Abrir `https://makita.onrender.com/` |
| 11 | Quanto de RAM está sendo usada? | Metrics → Memory |

### Roteiro de verificação no terminal (se tiver acesso ao shell do Render):

```bash
# Testar se Redis está respondendo
redis-cli -u $REDIS_URL ping
# → deve responder "PONG"

# Testar se o banco SQLite foi criado
ls -la makita.db
# → deve existir (se PostgreSQL não configurado)

# Verificar se o bot Telegram está vivo
curl -s "https://api.telegram.org/bot$TELEGRAM_TOKEN/getMe"
# → deve retornar {"ok":true,"result":{"id":...}}

# Testar healthcheck
curl -s http://localhost:8080/saude
# → deve retornar JSON com status "ok"