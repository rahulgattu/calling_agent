---
applyTo: "tests/**"
---
- Use pytest and pytest-asyncio. Name tests `test_<behavior>_<condition>`.
- Unit tests use fake providers. Integration tests use the docker-compose Postgres and Redis.
- The isolation test discovers tenant tables from `information_schema`. Never hardcode the table list.
- Scenario tests live in `tests/scenarios/*.yaml`. One scenario = one file. Include expected tool calls and forbidden phrases.
- No sleeps for synchronization. Use events or polling with a timeout.
- A skipped or flaky test is a failing test. Fix or delete it.
