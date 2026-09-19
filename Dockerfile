# Portal de Gestão de Cotações — imagem de produção.
FROM python:3.13-slim

# Não rodar como root: o volume do banco é montado com esse uid.
RUN useradd --create-home --uid 10001 portal

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências primeiro: mudança de código não reinstala tudo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# O banco vive fora da imagem, em /dados. Em hospedagem sem disco persistente
# o entrypoint recria a partir do banco que veio na imagem a cada boot.
RUN mkdir -p /dados && chown -R portal:portal /app /dados
ENV DB_PATH=/dados/demo.db \
    AMBIENTE=demonstracao \
    PORT=8000

USER portal
EXPOSE 8000

# A porta sai de $PORT porque Render, Koyeb e Spaces atribuem a porta em runtime.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{p}/healthz', timeout=4).status==200 else 1)"

# O entrypoint aplica as migrações e sobe o gunicorn na porta do ambiente.
# Sem CMD de propósito: a forma exec do CMD não expandiria $PORT.
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
