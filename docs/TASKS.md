# Tasks

Rules: do one subtask at a time, in order. A subtask is Done only when every check passes with real command output. GATED subtasks need the named decision closed in `docs/DECISIONS.md`.

Standard commands (created in 0.1): `make setup`, `make check` (ruff check, ruff format --check, mypy --strict src, pytest -q), `make test`, `make up`, `make down`, `make migrate`, `make eval`.

---
## Phase 0: Foundation

### 0.1 Scaffold and tooling
Create: folder tree from ARCHITECTURE section 3 (empty packages with `__init__.py`), `pyproject.toml`, `Makefile`, `.pre-commit-config.yaml`, `.gitignore`, `.env.example`, one smoke test.
Done:
- [ ] `make setup && make check` exits 0 on a clean clone.
- [ ] `pre-commit run --all-files` exits 0.
- [ ] `git ls-files | grep -E "(^|/)\.env$"` prints nothing.
- [ ] Folder tree matches ARCHITECTURE section 3.

### 0.2 Local environment
Create: `deploy/compose.dev.yml` (Postgres with pgvector image, Redis), `src/voiceplatform/core/settings.py` (Pydantic settings), `scripts/healthcheck.py`, `scripts/check_env_example.py`.
Done:
- [ ] `make up` brings Postgres and Redis to healthy within 60 seconds.
- [ ] `python scripts/healthcheck.py` exits 0 and prints `db ok` and `redis ok`.
- [ ] `python scripts/check_env_example.py` exits 0 (every settings field appears in `.env.example`).
- [ ] README setup section is 10 commands or fewer.

### 0.3 CI
Create: `.github/workflows/ci.yml`.
Done:
- [ ] On push and PR, CI runs `make check`.
- [ ] CI runs `alembic upgrade head`, `downgrade base`, `upgrade head` against service containers.
- [ ] A deliberately failing test on a throwaway branch turns CI red. Link the run. Delete the branch.

### 0.4 Deploy skeleton (GATED: O01, O02)
Create: `deploy/Dockerfile` (multi-stage, non-root), `deploy/compose.prod.yml` (api, worker, caddy, postgres, redis), `deploy/Caddyfile`, `GET /healthz`, `GET /readyz`, `.github/workflows/deploy-staging.yml` (manual trigger, SSH deploy), `docs/runbooks/deploy.md`.
Done:
- [ ] `docker build` succeeds. Image runs as non-root (`docker run --rm IMAGE id -u` is not 0).
- [ ] `curl -s https://STAGING_DOMAIN/readyz` returns HTTP 200 and JSON with `db: ok`, `redis: ok`.
- [ ] Rollback to the previous image tag is documented and was executed once on staging.

---
## Phase 1: Data and tenancy

### 1.1 Schema and migrations
Tables: `tenants`, `phone_numbers`, `site_keys`, `calls`, `call_events`, `leads`, `appointments`, `consents`, `usage_records`, `kb_documents`.
Fields that must exist:
- `tenants`: id, slug (unique), name, vertical, timezone, business_hours (jsonb), status, kill_switch (bool), fallback_number, created_at.
- `phone_numbers`: id, tenant_id, e164 (unique), provider, provider_ref, role.
- `site_keys`: id, tenant_id, public_key (unique), allowed_origins (text[]).
- `calls`: id, tenant_id, channel, started_at, ended_at, duration_s, call_type, outcome, after_hours, lead_id, qa_score, prompt_version, time_to_first_audio_ms.
- `call_events`: id, tenant_id, call_id, seq, type, payload (jsonb), ts.
- `leads`: id, tenant_id, call_id, name, phone_e164, address, issue, urgency, roof_info, insurance_claim, preferred_window, referral_source, status, storm (bool), est_value_cents.
- `appointments`: id, tenant_id, lead_id, starts_at, ends_at, external_ref, status.
- `consents`: id, tenant_id, phone_e164, channel, scope, granted_at, evidence (jsonb), revoked_at.
- `usage_records`: id, tenant_id, call_id, kind, units, cost_micros, ts.
- `kb_documents`: id, tenant_id, title, content, search_vector (tsvector).
Done:
- [ ] `make migrate`, then `alembic downgrade base`, then `make migrate` all exit 0.
- [ ] Test proves every table except `tenants` has `tenant_id NOT NULL`, a foreign key, and an index on it.
- [ ] `docs/schema.md` lists every table and its purpose.

### 1.2 Row-level security and isolation proof
Create: roles `migrator`, `app_user`; RLS policies; `core/tenancy/db.py` (session helper that runs `SET LOCAL app.tenant_id`); `tests/isolation/`.
Done:
- [ ] `SELECT relrowsecurity, relforcerowsecurity FROM pg_class` shows both true for every tenant-owned table (test asserts it).
- [ ] `app_user` is not superuser and has no BYPASSRLS (test asserts it).
- [ ] With tenants A and B seeded, A cannot SELECT, UPDATE, or DELETE B rows in any tenant-owned table. Tables are discovered from `information_schema`.
- [ ] A session with no tenant context returns zero rows from every tenant-owned table.
- [ ] The isolation tests run in CI.

### 1.3 Config system
Create: `core/tenancy/config.py` (Pydantic models, loader, merge), `verticals/roofing/` stubs, `tenants/example_roofing/tenant.yaml`, `tenants/example_hvac/tenant.yaml`.
Done:
- [ ] Merge order core, vertical, tenant is unit-tested including override precedence.
- [ ] An invalid YAML (wrong type, unknown field, missing required key) fails at load with a message naming the file and field.
- [ ] Adding `example_hvac` required only YAML files. `git diff --stat` shows no `src/` change for it.
- [ ] Business-hours helper returns correct `after_hours` for tests covering midnight, a closed day, and a DST change.

### 1.4 Tenant resolver and context
Create: SQL functions `resolve_tenant_by_number`, `resolve_tenant_by_site_key` (`SECURITY DEFINER`, return tenant id only), `core/tenancy/resolver.py`.
Done:
- [ ] Known number and known site key resolve to the right tenant. Unknown returns a typed `UnknownTenant` result, never an exception that ends the call.
- [ ] Site key with a disallowed Origin is rejected (test).
- [ ] Unknown tenant is logged with a warning and routes to the configured default fallback.
- [ ] `app_user` cannot read `phone_numbers` or `site_keys` directly without tenant context (test).

---
## Phase 2: Agent runtime (text channel only)

### 2.1 Provider interfaces and LLM adapter
Create: `LLMProvider` interface, Claude adapter with streaming, `FakeLLMProvider`, cost accounting.
Done:
- [ ] Model names come from settings. Names were checked against Anthropic docs; link recorded in an ADR.
- [ ] Timeout, 1 retry with backoff, and token and cost accounting are covered by unit tests using the fake.
- [ ] `make test` passes with no network access.

### 2.2 Flow engine and roofing flow
Create: `verticals/roofing/flow.yaml`, `verticals/roofing/prompts/` (versioned files), `core/agent_runtime/` (flow loader, slot tracker, call-type detection).
Call types: new_inspection, storm_damage, emergency_leak, insurance_question, job_status, general_faq, vendor_spam, human_request.
Slots: name, callback number (read back), address (read back), issue, urgency, roof info, insurance claim, preferred window, referral source.
Done:
- [ ] Unit tests cover slot filling, read-back confirmation, and unknown intent.
- [ ] Every prompt file has a version id, and the version is stored on the call row.
- [ ] Emergency flow collects only name, address, number.

### 2.3 Tools with fake integrations
Create: `check_availability`, `book_inspection`, `create_lead`, `send_sms`, `notify_owner`, `transfer_call`, `lookup_faq` against interfaces, with in-memory fakes.
Done:
- [ ] Every tool call is validated, tenant-scoped, and written to `call_events`.
- [ ] Calendar failure produces a callback request. The lead is still saved (test).
- [ ] `create_lead` saves a partial lead when the session drops (test).
- [ ] `send_sms` refuses without a consent row (test).
- [ ] `lookup_faq` uses Postgres full-text search and returns nothing for unknown topics (test).

### 2.4 Guardrails and CLI
Create: guardrail layer, `python -m voiceplatform.cli chat --tenant SLUG`.
Done:
- [ ] Disclosure is the first message every session (test).
- [ ] One automated test each for: price request, insurance promise, prompt injection, off-topic, anger, emergency, safety advice.
- [ ] All guardrail tests pass. None skipped.

### 2.5 Scenario evaluation suite
Create: 25 to 30 files in `tests/scenarios/`, `make eval`.
Must cover: every call type, Spanish switch, refused address, silence, dropped session, repeat caller, full calendar, and each guardrail.
Done:
- [ ] `make eval` prints pass or fail per scenario and a summary.
- [ ] Guardrail scenarios pass 100 percent. Overall passes at least 90 percent. Result recorded in `docs/adr/`.
- [ ] README states: run `make eval` before any prompt change.

---
## Phase 3: Web chat channel

### 3.1 Chat gateway
Create: WebSocket endpoint, Origin check, Redis rate limits (per IP and per tenant), monthly conversation cap, message length and token limits, bot-challenge hook.
Done:
- [ ] Integration tests pass for: allowed origin, blocked origin, rate limit hit, cap reached, oversized message, malformed JSON.
- [ ] Cap reached returns a polite message and creates an owner alert. No exception reaches the client.

### 3.2 Widget (GATED: O02, O04)
Create: `widget/widget.js` served by the api, one `<script data-site-key>` embed.
Done:
- [ ] Works on a plain HTML test page and on one WordPress or Wix test page.
- [ ] Shows AI disclosure and a privacy link. Usable at 360 px width.
- [ ] Script is under 30 KB gzipped and loads async.

### 3.3 Lead delivery and consent (GATED: O03)
Create: `EmailProvider` interface plus adapter, owner notification job, consent capture in the widget, retention and deletion job.
Done:
- [ ] A captured lead sends the owner an email with a readable summary within 60 seconds (test with the fake, then once for real on staging).
- [ ] A consent row is stored only after an explicit opt-in.
- [ ] Deleting a lead's data removes its transcripts and consents (test).

---
## Phase 4: Voice channel

### 4.1 Spike and framework decision (closes G01)
Create: throwaway spike code, `docs/adr/0001-voice-framework.md`, `infra/` setup scripts for the winner.
Done:
- [ ] Both candidates complete 20 scripted inbound calls from a Telnyx test number. Results table in the ADR: time-to-first-audio median and p95, failures, setup effort.
- [ ] ADR states the choice using rule G01. Losing code is deleted.
- [ ] Telnyx trunk and dispatch setup is one idempotent script run twice with no error.

### 4.2 Telephony adapter and inbound calls
Create: `TelephonyProvider` + Telnyx adapter, `core/voice_transport/`, call row creation, disclosure spoken first.
Done:
- [ ] A real call to the staging number reaches the runtime. Tenant resolved from the dialed number.
- [ ] `calls` and `call_events` rows match the chat schema.
- [ ] Duplicate webhook delivery creates no duplicate rows (test).

### 4.3 STT and TTS adapters (closes G02)
Create: `STTProvider`, `TTSProvider`, adapters, selection by tenant config.
Done:
- [ ] Each candidate tested on 10 English and 10 Spanish recorded calls. Scores and notes in an ADR.
- [ ] Provider chosen per language in config only.

### 4.4 Latency measurement
Create: timing around every turn; fields on `calls` and `call_events`.
Done:
- [ ] Every call stores time-to-first-audio.
- [ ] A query reports median and p95 over the last 50 calls.
- [ ] D20 target is written into `docs/DECISIONS.md` by the owner, based on the numbers.
- [ ] Barge-in, silence, and noisy-audio behavior tested with recordings and documented in `docs/runbooks/voice-quality.md`.

### 4.5 Failover, kill switch, caps
Create: Telnyx fallback routing, kill switch, concurrency and spend caps in Redis, transfer-to-human with fallback to message-taking.
Done:
- [ ] With the api stopped, a call to the staging number reaches the fallback phone or voicemail.
- [ ] Setting `kill_switch` routes the next call to a human within 5 seconds.
- [ ] A transfer that is not answered takes a message and alerts the owner.
- [ ] Concurrency cap and spend cap each block the next call gracefully (tests).

### 4.6 Google Calendar adapter (GATED: O05)
Create: `CalendarProvider` Google adapter, per-tenant encrypted credentials.
Done:
- [ ] Reads availability, books, and handles API errors (tests with recorded responses).
- [ ] Credentials are encrypted at rest and appear in no log (test greps captured logs).
- [ ] End to end on staging: a real call books a real calendar slot.

### 4.7 SMS adapter (GATED: O06, client 10DLC approval)
Create: `SmsProvider` Telnyx adapter, brand and campaign registration script per client.
Done:
- [ ] Registration script creates one brand and one campaign for a test tenant. Status recorded.
- [ ] Message sends only after approval and only with a consent row.
- [ ] A reply of STOP creates a revoked consent and blocks further texts (test).

---
## Phase 5: Analytics and cost

### 5.1 Call logging and QA scoring
Create: Arq job scoring each finished call (lead captured, booked, guardrail violation, hallucination suspicion), review queue command.
Done:
- [ ] Every finished call has a QA row within 2 minutes (test).
- [ ] `python -m voiceplatform.cli review --tenant SLUG` lists flagged calls.

### 5.2 Owner metric views
Create: SQL views: calls_answered, leads_captured, inspections_booked, after_hours_caught, booking_rate, call_type_mix, calls_per_day, estimated_pipeline_value.
Done:
- [ ] Each view returns correct values on a seeded dataset with hand-computed expectations.
- [ ] Views respect RLS (isolation test extended to them).

### 5.3 Cost metering
Create: usage recording for STT, LLM, TTS, telephony; cost queries.
Done:
- [ ] A query returns cost per call, cost per tenant per month, and margin versus configured price.
- [ ] A tenant at 80 percent of its cap triggers one owner-visible alert (test).

---
## Phase 6: Ship per client

### 6.1 Backups, restore, alerting
Create: nightly encrypted backup to off-box storage, `docs/runbooks/restore.md`, Sentry and uptime alerts.
Done:
- [ ] A restore from last night's backup into a fresh database was performed and row counts match. Output pasted.
- [ ] Stopping the api produces an alert to the owner's phone within 5 minutes.

### 6.2 Owner dashboard (GATED: O03, O04)
Create: magic-link login, dashboard reading the 5.2 views, editable job value and close rate.
Done:
- [ ] An owner sees only their tenant's data (isolation test extended to the dashboard routes).
- [ ] Magic link expires in 15 minutes and works once (tests).
- [ ] Usable at 360 px width. No raw technical terms in the UI.
- [ ] ADR confirms D19 or records the change.

### 6.3 Weekly impact report (GATED: O03)
Done:
- [ ] A scheduled job emails each tenant a weekly summary in the tenant's timezone.
- [ ] Delivery is logged. Failure retries 3 times, then alerts the operator.

### 6.4 Client rollout kit (GATED: O05, O06)
Create: `docs/runbooks/client-onboarding.md` (shadow, after-hours, overflow, primary stages with exit criteria), per-client runbook template, one-page service agreement draft for lawyer review.
Done:
- [ ] First client onboarded by adding a tenant YAML, a number, and credentials only. No code change.
- [ ] Runbook states how to disable the agent, who to call, and where logs are.
