"""FastAPI routes for the local browser transport."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from voice_agent.config import PROJECT_ROOT, Settings
from voice_agent.pipeline import run_conversation
from voice_agent.transports import create_browser_transport

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
