# Changelog

This file records user-visible features and project updates. Newest entries go first.

## 2026-09-28

- Added `principal_context.md` as a separate, editable source of school-specific information for the principal prompt, populated from the school's public website.
- Updated prompt configuration to load `principal_context.md` at session startup.
- Updated `.env.example` to point to the school context file and keep credentials out of the template.
- Documented Cloudflare Tunnel as a way to reach the existing browser and WebSocket endpoints for phone-browser testing. Cloudflare Tunnel does not provide a cellular dial-in number.
- Split browser JavaScript into `static/app.js`; FastAPI serves it under `/static`.
- Modularized the Phase 1 application into configuration, prompts, provider/pipeline assembly, serializer, transport, and FastAPI modules.
- Preserved the browser microphone and speaker tester using Deepgram, Groq, and Cartesia.
