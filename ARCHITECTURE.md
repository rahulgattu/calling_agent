# Voice agent architecture

## Phase 1: browser loopback

The browser captures microphone audio, resamples it to mono 16 kHz PCM16, and sends binary frames over a local WebSocket. The browser transport deserializes those frames and streams them to Deepgram for speech recognition. The transcript enters the conversation context, Groq generates a response, and Cartesia streams synthesized PCM audio back through the WebSocket. The browser plays the returned audio through the laptop speakers.

The `end_call` function tool ends the Pipecat worker after the assistant has delivered its goodbye. The local browser transport then closes its WebSocket as the pipeline shuts down.

### Test from a phone browser before Twilio

You can test the phone's microphone and speaker without Twilio by opening the browser tester through an HTTPS development tunnel. Phone browsers require a secure context for microphone access, and the page automatically selects `wss://` when opened over HTTPS.

1. Start the app on the laptop with `python server.py`.
2. In a second PowerShell window, run `cloudflared tunnel --url http://localhost:8000` (install `cloudflared` first if needed).
3. Open the generated `https://…trycloudflare.com` address on the phone and press **Connect**.

Keep both laptop processes running during the test. This uses the phone's web browser; calling the server from the native phone dialer still requires a telephony gateway such as Twilio. Cloudflare describes Quick Tunnels as a development/testing option and supports WebSocket connections. [Quick Tunnel instructions](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/), [WebSocket support](https://developers.cloudflare.com/network/websockets/).

## Code layout

- `server.py` is the local Uvicorn entry point.
- `voice_agent/app.py` owns the FastAPI routes and WebSocket session boundary.
- `voice_agent/config.py` loads and validates provider credentials and audio/model settings.
- `voice_agent/serializers.py` defines the browser PCM wire format.
- `voice_agent/transports.py` creates the browser transport and the Twilio Media Streams transport.
- `voice_agent/telephony.py` builds the Twilio TwiML webhook response, validates the webhook signature, and issues one-time Media Stream tokens.
- `voice_agent/pipeline.py` wires STT, LLM, TTS, turn handling, and graceful hangup. It is shared by transports.
- `voice_agent/prompts.py` holds the agent's opening and system instructions.
- `principal_context.md` is the separate, editable school information file loaded into the principal's prompt.
- `index.html` contains the browser tester markup; `static/app.js` handles microphone capture, WebSocket audio, and playback.

Configure `GROQ_API_KEY`, `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`, and `CARTESIA_VOICE_ID` in the project `.env`. The editable `principal_context.md` file supplies school facts to the principal prompt; add approved facts there, and the agent is instructed not to invent missing details. The default Groq model is `openai/gpt-oss-120b`; set `GROQ_MODEL` to select another model supported by the account.

Cloudflare Tunnel can forward the existing `/` page and `/ws` WebSocket to the local FastAPI server. No separate Cloudflare Worker or receiver service is needed for phone-browser testing. This is different from receiving an ordinary cellular call: that needs a phone/SIP provider such as Twilio or another telephony gateway.

## Phase 2: Twilio phone calls

Phase 2 adds a Twilio Media Streams WebSocket endpoint and a Twilio audio serializer/transport adapter. That adapter translates Twilio's call and audio events into the same pipeline input/output interface, leaving the Deepgram, Groq, Cartesia, prompts, and hangup logic reusable. The browser transport remains available for local development.

### Inbound call flow

1. Twilio receives a call on your Twilio phone number and sends an HTTP `POST` to `/twilio/voice` (configured as that number's Voice webhook in the Twilio console).
2. `voice_agent/telephony.py` validates the request's `X-Twilio-Signature` against `TWILIO_AUTH_TOKEN` (skipped with a warning if that variable is unset, so local testing without a token still works), then returns TwiML with a `<Connect><Stream>` pointing at `wss://<host>/twilio/ws/<one-time-token>`.
3. Twilio opens that WebSocket and streams 8 kHz μ-law audio. `voice_agent/app.py` checks the one-time token (rejecting replays or guesses), calls `pipecat.runner.utils.parse_telephony_websocket` to read Twilio's `start` handshake, and builds a `TwilioFrameSerializer` transport via `voice_agent.transports.create_twilio_transport`.
4. The same `run_conversation` pipeline used for the browser tester runs the call, with `audio_in_sample_rate` set to 8 kHz to match Twilio's wire format. The `end_call` tool now also triggers Twilio's own call-hangup (via `TwilioFrameSerializer`'s `auto_hang_up`, which needs `TWILIO_ACCOUNT_SID`/`TWILIO_AUTH_TOKEN`).

Configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_PHONE_NUMBER` in `.env`. Twilio must reach a public HTTPS/WSS endpoint; for local development, forward the same tunnel already documented above (e.g. Cloudflare Tunnel) and set the phone number's Voice webhook to `https://<tunnel-host>/twilio/voice`.

### Outbound calls (planned)

Outbound calls will use the Twilio REST API (`Calls.create`) to dial a number and point it at the same `/twilio/voice` TwiML webhook, reusing the inbound pipeline once the call connects. This is not yet implemented.

The Phase 2 implementation needs the call direction (inbound, outbound, or both), a Twilio phone number/account, and a public HTTPS/WSS endpoint reachable by Twilio. Twilio credentials should be stored in `.env`; keep them out of source control. For local development, the public endpoint can be supplied through a secure tunnel. The Twilio stream format is typically 8 kHz μ-law, so the new adapter handles its conversion separately from the browser's PCM16 format.
