# Changelog

This file records user-visible features and project updates. Newest entries go first.

## 2026-09-28 (Phase 2, inbound Twilio calls)

- Added `POST /twilio/voice` webhook that validates the Twilio request signature and returns TwiML connecting the call to a Media Stream.
- Added `WebSocket /twilio/ws/{token}` endpoint using a one-time token (minted per call) to prevent stream URL replay/guessing.
- Added `voice_agent/telephony.py` for TwiML generation, signature validation, and stream tokens.
- Added `create_twilio_transport` in `voice_agent/transports.py` using Pipecat's `TwilioFrameSerializer` (8 kHz μ-law).
- Made `run_conversation` accept an explicit input sample rate so the same pipeline serves both the 16 kHz browser tester and 8 kHz Twilio calls.
- Added `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` to configuration and `.env.example`; added the `twilio` package to `requirements.txt` for webhook signature validation.

## 2026-09-28

- Added `principal_context.md` as a separate, editable source of school-specific information for the principal prompt, populated from the school's public website.
- Updated prompt configuration to load `principal_context.md` at session startup.
- Updated `.env.example` to point to the school context file and keep credentials out of the template.
- Documented Cloudflare Tunnel as a way to reach the existing browser and WebSocket endpoints for phone-browser testing. Cloudflare Tunnel does not provide a cellular dial-in number.
- Split browser JavaScript into `static/app.js`; FastAPI serves it under `/static`.
- Modularized the Phase 1 application into configuration, prompts, provider/pipeline assembly, serializer, transport, and FastAPI modules.
- Preserved the browser microphone and speaker tester using Deepgram, Groq, and Cartesia.
