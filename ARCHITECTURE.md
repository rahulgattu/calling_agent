# Phase 1 voice agent

The browser captures microphone audio, resamples it to mono 16 kHz PCM16, and sends short binary audio frames over a local WebSocket. Pipecat's `FastAPIWebsocketTransport` passes those frames to Deepgram for streaming speech recognition. The recognized utterance enters the conversation context, Groq generates a response, and Cartesia streams synthesized speech back through the transport. The browser plays the returned PCM audio through the laptop speakers. The default Groq model is `openai/gpt-oss-120b`; set `GROQ_MODEL` to select another model supported by your account.

The WebSocket transport is for local browser testing in Phase 1. In Phase 2, replace that transport and its audio serializer with a Twilio transport/serializer; the STT, LLM, TTS, and conversation pipeline can remain modular.

Configure `GROQ_API_KEY`, `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`, and `CARTESIA_VOICE_ID` in `.env` before starting the server.
