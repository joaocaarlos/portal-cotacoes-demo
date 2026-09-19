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

# O banco vive em volume, fora da imagem. DB_PATH aponta para lá.
RUN mkdir -p /dados && chown -R portal:portal /app /dados
ENV DB_PATH=/dados/cotacoes.db \
    AMBIENTE=producao \
    PORT=8000

USER portal
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status==200 else 1)"

# entrypoint aplica migrações pendentes antes de servir.
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/bin/sh", "/entrypoint.sh"]
CMD ["gunicorn", "--workers", "2", "--threads", "4", "--timeout", "120", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "--bind", "0.0.0.0:8000", "app:app"]
