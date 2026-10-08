# Voice Platform

Multi-tenant AI receptionist framework for small service businesses. First vertical: roofing. Channels: web chat, inbound voice.

## Read first
- `docs/ARCHITECTURE.md`: how it fits together
- `docs/DECISIONS.md`: what is locked, gated, or open
- `docs/TASKS.md`: what to build next and how to prove it is done

## Repo map
See `docs/ARCHITECTURE.md` section 3.

## Setup (after subtask 0.2)
```
git clone <repo> && cd voice-platform
cp .env.example .env
make setup
make up
make migrate
make check
```

## Build workflow with GitHub Copilot (Agent mode, Sonnet)
1. Open the repo in VS Code. Copilot reads `.github/copilot-instructions.md` automatically.
2. Fill the OPEN items in `docs/DECISIONS.md` that block your next subtask.
3. Open a new chat in Agent mode. Paste:

```
Read docs/DECISIONS.md, docs/TASKS.md and docs/ARCHITECTURE.md.
Do subtask <ID> only. Branch task/<ID>.
First list the files you will create or change and the Done checks. Wait for my OK.
Then implement, run every Done command, and paste the real output.
```

4. Review the diff. Run the Done commands yourself. Open a pull request. Merge only when CI is green.
5. Start a new chat for the next subtask. Copilot does not remember the gate between chats, so you enforce it.
