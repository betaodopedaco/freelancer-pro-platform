# Variáveis de Ambiente — Render (Makita)

## Como configurar

Render Dashboard → Seu serviço → **Environment** → **Add Environment Variable**

**IMPORTANTE:** Todas as variáveis abaixo devem ter `sync: false` (não sincroniza com GitHub)

---

## Variáveis OBRIGATÓRIAS

### 1. TELEGRAM_TOKEN
```
8514449188:AAEaVkAee5wG2DNUeOGTnOchtkKk_xaisg0
```
**Onde conseguir:** @BotFather no Telegram → /newbot → copiar o token

---

### 2. TELEGRAM_CHAT_ID
```
123456789
```
**Onde conseguir:** 
1. Inicie uma conversa com o seu bot
2. Acesse: `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
3. Procure por `"chat":{"id":123456789,...}`

---

### 3. ADMIN_CHAT_ID
```
123456789
```
**Onde conseguir:** Mesmo valor do TELEGRAM_CHAT_ID (seu próprio chat)

---

### 4. FB_C_USER
```
100012345678901
```
**Onde conseguir:**
1. Abra o Facebook no navegador (logado)
2. F12 → Application → Cookies → `.facebook.com`
3. Procure o cookie `c_user`
4. Copie o valor (é um número)

---

### 5. FB_XS
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U
```
**Onde conseguir:**
1. Mesmo lugar do FB_C_USER
2. Procure o cookie `xs`
3. Copie o valor completo (é longo)

---

### 6. FB_FR
```
0AbcdEFgHiJkLmNoPqRsTuVwXyZ1234567890
```
**Onde conseguir:**
1. Mesmo lugar do FB_C_USER
2. Procure o cookie `fr`
3. Copie o valor completo

---

### 7. TWITTER_COOKIES_B64
```
eyJ0b2tlbiI6ICJ7XCJhdXRoX3Rva2VuXCI6IHtcImFsZ29yaXRob1wiOiBcInNlY3JldFwiLFwiY2hhbGxlbmdlXCI6IHtcImVuY3J5cHRpb25cIjogXCJ0cnVlXCJ9LFwiX2tleVwiOiB7XCJ0b2tlbl9rZXlcIjogXCJ0ZXN0XCJ9fSxcImN0MFwiOiBcIjEyMzQ1Njc4OVwifSJ9
```
**Como gerar:**
```powershell
# No Windows PowerShell:
[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content twitter_cookies.json -Raw)))

# Ou no Linux/Mac:
base64 -w 0 twitter_cookies.json
```

**Arquivo de origem:** `twitter_cookies.json` (na raiz do projeto)

---

### 8. INVITE_CODES
```
CODIGO1,CODIGO2,CODIGO3
```
**Formato:** Códigos separados por vírgula (sem espaços)

**Exemplo:**
```
ALFA2024,BETA2024,GAMA2024
```

---

### 9. REDIS_URL
```
redis://localhost:6379
```
**Se usar Redis local:**
```
redis://localhost:6379
```

**Se usar Redis cloud (ex: Upstash):**
```
redis://default:password@us1-abc123.upstash.io:6379
```

**Se NÃO usar Redis (deixar vazio):**
```
(Deixe em branco)
```

---

### 10. DATABASE_URL
```
postgresql://usuario:senha@host:5432/makita
```
**Se usar PostgreSQL (Render):**
```
postgresql://makita:senha123@host.render.com:5432/makita
```

**Se usar SQLite local (deixar vazio):**
```
(Deixe em branco)
```

---

### 11. DEBUG
```
false
```
**Valores possíveis:**
- `true` — logs detalhados (desenvolvimento)
- `false` — logs normais (produção)

---

## Variáveis OPCIONAIS (não precisam ser configuradas)

### PYTHON_VERSION
```
3.11.9
```
**Padrão:** Definido no `makita/runtime.txt`

### PLAYWRIGHT_BROWSERS_PATH
```
0
```
**Padrão:** `0` (usa browsers locais)

### TW_AUTH_TOKEN
```
(Deixe vazio)
```
**Legado:** Não é mais usado (substituído por TWITTER_COOKIES_B64)

### TW_CT0
```
(Deixe vazio)
```
**Legado:** Não é mais usado (substituído por TWITTER_COOKIES_B64)

---

## Checklist de Configuração

- [ ] TELEGRAM_TOKEN
- [ ] TELEGRAM_CHAT_ID
- [ ] ADMIN_CHAT_ID
- [ ] FB_C_USER
- [ ] FB_XS
- [ ] FB_FR
- [ ] TWITTER_COOKIES_B64
- [ ] INVITE_CODES
- [ ] REDIS_URL (ou deixar vazio)
- [ ] DATABASE_URL (ou deixar vazio)
- [ ] DEBUG = false

**Todas com `sync: false`**

---

## Após configurar

1. Clique em **"Save Changes"**
2. Aguarde o deploy (~2-3 minutos)
3. Verifique os logs procurando por:
   - `"MAKITA — todos os 5 coletores + infra"`
   - `"Entregador iniciado"`
   - `"Twitter adaptador iniciado"`
   - `"TWITTER_COOKIES_B64 válido: ok"`

---

## Se algo der errado

Verifique os logs no Render Dashboard → Logs

**Erros comuns:**
- `TELEGRAM_TOKEN não definido` → Variável não configurada
- `Twitter: nenhum cookie disponível` → TWITTER_COOKIES_B64 inválido
- `Tokens do Facebook não disponíveis` → FB_C_USER/FB_XS/FB_FR inválidos
- `0 palavras ativas` → Banco vazio, nenhuma keyword cadastrada