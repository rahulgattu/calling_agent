---
applyTo: "migrations/**"
---
- Use Alembic. One change per migration. Every migration has a working `downgrade`.
- New tenant-owned table checklist: `tenant_id uuid NOT NULL REFERENCES tenants(id)`, index on `tenant_id`, `ENABLE` and `FORCE ROW LEVEL SECURITY`, a policy using `current_setting('app.tenant_id', true)::uuid`, grants to `app_user`.
- Never grant `app_user` more than SELECT, INSERT, UPDATE (DELETE only where the task says so).
- Add columns as nullable or with a default. Backfill in a separate migration.
- Never edit a migration that has been merged. Add a new one.
