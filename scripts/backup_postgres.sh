#!/usr/bin/env bash
# Daily full PostgreSQL backup for Jewelry AI Analytics.
# Cron example (host): 15 2 * * * /opt/kz_ai/scripts/backup_postgres.sh
set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/kz_ai_${STAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "Backing up to ${OUT}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=plain' | gzip > "${OUT}"

find "${BACKUP_DIR}" -name 'kz_ai_*.sql.gz' -mtime +"${RETENTION_DAYS}" -delete

echo "Done. Sample restore:"
echo "  gunzip -c ${OUT} | docker compose -f ${COMPOSE_FILE} --env-file ${ENV_FILE} exec -T postgres psql -U \$POSTGRES_USER -d \$POSTGRES_DB"
