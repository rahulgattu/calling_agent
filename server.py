"""Local browser voice-agent MVP using cloud speech services."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from pipecat.frames.frames import (
    EndFrame,
    Frame,
    InputAudioRawFrame,
    LLMRunFrame,
    OutputAudioRawFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.turns.user_stop import SpeechTimeoutUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner


BASE_DIR = Path(__file__).resolve().parent
# This local MVP treats its project .env as the source of truth so a stale
# shell-level key (for example, an old Cartesia admin key) cannot silently win.
load_dotenv(BASE_DIR / ".env", override=True)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("calling_agent")

REQUIRED_ENV = (
    "GROQ_API_KEY",
    "DEEPGRAM_API_KEY",
    "CARTESIA_API_KEY",
    "CARTESIA_VOICE_ID",
)


class BrowserPcmSerializer(FrameSerializer):
    """PCM16 mono: raw 16 kHz on input, sample-rate-tagged audio on output."""

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if not isinstance(data, bytes) or not data:
            return None
        # The browser sends signed little-endian PCM16 at 16 kHz.
        return InputAudioRawFrame(audio=data, sample_rate=16_000, num_channels=1)

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if self.should_ignore_frame(frame) or not isinstance(frame, OutputAudioRawFrame):
            return None
        # 4-byte little-endian sample rate followed by signed little-endian PCM16.
        return int(frame.sample_rate).to_bytes(4, "little") + frame.audio


@asynccontextmanager
async def lifespan(_: FastAPI):
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        logger.warning("Missing environment variables: %s", ", ".join(missing))
    yield


app = FastAPI(title="Calling Agent", lifespan=lifespan)


@app.get("/")
async def home():
    return FileResponse(BASE_DIR / "index.html")


@app.websocket("/ws")
async def voice_socket(websocket: WebSocket):
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    if missing:
        await websocket.close(code=1011, reason=f"Missing server configuration: {', '.join(missing)}")
        return
    await websocket.accept()
    try:
        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
                serializer=BrowserPcmSerializer(),
                audio_in_sample_rate=16_000,
                audio_out_sample_rate=24_000,
            ),
        )
    except ValueError as exc:
        # Covers configured PIPECAT_ALLOWED_ORIGINS rejecting the browser origin.
        await websocket.close(code=1008, reason=str(exc))
        return

    stt = DeepgramSTTService(api_key=os.environ["DEEPGRAM_API_KEY"])
    llm = GroqLLMService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqLLMService.Settings(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            system_instruction=(
                "You are a warm, concise school principal speaking with a student's parent. "
                "Wish them a happy Independence Day. Speak naturally and keep replies brief. "
                "When the conversation reaches a natural goodbye, say a brief farewell and "
                "call the end_call tool."
            ),
        ),
    )
    tts = CartesiaTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        sample_rate=24_000,
        encoding="pcm_s16le",
        settings=CartesiaTTSService.Settings(voice=os.environ["CARTESIA_VOICE_ID"]),
    )

    end_call_tool = FunctionSchema(
        name="end_call",
        description="End the conversation after a natural goodbye has been spoken.",
        properties={},
        required=[],
    )
    context = LLMContext(tools=ToolsSchema(standard_tools=[end_call_tool]))
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            # Transcript inactivity ends a turn without running local VAD or
            # Smart Turn models, keeping all ML on the configured cloud APIs.
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.8)]
            )
        ),
    )
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    task = PipelineWorker(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            audio_in_sample_rate=16_000,
            audio_out_sample_rate=24_000,
        ),
    )

    async def end_call(params: FunctionCallParams):
        """End the call after the assistant has said goodbye."""
        await params.result_callback({"status": "ending_call"})
        # Let the function call finish, then gracefully end the pipeline. The
        # transport closes its WebSocket during the task's normal shutdown.
        await task.queue_frame(EndFrame())

    llm.register_function("end_call", end_call)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client):
        context.add_message(
            {
                "role": "developer",
                "content": "Open the conversation with a brief greeting and wish the parent a happy Independence Day.",
            }
        )
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        logger.info("Browser disconnected")
        await task.cancel()

    runner = WorkerRunner()
    try:
        await runner.run(task)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except asyncio.CancelledError:
        logger.info("Voice pipeline cancelled")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
