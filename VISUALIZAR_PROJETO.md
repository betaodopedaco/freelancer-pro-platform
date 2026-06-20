# Como Visualizar o Projeto Makita

## 🚀 OPÇÃO 1: Ver a Landing Page (Mais Rápido)

### No Windows:
```bash
# Abrir a landing page diretamente no navegador
start makita/landing_fluxo.html
```

### No Mac/Linux:
```bash
# Abrir a landing page
open makita/landing_fluxo.html
# ou
xdg-open makita/landing_fluxo.html
```

**O que você vai ver:**
- Hero section com CTA
- Prova social (stats + depoimentos)
- Fluxo das 6 etapas
- Preview interativo com sinais mockados
- Animações ao scroll

---

## 🧪 OPÇÃO 2: Testar os Módulos Python

### Testar Templates de Nicho:
```bash
cd "c:\Users\Ricardo\Downloads\alerta tfnd"
python makita/nichos/templates.py
```

**Saída esperada:**
```
=== TEMPLATES DISPONÍVEIS ===
🏠 Imobiliário: Imóveis, aluguéis, vendas e investimentos
☁️ SaaS / Software: Softwares, ferramentas, automação e produtividade
🛒 E-commerce: Lojas virtuais, vendas online, dropshipping
₿ Crypto / Web3: Criptomoedas, DeFi, NFTs, blockchain
📊 Marketing Digital: Tráfego, SEO, conteúdo, redes sociais
🚀 Startups: Empreendedorismo, investimentos, pitch
🤖 Inteligência Artificial: IA, ML, LLMs, automação inteligente
⚙️ Personalizado: Crie seu próprio conjunto de keywords
```

### Testar Sistema de Convites:
```bash
python makita/auth/convites.py
```

**Saída esperada:**
```
=== TESTE DE CONVITES ===

Gerando convites...
Convite 1: ABC123XYZ789
Convite 2: DEF456UVW012

Validando convites...
ABC123XYZ789 válido? True
INEXISTENTE válido? False

Marcando convite como usado...
ABC123XYZ789 ainda válido? False

Convites ativos: ['DEF456UVW012']
Convites usados: {'ABC123XYZ789': 'usuario_123'}
```

### Testar Cadastro:
```bash
python makita/auth/registro.py
```

**Saída esperada:**
```
=== TESTE DE REGISTRO ===

Cadastrando usuário...
✅ Usuário cadastrado: João Silva (teste@example.com)

Fazendo login...
✅ Login bem-sucedido: João Silva

Testando senha errada...
Resultado: None

Total de usuários: 1
```

### Testar Wizard de Configuração:
```bash
python makita/configuracao/wizard.py
```

**Saída esperada:**
```
=== TESTE DO WIZARD ===

Etapa: nichos
Título: Escolha seu nicho
Opções: ['Imobiliário', 'SaaS / Software', 'E-commerce', ...]

Resultado: {'sucesso': True, 'proxima_etapa': 'keywords', ...}

Etapa: keywords
Título: Quais keywords você quer monitorar?
Keywords padrão: ['software', 'ferramenta', 'automação', ...]

Resultado: {'sucesso': True, 'proxima_etapa': 'plataformas', ...}

Progresso: {'etapa_atual': 'plataformas', 'etapa_numero': 3, 'total_etapas': 6, 'percentual': 50}
```

### Testar Preview (Mock):
```bash
python makita/preview/gerador.py
```

**Saída esperada:**
```
=== TESTE DO GERADOR DE PREVIEW ===

Gerando 4 sinais para SaaS...

1. [TWITTER] Alguém conhece uma ferramenta de automação para WhatsApp?
   Relevância: 0.96
   Autor: @empreendedor_tech

2. [REDDIT] Qual o melhor SaaS para gestão de projetos em 2024?
   Relevância: 0.91
   Autor: u/startup_founder

3. [HACKER NEWS] Show HN: Ferramenta open source para analytics
   Relevância: 0.85
   Autor: devopensource

4. [TWITTER] Procurando API de pagamento para SaaS
   Relevância: 0.83
   Autor: @cto_startup

=== ESTATÍSTICAS ===
total_sinais: 247
sinais_hoje: 12
plataformas_ativas: 5
relevancia_media: 0.87
ultima_coleta: 2024-06-20T01:00:00.000000
```

### Testar Preview (Dados Reais):
```bash
python makita/preview/real.py
```

**Saída esperada:**
```
=== TESTE DE PREVIEW COM DADOS REAIS ===

Buscando sinais reais para: saas

✅ Encontrados 4 sinais reais:

1. [TWITTER] Alguém conhece uma ferramenta de automação para WhatsApp?
   Relevância: 0.96
   Autor: @empreendedor_tech

=== ESTATÍSTICAS ===
total_sinais: 150
sinais_hoje: 8
plataformas_ativas: 4
relevancia_media: 0.82
ultima_coleta: 2024-06-20T00:45:00.000000
```

---

## 🌐 OPÇÃO 3: Servidor Local (Avançado)

### Se quiser rodar o servidor completo:

```bash
# 1. Instalar dependências (se necessário)
pip install -r makita/requirements.txt

# 2. Rodar o servidor
cd makita
python main.py
```

**Acesse:**
- Landing page: http://localhost:8000
- Healthcheck: http://localhost:8000/saude
- Landing alternativa: http://localhost:10000/

---

## 📊 OPÇÃO 4: Ver o Banco de Dados

### Se quiser ver os sinais coletados:

```bash
# Opção 1: Usar DB Browser for SQLite
# Download: https://sqlitebrowser.org/

# Abrir o arquivo:
makita/makita.db

# Opção 2: Via linha de comando
sqlite3 makita/makita.db

# Ver tabelas
.tables

# Ver sinais
SELECT * FROM sinais LIMIT 10;

# Ver estatísticas
SELECT nicho, COUNT(*) as total, AVG(relevancia) as relevancia_media
FROM sinais
GROUP BY nicho;
```

---

## 🎯 OPÇÃO 5: Testar o Fluxo Completo

### Sequência recomendada:

1. **Abra a landing page:**
   ```bash
   start makita/landing_fluxo.html
   ```

2. **Teste os templates:**
   ```bash
   python makita/nichos/templates.py
   ```

3. **Teste o wizard:**
   ```bash
   python makita/configuracao/wizard.py
   ```

4. **Teste o preview:**
   ```bash
   python makita/preview/gerador.py
   python makita/preview/real.py
   ```

5. **Teste cadastro:**
   ```bash
   python makita/auth/registro.py
   ```

---

## 📁 ESTRUTURA PARA VISUALIZAR:

```
makita/
├── landing_fluxo.html          ← ABRIR ESTE (landing page)
├── landing.html                ← Landing anterior
├── nichos/
│   └── templates.py            ← python makita/nichos/templates.py
├── auth/
│   ├── convites.py             ← python makita/auth/convites.py
│   └── registro.py             ← python makita/auth/registro.py
├── configuracao/
│   └── wizard.py               ← python makita/configuracao/wizard.py
├── preview/
│   ├── gerador.py              ← python makita/preview/gerador.py
│   └── real.py                 ← python makita/preview/real.py
└── main.py                     ← python makita/main.py (servidor)
```

---

## ⚡ COMANDO RÁPIDO (Tudo em Um):

Crie um arquivo `testar_tudo.py`:

```python
#!/usr/bin/env python3
"""
Script para testar todos os módulos de uma vez
"""

import subprocess
import sys

modulos = [
    ("Templates de Nicho", "makita/nichos/templates.py"),
    ("Sistema de Convites", "makita/auth/convites.py"),
    ("Cadastro", "makita/auth/registro.py"),
    ("Wizard", "makita/configuracao/wizard.py"),
    ("Preview (Mock)", "makita/preview/gerador.py"),
    ("Preview (Real)", "makita/preview/real.py"),
]

print("=" * 60)
print("TESTANDO TODOS OS MÓDULOS")
print("=" * 60)

for nome, caminho in modulos:
    print(f"\n{'=' * 60}")
    print(f"TESTANDO: {nome}")
    print(f"{'=' * 60}\n")
    
    resultado = subprocess.run(
        [sys.executable, caminho],
        capture_output=True,
        text=True
    )
    
    print(resultado.stdout)
    
    if resultado.returncode != 0:
        print(f"❌ ERRO em {nome}:")
        print(resultado.stderr)
    else:
        print(f"✅ {nome} - OK")

print("\n" + "=" * 60)
print("TESTES CONCLUÍDOS!")
print("=" * 60)
```

**Executar:**
```bash
python testar_tudo.py
```

---

## 🎨 Visualizar a Landing Page:

**Arquivo principal:** `makita/landing_fluxo.html`

**Como abrir:**
1. Clique duas vezes no arquivo
2. Ou clique direito → Abrir com → Navegador
3. Ou execute: `start makita/landing_fluxo.html`

**O que ver:**
- Design moderno e responsivo
- Animações suaves
- Seções: Hero, Prova Social, Fluxo, Preview, CTA
- Exemplos de sinais reais do nicho SaaS

---

Qual opção você quer testar primeiro?