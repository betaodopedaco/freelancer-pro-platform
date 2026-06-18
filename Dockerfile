# makita — Dockerfile (raiz do repo)
# =====================================
# Usa Python 3.11-slim para garantir compatibilidade.
# Build: docker build -t makita .
# Run:   docker run --env-file .env makita

FROM python:3.11-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências do Playwright
RUN pip install --no-cache-dir playwright

# Instalar Chromium via Playwright
RUN playwright install chromium

# Instalar dependências do sistema do Chromium
RUN playwright install-deps chromium

# Definir diretório de trabalho
WORKDIR /app

# Copiar requirements.txt de makita/ e instalar dependências Python
COPY makita/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o projeto
COPY . .

# Variáveis de ambiente
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Comando padrão — inicia o main.py pelo makita
CMD ["python", "makita/main.py"]