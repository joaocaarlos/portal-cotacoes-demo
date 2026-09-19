#!/bin/sh
# Prepara o banco e só então entrega o processo ao servidor WSGI.
set -e

DB="${DB_PATH:-/dados/demo.db}"
PORTA="${PORT:-8000}"

# Alguns hospedadores (Render, Koyeb, Hugging Face Spaces) montam o diretório de
# trabalho por conta própria e definem a porta em tempo de execução. Por isso o
# diretório é criado aqui e a porta sai de $PORT, não de um valor fixo na imagem.
mkdir -p "$(dirname "$DB")" 2>/dev/null || true

if [ ! -f "$DB" ]; then
  SEMENTE_DB=""
  for candidato in /app/cotacoes.db /app/demo.db; do
    [ -f "$candidato" ] && SEMENTE_DB="$candidato" && break
  done
  if [ -n "$SEMENTE_DB" ]; then
    echo "[entrypoint] primeira subida: copiando $SEMENTE_DB para $DB"
    cp "$SEMENTE_DB" "$DB"
  else
    echo "[entrypoint] banco ausente em $DB e não há banco na imagem." >&2
    echo "[entrypoint] monte o volume com o banco ou rode gerar_demo.py antes." >&2
    exit 1
  fi
fi

echo "[entrypoint] aplicando migrações pendentes"
python /app/aplicar_migracoes.py "$DB"

# Sem argumentos: sobe o gunicorn na porta do ambiente. Com argumentos, executa
# o que veio (usado pelo compose e para rodar comandos avulsos no contêiner).
if [ "$#" -eq 0 ]; then
  echo "[entrypoint] gunicorn em 0.0.0.0:$PORTA"
  exec gunicorn --workers "${WEB_WORKERS:-2}" --threads "${WEB_THREADS:-4}" \
       --timeout 120 --access-logfile - --error-logfile - \
       --bind "0.0.0.0:$PORTA" app:app
fi

echo "[entrypoint] iniciando: $*"
exec "$@"
