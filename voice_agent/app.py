"""FastAPI routes for the local browser transport and Twilio phone calls."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pipecat.runner.utils import parse_telephony_websocket

from voice_agent.config import PROJECT_ROOT, Settings
from voice_agent.pipeline import run_conversation
from voice_agent.telephony import (
    build_voice_response,
    consume_stream_token,
    verify_twilio_request,
)
from voice_agent.transports import create_browser_transport, create_twilio_transport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Settings.warn_if_incomplete()
    yield


app = FastAPI(title="Calling Agent", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=PROJECT_ROOT / "static"), name="static")


@app.get("/")
async def home():
    return FileResponse(PROJECT_ROOT / "index.html")


@app.websocket("/ws")
async def browser_voice_socket(websocket: WebSocket):
    try:
        settings = Settings.from_environment()
    except ValueError as exc:
        await websocket.close(code=1011, reason=str(exc))
        return

    await websocket.accept()
    try:
        transport = create_browser_transport(websocket, settings)
    except ValueError as exc:
        # PIPECAT_ALLOWED_ORIGINS can reject a browser origin here.
        await websocket.close(code=1008, reason=str(exc))
        return

    try:
        await run_conversation(transport, settings)
    except WebSocketDisconnect:
        logger.info("Browser WebSocket disconnected")


@app.post("/twilio/voice")
async def twilio_voice(request: Request):
    """Twilio calls this webhook when a phone call reaches our number."""
    try:
        settings = Settings.from_environment()
    except ValueError as exc:
        return Response(content=str(exc), status_code=500)

    if not await verify_twilio_request(request, settings):
        logger.warning("Rejected Twilio webhook: invalid signature")
        return Response(status_code=403)

    return build_voice_response(request)


@app.websocket("/twilio/ws/{token}")
async def twilio_voice_socket(websocket: WebSocket, token: str):
    if not consume_stream_token(token):
        logger.warning("Rejected Twilio stream: invalid or reused token")
        await websocket.close(code=1008)
        return

    try:
        settings = Settings.from_environment()
    except ValueError as exc:
        await websocket.close(code=1011, reason=str(exc))
        return

    await websocket.accept()
    try:
        transport_type, call_data = await parse_telephony_websocket(websocket)
    except ValueError as exc:
        logger.warning("Twilio handshake failed: %s", exc)
        await websocket.close(code=1002)
        return

    if transport_type != "twilio":
        await websocket.close(code=1002, reason="Unsupported telephony provider")
        return

    try:
        transport = create_twilio_transport(websocket, settings, call_data)
    except ValueError as exc:
        await websocket.close(code=1011, reason=str(exc))
        return

    try:
        await run_conversation(
            transport, settings, audio_in_sample_rate=settings.telephony_sample_rate
        )
    except WebSocketDisconnect:
        logger.info("Twilio WebSocket disconnected")

