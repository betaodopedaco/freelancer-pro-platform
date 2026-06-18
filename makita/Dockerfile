# makita — Dockerfile (dentro de makita/ para o Render)
# ======================================================
# Usa Python 3.11-slim para garantir compatibilidade com
# greenlet, asyncpg e outras extensões C.
# Build context: makita/ (onde render.yaml está)
# Run: python main.py

FROM python:3.11-slim

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Instalar Playwright + Chromium
RUN pip install --no-cache-dir playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Definir diretório de trabalho
WORKDIR /app

# Copiar requirements.txt e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o projeto (makita/)
COPY . .

# Variáveis de ambiente
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Comando padrão
CMD ["python", "main.py"]