# Architecture

## 1. Purpose
Multi-tenant AI receptionist for small service businesses. First vertical: roofing. First channels: web chat, then inbound voice. One deployment serves many clients.

## 2. Context

```
Caller ──PSTN──> Telnyx ──SIP/WebSocket──> voice_transport ─┐
Visitor ──browser──> widget ──WebSocket──> api/chat_gateway ─┤
                                                             v
                                                    agent_runtime (one per call/chat)
                                                     │  loads flow + tenant config
                                                     │  calls tools, enforces guardrails
                                   ┌─────────────────┼──────────────────┐
                                   v                 v                  v
                              pipeline (STT/    integrations      analytics
                              LLM/TTS)          (calendar, SMS,   (call log, QA,
                                                 email)            metric views)
                                   └─────────────────┴──────────────────┘
                                                     v
                                      PostgreSQL (RLS)  +  Redis
Owner ──browser──> dashboard (reads metric views, RLS-scoped)
```

## 3. Repository layout

```
voice-platform/
├── .github/
│   ├── copilot-instructions.md
│   ├── instructions/            # path-specific Copilot rules
│   └── workflows/               # CI, deploy (created in 0.3, 0.4)
├── docs/
│   ├── ARCHITECTURE.md  DECISIONS.md  TASKS.md  schema.md
│   ├── adr/                     # one file per design decision
│   └── runbooks/                # per-client and incident runbooks
├── src/voiceplatform/
│   ├── core/
│   │   ├── tenancy/             # db session + tenant context, resolver, config loader/merge
│   │   ├── telephony/           # TelephonyProvider + telnyx adapter
│   │   ├── voice_transport/     # the ONLY place that imports LiveKit/Pipecat
│   │   ├── pipeline/            # STTProvider, TTSProvider, LLMProvider + adapters + fakes
│   │   ├── agent_runtime/       # flow engine, slots, guardrails, tool dispatch, disclosure
│   │   ├── integrations/        # CalendarProvider, SmsProvider, EmailProvider + fakes
│   │   ├── analytics/           # call logging, QA scoring, metric views
│   │   ├── billing/             # usage metering, caps
│   │   ├── errors.py  settings.py  logging.py
│   ├── api/                     # FastAPI: chat gateway, webhooks, owner dashboard, health
│   └── workers/                 # Arq jobs: QA scoring, reports, retries
├── verticals/roofing/           # flow.yaml, prompts/, tools.yaml, kb_seed/
├── tenants/                     # <slug>/tenant.yaml (no secrets)
├── widget/                      # embeddable chat widget (static JS)
├── migrations/                  # Alembic
├── infra/                       # voice transport + Telnyx setup scripts (idempotent)
├── deploy/                      # Dockerfile, compose.dev.yml, compose.prod.yml, Caddyfile
├── scripts/                     # healthcheck, env check, seed
├── tests/                       # unit/, integration/, isolation/, scenarios/
├── Makefile  pyproject.toml  .env.example  .pre-commit-config.yaml  README.md
```

## 4. Tenancy and isolation
- One database. Every tenant-owned table has `tenant_id` and forced RLS.
- Roles: `migrator` (owns schema), `app_user` (runtime, no BYPASSRLS).
- Each transaction runs `SET LOCAL app.tenant_id = '<uuid>'`. Policy: `tenant_id = current_setting('app.tenant_id', true)::uuid`. No context means zero rows.
- Tenant is unknown at the start of a call or chat. Resolution uses `SECURITY DEFINER` functions (`resolve_tenant_by_number`, `resolve_tenant_by_site_key`) that return only a tenant id. After that the session sets context.
- Isolation test discovers tables from `information_schema` and proves tenant A cannot SELECT, UPDATE, or DELETE tenant B rows. It runs in CI.

## 5. Config model
`core defaults` -> `verticals/<vertical>/` -> `tenants/<slug>/tenant.yaml`. Later layers override earlier. Pydantic validates the merged result. Invalid config fails at load, never mid-call. Config holds no secrets. Per-tenant credentials are stored encrypted in the database.

## 6. Call flow (voice)
1. Telnyx delivers the call. `voice_transport` receives audio and the dialed number.
2. Resolve tenant from the dialed number. If kill switch is on, or tenant unknown, route to the fallback number.
3. Compute `after_hours`. Open a `calls` row. Create the agent runtime with channel `voice`.
4. Speak the disclosure. Run the flow: STT -> LLM -> tools -> TTS, streaming.
5. Tools write leads and appointments through RLS-scoped sessions. Every tool call is a `call_events` row.
6. On end: close the call row, enqueue QA scoring and owner notification.

## 7. Chat flow
Widget connects with a public site key. Gateway checks site key and Origin, rate limits (Redis), enforces caps, opens a session on the same runtime with channel `web_chat`.

## 8. Failure modes
| Failure | Required behavior |
|---|---|
| Our service is down | Carrier-level fallback forwards to owner phone or voicemail. |
| Kill switch on | Calls go straight to a human. |
| Calendar API down | Agent takes a callback request. Lead still saved. |
| LLM timeout | One retry, then apologize and take a callback request. |
| Transfer not answered | Take a message, alert owner. |
| Tenant at spend or concurrency cap | Graceful message, owner alert, call routed to human. |
| Webhook delivered twice | Idempotent. No duplicate lead, booking, or text. |

## 9. Deployment topology
Single VPS per environment: Caddy (HTTPS) -> api, worker, Postgres, Redis, all in docker compose. Images: `api`, `worker`. Workers are stateless; add containers to add capacity. Per-tenant concurrency caps live in Redis.

## 10. Observability
structlog JSON with `tenant_id`, `call_id`. Sentry for errors. Langfuse for LLM traces and prompt versions. Metrics per call: time-to-first-audio, tool errors, cost. Alerts: outage, error spike, tenant at 80% of cap.

## 11. Portability rules
Vendor code stays in adapters. Voice framework stays in `voice_transport/`. Server address and keys come from env. Infra setup is scripted in `infra/`, never clicked. Moving from LiveKit Cloud to self-hosted, or Telnyx to another carrier, changes one module and config.

## 12. Out of scope until later
Outbound calling, price quotes, claim negotiation, payments, multi-location routing, CRM sync, multiple live agents, voice cloning.
