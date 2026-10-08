"""Transport adapters. Phase 1 supplies browser WebSockets; Phase 2 adds Twilio."""

from fastapi import WebSocket
from pipecat.serializers.twilio import TwilioFrameSerializer
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


def create_twilio_transport(
    websocket: WebSocket, settings: Settings, call_data
) -> FastAPIWebsocketTransport:
    """Build the transport for one Twilio Media Streams call.

    ``call_data`` comes from ``pipecat.runner.utils.parse_telephony_websocket``
    and carries the stream/call SIDs Twilio sent in its handshake.
    """
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        raise ValueError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN are required for phone calls")

    serializer = TwilioFrameSerializer(
        stream_sid=call_data["stream_id"],
        call_sid=call_data["call_id"],
        account_sid=settings.twilio_account_sid,
        auth_token=settings.twilio_auth_token,
    )
    return FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
            audio_in_sample_rate=settings.telephony_sample_rate,
            audio_out_sample_rate=settings.output_sample_rate,
        ),
    )

