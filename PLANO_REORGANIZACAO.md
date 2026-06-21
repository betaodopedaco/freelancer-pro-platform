# PLANO DE REORGANIZAÇÃO — BACKEND (Render) vs FRONTEND (Vercel)
**Data:** 20/06/2026  
**Status:** Diagnóstico completo, nada foi alterado ainda.

---

## TAREFA 1 — CAUSA RAIZ DO PROBLEMA DO REDIS_URL

### O código exato que lê REDIS_URL

**Arquivo:** `makita/comum/fila.py`, linha 27:
```python
REDIS_URL = os.environ.get("REDIS_URL", "")
```

**Problema:** Esta é uma variável **de módulo** (module-level). Ela é avaliada UMA ÚNICA VEZ, no momento em que o Python importa `makita.comum.fila` pela primeira vez. Depois disso, o valor fica congelado — mesmo que a variável de ambiente mude, `REDIS_URL` não atualiza.

### Fluxo de importação que congela o valor

```
main.py linha 28:
    from makita.processamento.filtro import loop_filtro
        ↓
filtro.py linha 14:
    from makita.comum.fila import publicar, consumir, tamanho
        ↓
fila.py linha 27:
    REDIS_URL = os.environ.get("REDIS_URL", "")   ← AVALIADO AQUI, UMA VEZ
```

### Por que "connecting to localhost:6379" aparece nos logs?

**Essa mensagem NÃO é gerada pelo código do Makita.** O Makita loga:
- `"Redis conectado: {REDIS_URL}"` (linha 49) — se conectar
- `"Redis indisponível: {erro}"` (linha 51) — se falhar
- `"REDIS INDISPONÍVEL — fila parada"` (linha 127) — se Redis for None

A mensagem `"connecting to localhost:6379"` só pode vir de **duas fontes**:

1. **Do próprio driver `redis`** — quando a URL `rediss://default:...@precious-amoeba-40626.upstash.io:6379` falha ao conectar (ex: SSL handshake, DNS não resolve, firewall bloqueia), o driver `redis-py` pode logar mensagens de debug/tentativa de fallback que mencionam `localhost:6379`.

2. **De um script de teste local** — `makita/rodar_10min.py` linha 40 tem um `print("  Redis: redis://localhost:6379/0")` hardcoded. Se alguém rodou esse script no Render por engano, explicaria a mensagem.

### Diagnóstico: o que realmente está acontecendo

| Hipótese | Probabilidade | Explicação |
|---|---|---|
| REDIS_URL lida como vazia | 🔴 **Alta** | Se a variável não foi configurada no Render dashboard (ou foi configurada com nome errado), `os.environ.get("REDIS_URL", "")` retorna `""`, `_get_redis()` retorna None, e o sistema loga "REDIS INDISPONÍVEL". A mensagem "localhost:6379" seria de outro lugar. |
| URL Upstash está falhando | 🟡 **Média** | A URL `rediss://` (SSL) pode estar falhando por certificado, e o driver redis loga algo confuso. |
| Script de teste rodando | 🟢 **Baixa** | Se o `rodar_10min.py` foi deployado por engano como entrypoint. |

### O que verificar no Render

1. **Confirme o nome exato da variável:** Tem que ser `REDIS_URL` (exatamente assim, com underscore, não `REDIS` nem `REDIS_URI`)
2. **Confirme que a variável aparece em:** Dashboard → Services → makita → Environment → `REDIS_URL`
3. **Teste manual no shell do Render:**
   ```bash
   python -c "import os; print(repr(os.environ.get('REDIS_URL', 'NAO_ENCONTRADA')))"
   ```
4. **Veja os logs completos do Redis:** Procure por `"fila"` nos logs do Render para ver se aparece `"Redis indisponível"` ou `"REDIS INDISPONÍVEL"`

---

## TAREFA 2 — ARQUIVOS DE FRONTEND PARA MOVER PARA `frontend/`

### Lista completa de arquivos que pertencem ao frontend (Vercel)

```
frontend/                          ← NOVA pasta na raiz
├── index.html                     ← (vindo de /frontend.html)
├── landing.html                   ← (vindo de makita/landing.html)
├── landing_fluxo.html             ← (vindo de makita/landing_fluxo.html)
├── auth/
│   ├── __init__.py
│   ├── servico.py                 ← (vindo de makita/auth/servico.py) — QUEBRADO, precisa correção
│   ├── registro.py                ← (vindo de makita/auth/registro.py) — versão em memória
│   └── convites.py                ← (vindo de makita/auth/convites.py)
├── preview/
│   ├── __init__.py
│   ├── real.py                    ← (vindo de makita/preview/real.py) — busca sinais reais
│   └── gerador.py                 ← (vindo de makita/preview/gerador.py) — fallback mockado
├── nichos/
│   ├── __init__.py
│   └── templates.py               ← (vindo de makita/nichos/templates.py)
├── configuracao/
│   ├── __init__.py
│   └── wizard.py                  ← (vindo de makita/configuracao/wizard.py)
└── requirements.txt               ← Dependências do frontend (se houver)
```

### Arquivos que ficam na raiz (não movidos, mas referenciam frontend)

```
tofinder/backend/app/frontend.html  ← Versão alternativa da landing (pode ser descartada ou movida)
```

### Commits recentes que adicionaram esses arquivos

Pelo git log (visível parcialmente):
```
7376b83 feat: implementa cadastro real de usuários
  A       frontend.html
  A       makita/auth/servico.py
```

---

## TAREFA 3 — ESTRUTURA FINAL DE `makita/` (SÓ BACKEND)

### Antes da limpeza (estado atual)

```
makita/
├── auth/                  ← FRONTEND (mover)
│   ├── __init__.py
│   ├── convites.py
│   ├── registro.py
│   └── servico.py
├── coletores/             ← BACKEND (manter)
│   ├── bluesky/
│   ├── facebook/
│   ├── hn/
│   ├── reddit/
│   └── twitter/
├── comum/                 ← BACKEND (manter, mas simplificar healthcheck)
│   ├── backup.py
│   ├── db.py
│   ├── fila.py
│   ├── healthcheck.py     ← REMOVER rotas de frontend (/, /api/cadastro, /api/login)
│   ├── modelos.py         ← SIMPLIFICAR (remover SQLAlchemy, só dataclass)
│   └── saude.py
├── configuracao/          ← FRONTEND (mover)
│   ├── __init__.py
│   └── wizard.py
├── docker/                ← BACKEND (manter)
│   ├── docker-compose.yml
│   └── Dockerfile
├── entrega/               ← BACKEND (manter)
│   └── bot.py
├── nichos/                ← FRONTEND (mover)
│   ├── __init__.py
│   └── templates.py
├── preview/               ← FRONTEND (mover)
│   ├── __init__.py
│   ├── gerador.py
│   └── real.py
├── processamento/         ← BACKEND (manter)
│   ├── entregador.py
│   └── filtro.py
├── landing.html           ← FRONTEND (mover)
├── landing_fluxo.html     ← FRONTEND (mover)
├── main.py                ← BACKEND (manter)
├── requirements.txt       ← BACKEND (manter, remover sqlalchemy)
├── render.yaml            ← BACKEND (manter)
├── runtime.txt            ← BACKEND (manter)
├── Dockerfile             ← BACKEND (manter)
├── .gitignore             ← BACKEND (manter)
├── rodar_5min.py          ← Script de teste (pode ficar ou ir para _testes/)
├── rodar_10min.py         ← Script de teste (pode ficar ou ir para _testes/)
├── rodar_e_mostrar.py     ← Script de teste
├── seed_e_teste.py        ← Script de teste
├── setup_usuario_real.py  ← Script de teste
├── testar_envio_telegram.py ← Script de teste
├── teste_completo.py      ← Script de teste
├── teste_fb_rapido.py     ← Script de teste
├── teste_reddit_rapido.py ← Script de teste
├── diagnostico_com_fresh.py ← Script de diagnóstico
├── diagnostico_pipeline.py ← Script de diagnóstico
├── limpar_dedup.py        ← Script de manutenção
├── limpar_teste.py        ← Script de manutenção
├── migrar_tokens.py       ← Script de manutenção
└── preparar_teste.py      ← Script de teste
```

### Depois da limpeza (estado desejado)

```
makita/                          ← SÓ BACKEND
├── coletores/
│   ├── bluesky/adaptador.py
│   ├── facebook/
│   │   ├── graphql.py
│   │   └── session_manager.py
│   ├── hn/adaptador.py
│   ├── reddit/adaptador.py
│   └── twitter/adaptador.py
├── comum/
│   ├── backup.py
│   ├── db.py
│   ├── fila.py
│   ├── healthcheck.py     ← SÓ /saude (remover /, /api/cadastro, /api/login)
│   ├── modelos.py         ← SÓ dataclass SinalBruto (remover SQLAlchemy)
│   └── saude.py
├── entrega/
│   └── bot.py
├── processamento/
│   ├── entregador.py
│   └── filtro.py
├── main.py
├── requirements.txt       ← REMOVER sqlalchemy, asyncpg
├── render.yaml
├── runtime.txt
├── Dockerfile
└── .gitignore
```

### Mudanças específicas no código

#### 1. `makita/comum/healthcheck.py` — Remover rotas de frontend

**Remover:**
- Rota `GET /` (servir frontend.html) — linhas 40-59
- Rota `POST /api/cadastro` — linhas 62-104
- Rota `POST /api/login` — linhas 107-146
- Variável `FRONTEND_PATH` — linha 26
- Import `from makita.auth.servico import cadastrar_usuario` — linha 81
- Import `from makita.auth.servico import login_usuario` — linha 123

**Manter apenas:**
- Rota `GET /saude` — health check JSON (linhas 148-174)

#### 2. `makita/comum/modelos.py` — Remover SQLAlchemy

**Remover:**
- Classe `Sinal(Base)` — tabela SQLAlchemy não usada
- Classe `Usuario(Base)` — tabela SQLAlchemy conflitante
- Import `from sqlalchemy import ...`
- `try/except ImportError` com `declarative_base`

**Manter apenas:**
- `@dataclass SinalBruto` — usado por todos os coletores, filtro e entregador

#### 3. `makita/requirements.txt` — Remover dependências não usadas

**Remover:**
- `sqlalchemy` (não usado após limpeza)
- `asyncpg` (não está no requirements mas é importado — remover import também)

**Manter:**
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

---

## RESUMO DAS AÇÕES

| Tarefa | Ação | Arquivos afetados |
|---|---|---|
| 1 - REDIS_URL | Investigar no Render se a env var está com o nome exato `REDIS_URL` | Nenhum (só verificação) |
| 2 - Mover frontend | Criar `frontend/` e mover 12+ arquivos de makita/ | `frontend.html`, `makita/auth/*`, `makita/preview/*`, `makita/nichos/*`, `makita/configuracao/*`, `makita/landing*.html` |
| 3 - Limpar backend | Remover rotas de frontend do healthcheck, simplificar modelos, limpar requirements | `makita/comum/healthcheck.py`, `makita/comum/modelos.py`, `makita/requirements.txt` |

**Nota:** O `makita/auth/servico.py` está quebrado (importa `get_db()` inexistente). Ao mover para `frontend/`, ele precisará ser corrigido para funcionar — mas isso é uma tarefa separada.