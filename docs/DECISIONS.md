# Decisions

Status: LOCKED = follow exactly. OPEN = owner must decide; dependent subtasks are GATED. GATE = decided by a named subtask.

## Locked

| ID | Decision | Detail |
|---|---|---|
| D01 | Carrier | Telnyx. One account. Number-to-tenant mapping lives in our Postgres. Behind `TelephonyProvider` interface. No per-client carrier accounts. |
| D02 | Language and tooling | Python 3.12, uv, ruff, mypy strict, pytest, pre-commit, Makefile. |
| D03 | API | FastAPI, asyncio, Pydantic v2, SQLAlchemy 2 async + asyncpg, Alembic. |
| D04 | Data | PostgreSQL with RLS. Redis for rate limits, concurrency counters, job queue. |
| D05 | Jobs | Arq. Not Celery. |
| D06 | FAQ lookup | Postgres full-text search. pgvector only if evals prove FTS insufficient. |
| D07 | LLM | Claude via API behind `LLMProvider`. Defaults from env: live turns `claude-haiku-5-5`, batch QA `claude-sonnet-5-5`. Verify model names against Anthropic docs in subtask 2.1. |
| D08 | Environments | local (compose), staging (own Telnyx number), prod. |
| D09 | Hosting | One US-region VPS, docker compose, Caddy reverse proxy for HTTPS. Staging is a separate VPS. |
| D10 | Postgres hosting | On the VPS at first. Automated off-box backups. Restore tested before first client (subtask 6.1). |
| D11 | Secrets | Doppler or Infisical for environment secrets. Tenant credentials encrypted at app level (AES-GCM), key from secret manager, never in DB. |
| D12 | Existing client number | Conditional forwarding to our number for shadow and after-hours. Port the number only at primary-answering stage. |
| D13 | Owner alerts | Email and web first. SMS to anyone only after 10DLC brand and campaign approval for that client. |
| D14 | SMS compliance | One 10DLC brand and campaign per client. Never share a campaign across clients. Consent row required before any text. |
| D15 | Business hours | Per tenant: IANA `timezone` plus weekly hours in tenant config. `after_hours` is computed once at call start in tenant timezone, stored on the call row, never recomputed. |
| D16 | Recordings | Transcripts always stored. Audio recording off by default, enabled per tenant. Default retention 90 days, set per tenant. |
| D17 | Owner login | Email magic link. No passwords. |
| D18 | Calendar | Google Calendar first, behind `CalendarProvider`. Confirm each client's real tool before onboarding. |
| D19 | Dashboard stack | FastAPI + Jinja templates + one charting library. No separate SPA. Final ADR in subtask 6.2. |
| D20 | Latency target | Set numerically after subtask 4.4 measurements. Log time-to-first-audio on every call from day one. |
| D21 | Voice portability | No LiveKit Inference. Own provider keys through plugins. Server address from env. SIP trunks and dispatch rules created by scripts in `infra/`. |

## Gated by a subtask

| ID | Decision | Decided in | Rule |
|---|---|---|---|
| G01 | Voice framework: Pipecat or LiveKit | 4.1 | Choose LiveKit if browser voice is needed or the spike shows clearly better latency. Otherwise Pipecat. If LiveKit, start on LiveKit Cloud. Record as ADR. Delete the loser. |
| G02 | STT and TTS providers | 4.3 | Test candidates on real English and Spanish calls. Record results. STT starting candidate: Deepgram. |

## OPEN (owner must fill)

| ID | Question | Blocks |
|---|---|---|
| O01 | VPS provider and region (US required) | 0.4 |
| O02 | Domain name for API, widget, dashboard | 0.4, 3.2 |
| O03 | Transactional email provider (Resend, Postmark, or SES) | 3.3, 6.2, 6.3 |
| O04 | Product and brand name | 3.2, 6.2 |
| O05 | First pilot client and its calendar tool | 4.6, 6.4 |
| O06 | Telnyx answers: managed accounts, 10DLC approval time, port-in time | 4.7, 6.4 |
