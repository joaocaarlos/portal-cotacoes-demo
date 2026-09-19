#!/usr/bin/env bash
# Backup consistente do SQLite. Usa a API de backup do próprio SQLite, que copia
# o banco com o processo rodando — `cp` durante uma escrita geraria arquivo corrompido.
#
#   ./backup.sh                       # backups/cotacoes-AAAAMMDD-HHMM.db
#   ./backup.sh /destino              # outro destino
#   No Docker: docker compose exec portal /app/backup.sh /backups
#
# Agende no cron do host:  0 2 * * *  cd /opt/portal && ./backup.sh >> backup.log 2>&1
set -euo pipefail

DB="${DB_PATH:-cotacoes.db}"
DESTINO="${1:-backups}"
MANTER="${MANTER_DIAS:-30}"

[ -f "$DB" ] || { echo "banco não encontrado: $DB" >&2; exit 1; }
mkdir -p "$DESTINO"

ARQ="$DESTINO/cotacoes-$(date +%Y%m%d-%H%M).db"

python3 - "$DB" "$ARQ" <<'PY'
import sqlite3, sys
origem, destino = sys.argv[1], sys.argv[2]
com, dest = sqlite3.connect(origem), sqlite3.connect(destino)
with dest:
    com.backup(dest)            # consistente mesmo com escrita concorrente
dest.close(); com.close()
PY

gzip -f "$ARQ"
echo "backup: ${ARQ}.gz  ($(du -h "${ARQ}.gz" | cut -f1))"

# Retenção
find "$DESTINO" -name 'cotacoes-*.db.gz' -mtime "+$MANTER" -print -delete
