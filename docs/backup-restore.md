# Restore check (monthly)

1. Pick latest `backups/kz_ai_*.sql.gz`.
2. Spin a throwaway Postgres: `docker run --rm -e POSTGRES_PASSWORD=tmp -e POSTGRES_DB=kz_ai -p 55432:5432 postgres:15-alpine`
3. Restore: `gunzip -c backups/….sql.gz | psql postgresql://postgres:tmp@localhost:55432/kz_ai`
4. Spot-check: `\dt`, count counterparties, sample report query.
5. Record date in ops log / `docs/uat-results.md`.
