# Production operations

1. Copy `.env.production.example` to a protected `.env` and set real provider,
   PostgreSQL, JWT, and `POSTGRES_PASSWORD` values. Never commit it.
2. Apply the schema with `python scripts/migrate.py` or let the API startup do
   it. Keep database backups with `scripts/backup.ps1` and test restores in a
   separate environment.
3. Start the stack with `docker compose up -d --build`. API requests enqueue
   pipeline jobs; the worker consumes them from PostgreSQL.
4. Monitor `/health` and `/metrics`. Provider errors and failed pipeline jobs
   remain visible in the job status and structured request logs.
5. Restrict `CONCEPTSCAPE_API_ALLOWED_ORIGINS` to the deployed frontend origin.
   Rotate provider credentials in their provider dashboards if they were ever
   exposed; replacing `.env` values alone does not revoke old credentials.
6. Set `CONCEPTSCAPE_REDIS_URL` for distributed rate limiting, connect
   `CONCEPTSCAPE_CLAMAV_HOST` for malware scanning, and set
   `CONCEPTSCAPE_SENTRY_DSN` for error tracking. If unset, the app keeps a
   local rate-limit fallback and reports missing optional integrations in logs.
   Qdrant must be reachable at `CONCEPTSCAPE_QDRANT_URL`; production compose
   disables local Qdrant fallback and exposes the dependency in `/health`.
7. Configure the GitHub `DEPLOY_ENABLED` repository variable and deployment
   secrets (`DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_PATH`) to
   enable the SSH deployment job.
