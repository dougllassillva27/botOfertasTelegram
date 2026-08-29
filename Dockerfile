FROM python:3.11-slim

# Evita criação de arquivos .pyc e força flush imediato de stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    TZ=America/Sao_Paulo

# Instala pacotes básicos de sistema para certificados e fuso horário
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências Python primeiro para aproveitar cache de camadas do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cria diretórios persistentes de dados e logs
RUN mkdir -p /app/data /app/logs

# Copia código da aplicação
COPY app/ ./app/

# Define volumes para persistência de sessão, estado e logs
VOLUME ["/app/data", "/app/logs"]

# Executa o bot
CMD ["python", "-m", "app.main"]
