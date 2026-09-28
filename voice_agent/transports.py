"""Transport adapters. Phase 1 supplies browser WebSockets; Phase 2 can add Twilio here."""

from fastapi import WebSocket
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from voice_agent.config import Settings
from voice_agent.serializers import BrowserPcmSerializer


def create_browser_transport(websocket: WebSocket, settings: Settings) -> FastAPIWebsocketTransport:
    return FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=BrowserPcmSerializer(),
            audio_in_sample_rate=settings.browser_input_sample_rate,
            audio_out_sample_rate=settings.output_sample_rate,
        ),
    )
