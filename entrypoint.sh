#!/bin/sh
# Prepara o banco e só então entrega o processo ao servidor WSGI.
set -e

DB="${DB_PATH:-/dados/demo.db}"

if [ ! -f "$DB" ]; then
  SEMENTE_DB=""
  for candidato in /app/cotacoes.db /app/demo.db; do
    [ -f "$candidato" ] && SEMENTE_DB="$candidato" && break
  done
  if [ -n "$SEMENTE_DB" ]; then
    echo "[entrypoint] primeira subida: copiando $SEMENTE_DB para o volume"
    cp "$SEMENTE_DB" "$DB"
  else
    echo "[entrypoint] banco ausente em $DB e não há cotacoes.db na imagem." >&2
    echo "[entrypoint] monte o volume com o banco ou rode gerar_demo.py antes." >&2
    exit 1
  fi
fi

echo "[entrypoint] aplicando migrações pendentes"
python /app/aplicar_migracoes.py "$DB"

echo "[entrypoint] iniciando: $*"
exec "$@"
