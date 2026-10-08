"""Provider construction and reusable conversation pipeline assembly."""

import asyncio
import logging

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import EndFrame, LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.turns.user_stop import SpeechTimeoutUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner

from voice_agent.config import Settings
from voice_agent.prompts import OPENING_INSTRUCTION, build_system_instruction

logger = logging.getLogger(__name__)


def build_provider_services(settings: Settings):
    """Create the cloud STT, LLM, and TTS services from validated settings."""
    stt = DeepgramSTTService(api_key=settings.deepgram_api_key)
    llm = GroqLLMService(
        api_key=settings.groq_api_key,
        settings=GroqLLMService.Settings(
            model=settings.groq_model,
            system_instruction=build_system_instruction(settings.school_context),
        ),
    )
    tts = CartesiaTTSService(
        api_key=settings.cartesia_api_key,
        sample_rate=settings.output_sample_rate,
        encoding="pcm_s16le",
        settings=CartesiaTTSService.Settings(voice=settings.cartesia_voice_id),
    )
    return stt, llm, tts


async def run_conversation(
    transport, settings: Settings, *, audio_in_sample_rate: int | None = None
) -> None:
    """Connect one transport session to the shared speech conversation flow.

    ``audio_in_sample_rate`` lets telephony transports (8 kHz) override the
    browser default so the pipeline matches the wire format of the caller.
    """
    stt, llm, tts = build_provider_services(settings)
    input_sample_rate = audio_in_sample_rate or settings.browser_input_sample_rate
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
            audio_in_sample_rate=input_sample_rate,
            audio_out_sample_rate=settings.output_sample_rate,
        ),
    )

    async def end_call(params: FunctionCallParams):
        await params.result_callback({"status": "ending_call"})
        await task.queue_frame(EndFrame())

    llm.register_function("end_call", end_call)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client):
        context.add_message({"role": "developer", "content": OPENING_INSTRUCTION})
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        logger.info("Client disconnected")
        await task.cancel()

    try:
        await WorkerRunner().run(task)
    except asyncio.CancelledError:
        logger.info("Voice pipeline cancelled")
