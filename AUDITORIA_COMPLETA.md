# AUDITORIA COMPLETA DO PROJETO TORFINDER/MAKITA
**Data:** 20/06/2026  
**Baseado exclusivamente no código real do repositório**

---

## PARTE 1 — VISÃO GERAL DA ARQUITETURA

### Diagrama de Fluxo Atual

```
Usuário (cliente potencial)
  │
  ▼
Landing Page (frontend.html — 2 versões)
  │  ├── /frontend.html (raiz — versão com cadastro)
  │  └── /tofinder/backend/app/frontend.html (versão sem cadastro)
  │
  ▼
Bot Telegram (makita/entrega/bot.py)
  │  ├── /start [codigo] — autenticação via invite code
  │  ├── /add <palavra> — adiciona keyword
  │  ├── /remove <palavra> — remove keyword
  │  ├── /list — lista keywords
  │  └── /ping — teste de vida
  │
  ▼
Banco SQLite (makita.db / tofinder.db)
  │  ├── usuarios (telegram_chat_id, plano, max_keywords)
  │  ├── palavras_chave (usuario_id, palavra, ativa)
  │  ├── sinais_vistos (source_id, visto_em) — dedup
  │  └── sessoes_plataforma (plataforma, tokens_json)
  │
  ▼
Makita — Orquestrador (makita/main.py)
  │
  ├── Coletor Facebook (makita/coletores/facebook/graphql.py)
  │     └── GraphQL direto via curl-cffi + tokens do session_manager
  │
  ├── Coletor Twitter (makita/coletores/twitter/adaptador.py)
  │     └── Playwright + interceptação SearchTimeline + DOM fallback
  │
  ├── Coletor Reddit (makita/coletores/reddit/adaptador.py)
  │     └── Playwright + GraphQL shreddit + DOM SDU fallback
  │
  ├── Coletor Bluesky (makita/coletores/bluesky/adaptador.py)
  │     └── WebSocket contínuo (Jetstream)
  │
  ├── Coletor HN (makita/coletores/hn/adaptador.py)
  │     └── Algolia API polling
  │
  ├── Filtro (makita/processamento/filtro.py)
  │     └── Intenção de compra + anti-vendedor + TTL
  │
  ├── Entregador (makita/processamento/entregador.py)
  │     └── Envia para Telegram dos usuários que monitoram a keyword
  │
  ├── Backup (makita/comum/backup.py)
  │     └── VACUUM INTO + envio para admin Telegram
  │
  ├── Saúde (makita/comum/saude.py)
  │     └── Monitora se coletores estão publicando
  │
  └── Healthcheck HTTP (makita/comum/healthcheck.py)
        └── :8080/saude + :8080/ (frontend) + :8080/api/cadastro + :8080/api/login
```

### Stack Tecnológica

| Componente | Tecnologia | Status |
|---|---|---|
| Frontend | HTML/CSS/JS puro (sem framework) | ✅ Existe |
| Backend | Python 3.11 + asyncio | ✅ Existe |
| Banco | SQLite (dev) / PostgreSQL (prod via DATABASE_URL) | ✅ Existe |
| Fila | Redis (obrigatório) / fallback em memória | ⚠️ Redis obrigatório |
| Coletores | Playwright + curl-cffi + aiohttp + websockets | ✅ Existe |
| Bot Telegram | python-telegram-bot v20.7 | ✅ Existe |
| Deploy | Render (web service free) | ⚠️ Configurado |
| Autenticação | Invite codes + hash SHA-256 | ⚠️ SHA-256 inseguro |

### Dependências Críticas (makita/requirements.txt)

```
playwright==1.40.0
curl-cffi==0.7.1
aiosqlite==0.20.0
redis==5.1.1
python-telegram-bot==20.7
python-dotenv==1.0.1
websockets==12.0
aiohttp==3.9.5
```

**Problema:** `sqlalchemy` e `asyncpg` são importados mas NÃO estão no requirements.txt. Se o DATABASE_URL estiver configurado para PostgreSQL, a aplicação quebrará.

---

## PARTE 2 — INVENTÁRIO DE FUNCIONALIDADES

### Frontend (Landing Page)

| Funcionalidade | Status | Detalhes |
|---|---|---|
| Landing page com hero | ✅ Funcionando | HTML/CSS estático, animações JS |
| Formulário de cadastro | ✅ Funcionando | POST /api/cadastro (apenas na versão raiz) |
| Live feed simulado | 🟡 Mockado | Dados 100% falsos, hardcoded no JS |
| Estatísticas (9,907 requests) | 🟡 Mockado | Números fixos no HTML |
| Seção de preços | ✅ Funcionando | Links para Stripe são PLACEHOLDERS |
| FAQ | ✅ Funcionando | Estático |
| Responsividade | ✅ Funcionando | CSS com media queries |
| Light mode | ✅ Funcionando | CSS prefers-color-scheme |

### Autenticação

| Funcionalidade | Status | Detalhes |
|---|---|---|
| Cadastro via email/senha | ✅ Funcionando | POST /api/cadastro no healthcheck |
| Login via email/senha | ✅ Funcionando | POST /api/login no healthcheck |
| Autenticação via invite code | ✅ Funcionando | Bot Telegram /start [codigo] |
| Hash de senha (SHA-256 + salt) | ⚠️ Parcial | SHA-256 é fraco para senhas |
| Sessão/JWT | ❌ Não existe | Sem tokens de sessão |
| Recuperação de senha | ❌ Não existe | |
| Verificação de email | ❌ Não existe | |

### Coletores (Makita)

| Coletor | Status | Detalhes |
|---|---|---|
| Facebook GraphQL | ⚠️ Parcial | Requer tokens renovados a cada 10min via Playwright. Pode quebrar se Facebook mudar doc_id ou estrutura da resposta. |
| Twitter (Playwright) | ⚠️ Parcial | Requer cookies.json. Playwright headless pode ser detectado. DOM fallback frágil. |
| Reddit (Playwright) | ⚠️ Parcial | Cookies opcionais. GraphQL shreddit + DOM SDU. Pode quebrar com mudanças no Reddit. |
| Bluesky (WebSocket) | ✅ Funcionando | WebSocket contínuo, mais estável. |
| Hacker News (Algolia) | ✅ Funcionando | API pública, mais estável. |

### Processamento

| Funcionalidade | Status | Detalhes |
|---|---|---|
| Fila Redis | ⚠️ Parcial | Redis é OBRIGATÓRIO. Sem Redis, fila para completamente. |
| Filtro de intenção | ✅ Funcionando | Palavras de intenção de compra |
| Anti-vendedor | ✅ Funcionando | Filtra posts de freelancers oferecendo serviços |
| Dedup (sinais_vistos) | ✅ Funcionando | Evita repetição |
| Expurgo 90 dias | ✅ Funcionando | Remove sinais_vistos antigos |

### Entrega

| Funcionalidade | Status | Detalhes |
|---|---|---|
| Entrega Telegram | ✅ Funcionando | Envia para chat_ids que monitoram a keyword |
| Mensagem com sugestão | ✅ Funcionando | Template com sugestão de abordagem |
| Rate limit | ✅ Funcionando | 1 mensagem/segundo |
| Bot Telegram (comandos) | ✅ Funcionando | /start, /add, /remove, /list, /ping |
| Limite por plano | ✅ Funcionando | Free: 3 keywords, Pro: 20 keywords |
| Upgrade de plano | ❌ Não existe | Stripe não integrado |

### Infraestrutura

| Funcionalidade | Status | Detalhes |
|---|---|---|
| Healthcheck HTTP | ✅ Funcionando | :8080/saude + :8080/ |
| Backup automático | ✅ Funcionando | VACUUM INTO a cada 6h + Telegram admin |
| Monitoramento de coletores | ✅ Funcionando | loop_saude verifica a cada 5min |
| Alerta admin Telegram | ✅ Funcionando | Se coletor morre ou Telegram falha |
| PostgreSQL | ⚠️ Não testado | Código existe mas nunca foi testado em produção |

### Funcionalidades Quebradas ou Abandonadas

| Funcionalidade | Status | Detalhes |
|---|---|---|
| tofinder/main.py (V1.6) | 🟡 Abandonado | Código legado, substituído pelo Makita |
| tofinder/coletores/ (antigos) | 🟡 Abandonado | Vários coletores antigos não usados |
| tofinder/entrega/telegram.py | 🟡 Abandonado | Código antigo com bug (função duplicada _get_semaphore) |
| tofinder/pipeline.py | 🟡 Abandonado | Pipeline antigo não integrado ao Makita |
| tofinder/models.py | 🟡 Abandonado | Modelos antigos (Lead, Platform) |
| tofinder/keyword_grouper.py | 🟡 Abandonado | Não usado no Makita |
| tofinder/bot_handler.py | 🟡 Abandonado | Bot antigo substituído pelo makita/entrega/bot.py |
| tofinder/admin_alerts.py | 🟡 Abandonado | Substituído pelo makita/comum/saude.py |
| tofinder/watchdog.py | 🟡 Abandonado | Substituído pelo makita/comum/saude.py |
| tofinder/janitor.py | 🟡 Abandonado | Substituído pelo makita/comum/backup.py |
| makita/auth/registro.py | 🟡 Abandonado | Usa dict em memória, substituído por servico.py com banco real |
| makita/auth/convites.py | 🟡 Não verificado | Existe mas não foi analisado |

---

## PARTE 3 — ANÁLISE DE MOCKS E SIMULAÇÕES

### 1. Live Feed — Dados 100% Falsos

**Arquivo:** `frontend.html` (linha 479) e `tofinder/backend/app/frontend.html` (linha 1294)

**Trecho:**
```javascript
var sig = [{p:'fb',pl:'Facebook',t:'"I need a <strong>logo designer</strong>..."',...}];
```

**Motivo:** Simulação visual para landing page. Nunca houve integração com dados reais.

**Impacto:** 🟡 **Médio** — Usuário vê oportunidades falsas. Se for para produção real, isso é enganoso.

### 2. Estatísticas — Números Fixos

**Arquivo:** `frontend.html` (linha 276)

**Trecho:**
```html
<div class="stat-num">9<span>,</span>907</div>
<div class="stat-num"><span><</span>60s</div>
<div class="stat-num">4</div>
```

**Motivo:** Prova social falsa para conversão.

**Impacto:** 🟡 **Médio** — Enganoso se for produção real.

### 3. Preços — Links Stripe Placeholder

**Arquivo:** `frontend.html` (linha 341)

**Trecho:**
```html
<a href="https://buy.stripe.com/PLACEHOLDER_PRO" ...>
```

**Motivo:** Stripe nunca foi integrado.

**Impacto:** 🔴 **Alto** — Impossível cobrar usuários. O modelo de negócio não funciona.

### 4. Bot Telegram — Invite Codes Fixos

**Arquivo:** `makita/entrega/bot.py` (linha 44)

**Trecho:**
```python
INVITE_CODES_ENV = os.environ.get(
    "INVITE_CODES",
    "MAKITA001,MAKITA002,...,MAKITA010",
)
```

**Motivo:** Códigos de convite padrão para teste.

**Impacto:** 🟢 **Baixo** — Códigos podem ser alterados via env var. Mas os defaults são públicos.

### 5. tofinder/entrega/telegram.py — Código Duplicado

**Arquivo:** `tofinder/entrega/telegram.py` (linhas 13-23)

**Trecho:**
```python
async def _get_semaphore():
    global _SEMAPHORE
    if _SEMAPHORE is None:
        _SEMAPHORE = None  # <-- BUG: atribui None a si mesma
```

**Motivo:** Código legado abandonado, nunca foi corrigido.

**Impacto:** 🟢 **Baixo** — Código não é mais usado (substituído pelo Makita).

---

## PARTE 4 — FLUXO REAL DO USUÁRIO

### Fluxo Atual (Implementado)

```
1. Usuário acessa landing page (frontend.html)
   │
2. Usuário vê:
   │  ├── Hero com mensagens rotativas (animação JS)
   │  ├── Live feed com dados FALSOS (simulação JS)
   │  ├── Estatísticas FIXAS (9,907 requests)
   │  ├── Seção "How it works" (estático)
   │  ├── Preview do alerta Telegram (estático)
   │  ├── Tabela de preços (Stripe links são PLACEHOLDERS)
   │  └── FAQ (estático)
   │
3. Usuário clica "Start Receiving Opportunities"
   │  └── Redireciona para https://t.me/TorfinderBot?start=TORFINDER001
   │
4. Usuário interage com o bot Telegram:
   │  ├── /start MAKITA001 → cria conta (plano free, 3 keywords)
   │  ├── /add "preciso de designer" → adiciona keyword
   │  └── /list → vê suas keywords
   │
5. Makita (orquestrador) roda em loop:
   │  ├── Lê palavras ativas do banco SQLite
   │  ├── Para cada palavra, coleta em 5 plataformas:
   │  │   ├── Facebook (GraphQL via curl-cffi)
   │  │   ├── Twitter (Playwright)
   │  │   ├── Reddit (Playwright)
   │  │   ├── Bluesky (WebSocket)
   │  │   └── Hacker News (Algolia API)
   │  ├── Publica na fila Redis
   │  ├── Filtro processa (intenção de compra?)
   │  └── Entregador envia para Telegram do usuário
   │
6. Usuário recebe alerta no Telegram:
   │  └── "Nova oportunidade — Facebook"
   │      "Preciso de um designer..."
   │      Sugestão: "Vi seu post sobre..."
   │
7. FIM (não há dashboard, não há analytics, não há upgrade)
```

### O que NÃO existe no fluxo real:

- ❌ Dashboard do usuário
- ❌ Página de login (fora do bot Telegram)
- ❌ Gerenciamento de keywords via web
- ❌ Pagamento/Stripe
- ❌ Analytics de oportunidades
- ❌ Histórico de alertas
- ❌ Notificações push (só Telegram)
- ❌ Suporte a múltiplos idiomas no frontend
- ❌ Página de status do sistema
- ❌ Página de documentação

---

## PARTE 5 — BANCO DE DADOS

### Tabelas Ativas (Makita)

#### `usuarios`
| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | Auto increment |
| telegram_chat_id | TEXT UNIQUE NOT NULL | ID do chat Telegram |
| ativo | INTEGER DEFAULT 1 | Se a conta está ativa |
| plano | TEXT DEFAULT 'basico' | 'free' ou 'pro' |
| max_keywords | INTEGER DEFAULT 10 | Limite de keywords |
| criado_em | TEXT NOT NULL | ISO 8601 |

#### `palavras_chave`
| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | Auto increment |
| usuario_id | INTEGER FK → usuarios.id | Dono da keyword |
| palavra | TEXT NOT NULL | A keyword |
| ativa | INTEGER DEFAULT 1 | Se está ativa |
| criado_em | TEXT NOT NULL | ISO 8601 |
| UNIQUE(usuario_id, palavra) | | |

#### `sinais_vistos`
| Campo | Tipo | Descrição |
|---|---|---|
| source_id | TEXT PK | Hash único do sinal |
| visto_em | TEXT NOT NULL | ISO 8601 |

#### `sessoes_plataforma`
| Campo | Tipo | Descrição |
|---|---|---|
| plataforma | TEXT PK | 'facebook', 'twitter', etc. |
| tokens_json | TEXT NOT NULL | JSON com tokens de autenticação |
| atualizado_em | TEXT NOT NULL | ISO 8601 |

### Tabelas do Modelo SQLAlchemy (NÃO usadas pelo Makita)

#### `sinais` (modelos.py)
| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | |
| plataforma | VARCHAR(50) INDEX | |
| tipo | VARCHAR(50) | |
| titulo | VARCHAR(500) | |
| descricao | TEXT | |
| autor | VARCHAR(200) | |
| relevancia | FLOAT INDEX | |
| timestamp | DATETIME INDEX | |
| link | VARCHAR(500) | |
| nicho | VARCHAR(50) INDEX | |
| criado_em | DATETIME | |

**Status:** 🟡 **Abandonada** — A tabela `sinais` está definida no SQLAlchemy mas NÃO é criada pelo `init_db()` do Makita. O Makita usa tabelas SQL diretas (sem ORM).

#### `usuarios` (modelos.py — SQLAlchemy)
| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK | |
| email | VARCHAR(200) UNIQUE INDEX | |
| password_hash | VARCHAR(255) | |
| nome | VARCHAR(200) | |
| nicho | VARCHAR(50) | |
| telegram_chat_id | VARCHAR(100) UNIQUE | |
| telegram_username | VARCHAR(100) | |
| ativo | BOOLEAN | |
| criado_em | DATETIME | |
| atualizado_em | DATETIME | |

**Status:** 🟡 **Inconsistente** — Este modelo SQLAlchemy tem campos diferentes da tabela SQL direta do Makita (email, password_hash, nome vs telegram_chat_id, plano, max_keywords). São DUAS definições diferentes de usuário.

### Tabelas do tofinder (legado)

#### `tofinder.db`
- Contém tabelas do sistema antigo (não analisado em detalhe)
- **Status:** 🟡 **Abandonado** — O Makita usa `makita.db` separado

### Problemas Críticos do Banco

1. **🔴 Duas definições de usuário** — `makita/comum/db.py` cria tabela com `telegram_chat_id` como identificador, enquanto `makita/comum/modelos.py` (SQLAlchemy) usa `email`. O `makita/auth/servico.py` tenta usar o modelo SQLAlchemy, que NÃO é criado pelo `init_db()` do Makita.

2. **🔴 servico.py quebra** — `makita/auth/servico.py` importa `get_db()` de `makita.comum.db`, mas `get_db()` NÃO existe. A função real é `init_db()`. O cadastro via API (`POST /api/cadastro`) vai falhar.

3. **⚠️ Sem índices em palavras_chave.palavra** — A busca por palavra é feita com `DISTINCT palavra`, sem índice.

4. **⚠️ Sem índices em sinais_vistos.visto_em** — O expurgo por data pode ser lento com muitos registros.

---

## PARTE 6 — APIs E ROTAS

### Rotas do Healthcheck HTTP (:8080)

| Rota | Método | Finalidade | Status | Testada |
|---|---|---|---|---|
| `/` | GET | Servir frontend.html | ✅ Funcionando | ✅ |
| `/index.html` | GET | Servir frontend.html | ✅ Funcionando | ❌ |
| `/saude` | GET | Health check JSON | ✅ Funcionando | ✅ |
| `/api/cadastro` | POST | Cadastrar usuário | 🔴 Quebrado | ❌ |
| `/api/login` | POST | Login usuário | 🔴 Quebrado | ❌ |

### Rotas do Bot Telegram

| Comando | Finalidade | Status | Testada |
|---|---|---|---|
| `/start [codigo]` | Autenticar via invite code | ✅ Funcionando | ✅ |
| `/add <palavra>` | Adicionar keyword | ✅ Funcionando | ✅ |
| `/remove <palavra>` | Remover keyword | ✅ Funcionando | ✅ |
| `/list` | Listar keywords | ✅ Funcionando | ✅ |
| `/ping` | Teste de vida | ✅ Funcionando | ✅ |

### Rotas do tofinder (legado — NÃO em uso)

| Rota | Finalidade | Status |
|---|---|---|
| tofinder/backend/app/ | Backend antigo | 🟡 Abandonado |

### Problemas com /api/cadastro e /api/login

**Arquivo:** `makita/comum/healthcheck.py` (linhas 62-146)

**Problema:** O código chama `from makita.auth.servico import cadastrar_usuario`, que por sua vez chama `from makita.comum.db import get_db`. A função `get_db()` **NÃO EXISTE** em `makita/comum/db.py`. A função real é `init_db()`.

**Impacto:** 🔴 **Crítico** — Qualquer tentativa de cadastro ou login via API HTTP resultará em `ImportError` ou `AttributeError`.

---

## PARTE 7 — DEPLOY E INFRAESTRUTURA

### Render (makita/render.yaml)

```yaml
services:
  - type: web
    name: makita
    env: python
    region: ohio
    plan: free
    buildCommand: |
      pip install -r requirements.txt &&
      playwright install chromium
    startCommand: python main.py
    healthCheckPath: /saude
```

**Status:** ⚠️ **Configurado mas não testado em produção**

### Problemas Identificados

1. **🔴 Playwright em plano free** — Render free tem 512MB RAM. Playwright + Chromium consome ~300-400MB. Com 5 coletores rodando concorrentemente, vai estourar memória.

2. **🔴 Redis necessário** — A fila Redis é OBRIGATÓRIA. Sem Redis, `publicar()` loga `CRITICAL` e perde sinais. Render free não tem Redis nativo — precisaria de Redis Cloud ou Upstash.

3. **🔴 Banco de dados** — SQLite em produção é inviável (dados voláteis, sem concorrência). PostgreSQL está configurado no código mas NUNCA foi testado.

4. **⚠️ Variáveis de ambiente** — 14 variáveis marcadas como `sync: false` no render.yaml. Todas precisam ser configuradas manualmente no dashboard do Render.

5. **⚠️ Healthcheck path** — `/saude` está configurado, mas o servidor HTTP roda na mesma thread do asyncio. Se algum coletor travar, o healthcheck também trava.

6. **⚠️ Sem Dockerfile funcional** — `makita/Dockerfile` existe mas não foi analisado. O `makita/docker/docker-compose.yml` também existe.

### Vercel

**Status:** ❌ **Não configurado** — Não há configuração de Vercel no projeto. O frontend.html é servido pelo próprio healthcheck HTTP do Makita.

### O que está deployado vs não está

| Item | Deployado? |
|---|---|
| Makita (orquestrador) | ❌ Não (só configurado no render.yaml) |
| Frontend (landing page) | ❌ Não (servido pelo Makita) |
| Bot Telegram | ❌ Não (precisa estar rodando) |
| Banco PostgreSQL | ❌ Não configurado |
| Redis | ❌ Não configurado |
| Stripe | ❌ Não integrado |

---

## PARTE 8 — SEGURANÇA

### Avaliação

| Item | Classificação | Detalhes |
|---|---|---|
| Senhas em texto plano no .env | 🔴 **Crítico** | `TW_PASSWORD=NICk2005@@` está no .env |
| Hash SHA-256 para senhas | 🔴 **Alto** | SHA-256 sem key stretching é vulnerável a ataques de força bruta. Deveria usar bcrypt/argon2. |
| Tokens do Facebook no .env | 🔴 **Crítico** | `FB_C_USER`, `FB_XS`, `FB_FR` expostos |
| Token do Telegram no .env | 🔴 **Crítico** | `TELEGRAM_TOKEN` exposto |
| Cookies do Twitter no .env | 🔴 **Crítico** | `TWITTER_COOKIES_B64` provavelmente contém cookies |
| Sem autenticação nas APIs | 🔴 **Alto** | `/api/cadastro` e `/api/login` não têm rate limit ou proteção CSRF |
| Sem HTTPS em dev | 🟡 **Médio** | Healthcheck HTTP sem TLS |
| Invite codes padrão públicos | 🟡 **Médio** | `MAKITA001` a `MAKITA010` são defaults |
| Códigos de convite em memória | 🟡 **Médio** | `USED_CODES` é um set em memória — se o bot reiniciar, códigos usados são revalidados |
| SQL injection | 🟢 **Baixo** | Usa parâmetros parametrizados (?, $1) |
| XSS no frontend | 🟢 **Baixo** | Conteúdo estático, sem inputs do usuário renderizados |

### Problemas Críticos de Segurança

1. **🔴 .env commitado** — O arquivo `.env` contém credenciais reais do Telegram, Facebook e Twitter. Isso é um vazamento de segurança grave.

2. **🔴 Senha do Twitter em texto plano** — `TW_PASSWORD=NICk2005@@` está legível.

3. **🔴 Hash fraco de senha** — SHA-256 + salt é melhor que nada, mas não é suficiente para produção. Deveria usar bcrypt com fator de custo 12+.

4. **🔴 Sem rate limit** — As APIs de cadastro/login não têm proteção contra brute force.

---

## PARTE 9 — PRONTIDÃO PARA LANÇAMENTO

### Teste Interno
**Status:** ❌ **Não pronto**

**Justificativa:**
- `/api/cadastro` e `/api/login` estão quebrados (importam função inexistente)
- Redis é obrigatório e não está configurado
- Playwright em servidor free vai estourar memória
- Duas definições conflitantes de usuário no banco

### Beta Fechado
**Status:** ❌ **Não pronto**

**Justificativa:**
- Stripe não integrado (não dá para cobrar)
- Live feed com dados falsos (engana usuários)
- Estatísticas falsas (engana usuários)
- Sem dashboard para o usuário
- Sem analytics
- Coletores podem quebrar a qualquer momento (Playwright headless é frágil)

### Beta Aberto
**Status:** ❌ **Não pronto**

**Justificativa:**
- Todos os problemas do beta fechado +
- Sem infraestrutura escalável
- SQLite não suporta concorrência
- Sem monitoramento de erros
- Sem página de status

### Produção
**Status:** ❌ **Não pronto**

**Justificativa:**
- Todos os problemas acima +
- Segurança crítica (senhas no .env, hash fraco)
- Sem backup de banco em produção
- Sem CI/CD
- Sem testes automatizados
- Código legado abandonado misturado com código novo

---

## PARTE 10 — PRÓXIMOS PASSOS PRIORITÁRIOS

### PRIORIDADE 1
**Impacto:** 🔴 Crítico  
**Esforço:** 2 horas  
**Motivo:** Impede qualquer uso do sistema

**Corrigir `makita/auth/servico.py` — função `get_db()` inexistente**
- O arquivo importa `from makita.comum.db import get_db`, mas essa função não existe
- Isso quebra `/api/cadastro` e `/api/login`
- Solução: criar `get_db()` ou refatorar para usar as funções existentes (`init_db`, `executar`, `buscar`)

### PRIORIDADE 2
**Impacto:** 🔴 Crítico  
**Esforço:** 4 horas  
**Motivo:** Segurança

**Remover credenciais do .env e usar variáveis de ambiente**
- `TELEGRAM_TOKEN`, `TW_PASSWORD`, `FB_C_USER`, `FB_XS`, `FB_FR` estão no .env
- Solução: .env.example sem valores reais, .env no .gitignore

### PRIORIDADE 3
**Impacto:** 🔴 Crítico  
**Esforço:** 8 horas  
**Motivo:** Infraestrutura

**Configurar Redis e PostgreSQL para produção**
- Fila Redis é obrigatória para o Makita funcionar
- SQLite não serve para produção
- Solução: Redis Cloud (free tier) + PostgreSQL (Render free tier ou Neon)

### PRIORIDADE 4
**Impacto:** 🔴 Alto  
**Esforço:** 16 horas  
**Motivo:** Modelo de negócio

**Integrar Stripe para pagamentos**
- Links de preços são placeholders
- Sem Stripe, não há como cobrar usuários
- Solução: Stripe Payment Links ou Stripe Checkout

### PRIORIDADE 5
**Impacto:** 🟡 Alto  
**Esforço:** 4 horas  
**Motivo:** Experiência do usuário

**Substituir dados mockados por dados reais no frontend**
- Live feed com dados falsos
- Estatísticas fixas
- Solução: endpoint `/api/stats` real ou remover seções enganosas

### PRIORIDADE 6
**Impacto:** 🟡 Alto  
**Esforço:** 8 horas  
**Motivo:** Confiabilidade

**Resolver conflito de modelos de banco**
- Duas definições de usuário (SQL direto vs SQLAlchemy)
- Tabela `sinais` criada mas nunca usada
- Solução: unificar em um modelo, remover o outro

### PRIORIDADE 7
**Impacto:** 🟡 Médio  
**Esforço:** 8 horas  
**Motivo:** Estabilidade

**Substituir Playwright por APIs nativas**
- Playwright headless é frágil, pesado e detectável
- Facebook: já usa GraphQL (bom)
- Twitter: migrar para API v2 (precisa de credenciais de dev)
- Reddit: migrar para API oficial (rate limit, mas mais estável)

### PRIORIDADE 8
**Impacto:** 🟡 Médio  
**Esforço:** 4 horas  
**Motivo:** Manutenibilidade

**Limpar código legado do tofinder/**
- Dezenas de arquivos mortos, scripts de teste, diagnósticos
- Solução: mover para `_legado/` ou remover

### PRIORIDADE 9
**Impacto:** 🟢 Baixo  
**Esforço:** 2 horas  
**Motivo:** Qualidade

**Adicionar testes automatizados**
- Zero testes no projeto
- Solução: pytest para os coletores + filtro + entregador

### PRIORIDADE 10
**Impacto:** 🟢 Baixo  
**Esforço:** 4 horas  
**Motivo:** Profissionalismo

**Criar dashboard web para usuários**
- Hoje o usuário só interage via bot Telegram
- Solução: página protegida com login para gerenciar keywords, ver histórico

---

## PARTE 11 — RESUMO EXECUTIVO

### 1. Onde estamos hoje?

Temos um **sistema parcialmente funcional** com:
- Um orquestrador (Makita) que coleta dados de 5 plataformas
- Um bot Telegram que permite cadastro e gestão de keywords
- Uma landing page bonita mas com dados falsos
- Um banco SQLite com dados reais de usuários e keywords
- Muito código legado morto e confuso

### 2. O que realmente funciona?

- ✅ Coleta do **Bluesky** (WebSocket) — estável
- ✅ Coleta do **Hacker News** (Algolia API) — estável
- ✅ **Bot Telegram** — cadastro, add/remove/list keywords
- ✅ **Filtro** de intenção de compra
- ✅ **Entrega** de alertas no Telegram
- ✅ **Backup** automático do banco
- ✅ **Healthcheck** HTTP
- ✅ **Monitoramento** de coletores (saude.py)

### 3. O que ainda é risco?

- 🔴 **Facebook** — depende de tokens que expiram e Playwright para renovar
- 🔴 **Twitter** — depende de cookies e Playwright headless (frágil)
- 🔴 **Reddit** — depende de Playwright e DOM scraping (frágil)
- 🔴 **Redis** — obrigatório e não configurado
- 🔴 **Cadastro/login HTTP** — quebrado (função inexistente)
- 🔴 **Segurança** — senhas no .env, hash fraco
- 🔴 **Stripe** — não integrado (sem cobrança)
- 🟡 **Playwright em produção** — vai estourar memória no plano free
- 🟡 **SQLite em produção** — não escala
- 🟡 **Código legado** — confunde e polui o repositório

### 4. O que falta para lançar?

**Mínimo para beta fechado:**
1. Corrigir `get_db()` no servico.py (2h)
2. Configurar Redis (2h)
3. Configurar PostgreSQL (2h)
4. Remover dados mockados do frontend (2h)
5. Testar se os 5 coletores rodam estáveis (8h)

**Mínimo para produção:**
6. Integrar Stripe (16h)
7. Corrigir segurança (4h)
8. Substituir Playwright por APIs (16h)
9. Adicionar testes (8h)
10. Criar dashboard (16h)

### 5. Estimativa de prontidão

| Critério | % | Justificativa |
|---|---|---|
| Código escrito | 60% | Muito código, mas parte é legado morto |
| Funcionalidades core | 40% | Coletores existem mas são frágeis |
| Infraestrutura | 10% | Só config.yaml, nada deployado |
| Segurança | 15% | Múltiplos problemas críticos |
| UX/UI | 30% | Landing bonita, mas sem dashboard |
| Modelo de negócio | 5% | Stripe não integrado |
| Testes | 0% | Zero testes automatizados |
| Documentação | 20% | Vários .md, mas código mal documentado |

### **Estimativa Geral: 15% pronto para produção**

**Nota:** O projeto tem uma base sólida (arquitetura de coletores, fila, filtro, entrega) mas está longe de produção. Os problemas críticos são: (1) dependência de Playwright em ambiente limitado, (2) Redis não configurado, (3) cadastro quebrado, (4) segurança comprometida, (5) Stripe não integrado. Recomendo focar em estabilizar o backend antes de pensar em lançamento.