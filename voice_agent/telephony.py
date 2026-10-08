"""Twilio webhook helpers: TwiML generation, signature checks, and stream tokens."""

import logging
import secrets

from fastapi import Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator

from voice_agent.config import Settings

logger = logging.getLogger(__name__)

# One-time tokens minted per inbound call and consumed when the matching Media
# Streams WebSocket connects, so a stream URL can't be replayed or guessed.
pending_stream_tokens: set[str] = set()


def _public_url(request: Request) -> str:
    """Reconstruct the externally visible URL, honoring a reverse proxy/tunnel."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.hostname or "")
    return f"{scheme}://{host}{request.url.path}"


def _public_host(request: Request) -> str:
    return request.headers.get("host", request.url.hostname or "")


async def verify_twilio_request(request: Request, settings: Settings) -> bool:
    """Validate the X-Twilio-Signature header against the request body.

    Skips validation (with a warning) when no auth token is configured, so
    local testing without Twilio credentials still works.
    """
    if not settings.twilio_auth_token:
        logger.warning("TWILIO_AUTH_TOKEN not set; skipping Twilio signature validation")
        return True

    signature = request.headers.get("x-twilio-signature", "")
    if not signature:
        return False

    form = await request.form()
    validator = RequestValidator(settings.twilio_auth_token)
    return validator.validate(_public_url(request), dict(form), signature)


def build_voice_response(request: Request) -> Response:
    """Return the TwiML that connects an inbound call to our Media Stream."""
    token = secrets.token_urlsafe(24)
    pending_stream_tokens.add(token)

    stream_url = f"wss://{_public_host(request)}/twilio/ws/{token}"
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Connect>"
        f'<Stream url="{stream_url}"></Stream>'
        "</Connect></Response>"
    )
    return Response(content=twiml, media_type="application/xml")


def consume_stream_token(token: str) -> bool:
    """Return True and invalidate the token if it was a pending, unused one."""
    if token in pending_stream_tokens:
        pending_stream_tokens.discard(token)
        return True
    return False
